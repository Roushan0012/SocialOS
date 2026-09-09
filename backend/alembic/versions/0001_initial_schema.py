"""create initial production schema for socialos

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-09 19:30:00.000000

"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enumeration names and value sets
PLATFORM_ENUM = sa.Enum("INSTAGRAM", "FACEBOOK", "LINKEDIN", "YOUTUBE", name="platform_enum")
SOCIAL_ACCOUNT_STATUS_ENUM = sa.Enum("ACTIVE", "DISCONNECTED", "EXPIRED", "ERROR", name="social_account_status_enum")
POST_STATUS_ENUM = sa.Enum("DRAFT", "SCHEDULED", "PUBLISHING", "PARTIALLY_PUBLISHED", "PUBLISHED", "FAILED", "CANCELLED", name="post_status_enum")
POST_TARGET_STATUS_ENUM = sa.Enum("PENDING", "PUBLISHING", "PUBLISHED", "FAILED", "SKIPPED", name="post_target_status_enum")
MEDIA_TYPE_ENUM = sa.Enum("IMAGE", "VIDEO", "PDF", "OTHER", name="media_type_enum")
TASK_PRIORITY_ENUM = sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="task_priority_enum")
TASK_STATUS_ENUM = sa.Enum("TODO", "IN_PROGRESS", "IN_REVIEW", "COMPLETED", "PENDING", "OVERDUE", "CANCELLED", name="task_status_enum")
ATTENDANCE_STATUS_ENUM = sa.Enum("PRESENT", "ABSENT", "HALF_DAY", "LEAVE", name="attendance_status_enum")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Core Tables: roles, users, companies
    # -------------------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_roles_name"), "roles", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("role_id", sa.Uuid(as_uuid=True), sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)

    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_companies_slug"), "companies", ["slug"], unique=True)

    # -------------------------------------------------------------------------
    # 2. Social Accounts & Posts
    # -------------------------------------------------------------------------
    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("company_id", sa.Uuid(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", PLATFORM_ENUM, nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("platform_account_id", sa.String(length=255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", SOCIAL_ACCOUNT_STATUS_ENUM, server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform", "platform_account_id", name="uq_social_accounts_platform_account"),
    )
    op.create_index(op.f("ix_social_accounts_company_id"), "social_accounts", ["company_id"], unique=False)
    op.create_index(op.f("ix_social_accounts_platform"), "social_accounts", ["platform"], unique=False)
    op.create_index(op.f("ix_social_accounts_platform_account_id"), "social_accounts", ["platform_account_id"], unique=False)

    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("company_id", sa.Uuid(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("status", POST_STATUS_ENUM, server_default=sa.text("'DRAFT'"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_posts_company_id"), "posts", ["company_id"], unique=False)
    op.create_index(op.f("ix_posts_created_by"), "posts", ["created_by"], unique=False)
    op.create_index(op.f("ix_posts_scheduled_at"), "posts", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_posts_status"), "posts", ["status"], unique=False)

    op.create_table(
        "post_targets",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("post_id", sa.Uuid(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("social_account_id", sa.Uuid(as_uuid=True), sa.ForeignKey("social_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("platform", PLATFORM_ENUM, nullable=False),
        sa.Column("status", POST_TARGET_STATUS_ENUM, server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("provider_post_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("post_id", "social_account_id", name="uq_post_targets_post_social_account"),
    )
    op.create_index(op.f("ix_post_targets_post_id"), "post_targets", ["post_id"], unique=False)
    op.create_index(op.f("ix_post_targets_social_account_id"), "post_targets", ["social_account_id"], unique=False)

    # -------------------------------------------------------------------------
    # 3. Media Assets
    # -------------------------------------------------------------------------
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("post_id", sa.Uuid(as_uuid=True), sa.ForeignKey("posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("cdn_url", sa.String(length=1024), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", MEDIA_TYPE_ENUM, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_media_assets_post_id"), "media_assets", ["post_id"], unique=False)
    op.create_index(op.f("ix_media_assets_created_by"), "media_assets", ["created_by"], unique=False)

    # -------------------------------------------------------------------------
    # 4. Tasks, Comments, Attachments
    # -------------------------------------------------------------------------
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("company_id", sa.Uuid(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("assigned_to", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", TASK_PRIORITY_ENUM, server_default=sa.text("'MEDIUM'"), nullable=False),
        sa.Column("status", TASK_STATUS_ENUM, server_default=sa.text("'TODO'"), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_tasks_company_id"), "tasks", ["company_id"], unique=False)
    op.create_index(op.f("ix_tasks_assigned_to"), "tasks", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)
    op.create_index(op.f("ix_tasks_deadline"), "tasks", ["deadline"], unique=False)

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("task_id", sa.Uuid(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_task_comments_task_id"), "task_comments", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_comments_user_id"), "task_comments", ["user_id"], unique=False)

    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("task_id", sa.Uuid(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("cdn_url", sa.String(length=1024), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_task_attachments_task_id"), "task_attachments", ["task_id"], unique=False)
    op.create_index(op.f("ix_task_attachments_uploaded_by"), "task_attachments", ["uploaded_by"], unique=False)

    # -------------------------------------------------------------------------
    # 5. Attendance
    # -------------------------------------------------------------------------
    op.create_table(
        "attendance",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("check_in", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", ATTENDANCE_STATUS_ENUM, server_default=sa.text("'PRESENT'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "date", name="uq_attendance_user_date"),
    )
    op.create_index(op.f("ix_attendance_user_id"), "attendance", ["user_id"], unique=False)
    op.create_index(op.f("ix_attendance_date"), "attendance", ["date"], unique=False)

    # -------------------------------------------------------------------------
    # 6. Notifications & Activity Logs
    # -------------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False)

    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f("ix_activity_logs_user_id"), "activity_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_entity_type"), "activity_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_activity_logs_entity_id"), "activity_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_activity_logs_created_at"), "activity_logs", ["created_at"], unique=False)

    # -------------------------------------------------------------------------
    # 7. Social Analytics Daily
    # -------------------------------------------------------------------------
    op.create_table(
        "social_analytics_daily",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("social_account_id", sa.Uuid(as_uuid=True), sa.ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("reach", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("likes", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("comments", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("shares", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("saves", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("views", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("followers", sa.BigInteger(), server_default=sa.text("0"), nullable=True),
        sa.Column("engagement_rate", sa.Numeric(precision=7, scale=4), server_default=sa.text("0.0"), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("social_account_id", "date", name="uq_social_analytics_daily_account_date"),
    )
    op.create_index(op.f("ix_social_analytics_daily_social_account_id"), "social_analytics_daily", ["social_account_id"], unique=False)
    op.create_index(op.f("ix_social_analytics_daily_date"), "social_analytics_daily", ["date"], unique=False)

    # -------------------------------------------------------------------------
    # 8. Idempotent Initial Seed: System Roles
    # -------------------------------------------------------------------------
    roles_table = sa.table(
        "roles",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    initial_roles = [
        {"id": uuid.UUID("00000000-0000-0000-0000-000000000001"), "name": "ADMIN", "description": "System Administrator with full organizational and tenant control"},
        {"id": uuid.UUID("00000000-0000-0000-0000-000000000002"), "name": "SOCIAL_MEDIA_MANAGER", "description": "Social Media Manager overseeing brands, campaigns, and approvals"},
        {"id": uuid.UUID("00000000-0000-0000-0000-000000000003"), "name": "CONTENT_CREATOR", "description": "Content Creator authoring post copy and content submissions"},
        {"id": uuid.UUID("00000000-0000-0000-0000-000000000004"), "name": "GRAPHIC_DESIGNER", "description": "Graphic Designer creating visual artwork and media assets"},
        {"id": uuid.UUID("00000000-0000-0000-0000-000000000005"), "name": "VIDEO_EDITOR", "description": "Video Editor producing reels, shorts, and video productions"},
    ]
    # In SQLite or Postgres, insert default roles safely
    op.bulk_insert(roles_table, initial_roles)


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("social_analytics_daily")
    op.drop_table("activity_logs")
    op.drop_table("notifications")
    op.drop_table("attendance")
    op.drop_table("task_attachments")
    op.drop_table("task_comments")
    op.drop_table("tasks")
    op.drop_table("media_assets")
    op.drop_table("post_targets")
    op.drop_table("posts")
    op.drop_table("social_accounts")
    op.drop_table("companies")
    op.drop_table("users")
    op.drop_table("roles")

    # Drop PostgreSQL enum types if running against postgresql
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        ATTENDANCE_STATUS_ENUM.drop(bind, checkfirst=True)
        TASK_STATUS_ENUM.drop(bind, checkfirst=True)
        TASK_PRIORITY_ENUM.drop(bind, checkfirst=True)
        MEDIA_TYPE_ENUM.drop(bind, checkfirst=True)
        POST_TARGET_STATUS_ENUM.drop(bind, checkfirst=True)
        POST_STATUS_ENUM.drop(bind, checkfirst=True)
        SOCIAL_ACCOUNT_STATUS_ENUM.drop(bind, checkfirst=True)
        PLATFORM_ENUM.drop(bind, checkfirst=True)
