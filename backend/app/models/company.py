"""Company (Brand) Database Model."""
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.social_account import SocialAccount
    from app.models.post import Post
    from app.models.task import Task
    from app.models.company_membership import CompanyMembership


class Company(Base, TimestampMixin):
    """Company (Brand) entity for multi-tenancy and workspace segmentation.

    The database model uses 'companies' consistently across all layers,
    while the frontend UI presents this concept as 'Brands'.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    logo_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    social_accounts: Mapped[List["SocialAccount"]] = relationship(
        "SocialAccount",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    posts: Mapped[List["Post"]] = relationship(
        "Post",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    memberships: Mapped[List["CompanyMembership"]] = relationship(
        "CompanyMembership",
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name='{self.name}', slug='{self.slug}')>"
