"""SocialOS Enumerations for Database Models.

Defines all supported enum types across SocialOS domain entities.
"""
import enum


class RoleName(str, enum.Enum):
    """Supported core system roles."""
    ADMIN = "ADMIN"
    SOCIAL_MEDIA_MANAGER = "SOCIAL_MEDIA_MANAGER"
    CONTENT_CREATOR = "CONTENT_CREATOR"
    GRAPHIC_DESIGNER = "GRAPHIC_DESIGNER"
    VIDEO_EDITOR = "VIDEO_EDITOR"


class Platform(str, enum.Enum):
    """Supported social publishing platforms."""
    INSTAGRAM = "INSTAGRAM"
    FACEBOOK = "FACEBOOK"
    LINKEDIN = "LINKEDIN"
    YOUTUBE = "YOUTUBE"


class SocialAccountStatus(str, enum.Enum):
    """Lifecycle status of a connected social media account."""
    ACTIVE = "ACTIVE"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class PostStatus(str, enum.Enum):
    """Publishing workflow status of a post."""
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PARTIALLY_PUBLISHED = "PARTIALLY_PUBLISHED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PostTargetStatus(str, enum.Enum):
    """Publishing dispatch status for an individual platform target channel."""
    PENDING = "PENDING"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class MediaType(str, enum.Enum):
    """Supported asset media types stored in AWS S3 and served via CloudFront."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    PDF = "PDF"
    OTHER = "OTHER"


class TaskPriority(str, enum.Enum):
    """Team task priority levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class TaskStatus(str, enum.Enum):
    """Team LMS task workflow status."""
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class AttendanceStatus(str, enum.Enum):
    """Daily employee attendance status."""
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"
