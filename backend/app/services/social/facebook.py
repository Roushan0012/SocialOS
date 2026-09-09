"""Facebook Social Provider Adapter.

Supports Meta Graph API OAuth 2.0 flow, short-to-long-lived token exchange,
token refresh, and page/profile fetching.
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


class FacebookProvider(SocialProvider):
    """Facebook OAuth 2.0 adapter."""

    platform = Platform.FACEBOOK

    AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self) -> None:
        self.client_id = settings.FACEBOOK_CLIENT_ID or ""
        self.client_secret = settings.FACEBOOK_CLIENT_SECRET or ""
        self.redirect_uri = settings.FACEBOOK_REDIRECT_URI or ""
        self.scopes = settings.FACEBOOK_SCOPES

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
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": callback_uri,
            "code": code,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(self.TOKEN_URL, params=params)
            except Exception:
                raise SocialTokenExchangeError("Failed to communicate with Facebook token endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenExchangeError(
                f"Facebook token exchange failed with status {response.status_code}."
            )

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise SocialTokenExchangeError("Facebook token response did not contain an access_token.")

        expires_in = payload.get("expires_in", 3600 * 24 * 60)
        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=access_token,  # Facebook uses access_token as exchange token
            expires_in=expires_in,
            token_type=payload.get("token_type", "Bearer"),
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenResult:
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "fb_exchange_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(self.TOKEN_URL, params=params)
            except Exception:
                raise SocialTokenRefreshError("Failed to communicate with Facebook refresh endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenRefreshError(
                f"Facebook token refresh failed with status {response.status_code}."
            )

        payload = response.json()
        new_token = payload.get("access_token")
        if not new_token:
            raise SocialTokenRefreshError("Facebook refresh response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=new_token,
            refresh_token=new_token,
            expires_in=payload.get("expires_in", 3600 * 24 * 60),
            token_type=payload.get("token_type", "Bearer"),
        )

    async def get_account_identity(self, access_token: str) -> SocialAccountIdentity:
        params = {
            "fields": "id,name,picture.width(200)",
            "access_token": access_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(f"{self.GRAPH_BASE_URL}/me", params=params)
            except Exception:
                raise SocialAPIError("Failed to communicate with Facebook Graph API.") from None

        if response.status_code != 200:
            raise SocialAPIError(f"Facebook profile request failed with status {response.status_code}.")

        payload = response.json()
        account_id = str(payload.get("id"))
        account_name = payload.get("name", f"Facebook User {account_id}")

        avatar_url = None
        picture_obj = payload.get("picture", {})
        if isinstance(picture_obj, dict):
            data = picture_obj.get("data", {})
            if isinstance(data, dict):
                avatar_url = data.get("url")

        return SocialAccountIdentity(
            platform=self.platform,
            platform_account_id=account_id,
            account_name=account_name,
            profile_url=f"https://www.facebook.com/{account_id}" if account_id else None,
            avatar_url=avatar_url,
            metadata={},
        )
