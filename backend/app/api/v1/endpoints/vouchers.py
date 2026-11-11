from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.bill import Bill
from app.models.bill_item import BillItem
from app.models.voucher import VoucherPreview, TallyTransaction
from app.models.tally_master import TallyMaster, PartyMapping
from app.models.audit import AuditLog
from app.schemas.voucher import (
    VoucherPreviewResponse, VoucherApprovalRequest, VoucherUpdateRequest, TallyTransactionResponse
)
from app.services.tally.tally_client import tally_client
from app.services.tally.matcher import master_matcher, unit_converter

router = APIRouter(prefix="/vouchers", tags=["Vouchers"])

def process_and_convert_items(
    items: List[Any],
    stock_items_masters: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    1. Extracts clean base commodity name (stripping brand, variety, packaging e.g.
       'RICE SONPARI INDRAYANI - 30 KG' -> 'RICE').
    2. Auto-converts units (e.g. 7.5 QTL @ ₹5300/QTL -> 750 KG @ ₹53/KG)
       when bill unit is QTL and Tally stock item unit is KG.
    """
    processed = []
    for it in items:
        # Support both ORM BillItem model and dict
        if isinstance(it, dict):
            raw_name = it.get("item_name") or it.get("raw_item_name") or "Item"
            raw_qty = float(it.get("original_quantity") or it.get("quantity") or 1.0)
            raw_rate = float(it.get("original_rate") or it.get("rate") or 0.0)
            raw_unit = str(it.get("original_unit") or it.get("unit") or "NOS")
            raw_amt = float(it.get("amount") or (raw_qty * raw_rate))
            raw_disc = float(it.get("discount") or 0.0)
            existing_stock = it.get("stock_item_name")
        else:
            raw_name = it.raw_item_name or "Item"
            raw_qty = float(it.quantity or 1.0)
            raw_rate = float(it.rate or 0.0)
            raw_unit = str(it.unit or "NOS")
            raw_amt = float(it.amount or (raw_qty * raw_rate))
            raw_disc = float(it.discount or 0.0)
            existing_stock = it.matched_stock_item_name

        # 1. Base Commodity Matching
        match = master_matcher.find_best_stock_match(raw_name, stock_items_masters)
        stock_name = match["name"] if match else (existing_stock or raw_name)
        target_unit = match.get("unit") if match else "KG"

        # 2. Unit Conversion (e.g. QTL -> KG)
        conv_qty, conv_rate, eff_unit, was_conv, explanation = unit_converter.convert(
            raw_qty, raw_rate, raw_unit, target_unit or "KG"
        )

        processed.append({
            "item_name": raw_name,
            "stock_item_name": stock_name,
            "quantity": conv_qty,
            "unit": eff_unit,
            "rate": conv_rate,
            "amount": raw_amt,
            "discount": raw_disc,
            "original_quantity": raw_qty if was_conv else None,
            "original_rate": raw_rate if was_conv else None,
            "original_unit": raw_unit if was_conv else None,
            "conversion_applied": explanation
        })
    return processed

async def get_party_suggestion_info(party_name: str, db: AsyncSession):
    """
    Checks if party_name exists in Tally masters or party_mappings.
    Returns (suggested_party, confidence, is_matched)
    """
    if not party_name:
        return None, 0.0, False

    # 1. Check if exact match exists in Tally masters
    m_res = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "LEDGER"))
    masters = m_res.scalars().all()
    ledgers = [{"name": m.name, "parent": m.parent_group} for m in masters]

    for l in ledgers:
        if l["name"].strip().lower() == party_name.strip().lower():
            return l["name"], 1.0, True

    # 2. Check PartyMapping table
    map_res = await db.execute(select(PartyMapping).where(PartyMapping.raw_name == party_name.strip()))
    mapping = map_res.scalar_one_or_none()
    if mapping:
        return mapping.tally_ledger_name, 1.0, True

    # 3. Fuzzy search for best match (e.g. 'HARSH INDUSTRIES' -> 'Harsh Industries , Ghoti')
    best = master_matcher.find_best_ledger_match(party_name, ledgers, threshold=0.60)
    if best:
        return best["name"], best["score"], False

    return None, 0.0, False

def format_date_for_tally(date_str: Optional[str]) -> str:
    """
    Converts DD-MM-YYYY, DD/MM/YYYY, 1-Apr-25, or ISO to Tally YYYYMMDD format.
    Ensures date is valid for Tally company financial books (defaulting to 20250401 if missing).
    """
    if not date_str:
        return "20250401"

    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12"
    }

    clean = date_str.replace("/", "-").strip()
    parts = clean.split("-")
    if len(parts) == 3:
        p0, p1, p2 = parts[0].strip(), parts[1].strip(), parts[2].strip()

        # Month resolution
        m_lower = p1.lower()[:3]
        if m_lower in months:
            mm = months[m_lower]
        elif p1.isdigit():
            mm = p1.zfill(2)
        else:
            mm = "04"

        if len(p0) == 4: # YYYY-MM-DD
            yyyy = p0
            dd = p2.zfill(2)
            return f"{yyyy}{mm}{dd}"
        else: # DD-MM-YYYY or DD-MM-YY
            dd = p0.zfill(2)
            yyyy = p2
            if len(yyyy) == 2:
                yyyy = f"20{yyyy}"
            elif len(yyyy) != 4:
                yyyy = "2025"
            return f"{yyyy}{mm}{dd}"

    return "20250401"

@router.get("/bills/{bill_id}/preview", response_model=VoucherPreviewResponse)
async def get_or_create_voucher_preview(bill_id: int, db: AsyncSession = Depends(get_db)):
    """
    Retrieves existing voucher preview or builds a new one from validated bill data.
    """
    bill_query = select(Bill).options(
        selectinload(Bill.items),
        selectinload(Bill.voucher_preview)
    ).where(Bill.id == bill_id)
    result = await db.execute(bill_query)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if bill.is_gst_detected:
        raise HTTPException(
            status_code=400,
            detail="Cannot prepare voucher: Bill has detected GST lines. Please resolve in Clarifications."
        )

    # Fetch cached Tally stock items to match base commodity and check master units
    stock_masters_q = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "STOCK_ITEM"))
    stock_masters = stock_masters_q.scalars().all()
    stock_items_list = []
    for sm in stock_masters:
        sm_unit = "KG"
        if sm.details_json:
            try:
                sm_unit = json.loads(sm.details_json).get("unit", "KG")
            except Exception:
                pass
        stock_items_list.append({"name": sm.name, "parent": sm.parent_group, "unit": sm_unit})

    # Return existing preview if already prepared, applying base commodity match & unit conversion
    if bill.voucher_preview:
        vp = bill.voucher_preview
        sugg_party, conf, is_match = await get_party_suggestion_info(vp.party_ledger, db)
        
        # Ensure items are matched to clean base commodity and converted from QTL -> KG if necessary
        raw_items_list = json.loads(vp.items_json)
        # Check if original items from bill should be used for conversion
        items_to_process = bill.items if bill.items and len(bill.items) == len(raw_items_list) else raw_items_list
        converted_items = process_and_convert_items(items_to_process, stock_items_list)
        vp.items_json = json.dumps(converted_items)
        await db.commit()

        return VoucherPreviewResponse(
            id=vp.id,
            bill_id=vp.bill_id,
            voucher_type=vp.voucher_type,
            party_ledger=vp.party_ledger,
            sales_purchase_ledger=vp.sales_purchase_ledger,
            invoice_number=vp.invoice_number,
            invoice_date=vp.invoice_date,
            items=converted_items,
            subtotal=vp.subtotal,
            discount=vp.discount,
            additional_charges=vp.additional_charges,
            round_off=vp.round_off,
            final_amount=vp.final_amount,
            narration=vp.narration,
            is_approved=vp.is_approved,
            approved_at=vp.approved_at,
            created_at=vp.created_at,
            suggested_party_ledger=sugg_party,
            party_match_confidence=conf,
            is_party_matched=is_match
        )

    # Build new preview
    vch_type = "Sales" if bill.bill_type.upper() == "SALES" else "Purchase"
    default_acct = "Sales Accounts" if vch_type == "Sales" else "Purchase Accounts"
    
    # Check if party has a verified mapping in database
    initial_party = bill.party_name or "Cash"
    sugg_party, conf, is_match = await get_party_suggestion_info(initial_party, db)
    if is_match and sugg_party:
        initial_party = sugg_party

    item_lines = process_and_convert_items(bill.items, stock_items_list)

    new_vp = VoucherPreview(
        bill_id=bill.id,
        voucher_type=vch_type,
        party_ledger=initial_party,
        sales_purchase_ledger=default_acct,
        invoice_number=bill.invoice_number or f"INV-{bill.id}",
        invoice_date=bill.invoice_date or datetime.now().strftime("%d-%m-%Y"),
        items_json=json.dumps(item_lines),
        subtotal=bill.subtotal or sum(l["amount"] for l in item_lines),
        discount=bill.discount,
        additional_charges=bill.additional_charges,
        round_off=bill.round_off,
        final_amount=bill.final_amount or bill.subtotal,
        narration=f"Non-GST {vch_type} Voucher generated by AI Bill Scanner"
    )
    db.add(new_vp)
    await db.commit()
    await db.refresh(new_vp)

    return VoucherPreviewResponse(
        id=new_vp.id,
        bill_id=new_vp.bill_id,
        voucher_type=new_vp.voucher_type,
        party_ledger=new_vp.party_ledger,
        sales_purchase_ledger=new_vp.sales_purchase_ledger,
        invoice_number=new_vp.invoice_number,
        invoice_date=new_vp.invoice_date,
        items=item_lines,
        subtotal=new_vp.subtotal,
        discount=new_vp.discount,
        additional_charges=new_vp.additional_charges,
        round_off=new_vp.round_off,
        final_amount=new_vp.final_amount,
        narration=new_vp.narration,
        is_approved=new_vp.is_approved,
        approved_at=new_vp.approved_at,
        created_at=new_vp.created_at,
        suggested_party_ledger=sugg_party,
        party_match_confidence=conf,
        is_party_matched=is_match
    )

@router.put("/{voucher_id}", response_model=VoucherPreviewResponse)
async def update_voucher_preview(
    voucher_id: int,
    payload: VoucherUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates voucher details before posting (e.g. changing Party Ledger,
    Accounting Ledger, Item Names, Rates, or Amounts).
    """
    vp = await db.get(VoucherPreview, voucher_id)
    if not vp:
        raise HTTPException(status_code=404, detail="Voucher preview not found")

    if vp.is_approved:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify a voucher that has already been approved and posted to Tally."
        )

    if payload.party_ledger is not None:
        new_party = payload.party_ledger.strip()
        vp.party_ledger = new_party
        
        # Auto-learn mapping if user selected a different master for bill's original party
        bill_obj = await db.get(Bill, vp.bill_id)
        if bill_obj and bill_obj.party_name:
            raw_orig = bill_obj.party_name.strip()
            if raw_orig.lower() != new_party.lower():
                map_q = await db.execute(select(PartyMapping).where(PartyMapping.raw_name == raw_orig))
                existing_map = map_q.scalar_one_or_none()
                if existing_map:
                    existing_map.tally_ledger_name = new_party
                    existing_map.is_verified = True
                else:
                    db.add(PartyMapping(raw_name=raw_orig, tally_ledger_name=new_party, is_verified=True))

    if payload.sales_purchase_ledger is not None:
        vp.sales_purchase_ledger = payload.sales_purchase_ledger.strip()
    if payload.invoice_number is not None:
        vp.invoice_number = payload.invoice_number.strip()
    if payload.invoice_date is not None:
        vp.invoice_date = payload.invoice_date.strip()
    if payload.narration is not None:
        vp.narration = payload.narration.strip()

    if payload.items is not None:
        items_dict = [it.model_dump() for it in payload.items]
        vp.items_json = json.dumps(items_dict)
        calc_subtotal = sum(it.amount for it in payload.items)
        vp.subtotal = payload.subtotal if payload.subtotal is not None else calc_subtotal

    if payload.subtotal is not None:
        vp.subtotal = payload.subtotal
    if payload.discount is not None:
        vp.discount = payload.discount
    if payload.additional_charges is not None:
        vp.additional_charges = payload.additional_charges
    if payload.round_off is not None:
        vp.round_off = payload.round_off
    if payload.final_amount is not None:
        vp.final_amount = payload.final_amount
    else:
        vp.final_amount = round(vp.subtotal - vp.discount + vp.additional_charges + vp.round_off, 2)

    await db.commit()
    await db.refresh(vp)

    items_list = json.loads(vp.items_json)
    sugg_party, conf, is_match = await get_party_suggestion_info(vp.party_ledger, db)

    return VoucherPreviewResponse(
        id=vp.id,
        bill_id=vp.bill_id,
        voucher_type=vp.voucher_type,
        party_ledger=vp.party_ledger,
        sales_purchase_ledger=vp.sales_purchase_ledger,
        invoice_number=vp.invoice_number,
        invoice_date=vp.invoice_date,
        items=items_list,
        subtotal=vp.subtotal,
        discount=vp.discount,
        additional_charges=vp.additional_charges,
        round_off=vp.round_off,
        final_amount=vp.final_amount,
        narration=vp.narration,
        is_approved=vp.is_approved,
        approved_at=vp.approved_at,
        created_at=vp.created_at,
        suggested_party_ledger=sugg_party,
        party_match_confidence=conf,
        is_party_matched=is_match
    )

