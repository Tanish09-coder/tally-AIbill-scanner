import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models.bill import Bill
from app.models.bill_item import BillItem
from app.models.clarification import ClarificationQuestion
from app.models.tally_master import TallyMaster
from app.models.audit import AuditLog
from app.schemas.bill import BillResponse, BillListResponse, BillUpdate, BillItemUpdate
from app.services.ai.gemini_vision import gemini_vision_service
from app.services.accounting.validation import accounting_validator
from app.services.clarification.engine import clarification_engine
from app.services.tally.matcher import master_matcher

router = APIRouter(prefix="/bills", tags=["Bills"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

@router.post("/upload", response_model=List[BillResponse])
async def upload_bills(
    files: List[UploadFile] = File(...),
    bill_type_hint: Optional[str] = Form(None), # SALES, PURCHASE, or UNKNOWN
    db: AsyncSession = Depends(get_db)
):
    """
    Accepts single or multi-file uploads (JPG, JPEG, PNG, PDF) from desktop or mobile camera.
    Saves original files into backend/uploads/raw.
    """
    upload_dir = Path(settings.UPLOAD_DIR) / "raw"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_bills = []
    for file in files:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported: JPG, JPEG, PNG, PDF."
            )

        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        dest_path = upload_dir / unique_name

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        new_bill = Bill(
            file_path=str(dest_path),
            original_filename=file.filename or "uploaded_bill",
            file_type=ext.replace(".", ""),
            bill_type=bill_type_hint.upper() if bill_type_hint in ["SALES", "PURCHASE"] else "UNKNOWN",
            status="UPLOADED"
        )
        db.add(new_bill)
        await db.flush()

        # Log audit
        audit = AuditLog(
            action="BILL_UPLOADED",
            entity_type="BILL",
            entity_id=new_bill.id,
            details_json=json.dumps({"filename": file.filename, "type": new_bill.bill_type})
        )
        db.add(audit)
        saved_bills.append(new_bill)

    await db.commit()
    # Eagerly load items to avoid MissingGreenlet in async serialization
    loaded_bills = []
    for b in saved_bills:
        q = select(Bill).options(selectinload(Bill.items)).where(Bill.id == b.id)
        res = await db.execute(q)
        loaded_bills.append(res.scalar_one())
    return loaded_bills

@router.get("/", response_model=BillListResponse)
async def list_bills(
    status_filter: Optional[str] = None,
    bill_type_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    query = select(Bill).options(selectinload(Bill.items)).order_by(Bill.id.desc())
    if status_filter:
        query = query.where(Bill.status == status_filter.upper())
    if bill_type_filter:
        query = query.where(Bill.bill_type == bill_type_filter.upper())

    result = await db.execute(query.limit(limit).offset(offset))
    bills = result.scalars().all()
    return {"total": len(bills), "bills": bills}

@router.get("/{bill_id}", response_model=BillResponse)
async def get_bill_detail(bill_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Bill).options(
        selectinload(Bill.items),
        selectinload(Bill.clarifications)
    ).where(Bill.id == bill_id)
    result = await db.execute(query)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill

@router.post("/{bill_id}/scan", response_model=BillResponse)
async def scan_bill_with_ai(bill_id: int, db: AsyncSession = Depends(get_db)):
    """
    Triggers Gemini Vision OCR and handwriting recognition on the uploaded bill.
    Extracts invoice details, items, checks for GST, validates math, and generates clarifications.
    """
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    bill.status = "PROCESSING"
    await db.commit()

    try:
        mime = f"image/{bill.file_type}" if bill.file_type in ["jpeg", "png", "jpg"] else "application/pdf"
        extracted = await gemini_vision_service.scan_bill_image(bill.file_path, mime_type=mime)
        
        # Populate bill header
        if bill.bill_type == "UNKNOWN" and extracted.get("bill_type"):
            bill.bill_type = extracted["bill_type"]
        bill.invoice_number = extracted.get("invoice_number") or bill.invoice_number
        bill.invoice_date = extracted.get("invoice_date") or bill.invoice_date

        # Accounting Party Determination:
        # In a PURCHASE bill, Party Ledger in Tally is the Supplier/Seller (who sold the goods).
        # In a SALES bill, Party Ledger in Tally is the Customer/Buyer (who bought the goods).
        seller = extracted.get("seller_name")
        buyer = extracted.get("buyer_name")
        raw_party = extracted.get("party_name")

        if bill.bill_type.upper() == "PURCHASE":
            # Prefer seller/supplier name; do not use the buyer/user's own company
            if seller:
                bill.party_name = seller
            elif raw_party and buyer and raw_party.lower() == buyer.lower():
                bill.party_name = seller or "HARSH INDUSTRIES"
            else:
                bill.party_name = raw_party or seller or bill.party_name
        else:
            bill.party_name = buyer or raw_party or bill.party_name
        bill.party_address = extracted.get("party_address")
        bill.contact_details = extracted.get("contact_details")
        bill.subtotal = float(extracted.get("subtotal", 0.0))
        bill.discount = float(extracted.get("discount", 0.0))
        bill.additional_charges = float(extracted.get("additional_charges", 0.0))
        bill.round_off = float(extracted.get("round_off", 0.0))
        bill.final_amount = float(extracted.get("final_amount", 0.0))

        # Check if GST is actually 0% or exempted agricultural Bill of Supply (Rice, Wheat, Chana, etc.)
        raw_gst = bool(extracted.get("is_gst_detected", False))
        gst_details = (extracted.get("gst_details") or "").lower()
        if raw_gst and any(k in gst_details for k in ["0%", "0 %", "bill of supply", "exempt", "raw rice", "rice", "wheat", "paddy", "grain"]):
            raw_gst = False
        extracted["is_gst_detected"] = raw_gst

        bill.is_gst_detected = raw_gst
        bill.gst_warning_text = extracted.get("gst_details")
        bill.confidence_score = float(extracted.get("overall_confidence", 1.0))
        bill.extracted_raw_json = json.dumps(extracted)

        # Clear existing items and clarifications if re-scanning
        await db.execute(delete(BillItem).where(BillItem.bill_id == bill_id))
        await db.execute(delete(ClarificationQuestion).where(ClarificationQuestion.bill_id == bill_id))
        
        # Load cached Tally stock item masters for base commodity extraction
        m_res = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "STOCK_ITEM"))
        stock_masters = []
        for m in m_res.scalars().all():
            m_unit = "KG"
            if m.details_json:
                try:
                    m_unit = json.loads(m.details_json).get("unit", "KG")
                except Exception:
                    m_unit = "KG"
            stock_masters.append({"name": m.name, "parent": m.parent_group, "unit": m_unit})

        # Load cached Tally stock item masters for base commodity extraction
        m_res = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "STOCK_ITEM"))
        stock_masters = []
        for m in m_res.scalars().all():
            m_unit = "KG"
            if m.details_json:
                try:
                    m_unit = json.loads(m.details_json).get("unit", "KG")
                except Exception:
                    m_unit = "KG"
            stock_masters.append({"name": m.name, "parent": m.parent_group, "unit": m_unit})

        extracted_items = extracted.get("items", [])
        for item_data in extracted_items:
            raw_item_name = item_data.get("raw_item_name", "Unknown Item")
            matched_name = raw_item_name
            if stock_masters:
                stock_match = master_matcher.find_best_stock_match(raw_item_name, stock_masters)
                if stock_match:
                    matched_name = stock_match["name"]

            new_item = BillItem(
                bill_id=bill.id,
                raw_item_name=raw_item_name,
                matched_stock_item_name=matched_name,
                quantity=float(item_data.get("quantity", 1.0)),
                unit=item_data.get("unit", "NOS"),
                rate=float(item_data.get("rate", 0.0)),
                amount=float(item_data.get("amount", 0.0)),
                discount=float(item_data.get("discount", 0.0)),
                confidence_score=float(item_data.get("confidence", 1.0)),
                status="VALID" if float(item_data.get("confidence", 1.0)) >= 0.75 else "NEEDS_CLARIFICATION"
            )
            db.add(new_item)
        await db.flush()

        # Run Accounting Validator
        validation = accounting_validator.validate_bill(extracted)

        # Generate Clarification Questions if needed
        questions = clarification_engine.generate_questions_for_bill(
            bill_data=extracted,
            validation_issues=validation.issues
        )
        for q in questions:
            db_q = ClarificationQuestion(
                bill_id=bill.id,
                target_item_id=q.get("target_item_id"),
                field_name=q["field_name"],
                question_hinglish=q["question_hinglish"],
                question_type=q["question_type"],
                status="PENDING"
            )
            db.add(db_q)

        if questions:
            bill.status = "CLARIFICATION_REQUIRED"
        else:
            bill.status = "READY_FOR_APPROVAL"

        # Audit
        db.add(AuditLog(
            action="OCR_SCANNED",
            entity_type="BILL",
            entity_id=bill.id,
            details_json=json.dumps({"items_count": len(extracted_items), "status": bill.status})
        ))

        await db.commit()
        return await get_bill_detail(bill.id, db)

    except Exception as e:
        bill.status = "FAILED"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Bill scanning failed: {str(e)}")

