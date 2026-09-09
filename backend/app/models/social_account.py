"""Social Account Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Platform, SocialAccountStatus

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.post_target import PostTarget
    from app.models.social_analytics import SocialAnalyticsDaily


class SocialAccount(Base, TimestampMixin):
    """Connected social media account entity.

    Stores OAuth token credentials (encrypted at rest), channel identifiers,
    and platform configuration. Sensitive tokens must NEVER be stored in plaintext.
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_account_id",
            name="uq_social_accounts_platform_account",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform, name="platform_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    account_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    platform_account_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    encrypted_access_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[SocialAccountStatus] = mapped_column(
        SAEnum(SocialAccountStatus, name="social_account_status_enum", native_enum=True),
        default=SocialAccountStatus.ACTIVE,
        nullable=False,
    )
    # Using 'account_metadata' attribute to map column 'metadata' (prevent shadowing Base.metadata)
    account_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="social_accounts",
    )
    post_targets: Mapped[List["PostTarget"]] = relationship(
        "PostTarget",
        back_populates="social_account",
    )
    analytics_daily: Mapped[List["SocialAnalyticsDaily"]] = relationship(
        "SocialAnalyticsDaily",
        back_populates="social_account",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SocialAccount(id={self.id}, platform='{self.platform}', account_name='{self.account_name}')>"
