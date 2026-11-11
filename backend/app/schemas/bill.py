from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class BillItemBase(BaseModel):
    raw_item_name: str
    matched_stock_item_name: Optional[str] = None
    quantity: float = Field(default=1.0, ge=0.0)
    unit: str = "NOS"
    rate: float = Field(default=0.0, ge=0.0)
    amount: float = Field(default=0.0, ge=0.0)
    discount: float = Field(default=0.0, ge=0.0)
    confidence_score: float = 1.0
    status: str = "VALID"

class BillItemCreate(BillItemBase):
    pass

class BillItemUpdate(BaseModel):
    raw_item_name: Optional[str] = None
    matched_stock_item_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    rate: Optional[float] = None
    amount: Optional[float] = None
    discount: Optional[float] = None
    status: Optional[str] = None

class BillItemResponse(BillItemBase):
    id: int
    bill_id: int
    model_config = ConfigDict(from_attributes=True)

class BillBase(BaseModel):
    bill_type: str = "UNKNOWN" # SALES, PURCHASE, UNKNOWN
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    party_name: Optional[str] = None
    party_address: Optional[str] = None
    contact_details: Optional[str] = None
    subtotal: float = 0.0
    discount: float = 0.0
    additional_charges: float = 0.0
    round_off: float = 0.0
    final_amount: float = 0.0

class BillUpdate(BaseModel):
    bill_type: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    party_name: Optional[str] = None
    party_address: Optional[str] = None
    contact_details: Optional[str] = None
    subtotal: Optional[float] = None
    discount: Optional[float] = None
    additional_charges: Optional[float] = None
    round_off: Optional[float] = None
    final_amount: Optional[float] = None
    status: Optional[str] = None

class BillResponse(BillBase):
    id: int
    file_path: str
    original_filename: str
    file_type: str
    status: str
    is_gst_detected: bool
    gst_warning_text: Optional[str] = None
    confidence_score: float
    created_at: datetime
    updated_at: datetime
    items: List[BillItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class BillListResponse(BaseModel):
    total: int
    bills: List[BillResponse]
