"""Post Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PostStatus

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User
    from app.models.post_target import PostTarget
    from app.models.media_asset import MediaAsset


class Post(Base, TimestampMixin):
    """Post entity for cross-platform publishing and schedule management."""

    __tablename__ = "posts"

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
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    caption: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(PostStatus, name="post_status_enum", native_enum=True),
        default=PostStatus.DRAFT,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="posts",
    )
    creator: Mapped["User"] = relationship(
        "User",
        back_populates="created_posts",
        foreign_keys=[created_by],
    )
    targets: Mapped[List["PostTarget"]] = relationship(
        "PostTarget",
        back_populates="post",
        cascade="all, delete-orphan",
    )
    media_assets: Mapped[List["MediaAsset"]] = relationship(
        "MediaAsset",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, company_id={self.company_id}, status='{self.status}')>"
