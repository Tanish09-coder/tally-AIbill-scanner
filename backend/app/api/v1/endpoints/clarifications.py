from typing import List, Optional
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.bill import Bill
from app.models.bill_item import BillItem
from app.models.clarification import ClarificationQuestion, ClarificationAnswer
from app.models.audit import AuditLog
from app.schemas.clarification import (
    ClarificationQuestionResponse, ClarificationResolveRequest
)
from app.services.clarification.engine import clarification_engine
from app.services.voice.sarvam_service import sarvam_voice_service

router = APIRouter(prefix="/clarifications", tags=["Clarifications"])

@router.get("/bills/{bill_id}/questions", response_model=List[ClarificationQuestionResponse])
async def get_bill_clarifications(bill_id: int, db: AsyncSession = Depends(get_db)):
    query = select(ClarificationQuestion).options(
        selectinload(ClarificationQuestion.answers)
    ).where(ClarificationQuestion.bill_id == bill_id).order_by(ClarificationQuestion.id.asc())
    
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/questions/{question_id}/answer")
async def answer_clarification(
    question_id: int,
    payload: ClarificationResolveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submits user clarification (via spoken Hinglish voice or text input).
    Updates the target field on the Bill or BillItem and marks the question answered.
    """
    question = await db.get(ClarificationQuestion, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    user_text = payload.user_response.strip()
    bill = await db.get(Bill, question.bill_id)

    ai_reply_hinglish = "Theek hai, details note kar li gayi hain."

    # Parse and apply to target entity
    if question.field_name == "item_name" and question.target_item_id:
        item = await db.get(BillItem, question.target_item_id)
        if item:
            item.raw_item_name = user_text
            item.matched_stock_item_name = user_text
            item.status = "RESOLVED"
            ai_reply_hinglish = f"Perfect! Maine item ka naam '{user_text}' update kar diya hai."

    elif question.field_name == "quantity" and question.target_item_id:
        num = clarification_engine.parse_numeric_hinglish(user_text)
        if num is not None:
            item = await db.get(BillItem, question.target_item_id)
            if item:
                item.quantity = num
                item.amount = round(item.quantity * item.rate, 2)
                ai_reply_hinglish = f"Quantity {num} set ho gayi hai."

    elif question.field_name == "rate" and question.target_item_id:
        num = clarification_engine.parse_numeric_hinglish(user_text)
        if num is not None:
            item = await db.get(BillItem, question.target_item_id)
            if item:
                item.rate = num
                item.amount = round(item.quantity * item.rate, 2)
                ai_reply_hinglish = f"Rate ₹{num} update kar diya hai."

    elif question.field_name == "final_amount" and bill:
        num = clarification_engine.parse_numeric_hinglish(user_text)
        if num is not None:
            bill.final_amount = num
            ai_reply_hinglish = f"Final bill amount ₹{num} confirm ho gaya hai."

    elif question.field_name == "party_name" and bill:
        bill.party_name = user_text
        ai_reply_hinglish = f"Party name '{user_text}' set ho gaya hai."

    elif question.field_name == "is_gst_detected" and bill:
        # User confirmed to proceed as Non-GST
        bill.is_gst_detected = False
        ai_reply_hinglish = "Theek hai, isko Non-GST voucher ki tarah proceed karte hain."

    # Record answer
    answer = ClarificationAnswer(
        question_id=question.id,
        raw_transcript=user_text,
        extracted_value=user_text,
        confirmed_by_user=True
    )
    db.add(answer)
    question.status = "ANSWERED"

    # Check remaining pending questions
    pending_res = await db.execute(
        select(ClarificationQuestion).where(
            ClarificationQuestion.bill_id == question.bill_id,
            ClarificationQuestion.status == "PENDING",
            ClarificationQuestion.id != question.id
        )
    )
    remaining_pending = pending_res.scalars().all()

    if not remaining_pending and bill:
        bill.status = "READY_FOR_APPROVAL"
        ai_reply_hinglish += " Bill ki saari details verify ho gayi hain. Kya main voucher TallyPrime mein save kar doon?"

    # Generate Hinglish spoken voice confirmation
    audio_base64 = None
    try:
        tts_res = await sarvam_voice_service.text_to_speech(ai_reply_hinglish)
        audio_base64 = tts_res.get("audio_base64")
    except Exception:
        pass # Graceful fallback to text if TTS unavailable

    await db.commit()

    return {
        "success": True,
        "message": ai_reply_hinglish,
        "audio_base64": audio_base64,
        "bill_status": bill.status if bill else None,
        "remaining_pending_count": len(remaining_pending)
    }

