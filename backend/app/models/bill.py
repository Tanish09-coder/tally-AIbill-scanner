from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False) # jpg, png, pdf
    
    # Bill details
    bill_type = Column(String(20), default="UNKNOWN") # SALES, PURCHASE, UNKNOWN
    invoice_number = Column(String(100), nullable=True, index=True)
    invoice_date = Column(String(50), nullable=True) # DD-MM-YYYY or ISO format
    party_name = Column(String(255), nullable=True, index=True)
    party_address = Column(Text, nullable=True)
    contact_details = Column(String(100), nullable=True)
    
    # Financials (Non-GST)
    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    additional_charges = Column(Float, default=0.0)
    round_off = Column(Float, default=0.0)
    final_amount = Column(Float, default=0.0)
    
    # Processing state
    # UPLOADED, SCANNING, PENDING_CLARIFICATION, READY_FOR_APPROVAL, APPROVED, POSTED, FAILED
    status = Column(String(50), default="UPLOADED", index=True)
    
    # Non-GST verification flag
    is_gst_detected = Column(Boolean, default=False)
    gst_warning_text = Column(Text, nullable=True)
    
    # Quality & OCR metadata
    confidence_score = Column(Float, default=1.0)
    extracted_raw_json = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")
    clarifications = relationship("ClarificationQuestion", back_populates="bill", cascade="all, delete-orphan")
    voucher_preview = relationship("VoucherPreview", back_populates="bill", uselist=False, cascade="all, delete-orphan")

