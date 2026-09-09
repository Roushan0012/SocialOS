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
