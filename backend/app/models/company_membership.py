"""Company Membership Database Model."""
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class CompanyMembership(Base, TimestampMixin):
    """Associates users with companies (brands) they are authorized to access.

    Access Control Architecture:
    - User's system role (users.role_id) dictates WHAT permissions they possess (e.g. ADMIN, CONTENT_CREATOR).
    - Company memberships dictate WHICH companies/brands they are permitted to access.
    - System ADMINs bypass membership checks and have access to all companies.
    - Non-admin users are strictly isolated to companies where an active membership exists.
    """

    __tablename__ = "company_memberships"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", name="uq_company_memberships_company_user"),
    )

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    company: Mapped["Company"] = relationship(
        "Company",
        back_populates="memberships",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="company_memberships",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<CompanyMembership(id={self.id}, company_id={self.company_id}, user_id={self.user_id})>"
