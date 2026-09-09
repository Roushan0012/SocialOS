"""Attendance Database Model."""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import AttendanceStatus

if TYPE_CHECKING:
    from app.models.user import User


class Attendance(Base, TimestampMixin):
    """Daily employee attendance entity.

    Tracks clock-in, clock-out timestamps, and attendance status per team member.
    Enforces strictly one attendance entry per user per date.
    """

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "date",
            name="uq_attendance_user_date",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    check_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendance_status_enum", native_enum=True),
        default=AttendanceStatus.PRESENT,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="attendance_records",
    )

    def __repr__(self) -> str:
        return f"<Attendance(id={self.id}, user_id={self.user_id}, date={self.date}, status='{self.status}')>"
