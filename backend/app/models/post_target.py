"""Post Target Channel Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Platform, PostTargetStatus

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.social_account import SocialAccount


class PostTarget(Base, TimestampMixin):
    """Target social channel destination for a post dispatch.

    CRITICAL BRAND ISOLATION INVARIANT:
    A post belongs to one company (Brand).
    A selected social_account MUST belong to the EXACT same company as the post.
    Cross-company posting is strictly forbidden and must be prevented
    at the model and service layer.
    """

    __tablename__ = "post_targets"
    __table_args__ = (
        UniqueConstraint(
            "post_id",
            "social_account_id",
            name="uq_post_targets_post_social_account",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    social_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("social_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform, name="platform_enum", native_enum=True),
        nullable=False,
    )
    status: Mapped[PostTargetStatus] = mapped_column(
        SAEnum(PostTargetStatus, name="post_target_status_enum", native_enum=True),
        default=PostTargetStatus.PENDING,
        nullable=False,
    )
    provider_post_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="targets",
    )
    social_account: Mapped["SocialAccount"] = relationship(
        "SocialAccount",
        back_populates="post_targets",
    )

    @staticmethod
    def validate_brand_isolation(post_company_id: uuid.UUID, account_company_id: uuid.UUID) -> None:
        """Validate that the post and social account belong to the same company.

        Raises:
            ValueError: If post_company_id does not equal account_company_id.
        """
        if post_company_id != account_company_id:
            raise ValueError(
                f"Brand isolation violation: Post company '{post_company_id}' does not match "
                f"SocialAccount company '{account_company_id}'. Cross-company target dispatch is forbidden."
            )

    def __repr__(self) -> str:
        return f"<PostTarget(id={self.id}, post_id={self.post_id}, platform='{self.platform}', status='{self.status}')>"
