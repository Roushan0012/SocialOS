"""Task Attachment Database Model."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskAttachment(Base):
    """Attachment file metadata for a team task.

    STORAGE ARCHITECTURE:
    - Production storage is AWS S3 with delivery via CloudFront.
    - Local development storage is MinIO.
    - PostgreSQL stores file metadata only.
    """

    __tablename__ = "task_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="attachments",
    )
    uploader: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )

    def __repr__(self) -> str:
        return f"<TaskAttachment(id={self.id}, task_id={self.task_id}, file_name='{self.file_name}')>"
