"""Abstract Social Provider Base Class and Data Models.

Defines the contract for external social platform OAuth adapters
(Instagram, Facebook, LinkedIn, YouTube).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import urllib.parse

from app.models.enums import Platform


class SocialProviderError(Exception):
    """Base exception for all social provider operations."""
    pass


class SocialAuthError(SocialProviderError):
    """Raised when authorization or client configuration is invalid."""
    pass


class SocialTokenExchangeError(SocialProviderError):
    """Raised when authorization code exchange fails."""
    pass


class SocialTokenRefreshError(SocialProviderError):
    """Raised when token refresh fails."""
    pass


class SocialAPIError(SocialProviderError):
    """Raised when remote platform API requests fail."""
    pass


@dataclass
class OAuthTokenResult:
    """Normalized result of an OAuth code exchange or token refresh operation."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: Optional[str] = "Bearer"
    scope: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class SocialAccountIdentity:
    """Normalized account profile data retrieved from the social platform."""
    platform: Platform
    platform_account_id: str
    account_name: str
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


class SocialProvider(ABC):
    """Abstract Base Class for social platform OAuth adapters."""

    platform: Platform

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: Optional[str] = None) -> str:
        """Construct the external platform's OAuth authorization redirect URL."""
        pass

    @abstractmethod
    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: Optional[str] = None
    ) -> OAuthTokenResult:
        """Exchange the received OAuth authorization code for access and refresh tokens."""
        pass

    @abstractmethod
    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenResult:
        """Refresh expired access tokens using a long-lived or refresh token."""
        pass

    @abstractmethod
    async def get_account_identity(self, access_token: str) -> SocialAccountIdentity:
        """Fetch normalized identity and profile metadata using a valid access token."""
        pass
