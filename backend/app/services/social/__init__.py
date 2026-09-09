"""Social Provider Adapters and Factory Registry."""
from typing import Dict, Type, Union

from app.models.enums import Platform
from app.services.social.base import (
    OAuthTokenResult,
    SocialAccountIdentity,
    SocialAPIError,
    SocialAuthError,
    SocialProvider,
    SocialProviderError,
    SocialTokenExchangeError,
    SocialTokenRefreshError,
)
from app.services.social.facebook import FacebookProvider
from app.services.social.instagram import InstagramProvider
from app.services.social.linkedin import LinkedInProvider
from app.services.social.youtube import YouTubeProvider

_PROVIDERS: Dict[Platform, Type[SocialProvider]] = {
    Platform.INSTAGRAM: InstagramProvider,
    Platform.FACEBOOK: FacebookProvider,
    Platform.LINKEDIN: LinkedInProvider,
    Platform.YOUTUBE: YouTubeProvider,
}


def get_social_provider(platform: Union[Platform, str]) -> SocialProvider:
    """Factory to retrieve the registered SocialProvider instance for a given platform."""
    if isinstance(platform, str):
        try:
            platform = Platform(platform.upper())
        except ValueError:
            raise ValueError(f"Unsupported social platform: {platform}")

    provider_cls = _PROVIDERS.get(platform)
    if not provider_cls:
        raise ValueError(f"No social provider adapter registered for platform: {platform.value}")

    return provider_cls()


__all__ = [
    "SocialProvider",
    "OAuthTokenResult",
    "SocialAccountIdentity",
    "SocialProviderError",
    "SocialAuthError",
    "SocialTokenExchangeError",
    "SocialTokenRefreshError",
    "SocialAPIError",
    "InstagramProvider",
    "FacebookProvider",
    "LinkedInProvider",
    "YouTubeProvider",
    "get_social_provider",
]
