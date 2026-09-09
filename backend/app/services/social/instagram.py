"""Instagram Social Provider Adapter.

Supports Instagram Graph API / Basic Display OAuth flow, token exchange,
refresh, and profile fetching.
"""
from typing import Any, Dict, Optional
import urllib.parse
import httpx

from app.core.config import settings
from app.models.enums import Platform
from app.services.social.base import (
    OAuthTokenResult,
    SocialAccountIdentity,
    SocialAPIError,
    SocialAuthError,
    SocialProvider,
    SocialTokenExchangeError,
    SocialTokenRefreshError,
)


class InstagramProvider(SocialProvider):
    """Instagram OAuth 2.0 adapter."""

    platform = Platform.INSTAGRAM

    AUTH_URL = "https://api.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    GRAPH_BASE_URL = "https://graph.instagram.com"

    def __init__(self) -> None:
        self.client_id = settings.INSTAGRAM_CLIENT_ID or ""
        self.client_secret = settings.INSTAGRAM_CLIENT_SECRET or ""
        self.redirect_uri = settings.INSTAGRAM_REDIRECT_URI or ""
        self.scopes = settings.INSTAGRAM_SCOPES

    def get_authorization_url(self, state: str, redirect_uri: Optional[str] = None) -> str:
        callback_uri = redirect_uri or self.redirect_uri
        scopes = [s.strip() for s in self.scopes.split(",")] if isinstance(self.scopes, str) else list(self.scopes)
        params = {
            "client_id": self.client_id,
            "redirect_uri": callback_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: Optional[str] = None
    ) -> OAuthTokenResult:
        callback_uri = redirect_uri or self.redirect_uri
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": callback_uri,
            "code": code,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
            except Exception as exc:
                raise SocialTokenExchangeError("Failed to communicate with Instagram token endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenExchangeError(
                f"Instagram token exchange failed with status {response.status_code}."
            )

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise SocialTokenExchangeError("Instagram token response did not contain an access_token.")

        # Instagram returns short-lived token or long-lived token
        expires_in = payload.get("expires_in", 3600 * 24 * 60)  # default 60 days if long-lived
        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=payload.get("refresh_token") or access_token,  # Instagram uses access_token as refresh key
            expires_in=expires_in,
            token_type=payload.get("token_type", "Bearer"),
            raw_data={"user_id": payload.get("user_id")},
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenResult:
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(
                    f"{self.GRAPH_BASE_URL}/refresh_access_token",
                    params=params,
                )
            except Exception:
                raise SocialTokenRefreshError("Failed to communicate with Instagram refresh endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenRefreshError(
                f"Instagram token refresh failed with status {response.status_code}."
            )

        payload = response.json()
        new_token = payload.get("access_token")
        if not new_token:
            raise SocialTokenRefreshError("Instagram refresh response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=new_token,
            refresh_token=new_token,
            expires_in=payload.get("expires_in", 3600 * 24 * 60),
            token_type=payload.get("token_type", "Bearer"),
        )

    async def get_account_identity(self, access_token: str) -> SocialAccountIdentity:
        params = {
            "fields": "id,username,account_type",
            "access_token": access_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(f"{self.GRAPH_BASE_URL}/me", params=params)
            except Exception:
                raise SocialAPIError("Failed to communicate with Instagram Graph API.") from None

        if response.status_code != 200:
            raise SocialAPIError(f"Instagram profile request failed with status {response.status_code}.")

        payload = response.json()
        account_id = str(payload.get("id"))
        username = payload.get("username", f"instagram_user_{account_id}")

        return SocialAccountIdentity(
            platform=self.platform,
            platform_account_id=account_id,
            account_name=username,
            profile_url=f"https://www.instagram.com/{username}" if username else None,
            metadata={"account_type": payload.get("account_type")},
        )
