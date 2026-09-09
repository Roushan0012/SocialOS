"""Social Analytics Daily Database Model."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.social_account import SocialAccount


class SocialAnalyticsDaily(Base):
    """Daily aggregated social media performance metrics.

    Stores official channel-level metrics fetched from platform APIs.
    Fake analytics data must NEVER be seeded.
    """

    __tablename__ = "social_analytics_daily"
    __table_args__ = (
        UniqueConstraint(
            "social_account_id",
            "date",
            name="uq_social_analytics_daily_account_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    impressions: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    reach: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    likes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    comments: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    shares: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    saves: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    views: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    followers: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        default=0,
        nullable=True,
    )
    engagement_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(precision=7, scale=4),
        default=0.0,
        nullable=True,
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    social_account: Mapped["SocialAccount"] = relationship(
        "SocialAccount",
        back_populates="analytics_daily",
    )

    def __repr__(self) -> str:
        return f"<SocialAnalyticsDaily(id={self.id}, account_id={self.social_account_id}, date={self.date})>"
