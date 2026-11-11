import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.database import init_db, engine
from app.models import (
    User, Bill, BillItem, ClarificationQuestion, ClarificationAnswer,
    TallyMaster, PartyMapping, StockItemMapping, VoucherPreview,
    TallyTransaction, AuditLog
)

async def main():
    print("Initializing Database tables...")
    await init_db()
    print("✅ All database tables successfully created in SQLite!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

