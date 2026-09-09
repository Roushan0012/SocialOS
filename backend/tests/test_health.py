import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_healthz_endpoint():
    """Verify that GET /healthz returns status 200 and healthy payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "SocialOS"
        assert "version" in data
        assert "environment" in data


@pytest.mark.asyncio
async def test_api_v1_healthz_endpoint():
    """Verify that GET /api/v1/healthz returns status 200 and healthy payload."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["app"] == "SocialOS"


@pytest.mark.asyncio
async def test_root_info_endpoint():
    """Verify root / info endpoint."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["app"] == "SocialOS"
        assert data["health"] == "/healthz"
