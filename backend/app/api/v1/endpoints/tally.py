from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.core.database import get_db
from app.models.tally_master import TallyMaster, PartyMapping
from app.models.audit import AuditLog
from app.schemas.tally import (
    TallyConnectionStatus,
    TallySyncResponse,
    PartyMappingRequest,
    PartyMappingResponse,
    SuggestLedgerRequest,
    SuggestLedgerResponse
)
from app.services.tally.tally_client import tally_client
from app.services.tally.matcher import master_matcher

router = APIRouter(prefix="/tally", tags=["TallyPrime"])

@router.get("/status", response_model=TallyConnectionStatus)
async def check_tally_status():
    """Live XML ping to TallyPrime to inspect connection and open company."""
    status_info = await tally_client.get_connection_status()
    return TallyConnectionStatus(
        is_connected=status_info.get("is_connected", False),
        status=status_info.get("status", "DISCONNECTED"),
        endpoint=status_info.get("endpoint", tally_client.endpoint),
        company_name=status_info.get("company_name"),
        message=status_info.get("message", "")
    )

@router.post("/sync-masters", response_model=TallySyncResponse)
async def sync_tally_masters(db: AsyncSession = Depends(get_db)):
    """
    Connects to TallyPrime, fetches Ledgers, Stock Items, and Units,
    and updates the local cache for fuzzy matching.
    """
    # Attempt to fetch ledgers and detect active company directly
    ledgers, detected_company = await tally_client.get_ledgers_and_company()
    company_name = detected_company or tally_client.active_company_name

    if not ledgers and not company_name:
        status_info = await tally_client.get_connection_status()
        if not status_info.get("is_connected"):
            raise HTTPException(
                status_code=503,
                detail=f"Cannot sync: TallyPrime is disconnected at {tally_client.endpoint}. Please ensure TallyPrime is running with HTTP Server enabled on port {tally_client.port}."
            )
        raise HTTPException(
            status_code=400,
            detail="Cannot sync: No company is currently selected or open in TallyPrime. Please select and open your company at 'Gateway of Tally' (and close any popup dialogs)."
        )

    company_display = company_name or "Active Company"
    stock_items = await tally_client.get_stock_items(company_name)
    units = await tally_client.get_units(company_name)

    # Clear and replace cached masters
    await db.execute(delete(TallyMaster))
    now = datetime.now(timezone.utc)
    
    for l in ledgers:
        db.add(TallyMaster(
            master_type="LEDGER",
            name=l["name"],
            parent_group=l.get("parent"),
            details_json=json.dumps(l),
            last_synced=now
        ))

    for it in stock_items:
        db.add(TallyMaster(
            master_type="STOCK_ITEM",
            name=it["name"],
            parent_group=it.get("parent"),
            details_json=json.dumps(it),
            last_synced=now
        ))

    for u in units:
        db.add(TallyMaster(
            master_type="UNIT",
            name=u,
            parent_group=None,
            last_synced=now
        ))

    db.add(AuditLog(
        action="TALLY_MASTERS_SYNCED",
        entity_type="MASTER",
        details_json=json.dumps({
            "company": company_name,
            "ledgers": len(ledgers),
            "stock_items": len(stock_items),
            "units": len(units)
        })
    ))

    await db.commit()

    return TallySyncResponse(
        success=True,
        company_name=company_name,
        ledgers_synced=len(ledgers),
        stock_items_synced=len(stock_items),
        units_synced=len(units),
        timestamp=datetime.now(timezone.utc),
        message=f"Synced {len(ledgers)} ledgers and {len(stock_items)} items from '{company_name}'."
    )

class CreateLedgerRequest(BaseModel):
    ledger_name: str
    parent_group: Optional[str] = "Sundry Debtors"
    confirmed: bool = True

class CreateStockItemRequest(BaseModel):
    item_name: str
    parent_group: Optional[str] = "Primary"
    uom: Optional[str] = "NOS"
    confirmed: bool = True

