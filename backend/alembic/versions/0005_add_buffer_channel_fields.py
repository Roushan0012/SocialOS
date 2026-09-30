"""add buffer channel fields to social_accounts

Revision ID: 0005_add_buffer_channel_fields
Revises: 0004_add_social_oauth_foundation
Create Date: 2026-10-01 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_add_buffer_channel_fields"
down_revision: Union[str, None] = "0004_add_social_oauth_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "social_accounts",
        sa.Column("buffer_channel_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "social_accounts",
        sa.Column("buffer_organization_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_social_accounts_buffer_channel_id"),
        "social_accounts",
        ["buffer_channel_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_social_accounts_buffer_organization_id"),
        "social_accounts",
        ["buffer_organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_social_accounts_buffer_organization_id"), table_name="social_accounts")
    op.drop_index(op.f("ix_social_accounts_buffer_channel_id"), table_name="social_accounts")
    op.drop_column("social_accounts", "buffer_organization_id")
    op.drop_column("social_accounts", "buffer_channel_id")
