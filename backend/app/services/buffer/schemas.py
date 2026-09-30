"""Pydantic data models for Buffer API GraphQL responses.

Guarantees type-safety and isolates Buffer data structures.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BufferOrganization(BaseModel):
    """Buffer organization data model."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str


class BufferAccount(BaseModel):
    """Buffer account data model with affiliated organizations."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    organizations: List[BufferOrganization] = Field(default_factory=list)


class BufferChannel(BaseModel):
    """Buffer connected social channel data model."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    name: str
    service: str
    avatar: Optional[str] = None
    is_queue_paused: bool = Field(default=False, alias="isQueuePaused")


class BufferOrganizationWithChannels(BaseModel):
    """Buffer organization associated with its retrieved channels."""

    model_config = ConfigDict(extra="ignore")

    organization: BufferOrganization
    channels: List[BufferChannel] = Field(default_factory=list)


class BufferAccountOverview(BaseModel):
    """Comprehensive read-only overview of authenticated account, organizations, and channels."""

    model_config = ConfigDict(extra="ignore")

    account: BufferAccount
    organizations_with_channels: List[BufferOrganizationWithChannels] = Field(default_factory=list)


class BufferPostItem(BaseModel):
    """Buffer post item returned upon creation/publishing."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    status: Optional[str] = None
    shared_now: bool = Field(default=False, alias="sharedNow")
    sent_at: Optional[str] = Field(default=None, alias="sentAt")
    created_at: Optional[str] = Field(default=None, alias="createdAt")


class BufferPublishResult(BaseModel):
    """Typed outcome of a Buffer target channel publish operation."""

    model_config = ConfigDict(extra="ignore")

    success: bool
    buffer_post_id: Optional[str] = None
    buffer_status: Optional[str] = None
    shared_now: bool = False
    error_message: Optional[str] = None
