"""Pydantic schemas for Post creation and management.

Strict security guarantee: No schema exposes provider access tokens,
refresh tokens, encrypted credentials, or external API keys.
"""
from datetime import datetime
from typing import Any, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Platform, PostStatus, PostTargetStatus


class PostTargetRead(BaseModel):
    """Publicly safe representation of an individual platform target channel."""
    id: uuid.UUID
    social_account_id: uuid.UUID
    platform: Platform
    account_name: str
    status: PostTargetStatus
    provider_post_id: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostCreateRequest(BaseModel):
    """Payload for creating a new post with platform targets."""
    company_id: uuid.UUID = Field(..., description="Target brand company UUID")
    caption: Optional[str] = Field(None, max_length=5000, description="Post text caption")
    social_account_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Target social account UUIDs to publish to",
    )
    scheduled_at: Optional[datetime] = Field(
        None,
        description="Optional scheduled publish time (stored metadata only)",
    )

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Allow flexible aliases for target social account IDs."""
        if isinstance(data, dict):
            # Support target_social_account_ids, target_account_ids, or targets
            if "target_social_account_ids" in data and "social_account_ids" not in data:
                data["social_account_ids"] = data["target_social_account_ids"]
            elif "target_account_ids" in data and "social_account_ids" not in data:
                data["social_account_ids"] = data["target_account_ids"]
            elif "targets" in data and "social_account_ids" not in data:
                data["social_account_ids"] = data["targets"]
        return data


class PostCreateResponse(BaseModel):
    """Response returned upon successful post creation."""
    id: uuid.UUID
    company_id: uuid.UUID
    caption: Optional[str] = None
    status: PostStatus
    scheduled_at: Optional[datetime] = None
    created_at: datetime
    targets: List[PostTargetRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
