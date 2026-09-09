import pytest
from app.core.config import Settings


def test_supabase_config_defaults():
    """Verify default Supabase settings are present and correctly formatted."""
    test_settings = Settings()
    assert test_settings.SUPABASE_URL == "https://nsgpjfjziuedhnjkpucp.supabase.co"
    assert test_settings.SUPABASE_JWKS_URL == "https://nsgpjfjziuedhnjkpucp.supabase.co/auth/v1/.well-known/jwks.json"
    assert test_settings.SUPABASE_SECRET_KEY is None or isinstance(test_settings.SUPABASE_SECRET_KEY, str)


def test_asyncpg_url_conversion():
    """Verify that PostgreSQL URLs are automatically converted to asyncpg dialect."""
    # Test postgres:// conversion
    converted_1 = Settings.assemble_async_db_connection("postgres://user:pass@host:5432/db")
    assert converted_1 == "postgresql+asyncpg://user:pass@host:5432/db"

    # Test postgresql:// conversion
    converted_2 = Settings.assemble_async_db_connection("postgresql://user:pass@host:5432/db")
    assert converted_2 == "postgresql+asyncpg://user:pass@host:5432/db"

    # Test postgresql+asyncpg:// left intact
    converted_3 = Settings.assemble_async_db_connection("postgresql+asyncpg://user:pass@host:5432/db")
    assert converted_3 == "postgresql+asyncpg://user:pass@host:5432/db"

    # Test None / empty string
    assert Settings.assemble_async_db_connection(None) is None
    assert Settings.assemble_async_db_connection("") == ""


def test_migration_database_url_preference():
    """Verify migration_database_url prefers DIRECT_URL over DATABASE_URL when set."""
    # When DIRECT_URL is set
    settings_with_direct = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@pooler:6543/postgres",
        DIRECT_URL="postgresql+asyncpg://user:pass@direct:5432/postgres",
    )
    assert settings_with_direct.migration_database_url == "postgresql+asyncpg://user:pass@direct:5432/postgres"

    # When DIRECT_URL is not set, fallback to DATABASE_URL
    settings_without_direct = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@pooler:6543/postgres",
        DIRECT_URL=None,
    )
    assert settings_without_direct.migration_database_url == "postgresql+asyncpg://user:pass@pooler:6543/postgres"


def test_sanitize_db_url_strips_credentials():
    """Verify sanitize_db_url completely strips user passwords from database connection strings."""
    raw_url = "postgresql+asyncpg://postgres.nsgpjfjziuedhnjkpucp:SuperSecretPassword123!@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
    sanitized = Settings.sanitize_db_url(raw_url)

    # Password must not be present
    assert "SuperSecretPassword123!" not in sanitized
    # Host and username should remain for diagnostics
    assert "postgres.nsgpjfjziuedhnjkpucp" in sanitized
    assert "aws-0-ap-southeast-1.pooler.supabase.com:6543" in sanitized
    assert "postgres" in sanitized

    # Empty / None test
    assert Settings.sanitize_db_url(None) == "not-configured"
    assert Settings.sanitize_db_url("") == "not-configured"
