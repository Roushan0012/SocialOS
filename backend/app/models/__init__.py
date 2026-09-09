"""SocialOS SQLAlchemy ORM Declarative Models.

Registers all 14 core domain entities with Base.metadata for Alembic migrations.
"""
from app.models.base import Base, TimestampMixin
from app.models.enums import (
    AttendanceStatus,
    MediaType,
    Platform,
    PostStatus,
    PostTargetStatus,
    RoleName,
    SocialAccountStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.role import Role
from app.models.user import User
from app.models.company import Company
from app.models.social_account import SocialAccount
from app.models.post import Post
from app.models.post_target import PostTarget
from app.models.media_asset import MediaAsset
from app.models.task import Task
from app.models.task_comment import TaskComment
from app.models.task_attachment import TaskAttachment
from app.models.attendance import Attendance
from app.models.notification import Notification
from app.models.activity_log import ActivityLog
from app.models.social_analytics import SocialAnalyticsDaily

__all__ = [
    "Base",
    "TimestampMixin",
    # Enums
    "RoleName",
    "Platform",
    "SocialAccountStatus",
    "PostStatus",
    "PostTargetStatus",
    "MediaType",
    "TaskPriority",
    "TaskStatus",
    "AttendanceStatus",
    # Models (14 tables)
    "Role",
    "User",
    "Company",
    "SocialAccount",
    "Post",
    "PostTarget",
    "MediaAsset",
    "Task",
    "TaskComment",
    "TaskAttachment",
    "Attendance",
    "Notification",
    "ActivityLog",
    "SocialAnalyticsDaily",
]
