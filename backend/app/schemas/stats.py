from pydantic import BaseModel

class DashboardStatsResponse(BaseModel):
    total_bills: int
    sales_bills: int
    purchase_bills: int
    pending_clarifications: int
    ready_for_approval: int
    posted_to_tally: int
    failed_transactions: int
    tally_connected: bool
    active_company: str | None = None

