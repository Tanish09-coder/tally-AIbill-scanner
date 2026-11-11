from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.core.database import get_db
from app.models.bill import Bill
from app.models.voucher import TallyTransaction
from app.schemas.stats import DashboardStatsResponse
from app.services.tally.tally_client import tally_client

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # Total count
    total_q = await db.execute(select(func.count(Bill.id)))
    total_bills = total_q.scalar() or 0

    # Sales count
    sales_q = await db.execute(select(func.count(Bill.id)).where(Bill.bill_type == "SALES"))
    sales_bills = sales_q.scalar() or 0

    # Purchase count
    purchase_q = await db.execute(select(func.count(Bill.id)).where(Bill.bill_type == "PURCHASE"))
    purchase_bills = purchase_q.scalar() or 0

    # Pending clarifications
    pending_q = await db.execute(select(func.count(Bill.id)).where(Bill.status == "CLARIFICATION_REQUIRED"))
    pending_clarifications = pending_q.scalar() or 0

    # Ready for approval
    ready_q = await db.execute(select(func.count(Bill.id)).where(Bill.status == "READY_FOR_APPROVAL"))
    ready_for_approval = ready_q.scalar() or 0

    # Posted
    posted_q = await db.execute(select(func.count(Bill.id)).where(Bill.status == "POSTED"))
    posted_to_tally = posted_q.scalar() or 0

    # Failed
    failed_q = await db.execute(select(func.count(Bill.id)).where(Bill.status == "FAILED"))
    failed_transactions = failed_q.scalar() or 0

    # Tally status
    tally_info = await tally_client.get_connection_status()

    return DashboardStatsResponse(
        total_bills=total_bills,
        sales_bills=sales_bills,
        purchase_bills=purchase_bills,
        pending_clarifications=pending_clarifications,
        ready_for_approval=ready_for_approval,
        posted_to_tally=posted_to_tally,
        failed_transactions=failed_transactions,
        tally_connected=tally_info.get("is_connected", False),
        active_company=tally_info.get("company_name")
    )

