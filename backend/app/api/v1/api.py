from fastapi import APIRouter
from app.api.v1.endpoints import bills, clarifications, vouchers, tally, voice, dashboard, audit

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(dashboard.router)
api_router.include_router(bills.router)
api_router.include_router(clarifications.router)
api_router.include_router(vouchers.router)
api_router.include_router(tally.router)
api_router.include_router(voice.router)
api_router.include_router(audit.router)

