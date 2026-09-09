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


EXPECTED_TABLES = {
    "roles",
    "users",
    "companies",
    "social_accounts",
    "posts",
    "post_targets",
    "media_assets",
    "tasks",
    "task_comments",
    "task_attachments",
    "attendance",
    "notifications",
    "activity_logs",
    "social_analytics_daily",
}


def test_alembic_target_metadata_contains_all_14_tables():
    """Verify that Alembic target metadata registers all 14 required SocialOS tables."""
    table_names = set(Base.metadata.tables.keys())
    assert table_names == EXPECTED_TABLES, (
        f"Base.metadata mismatch. Missing: {EXPECTED_TABLES - table_names}, Extra: {table_names - EXPECTED_TABLES}"
    )


def test_alembic_migration_upgrade_sql_generation(capsys):
    """Verify that alembic upgrade head --sql generates valid DDL for all 14 tables."""
    from alembic import command

    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.migration_database_url)

    # Generate offline SQL
    command.upgrade(alembic_cfg, "head", sql=True)
    captured = capsys.readouterr()
    sql_output = captured.out

    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE {table}" in sql_output, f"Table {table} missing from generated upgrade SQL"

    assert "INSERT INTO roles" in sql_output
    assert "0001_initial_schema" in sql_output


def test_alembic_migration_downgrade_sql_generation(capsys):
    """Verify that alembic downgrade --sql generates reversible DDL dropping all 14 tables."""
    from alembic import command

    alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.migration_database_url)

    # Generate offline downgrade SQL
    command.downgrade(alembic_cfg, "0001_initial_schema:base", sql=True)
    captured = capsys.readouterr()
    sql_output = captured.out

    for table in EXPECTED_TABLES:
        assert f"DROP TABLE {table}" in sql_output, f"Table {table} missing from generated downgrade SQL"

    assert "DROP TYPE" in sql_output
    assert "DELETE FROM alembic_version" in sql_output

