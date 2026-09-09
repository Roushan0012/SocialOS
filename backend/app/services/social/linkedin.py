"""LinkedIn Social Provider Adapter.

Supports LinkedIn OAuth 2.0 (OpenID Connect / Sign In with LinkedIn v2),
token exchange, refresh, and profile fetching.
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


class LinkedInProvider(SocialProvider):
    """LinkedIn OAuth 2.0 adapter."""

    platform = Platform.LINKEDIN

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

    def __init__(self) -> None:
        self.client_id = settings.LINKEDIN_CLIENT_ID or ""
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET or ""
        self.redirect_uri = settings.LINKEDIN_REDIRECT_URI or ""
        self.scopes = settings.LINKEDIN_SCOPES

    def get_authorization_url(self, state: str, redirect_uri: Optional[str] = None) -> str:
        callback_uri = redirect_uri or self.redirect_uri
        if isinstance(self.scopes, str):
            scopes = [s.strip() for s in (self.scopes.split(",") if "," in self.scopes else self.scopes.split()) if s.strip()]
        else:
            scopes = list(self.scopes)
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": callback_uri,
            "state": state,
            "scope": " ".join(scopes),
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: Optional[str] = None
    ) -> OAuthTokenResult:
        callback_uri = redirect_uri or self.redirect_uri
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
            except Exception:
                raise SocialTokenExchangeError("Failed to communicate with LinkedIn token endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenExchangeError(
                f"LinkedIn token exchange failed with status {response.status_code}."
            )

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise SocialTokenExchangeError("LinkedIn token response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_in=payload.get("expires_in", 3600 * 24 * 60),
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenResult:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
            except Exception:
                raise SocialTokenRefreshError("Failed to communicate with LinkedIn refresh endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenRefreshError(
                f"LinkedIn token refresh failed with status {response.status_code}."
            )

        payload = response.json()
        new_token = payload.get("access_token")
        if not new_token:
            raise SocialTokenRefreshError("LinkedIn refresh response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=new_token,
            refresh_token=payload.get("refresh_token") or refresh_token,
            expires_in=payload.get("expires_in", 3600 * 24 * 60),
            token_type=payload.get("token_type", "Bearer"),
        )

    async def get_account_identity(self, access_token: str) -> SocialAccountIdentity:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(self.USERINFO_URL, headers=headers)
            except Exception:
                raise SocialAPIError("Failed to communicate with LinkedIn userinfo endpoint.") from None

        if response.status_code != 200:
            raise SocialAPIError(f"LinkedIn userinfo request failed with status {response.status_code}.")

        payload = response.json()
        sub = str(payload.get("sub"))
        name = payload.get("name") or f"{payload.get('given_name', '')} {payload.get('family_name', '')}".strip()
        if not name:
            name = f"LinkedIn User {sub}"

        return SocialAccountIdentity(
            platform=self.platform,
            platform_account_id=sub,
            account_name=name,
            avatar_url=payload.get("picture"),
            metadata={"email": payload.get("email")},
        )
