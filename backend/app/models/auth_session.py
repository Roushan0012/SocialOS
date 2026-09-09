"""Auth Session / Refresh Token Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthSession(Base, TimestampMixin):
    """Authentication session entity tracking hashed refresh tokens.

    SECURITY INVARIANTS:
    - Raw refresh tokens are NEVER stored in PostgreSQL.
    - Only a cryptographically secure SHA-256 digest (token_hash) is persisted.
    - Each refresh operation rotates the token: the old session is marked revoked_at = now,
      and a brand new refresh token and session are generated.
    - Revoked or expired sessions cannot be reused to obtain new access tokens.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="auth_sessions",
    )

    @property
    def is_active(self) -> bool:
        """Return True if session is not revoked and not expired."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return self.revoked_at is None and (exp > now if exp is not None else False)

    def __repr__(self) -> str:
        return f"<AuthSession(id={self.id}, user_id={self.user_id}, active={self.is_active})>"
