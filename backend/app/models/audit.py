from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class AuditLog(Base):
    """Immutable audit trail for financial accountability, approvals, and system changes."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False, index=True) # BILL_UPLOAD, OCR_SCANNED, CLARIFICATION_RESOLVED, VOUCHER_APPROVED, TALLY_POSTED, TALLY_FAILED
    entity_type = Column(String(50), nullable=False) # BILL, VOUCHER, MASTER, SYSTEM
    entity_id = Column(Integer, nullable=True)
    details_json = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)
