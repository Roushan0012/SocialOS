from pathlib import Path
from alembic.config import Config
from app.core.config import settings
from app.models import Base


def test_alembic_config_loading():
    """Verify that alembic.ini loads correctly and points to valid migration configuration."""
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    assert alembic_ini_path.exists(), f"alembic.ini not found at {alembic_ini_path}"

    alembic_cfg = Config(str(alembic_ini_path))
    assert alembic_cfg.get_main_option("script_location") == "alembic"


def test_alembic_uses_migration_database_url():
    """Verify that Alembic configuration can be overridden with settings.migration_database_url."""
    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))

    migration_url = settings.migration_database_url
    alembic_cfg.set_main_option("sqlalchemy.url", migration_url)

    assert alembic_cfg.get_main_option("sqlalchemy.url") == migration_url


def test_alembic_target_metadata_has_zero_business_tables():
    """Verify that Alembic target metadata currently contains no business tables."""
    assert len(Base.metadata.tables) == 0, (
        "Business tables must not be present in migration metadata during foundation step."
    )
