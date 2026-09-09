"""add social oauth foundation (oauth_states table and social_accounts last_connected_at)

Revision ID: 0004_add_social_oauth_foundation
Revises: 0003_add_company_memberships
Create Date: 2026-09-10 01:45:00.000000

"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_add_social_oauth_foundation"
down_revision: Union[str, None] = "0003_add_company_memberships"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PLATFORM_ENUM = sa.Enum(
    "INSTAGRAM",
    "FACEBOOK",
    "LINKEDIN",
    "YOUTUBE",
    name="platform_enum",
).with_variant(
    postgresql.ENUM(
        "INSTAGRAM",
        "FACEBOOK",
        "LINKEDIN",
        "YOUTUBE",
        name="platform_enum",
        create_type=False,
    ),
    "postgresql",
)


def upgrade() -> None:
    # 1. Add last_connected_at to social_accounts
    op.add_column(
        "social_accounts",
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Create oauth_states table for CSRF protection and state binding
    op.create_table(
        "oauth_states",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("state_token", sa.String(length=128), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "platform",
            PLATFORM_ENUM,
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_oauth_states_state_token"),
        "oauth_states",
        ["state_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_oauth_states_user_id"),
        "oauth_states",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_states_company_id"),
        "oauth_states",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_states_platform"),
        "oauth_states",
        ["platform"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth_states_expires_at"),
        "oauth_states",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
    op.drop_column("social_accounts", "last_connected_at")
