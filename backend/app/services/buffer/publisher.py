"""Buffer Publishing Adapter Service.

Handles immediate dispatch of PostTarget content to Buffer's GraphQL API.
Enforces channel mapping, media URL validation, safe exception mapping, and zero token leakage.
"""
import logging
from typing import Any, Dict, List, Optional

from app.models.enums import MediaType
from app.models.media_asset import MediaAsset
from app.models.post import Post
from app.models.post_target import PostTarget
from app.models.social_account import SocialAccount
from app.services.buffer.client import BufferClient
from app.services.buffer.exceptions import (
    BufferAPIError,
    BufferAuthError,
    BufferConnectionError,
    BufferError,
    BufferGraphQLError,
    BufferMissingApiKeyError,
    BufferTimeoutError,
)
from app.services.buffer.schemas import BufferPublishResult

logger = logging.getLogger(__name__)


class BufferPublisher:
    """Service adapter for executing publish mutations against the Buffer API."""

    def __init__(self, client: Optional[BufferClient] = None) -> None:
        """Initialize publisher with optional injected BufferClient."""
        self._client = client or BufferClient()

    @property
    def is_configured(self) -> bool:
        """Indicate whether the underlying Buffer client has an API key configured."""
        return self._client.is_configured

    async def publish_target(
        self,
        target: PostTarget,
        post: Post,
        account: SocialAccount,
        media_assets: Optional[List[MediaAsset]] = None,
    ) -> BufferPublishResult:
        """Publish a single PostTarget immediately via Buffer GraphQL API.

        Args:
            target: PostTarget entity to publish.
            post: Parent Post entity containing caption/text.
            account: Connected SocialAccount carrying buffer_channel_id.
            media_assets: Optional list of MediaAsset objects attached to the post.

        Returns:
            BufferPublishResult with success flag, buffer_post_id, or sanitized error_message.
        """
        if not self._client.is_configured:
            return BufferPublishResult(
                success=False,
                error_message="Buffer integration is not configured. BUFFER_API_KEY is not set.",
            )

        channel_id = account.buffer_channel_id
        if not channel_id or not channel_id.strip():
            return BufferPublishResult(
                success=False,
                error_message=f"Social account '{account.id}' ({account.account_name}) is not linked to a Buffer channel.",
            )

        # 1. Process media assets if present
        asset_inputs: List[Dict[str, Any]] = []
        assets_to_check = media_assets or []
        for asset in assets_to_check:
            if not asset.cdn_url or not asset.cdn_url.strip():
                return BufferPublishResult(
                    success=False,
                    error_message=(
                        f"Media asset '{asset.id}' ({asset.file_name}) has no public CDN URL. "
                        "Media upload/public URL distribution is not yet ready."
                    ),
                )
            if asset.media_type == MediaType.VIDEO:
                asset_inputs.append({"video": {"url": asset.cdn_url.strip()}})
            else:
                asset_inputs.append({"image": {"url": asset.cdn_url.strip()}})

        # 2. Build CreatePostInput conforming to Buffer's verified schema
        input_data: Dict[str, Any] = {
            "channelId": channel_id.strip(),
            "mode": "shareNow",
            "schedulingType": "automatic",
            "needsApproval": False,
            "text": post.caption or "",
            "assets": asset_inputs,
        }

        # 3. Execute mutation via Buffer client
        try:
            result = await self._client.create_post(input_data)
        except BufferMissingApiKeyError:
            return BufferPublishResult(
                success=False,
                error_message="Buffer integration is not configured. BUFFER_API_KEY is missing.",
            )
        except BufferAuthError:
            return BufferPublishResult(
                success=False,
                error_message="Buffer authentication failed. Check account credentials.",
            )
        except BufferTimeoutError:
            return BufferPublishResult(
                success=False,
                error_message="Buffer API request timed out during publish.",
            )
        except BufferConnectionError:
            return BufferPublishResult(
                success=False,
                error_message="Failed to connect to Buffer API during publish.",
            )
        except BufferGraphQLError as exc:
            return BufferPublishResult(
                success=False,
                error_message=f"Buffer GraphQL error: {exc.message}",
            )
        except BufferAPIError as exc:
            return BufferPublishResult(
                success=False,
                error_message=f"Buffer API request failed (HTTP {exc.status_code}).",
            )
        except Exception as exc:
            logger.exception("Unexpected error during Buffer publish")
            return BufferPublishResult(
                success=False,
                error_message=f"Unexpected error during Buffer publish: {type(exc).__name__}",
            )

        # 4. Parse response union payload
        typename = result.get("__typename")
        if typename == "PostActionSuccess":
            post_payload = result.get("post") or {}
            buffer_id = post_payload.get("id")
            buffer_status = post_payload.get("status")
            shared_now = post_payload.get("sharedNow", True)
            return BufferPublishResult(
                success=True,
                buffer_post_id=buffer_id,
                buffer_status=buffer_status,
                shared_now=shared_now,
            )

        # Handle union failure types (NotFoundError, UnauthorizedError, UnexpectedError, LimitReachedError, InvalidInputError, RestProxyError)
        error_msg = result.get("message")
        if not error_msg:
            error_msg = f"Buffer rejected post with {typename or 'unknown error'}."

        return BufferPublishResult(
            success=False,
            error_message=error_msg,
        )