@router.post("/{voucher_id}/approve-and-post")
async def approve_and_post_voucher(
    voucher_id: int,
    approval: VoucherApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Requires explicit user approval.
    Pings Tally, builds official XML, and posts the voucher to TallyPrime.
    Validates actual Tally response and records transaction log.
    """
    if not approval.confirmed:
        raise HTTPException(status_code=400, detail="Voucher must be explicitly confirmed by user.")

    vp = await db.get(VoucherPreview, voucher_id)
    if not vp:
        raise HTTPException(status_code=404, detail="Voucher preview not found")

    bill = await db.get(Bill, vp.bill_id)

    # 1. Check Tally connection
    tally_status = await tally_client.get_connection_status()
    if not tally_status.get("is_connected"):
        raise HTTPException(
            status_code=503,
            detail=f"TallyPrime is not connected at {tally_client.endpoint}. Please ensure TallyPrime is running with HTTP Server enabled."
        )

    company_name = tally_status.get("company_name") or ""

    # 2. Build Tally XML
    items = json.loads(vp.items_json)
    tally_date = format_date_for_tally(vp.invoice_date)
    xml_payload = tally_client.build_non_gst_voucher_xml(
        company_name=company_name,
        voucher_type=vp.voucher_type,
        invoice_number=vp.invoice_number,
        invoice_date_tally=tally_date,
        party_ledger=vp.party_ledger,
        sales_purchase_ledger=vp.sales_purchase_ledger,
        items=items,
        final_amount=vp.final_amount,
        narration=vp.narration or "Posted via AI Bill Scanner",
        additional_charges=vp.additional_charges or 0.0,
        discount=vp.discount or 0.0,
        round_off=vp.round_off or 0.0
    )

    # 3. Post to TallyPrime
    success, result = await tally_client.post_voucher(xml_payload)

    # 4. Record Transaction
    tx = TallyTransaction(
        voucher_preview_id=vp.id,
        request_xml=xml_payload,
        response_xml=result.get("raw_response", ""),
        status="SUCCESS" if success else "FAILED",
        tally_voucher_number=result.get("voucher_number") or vp.invoice_number,
        error_message=result.get("error") if not success else None
    )
    db.add(tx)

    if success:
        vp.is_approved = True
        vp.approved_at = datetime.now(timezone.utc)
        if bill:
            bill.status = "POSTED"
        db.add(AuditLog(
            action="TALLY_POSTED",
            entity_type="VOUCHER",
            entity_id=vp.id,
            details_json=json.dumps({"company": company_name, "invoice": vp.invoice_number})
        ))
    else:
        if bill:
            bill.status = "FAILED"
        db.add(AuditLog(
            action="TALLY_FAILED",
            entity_type="VOUCHER",
            entity_id=vp.id,
            details_json=json.dumps({"error": result.get("error")})
        ))

    await db.commit()

    if not success:
        err_msg = result.get('error') or "Unknown error"
        suggested_name = None
        sugg_conf = 0.0

        import re
        ledger_match = re.search(r"Ledger '([^']+)' does not exist", err_msg, re.IGNORECASE)
        if ledger_match:
            missing_ledger = ledger_match.group(1).strip()
            # Lookup best match among cached masters
            m_res = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "LEDGER"))
            masters = m_res.scalars().all()
            ledgers_list = [{"name": m.name, "parent": m.parent_group} for m in masters]
            best = master_matcher.find_best_ledger_match(missing_ledger, ledgers_list, threshold=0.60)
            if best:
                suggested_name = best["name"]
                sugg_conf = best["score"]

        return {
            "success": False,
            "status": "FAILED",
            "message": f"Tally rejected voucher creation: {err_msg}",
            "details": result,
            "suggested_ledger": suggested_name,
            "confidence": sugg_conf
        }

    return {
        "success": True,
        "status": "POSTED",
        "message": f"Voucher successfully created in TallyPrime under company '{company_name}'.",
        "voucher_number": result.get("voucher_number") or vp.invoice_number,
        "company": company_name
    }

