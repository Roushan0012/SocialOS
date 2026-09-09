"""Unit tests for SocialOS SQLAlchemy 2.0 database models and schema constraints."""
import uuid
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import (
    Base,
    Role,
    User,
    Company,
    SocialAccount,
    Post,
    PostTarget,
    MediaAsset,
    Task,
    TaskComment,
    TaskAttachment,
    Attendance,
    Notification,
    ActivityLog,
    SocialAnalyticsDaily,
    RoleName,
    Platform,
    SocialAccountStatus,
    PostStatus,
    PostTargetStatus,
    MediaType,
    TaskPriority,
    TaskStatus,
    AttendanceStatus,
)


def test_all_models_registered_in_metadata():
    """Verify that all 14 expected models are registered with Base.metadata."""
    expected_tables = {
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
    actual_tables = set(Base.metadata.tables.keys())
    assert actual_tables == expected_tables


def test_enum_values():
    """Verify all domain enumeration types contain the strictly required values."""
    assert {e.value for e in RoleName} == {
        "ADMIN",
        "SOCIAL_MEDIA_MANAGER",
        "CONTENT_CREATOR",
        "GRAPHIC_DESIGNER",
        "VIDEO_EDITOR",
    }
    assert {e.value for e in Platform} == {
        "INSTAGRAM",
        "FACEBOOK",
        "LINKEDIN",
        "YOUTUBE",
    }
    assert {e.value for e in SocialAccountStatus} == {
        "ACTIVE",
        "DISCONNECTED",
        "EXPIRED",
        "ERROR",
    }
    assert {e.value for e in PostStatus} == {
        "DRAFT",
        "SCHEDULED",
        "PUBLISHING",
        "PARTIALLY_PUBLISHED",
        "PUBLISHED",
        "FAILED",
        "CANCELLED",
    }
    assert {e.value for e in PostTargetStatus} == {
        "PENDING",
        "PUBLISHING",
        "PUBLISHED",
        "FAILED",
        "SKIPPED",
    }
    assert {e.value for e in MediaType} == {
        "IMAGE",
        "VIDEO",
        "PDF",
        "OTHER",
    }
    assert {e.value for e in TaskPriority} == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "URGENT",
    }
    assert {e.value for e in TaskStatus} == {
        "TODO",
        "IN_PROGRESS",
        "IN_REVIEW",
        "COMPLETED",
        "PENDING",
        "OVERDUE",
        "CANCELLED",
    }
    assert {e.value for e in AttendanceStatus} == {
        "PRESENT",
        "ABSENT",
        "HALF_DAY",
        "LEAVE",
    }


def test_unique_constraints_and_indices():
    """Verify critical uniqueness constraints and indexes on models."""
    # Roles: name is unique
    roles_table = Base.metadata.tables["roles"]
    assert roles_table.columns["name"].unique or any(
        idx.unique and "name" in [c.name for c in idx.columns]
        for idx in roles_table.indexes
    )

    # Users: email is unique
    users_table = Base.metadata.tables["users"]
    assert users_table.columns["email"].unique or any(
        idx.unique and "email" in [c.name for c in idx.columns]
        for idx in users_table.indexes
    )

    # Companies: slug is unique
    companies_table = Base.metadata.tables["companies"]
    assert companies_table.columns["slug"].unique or any(
        idx.unique and "slug" in [c.name for c in idx.columns]
        for idx in companies_table.indexes
    )

    # Attendance: (user_id, date) is unique
    attendance_table = Base.metadata.tables["attendance"]
    attendance_uq = [
        c.columns.keys() for c in attendance_table.constraints if hasattr(c, "columns") and c.__class__.__name__ == "UniqueConstraint"
    ]
    assert ["user_id", "date"] in attendance_uq

    # Social Analytics: (social_account_id, date) is unique
    analytics_table = Base.metadata.tables["social_analytics_daily"]
    analytics_uq = [
        c.columns.keys() for c in analytics_table.constraints if hasattr(c, "columns") and c.__class__.__name__ == "UniqueConstraint"
    ]
    assert ["social_account_id", "date"] in analytics_uq

    # Post Targets: (post_id, social_account_id) is unique
    post_targets_table = Base.metadata.tables["post_targets"]
    post_targets_uq = [
        c.columns.keys() for c in post_targets_table.constraints if hasattr(c, "columns") and c.__class__.__name__ == "UniqueConstraint"
    ]
    assert ["post_id", "social_account_id"] in post_targets_uq

    # Social Accounts: (platform, platform_account_id) is unique
    social_accounts_table = Base.metadata.tables["social_accounts"]
    social_accounts_uq = [
        c.columns.keys() for c in social_accounts_table.constraints if hasattr(c, "columns") and c.__class__.__name__ == "UniqueConstraint"
    ]
    assert ["platform", "platform_account_id"] in social_accounts_uq


