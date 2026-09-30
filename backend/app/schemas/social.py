"""Pydantic Schemas for Social Accounts and OAuth flows.

Strict security guarantee: No schema exposes provider access tokens,
refresh tokens, or client secrets to the client.
"""
from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Platform, SocialAccountStatus


class SocialAccountRead(BaseModel):
    """Publicly safe representation of a connected social account.
    
    NEVER includes access_token, refresh_token, or cryptographic keys.
    """
    id: uuid.UUID
    company_id: uuid.UUID
    platform: Platform
    account_name: str
    platform_account_id: str
    status: SocialAccountStatus
    buffer_channel_id: Optional[str] = None
    buffer_organization_id: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_connected_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OAuthStartResponse(BaseModel):
    """Response returned when initiating an OAuth connection flow."""
    authorization_url: str = Field(..., description="External platform OAuth authorization redirect URL")
    state: str = Field(..., description="High-entropy CSRF state token bound to request")
    platform: Platform


class OAuthCallbackResponse(BaseModel):
    """Response returned upon successful OAuth callback completion."""
    message: str = "Social account connected successfully"
    account: SocialAccountRead


class TokenRefreshResponse(BaseModel):
    """Response returned upon successful manual or automated token refresh."""
    message: str = "Social account token refreshed successfully"
    account: SocialAccountRead


class BufferSyncRequest(BaseModel):
    """Request payload to trigger Buffer channel synchronization for an authorized company."""
    company_id: uuid.UUID = Field(..., description="Target brand company UUID")
    organization_id: Optional[str] = Field(None, description="Optional Buffer organization ID filter")


class SyncAccountSummaryItem(BaseModel):
    """Summary item for a single channel in synchronization results."""
    id: Optional[uuid.UUID] = None
    buffer_channel_id: str
    name: str
    platform: Optional[Platform] = None
    service: Optional[str] = None
    reason: Optional[str] = None
    error: Optional[str] = None


class BufferSyncResponse(BaseModel):
    """Response returned upon completion of Buffer channel synchronization."""
    message: str = "Buffer channels synchronized successfully"
    company_id: uuid.UUID
    created: list[SyncAccountSummaryItem] = Field(default_factory=list)
    updated: list[SyncAccountSummaryItem] = Field(default_factory=list)
    unchanged: list[SyncAccountSummaryItem] = Field(default_factory=list)
    skipped: list[SyncAccountSummaryItem] = Field(default_factory=list)
    errors: list[SyncAccountSummaryItem] = Field(default_factory=list)
    total_synced: int = 0
