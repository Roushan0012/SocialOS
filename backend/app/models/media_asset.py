"""Media Asset Database Model."""
import uuid
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
    Enum as SAEnum,
    ForeignKey,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import MediaType

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class MediaAsset(Base, TimestampMixin):
    """Media asset metadata entity.

    STRICT STORAGE ARCHITECTURE:
    - Production storage is AWS S3 (private bucket) with delivery via Amazon CloudFront.
    - Local development storage is MinIO (offline S3 API parity).
    - PostgreSQL strictly stores metadata, pointers, and CDN URLs.
    - Binary blobs are NEVER stored in PostgreSQL or Supabase Storage.
    """

    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    post_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    cdn_url: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    media_type: Mapped[MediaType] = mapped_column(
        SAEnum(MediaType, name="media_type_enum", native_enum=True),
        nullable=False,
    )

    # Relationships
    post: Mapped[Optional["Post"]] = relationship(
        "Post",
        back_populates="media_assets",
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
    )

    def __repr__(self) -> str:
        return f"<MediaAsset(id={self.id}, file_name='{self.file_name}', media_type='{self.media_type}')>"