def test_foreign_key_relationships():
    """Verify foreign key definitions link correct parent and child entities."""
    users_table = Base.metadata.tables["users"]
    fk_targets = {fk.target_fullname for fk in users_table.foreign_keys}
    assert "roles.id" in fk_targets

    posts_table = Base.metadata.tables["posts"]
    post_fks = {fk.target_fullname for fk in posts_table.foreign_keys}
    assert "companies.id" in post_fks
    assert "users.id" in post_fks

    post_targets_table = Base.metadata.tables["post_targets"]
    target_fks = {fk.target_fullname for fk in post_targets_table.foreign_keys}
    assert "posts.id" in target_fks
    assert "social_accounts.id" in target_fks

    media_table = Base.metadata.tables["media_assets"]
    media_fks = {fk.target_fullname for fk in media_table.foreign_keys}
    assert "posts.id" in media_fks
    assert "users.id" in media_fks

    tasks_table = Base.metadata.tables["tasks"]
    task_fks = {fk.target_fullname for fk in tasks_table.foreign_keys}
    assert "companies.id" in task_fks
    assert "users.id" in task_fks


def test_brand_isolation_invariant():
    """Verify that PostTarget enforces brand isolation validation."""
    company_a = uuid.uuid4()
    company_b = uuid.uuid4()

    # Same company: valid
    PostTarget.validate_brand_isolation(company_a, company_a)

    # Different companies: must raise ValueError
    with pytest.raises(ValueError) as exc_info:
        PostTarget.validate_brand_isolation(company_a, company_b)

    assert "Brand isolation violation" in str(exc_info.value)
    assert "Cross-company target dispatch is forbidden" in str(exc_info.value)


def test_security_rules():
    """Verify no plaintext password or insecure secret columns exist on models."""
    users_table = Base.metadata.tables["users"]
    assert "password_hash" in users_table.columns
    assert "password" not in users_table.columns
    assert "plaintext_password" not in users_table.columns

    social_accounts_table = Base.metadata.tables["social_accounts"]
    assert "encrypted_access_token" in social_accounts_table.columns
    assert "encrypted_refresh_token" in social_accounts_table.columns
    assert "access_token" not in social_accounts_table.columns
    assert "refresh_token" not in social_accounts_table.columns

    # Media assets must store S3 key / CDN url, not binary file blobs
    media_table = Base.metadata.tables["media_assets"]
    assert "storage_key" in media_table.columns
    assert "file_blob" not in media_table.columns
    assert "binary_data" not in media_table.columns


def test_schema_creation_and_teardown_in_sqlite():
    """Verify all 14 models can be created and dropped cleanly in an in-memory SQLite database."""
    from sqlalchemy import create_engine

    test_engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    Base.metadata.create_all(test_engine)

    insp = inspect(test_engine)
    tables = insp.get_table_names()
    assert len(tables) == 14
    assert "roles" in tables
    assert "users" in tables
    assert "companies" in tables
    assert "posts" in tables
    assert "tasks" in tables
    assert "attendance" in tables

    # Teardown
    Base.metadata.drop_all(test_engine)
    assert len(inspect(test_engine).get_table_names()) == 0

    test_engine.dispose()
