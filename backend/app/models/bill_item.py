from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    
    raw_item_name = Column(String(255), nullable=False)
    matched_stock_item_name = Column(String(255), nullable=True)
    
    quantity = Column(Float, nullable=False, default=1.0)
    unit = Column(String(50), default="NOS")
    rate = Column(Float, nullable=False, default=0.0)
    amount = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, default=0.0)
    
    confidence_score = Column(Float, default=1.0)
    status = Column(String(30), default="VALID") # VALID, NEEDS_CLARIFICATION, RESOLVED

    # Relationships
    bill = relationship("Bill", back_populates="items")

