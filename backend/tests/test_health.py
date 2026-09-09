from unittest.mock import patch
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
async def test_root_database_healthz_success():
    """Verify that GET /healthz/db returns 200 when database connectivity succeeds."""
    with patch("app.main.check_database_health", return_value=True):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/healthz/db")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "connected"
            assert data["engine"] == "postgresql+asyncpg"
            # Ensure no credentials leaked
            assert "password" not in str(data).lower()


@pytest.mark.asyncio
async def test_root_database_healthz_unreachable():
    """Verify that GET /healthz/db returns 503 when database is unreachable."""
    with patch("app.main.check_database_health", return_value=False):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/healthz/db")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "error"
            assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_api_v1_database_healthz_endpoint():
    """Verify that GET /api/v1/healthz/db returns valid payload."""
    with patch("app.api.v1.api_router.check_database_health", return_value=True):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/healthz/db")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "connected"


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
        assert data["health_db"] == "/healthz/db"
