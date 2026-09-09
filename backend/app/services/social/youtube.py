"""YouTube (Google OAuth 2.0) Social Provider Adapter.

Supports Google OAuth 2.0 flow with offline access (refresh tokens),
token exchange, refresh, and YouTube Data API v3 channel identity retrieval.
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


class YouTubeProvider(SocialProvider):
    """YouTube OAuth 2.0 adapter."""

    platform = Platform.YOUTUBE

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self) -> None:
        self.client_id = settings.YOUTUBE_CLIENT_ID or ""
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET or ""
        self.redirect_uri = settings.YOUTUBE_REDIRECT_URI or ""
        self.scopes = settings.YOUTUBE_SCOPES

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
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"

    async def exchange_code_for_tokens(
        self, code: str, redirect_uri: Optional[str] = None
    ) -> OAuthTokenResult:
        callback_uri = redirect_uri or self.redirect_uri
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": callback_uri,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
            except Exception:
                raise SocialTokenExchangeError("Failed to communicate with Google token endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenExchangeError(
                f"Google token exchange failed with status {response.status_code}."
            )

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise SocialTokenExchangeError("Google token response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_in=payload.get("expires_in", 3600),
            token_type=payload.get("token_type", "Bearer"),
            scope=payload.get("scope"),
        )

    async def refresh_tokens(self, refresh_token: str) -> OAuthTokenResult:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data)
            except Exception:
                raise SocialTokenRefreshError("Failed to communicate with Google refresh endpoint.") from None

        if response.status_code != 200:
            raise SocialTokenRefreshError(
                f"Google token refresh failed with status {response.status_code}."
            )

        payload = response.json()
        new_token = payload.get("access_token")
        if not new_token:
            raise SocialTokenRefreshError("Google refresh response did not contain an access_token.")

        return OAuthTokenResult(
            access_token=new_token,
            refresh_token=payload.get("refresh_token") or refresh_token,
            expires_in=payload.get("expires_in", 3600),
            token_type=payload.get("token_type", "Bearer"),
        )

    async def get_account_identity(self, access_token: str) -> SocialAccountIdentity:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"part": "snippet", "mine": "true"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(self.CHANNELS_URL, headers=headers, params=params)
            except Exception:
                raise SocialAPIError("Failed to communicate with YouTube API.") from None

            if response.status_code == 200:
                payload = response.json()
                items = payload.get("items", [])
                if items:
                    channel = items[0]
                    channel_id = str(channel.get("id"))
                    snippet = channel.get("snippet", {})
                    title = snippet.get("title", f"YouTube Channel {channel_id}")
                    custom_url = snippet.get("customUrl")
                    thumbnails = snippet.get("thumbnails", {})
                    avatar = thumbnails.get("default", {}).get("url")

                    profile_url = f"https://www.youtube.com/{custom_url}" if custom_url else f"https://www.youtube.com/channel/{channel_id}"
                    return SocialAccountIdentity(
                        platform=self.platform,
                        platform_account_id=channel_id,
                        account_name=title,
                        profile_url=profile_url,
                        avatar_url=avatar,
                        metadata={"custom_url": custom_url},
                    )

            # Fallback to Google userinfo if no channel exists
            try:
                userinfo_resp = await client.get(self.USERINFO_URL, headers=headers)
                if userinfo_resp.status_code == 200:
                    info = userinfo_resp.json()
                    sub = str(info.get("sub"))
                    name = info.get("name", f"Google User {sub}")
                    return SocialAccountIdentity(
                        platform=self.platform,
                        platform_account_id=sub,
                        account_name=name,
                        avatar_url=info.get("picture"),
                        metadata={"email": info.get("email")},
                    )
            except Exception:
                pass

        raise SocialAPIError("Could not retrieve YouTube channel or Google account identity.")
