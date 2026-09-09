"""add company memberships table for brand multi-tenancy access control

Revision ID: 0003_add_company_memberships
Revises: 0002_add_auth_sessions
Create Date: 2026-09-09 20:30:00.000000

"""
from typing import Sequence, Union
import uuid
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_add_company_memberships"
down_revision: Union[str, None] = "0002_add_auth_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_memberships",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "company_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("company_id", "user_id", name="uq_company_memberships_company_user"),
    )
    op.create_index(
        op.f("ix_company_memberships_company_id"),
        "company_memberships",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_company_memberships_user_id"),
        "company_memberships",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("company_memberships")