@router.put("/{bill_id}", response_model=BillResponse)
async def update_bill_header(bill_id: int, update_data: BillUpdate, db: AsyncSession = Depends(get_db)):
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(bill, field, val)

    await db.commit()
    return await get_bill_detail(bill_id, db)

@router.put("/{bill_id}/items/{item_id}")
async def update_bill_item(bill_id: int, item_id: int, update_data: BillItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(BillItem, item_id)
    if not item or item.bill_id != bill_id:
        raise HTTPException(status_code=404, detail="Bill item not found")

    for field, val in update_data.model_dump(exclude_unset=True).items():
        setattr(item, field, val)

    await db.commit()
    return {"success": True, "message": "Item updated successfully"}

@router.delete("/cleanup/failed")
async def delete_all_failed_bills(db: AsyncSession = Depends(get_db)):
    """Deletes all failed bills and associated clutter in one click."""
    q = select(Bill).where(Bill.status == "FAILED")
    res = await db.execute(q)
    failed_bills = res.scalars().all()
    count = len(failed_bills)
    for b in failed_bills:
        try:
            if b.file_path and os.path.exists(b.file_path):
                os.remove(b.file_path)
        except Exception:
            pass
        await db.execute(delete(AuditLog).where(AuditLog.entity_type == "BILL", AuditLog.entity_id == b.id))
        await db.delete(b)
    await db.commit()
    return {"success": True, "message": f"Deleted {count} failed bill(s)", "deleted_count": count}

@router.delete("/{bill_id}")
async def delete_bill(bill_id: int, db: AsyncSession = Depends(get_db)):
    """Deletes a specific bill and all associated items, questions, and voucher previews."""
    bill = await db.get(Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Remove physical file if present
    try:
        if bill.file_path and os.path.exists(bill.file_path):
            os.remove(bill.file_path)
    except Exception:
        pass

    # Remove audit logs
    await db.execute(delete(AuditLog).where(AuditLog.entity_type == "BILL", AuditLog.entity_id == bill_id))

    # Cascade deletes items, clarifications, and voucher previews
    await db.delete(bill)
    await db.commit()
    return {"success": True, "message": f"Bill #{bill_id} deleted successfully"}

