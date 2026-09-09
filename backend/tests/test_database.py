from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.core.database import Base, check_database_health


def test_all_14_business_tables_registered():
    """Verify strictly 14 core business tables are defined in Step 6."""
    assert len(Base.metadata.tables) == 14, (
        f"Expected 14 tables in Base.metadata, found {len(Base.metadata.tables)}: {list(Base.metadata.tables.keys())}"
    )


@pytest.mark.asyncio
async def test_check_database_health_mocked_success():
    """Verify check_database_health returns True when SELECT 1 succeeds."""
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1

    mock_conn = AsyncMock()
    mock_conn.execute.return_value = mock_result

    # In SQLAlchemy AsyncEngine, connect() is a synchronous method returning an async context manager
    mock_connect_ctx = MagicMock()
    mock_connect_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_connect_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connect_ctx

    with patch("app.core.database.async_engine", mock_engine):
        is_healthy = await check_database_health()
        assert is_healthy is True


@pytest.mark.asyncio
async def test_check_database_health_mocked_failure():
    """Verify check_database_health returns False gracefully when connection fails."""
    mock_connect_ctx = MagicMock()
    mock_connect_ctx.__aenter__ = AsyncMock(side_effect=ConnectionRefusedError("Connection refused"))
    mock_connect_ctx.__aexit__ = AsyncMock(return_value=None)

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_connect_ctx

    with patch("app.core.database.async_engine", mock_engine):
        is_healthy = await check_database_health()
        assert is_healthy is False


@pytest.mark.asyncio
async def test_check_database_health_returns_boolean():
    """Verify check_database_health executes without unhandled exceptions on real engine call."""
    # Under test environment, this executes against configured DATABASE_URL
    # and must safely return a boolean (True if live Supabase is configured, False if placeholder)
    result = await check_database_health()
    assert isinstance(result, bool)