@router.post("/create-ledger")
async def create_tally_ledger(payload: CreateLedgerRequest, db: AsyncSession = Depends(get_db)):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation required to create ledger in Tally.")
    status_info = await tally_client.get_connection_status()
    company_name = status_info.get("company_name")
    if not company_name:
        raise HTTPException(status_code=400, detail="No active company open in TallyPrime.")
    
    success, msg = await tally_client.create_ledger(company_name, payload.ledger_name, payload.parent_group or "Sundry Debtors")
    if not success:
        raise HTTPException(status_code=500, detail=msg)
    
    db.add(AuditLog(
        action="TALLY_LEDGER_CREATED",
        entity_type="MASTER",
        details_json=json.dumps({"ledger": payload.ledger_name, "company": company_name})
    ))
    await db.commit()
    return {"success": True, "message": msg}

@router.post("/create-stock-item")
async def create_tally_stock_item(payload: CreateStockItemRequest, db: AsyncSession = Depends(get_db)):
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail="Explicit confirmation required to create stock item in Tally.")
    status_info = await tally_client.get_connection_status()
    company_name = status_info.get("company_name")
    if not company_name:
        raise HTTPException(status_code=400, detail="No active company open in TallyPrime.")

    success, msg = await tally_client.create_stock_item(
        company_name, payload.item_name, payload.parent_group or "Primary", payload.uom or "NOS"
    )
    if not success:
        raise HTTPException(status_code=500, detail=msg)

    db.add(AuditLog(
        action="TALLY_STOCK_ITEM_CREATED",
        entity_type="MASTER",
        details_json=json.dumps({"stock_item": payload.item_name, "company": company_name})
    ))
    await db.commit()
    return {"success": True, "message": msg}

@router.get("/ledgers")
async def get_cached_ledgers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "LEDGER"))
    masters = result.scalars().all()
    return [{"name": m.name, "parent": m.parent_group} for m in masters]

@router.get("/stock-items")
async def get_cached_stock_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "STOCK_ITEM"))
    masters = result.scalars().all()
    return [{"name": m.name, "parent": m.parent_group} for m in masters]

@router.get("/masters")
async def get_all_masters(db: AsyncSession = Depends(get_db)):
    """
    Returns all cached masters (Ledgers, Stock Items, Units).
    Includes smart defaults for Non-GST commerce if no masters have been synced yet.
    """
    result = await db.execute(select(TallyMaster))
    masters = result.scalars().all()

    ledgers = [{"name": m.name, "parent": m.parent_group} for m in masters if m.master_type == "LEDGER"]
    stock_items = []
    for m in masters:
        if m.master_type == "STOCK_ITEM":
            unit = "NOS"
            if m.details_json:
                try:
                    data = json.loads(m.details_json)
                    unit = data.get("unit", "NOS")
                except Exception:
                    pass
            stock_items.append({"name": m.name, "parent": m.parent_group, "unit": unit})

    units = [m.name for m in masters if m.master_type == "UNIT"]

    # If cache is currently empty, provide common standard Indian Non-GST ledgers and units
    default_used = False
    if not ledgers:
        default_used = True
        ledgers = [
            {"name": "Cash", "parent": "Cash-in-Hand"},
            {"name": "Sales Accounts", "parent": "Sales Accounts"},
            {"name": "Purchase Accounts", "parent": "Purchase Accounts"},
            {"name": "Bank Accounts", "parent": "Bank Accounts"},
            {"name": "Sundry Debtors", "parent": "Sundry Debtors"},
            {"name": "Sundry Creditors", "parent": "Sundry Creditors"},
        ]
    if not units:
        units = ["NOS", "KGS", "QTL", "BAG", "BOX", "MTR", "LTR", "PKT", "PCS", "TON", "QUINTAL"]

    last_synced = None
    synced_dates = [m.last_synced for m in masters if m.last_synced]
    if synced_dates:
        last_synced = max(synced_dates).isoformat()

    return {
        "ledgers": ledgers,
        "stock_items": stock_items,
        "units": units,
        "total_ledgers": len(ledgers),
        "total_stock_items": len(stock_items),
        "last_synced": last_synced,
        "is_default_fallback": default_used
    }

