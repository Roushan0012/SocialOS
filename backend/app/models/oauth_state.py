"""OAuth State Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import Platform

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class OAuthState(Base):
    """Temporary CSRF protection state token for social OAuth authorizations.

    Binds an unpredictable high-entropy token to an authenticated user,
    target company/brand, and destination platform.
    Enforces expiration (TTL) and single-use invalidation upon consumption.
    """

    __tablename__ = "oauth_states"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    state_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    company: Mapped["Company"] = relationship("Company")

    def __repr__(self) -> str:
        return f"<OAuthState(id={self.id}, platform='{self.platform}', company_id={self.company_id})>"
