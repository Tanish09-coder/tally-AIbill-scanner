from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class TallyConnectionStatus(BaseModel):
    is_connected: bool
    status: str # CONNECTED, DISCONNECTED, COMPANY_NOT_SELECTED, ERROR
    endpoint: str
    company_name: Optional[str] = None
    message: str

class TallyMasterItem(BaseModel):
    name: str
    parent_group: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class TallySyncResponse(BaseModel):
    success: bool
    company_name: Optional[str] = None
    ledgers_synced: int
    stock_items_synced: int
    units_synced: int
    timestamp: datetime
    message: str

class PartyMappingRequest(BaseModel):
    raw_name: str
    tally_ledger_name: str

class PartyMappingResponse(BaseModel):
    raw_name: str
    tally_ledger_name: str
    is_verified: bool = True
    created_at: Optional[datetime] = None

class SuggestLedgerRequest(BaseModel):
    raw_name: str
    bill_type: Optional[str] = None # SALES or PURCHASE

class SuggestLedgerResponse(BaseModel):
    raw_name: str
    exact_match: Optional[str] = None
    suggested_ledger: Optional[str] = None
    parent_group: Optional[str] = None
    confidence: float = 0.0
    candidates: List[Dict[str, Any]] = []


