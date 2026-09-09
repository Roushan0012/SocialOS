"""Task Comment Database Model."""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.user import User


class TaskComment(Base, TimestampMixin):
    """Comment entry on a team LMS task."""

    __tablename__ = "task_comments"

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="comments",
    )
    user: Mapped["User"] = relationship(
        "User",
    )

    def __repr__(self) -> str:
        return f"<TaskComment(id={self.id}, task_id={self.task_id}, user_id={self.user_id})>"
