from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class VoucherPreview(Base):
    """Stores the pre-computed, verified accounting voucher waiting for explicit user approval."""
    __tablename__ = "voucher_previews"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    voucher_type = Column(String(50), nullable=False) # Sales or Purchase
    party_ledger = Column(String(255), nullable=False)
    sales_purchase_ledger = Column(String(255), nullable=False)
    
    invoice_number = Column(String(100), nullable=False)
    invoice_date = Column(String(50), nullable=False)
    
    # Serialized JSON of lines: [{item_name, qty, unit, rate, amount, discount}]
    items_json = Column(Text, nullable=False)
    
    subtotal = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, default=0.0)
    additional_charges = Column(Float, default=0.0)
    round_off = Column(Float, default=0.0)
    final_amount = Column(Float, nullable=False, default=0.0)
    
    narration = Column(Text, nullable=True)
    is_approved = Column(Boolean, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    bill = relationship("Bill", back_populates="voucher_preview")
    transactions = relationship("TallyTransaction", back_populates="voucher_preview", cascade="all, delete-orphan")

class TallyTransaction(Base):
    """Complete audit of actual Tally XML post requests and TallyPrime XML responses."""
    __tablename__ = "tally_transactions"

    id = Column(Integer, primary_key=True, index=True)
    voucher_preview_id = Column(Integer, ForeignKey("voucher_previews.id", ondelete="CASCADE"), nullable=False)
    
    request_xml = Column(Text, nullable=False)
    response_xml = Column(Text, nullable=False)
    
    status = Column(String(30), nullable=False) # SUCCESS, FAILED
    tally_voucher_number = Column(String(100), nullable=True)
    tally_guid = Column(String(150), nullable=True)
    error_message = Column(Text, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    voucher_preview = relationship("VoucherPreview", back_populates="transactions")
