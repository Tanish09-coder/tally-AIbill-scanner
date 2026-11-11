from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, ConfigDict

class VoucherItemLine(BaseModel):
    item_name: str
    stock_item_name: str
    quantity: float
    unit: str
    rate: float
    amount: float
    discount: float = 0.0
    original_quantity: Optional[float] = None
    original_rate: Optional[float] = None
    original_unit: Optional[str] = None
    conversion_applied: Optional[str] = None

class VoucherPreviewResponse(BaseModel):
    id: int
    bill_id: int
    voucher_type: str
    party_ledger: str
    sales_purchase_ledger: str
    invoice_number: str
    invoice_date: str
    items: List[VoucherItemLine]
    subtotal: float
    discount: float
    additional_charges: float
    round_off: float
    final_amount: float
    narration: Optional[str] = None
    is_approved: bool
    approved_at: Optional[datetime] = None
    created_at: datetime
    suggested_party_ledger: Optional[str] = None
    party_match_confidence: Optional[float] = None
    is_party_matched: bool = False
    model_config = ConfigDict(from_attributes=True)

class VoucherApprovalRequest(BaseModel):
    voucher_id: int
    confirmed: bool = True

class VoucherUpdateRequest(BaseModel):
    party_ledger: Optional[str] = None
    sales_purchase_ledger: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    narration: Optional[str] = None
    items: Optional[List[VoucherItemLine]] = None
    subtotal: Optional[float] = None
    discount: Optional[float] = None
    additional_charges: Optional[float] = None
    round_off: Optional[float] = None
    final_amount: Optional[float] = None

class TallyTransactionResponse(BaseModel):
    id: int
    voucher_preview_id: int
    status: str
    tally_voucher_number: Optional[str] = None
    tally_guid: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
