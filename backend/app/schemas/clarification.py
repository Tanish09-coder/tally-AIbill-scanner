from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ClarificationAnswerCreate(BaseModel):
    raw_transcript: Optional[str] = None
    extracted_value: str
    confirmed_by_user: bool = True

class ClarificationAnswerResponse(ClarificationAnswerCreate):
    id: int
    question_id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class ClarificationQuestionResponse(BaseModel):
    id: int
    bill_id: int
    target_item_id: Optional[int] = None
    field_name: str
    question_hinglish: str
    question_type: str
    status: str
    created_at: datetime
    answers: List[ClarificationAnswerResponse] = []
    model_config = ConfigDict(from_attributes=True)

class ClarificationResolveRequest(BaseModel):
    question_id: int
    user_response: str
    is_voice: bool = False
