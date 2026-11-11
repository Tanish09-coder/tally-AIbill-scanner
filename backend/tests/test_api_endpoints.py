import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from main import app
from app.core.database import init_db

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    await init_db()

@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "tally_endpoint" in data

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["api_keys_configured"] is True

@pytest.mark.asyncio
async def test_dashboard_stats():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_bills" in data
        assert "tally_connected" in data

@pytest.mark.asyncio
async def test_bills_list_empty():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/bills/")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "bills" in data