@router.post("/party-mapping", response_model=PartyMappingResponse)
async def save_party_mapping(payload: PartyMappingRequest, db: AsyncSession = Depends(get_db)):
    """
    Saves or updates a verified mapping between an extracted bill party name and a Tally ledger.
    E.g. 'HARSH INDUSTRIES' -> 'Harsh Industries , Ghoti'.
    Future bills with this raw name will automatically map to this Tally master.
    """
    clean_raw = payload.raw_name.strip()
    clean_ledger = payload.tally_ledger_name.strip()

    # Check if mapping already exists
    res = await db.execute(select(PartyMapping).where(PartyMapping.raw_name == clean_raw))
    mapping = res.scalar_one_or_none()
    if mapping:
        mapping.tally_ledger_name = clean_ledger
        mapping.is_verified = True
    else:
        mapping = PartyMapping(raw_name=clean_raw, tally_ledger_name=clean_ledger, is_verified=True)
        db.add(mapping)

    db.add(AuditLog(
        action="PARTY_MAPPING_SAVED",
        entity_type="MASTER",
        details_json=json.dumps({"raw_name": clean_raw, "tally_ledger": clean_ledger})
    ))
    await db.commit()
    await db.refresh(mapping)
    return PartyMappingResponse(
        raw_name=mapping.raw_name,
        tally_ledger_name=mapping.tally_ledger_name,
        is_verified=mapping.is_verified,
        created_at=mapping.created_at
    )

@router.get("/party-mappings", response_model=List[PartyMappingResponse])
async def get_party_mappings(db: AsyncSession = Depends(get_db)):
    """Returns all saved party name mappings."""
    res = await db.execute(select(PartyMapping).order_by(PartyMapping.id.desc()))
    mappings = res.scalars().all()
    return [
        PartyMappingResponse(
            raw_name=m.raw_name,
            tally_ledger_name=m.tally_ledger_name,
            is_verified=m.is_verified,
            created_at=m.created_at
        ) for m in mappings
    ]

@router.post("/suggest-ledger", response_model=SuggestLedgerResponse)
async def suggest_ledger_for_name(payload: SuggestLedgerRequest, db: AsyncSession = Depends(get_db)):
    """
    Given an extracted party name, checks saved mappings first, then searches
    cached Tally masters using fuzzy / token matching to suggest 'Did you mean: ...?'.
    """
    raw = payload.raw_name.strip()
    if not raw:
        return SuggestLedgerResponse(raw_name=raw)

    # 1. Check verified mapping in DB
    mapping_res = await db.execute(select(PartyMapping).where(PartyMapping.raw_name == raw))
    mapping = mapping_res.scalar_one_or_none()
    if mapping:
        # Also find parent group from masters if possible
        m_res = await db.execute(select(TallyMaster).where(TallyMaster.name == mapping.tally_ledger_name))
        tm = m_res.scalar_one_or_none()
        return SuggestLedgerResponse(
            raw_name=raw,
            exact_match=mapping.tally_ledger_name,
            suggested_ledger=mapping.tally_ledger_name,
            parent_group=tm.parent_group if tm else None,
            confidence=1.0,
            candidates=[{"name": mapping.tally_ledger_name, "parent": tm.parent_group if tm else None, "score": 1.0}]
        )

    # 2. Check cached masters
    res = await db.execute(select(TallyMaster).where(TallyMaster.master_type == "LEDGER"))
    masters = res.scalars().all()
    ledgers_list = [{"name": m.name, "parent": m.parent_group} for m in masters]

    # Check exact match
    for l in ledgers_list:
        if l["name"].strip().lower() == raw.lower():
            return SuggestLedgerResponse(
                raw_name=raw,
                exact_match=l["name"],
                suggested_ledger=l["name"],
                parent_group=l["parent"],
                confidence=1.0,
                candidates=[{"name": l["name"], "parent": l["parent"], "score": 1.0}]
            )

    # Find best match
    best = master_matcher.find_best_ledger_match(raw, ledgers_list, threshold=0.60)
    top_candidates = master_matcher.get_top_ledger_matches(raw, ledgers_list, limit=5, threshold=0.55)

    return SuggestLedgerResponse(
        raw_name=raw,
        exact_match=None,
        suggested_ledger=best["name"] if best else None,
        parent_group=best["parent"] if best else None,
        confidence=best["score"] if best else 0.0,
        candidates=top_candidates
    )


