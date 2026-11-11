import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.api.v1.api import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("tally_ai")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing AI Bill Scanner + TallyPrime Automation System...")
    logger.info(f"Target Tally Endpoint: {settings.tally_endpoint_url}")
    
    # 1. Initialize SQLite tables
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    # 2. Check API keys
    is_valid, errors = settings.validate_api_keys(raise_on_error=False)
    if not is_valid:
        logger.warning("\n" + "!" * 70)
        logger.warning("STARTUP WARNING: API KEYS REQUIRE CONFIGURATION")
        for err in errors:
            logger.warning(err)
        logger.warning("!" * 70 + "\n")
    else:
        logger.info("✅ All required API keys are configured and active.")

    yield

    logger.info("Shutting down AI Bill Scanner service.")

app = FastAPI(
    title="AI Bill Scanner + Hinglish Voice Assistant + TallyPrime Automation",
    description="Backend API for multilingual bill recognition, Hinglish voice clarification, and automated TallyPrime non-GST voucher posting.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Uploads directory for bill preview in frontend
upload_path = Path(settings.UPLOAD_DIR)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")

# Include API Router
app.include_router(api_router)

@app.get("/")
async def root():
    return {
        "app": "AI Bill Scanner & TallyPrime Automation",
        "status": "online",
        "version": "1.0.0",
        "tally_endpoint": settings.tally_endpoint_url
    }

@app.get("/api/v1/health")
async def health_check():
    is_valid, errors = settings.validate_api_keys(raise_on_error=False)
    return {
        "status": "healthy",
        "api_keys_configured": is_valid,
        "key_issues": errors if not is_valid else [],
        "tally_endpoint": settings.tally_endpoint_url
    }
