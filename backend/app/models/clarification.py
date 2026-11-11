from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class ClarificationQuestion(Base):
    __tablename__ = "clarification_questions"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False)
    target_item_id = Column(Integer, nullable=True) # If targeting a specific BillItem
    
    field_name = Column(String(50), nullable=False) # item_name, quantity, party_name, etc.
    question_hinglish = Column(Text, nullable=False) # Natural spoken Hinglish question
    question_type = Column(String(50), nullable=False) # UNCLEAR_ITEM, UNCLEAR_QTY, MISSING_PARTY, etc.
    status = Column(String(30), default="PENDING") # PENDING, ANSWERED, RESOLVED, SKIPPED
    
    created_at = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    bill = relationship("Bill", back_populates="clarifications")
    answers = relationship("ClarificationAnswer", back_populates="question", cascade="all, delete-orphan")

class ClarificationAnswer(Base):
    __tablename__ = "clarification_answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("clarification_questions.id", ondelete="CASCADE"), nullable=False)
    
    raw_transcript = Column(Text, nullable=True) # Voice recognition raw speech text
    extracted_value = Column(Text, nullable=False) # Parsed/confirmed value
    confirmed_by_user = Column(Boolean, default=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow)

    # Relationships
    question = relationship("ClarificationQuestion", back_populates="answers")

