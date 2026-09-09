"""Role Database Model."""
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base, TimestampMixin):
    """Role definition entity for Role-Based Access Control (RBAC).

    Supported initial roles:
    - ADMIN
    - SOCIAL_MEDIA_MANAGER
    - CONTENT_CREATOR
    - GRAPHIC_DESIGNER
    - VIDEO_EDITOR
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="role",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"
