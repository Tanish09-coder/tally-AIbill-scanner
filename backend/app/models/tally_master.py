from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class TallyMaster(Base):
    """Local cache of Tally masters for matching, speed and offline resilience."""
    __tablename__ = "tally_masters"

    id = Column(Integer, primary_key=True, index=True)
    master_type = Column(String(50), nullable=False, index=True) # LEDGER, STOCK_ITEM, UNIT, STOCK_GROUP, COMPANY
    name = Column(String(255), nullable=False, index=True)
    parent_group = Column(String(255), nullable=True) # e.g. Sundry Debtors, Sundry Creditors, Sales Accounts
    details_json = Column(Text, nullable=True)
    last_synced = Column(DateTime(timezone=True), default=utcnow)

class PartyMapping(Base):
    """User-approved mapping between raw OCR party name and Tally ledger."""
    __tablename__ = "party_mappings"

    id = Column(Integer, primary_key=True, index=True)
    raw_name = Column(String(255), nullable=False, index=True)
    tally_ledger_name = Column(String(255), nullable=False)
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

class StockItemMapping(Base):
    """User-approved mapping between raw OCR item name and Tally stock item."""
    __tablename__ = "stock_item_mappings"

    id = Column(Integer, primary_key=True, index=True)
    raw_name = Column(String(255), nullable=False, index=True)
    tally_stock_item_name = Column(String(255), nullable=False)
    unit = Column(String(50), default="NOS")
    is_verified = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

