"""User Database Model."""
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.post import Post
    from app.models.task import Task
    from app.models.attendance import Attendance
    from app.models.notification import Notification
    from app.models.activity_log import ActivityLog
    from app.models.auth_session import AuthSession
    from app.models.company_membership import CompanyMembership


class User(Base, TimestampMixin):
    """User account entity.

    Holds user credentials (securely hashed), profile identity, and role assignment.
    Plaintext passwords must NEVER be stored in this table.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="users",
        lazy="joined",
    )
    created_posts: Mapped[List["Post"]] = relationship(
        "Post",
        back_populates="creator",
        foreign_keys="Post.created_by",
    )
    assigned_tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="assignee",
        foreign_keys="Task.assigned_to",
    )
    created_tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="creator",
        foreign_keys="Task.created_by",
    )
    attendance_records: Mapped[List["Attendance"]] = relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    activity_logs: Mapped[List["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="user",
    )
    auth_sessions: Mapped[List["AuthSession"]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    company_memberships: Mapped[List["CompanyMembership"]] = relationship(
        "CompanyMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role_id={self.role_id})>"
