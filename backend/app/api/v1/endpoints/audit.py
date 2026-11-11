from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.audit import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit History"])

class AuditLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details_json: Optional[str] = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    return result.scalars().all()
