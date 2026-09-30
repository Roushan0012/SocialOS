"""Buffer API GraphQL Client.

Handles secure communication with the Buffer GraphQL API (https://api.buffer.com).
Enforces:
- Isolation of Buffer API operations
- Strict credential masking (no API key in logs, exceptions, or string representations)
- Distinct authentication failure handling (HTTP 401 vs GraphQL / other HTTP errors)
- Configurable timeouts
- Strongly-typed Pydantic model outputs
- Read-only operations for connectivity verification
"""
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.services.buffer.exceptions import (
    BufferAPIError,
    BufferAuthError,
    BufferConnectionError,
    BufferGraphQLError,
    BufferMissingApiKeyError,
    BufferTimeoutError,
)
from app.services.buffer.schemas import (
    BufferAccount,
    BufferAccountOverview,
    BufferChannel,
    BufferOrganization,
    BufferOrganizationWithChannels,
)

logger = logging.getLogger(__name__)

GET_ORGANIZATIONS_QUERY = """
query GetOrganizations {
  account {
    id
    name
    email
    organizations {
      id
      name
    }
  }
}
""".strip()

GET_CHANNELS_QUERY = """
query GetChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    name
    service
    avatar
    isQueuePaused
  }
}
""".strip()

CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess {
      post {
        id
        status
        sharedNow
        sentAt
        createdAt
      }
    }
    ... on NotFoundError {
      message
    }
    ... on UnauthorizedError {
      message
    }
    ... on UnexpectedError {
      message
    }
    ... on LimitReachedError {
      message
    }
    ... on InvalidInputError {
      message
    }
  }
}
""".strip()


class BufferClient:
    """Client for interacting with Buffer's GraphQL API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        timeout: float = 15.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Initialize Buffer GraphQL API client.

        Args:
            api_key: Optional explicit API key. Falls back to settings.BUFFER_API_KEY.
            api_url: Optional explicit endpoint URL. Falls back to settings.BUFFER_API_URL.
            timeout: HTTP timeout in seconds (default: 15.0s).
            http_client: Optional pre-configured httpx.AsyncClient for dependency injection/testing.
        """
        raw_key = api_key if api_key is not None else settings.BUFFER_API_KEY
        self._api_key: Optional[str] = raw_key.strip() if raw_key else None
        raw_url = api_url if api_url is not None else settings.BUFFER_API_URL
        self._api_url: str = (raw_url or "https://api.buffer.com").rstrip("/")
        if isinstance(timeout, httpx.Timeout):
            self._timeout = timeout
            self._timeout_seconds = timeout.read or 15.0
        else:
            self._timeout_seconds = float(timeout)
            self._timeout = httpx.Timeout(
                timeout=self._timeout_seconds,
                connect=min(5.0, self._timeout_seconds),
                read=self._timeout_seconds,
                write=min(5.0, self._timeout_seconds),
                pool=min(5.0, self._timeout_seconds),
            )
        self._http_client: Optional[httpx.AsyncClient] = http_client

    @property
    def is_configured(self) -> bool:
        """Indicate whether an API key has been configured."""
        return bool(self._api_key)

    def __repr__(self) -> str:
        """Safe representation guaranteeing no credential exposure."""
        return f"<BufferClient(api_url='{self._api_url}', is_configured={self.is_configured})>"

    def __str__(self) -> str:
        """Safe string representation guaranteeing no credential exposure."""
        return self.__repr__()

    async def _execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a GraphQL query against Buffer API.

        Raises:
            BufferMissingApiKeyError: If BUFFER_API_KEY is not configured.
            BufferAuthError: If authentication fails (HTTP 401/403 or GraphQL auth error).
            BufferTimeoutError: If the HTTP request times out.
            BufferConnectionError: If network connection fails.
            BufferAPIError: If a non-200 HTTP response is returned.
            BufferGraphQLError: If GraphQL query returns errors.
        """
        if not self._api_key:
            raise BufferMissingApiKeyError(
                "BUFFER_API_KEY is not configured or is empty. Please set BUFFER_API_KEY in the environment."
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        logger.debug("Executing Buffer GraphQL operation: %s", operation_name or "unnamed")

        try:
            if self._http_client is not None:
                response = await self._http_client.post(
                    self._api_url,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        self._api_url,
                        json=payload,
                        headers=headers,
                        timeout=self._timeout,
                    )
        except httpx.TimeoutException:
            logger.warning("Buffer API request timed out after %s seconds", self._timeout_seconds)
            raise BufferTimeoutError(f"Buffer API request timed out after {self._timeout_seconds}s.") from None
        except httpx.RequestError as exc:
            logger.warning("Buffer API connection failed: %s", type(exc).__name__)
            raise BufferConnectionError(f"Buffer API connection failed: {type(exc).__name__}") from None

        # Check HTTP status codes
        if response.status_code == 401:
            logger.warning("Buffer API authentication failed: HTTP 401 Unauthorized")
            raise BufferAuthError(
                "Buffer authentication failed (HTTP 401 Unauthorized). Verify BUFFER_API_KEY.",
                status_code=401,
            )
        elif response.status_code == 403:
            logger.warning("Buffer API access forbidden: HTTP 403 Forbidden")
            raise BufferAuthError(
                "Buffer access forbidden (HTTP 403 Forbidden). Check account permissions.",
                status_code=403,
            )
        elif response.status_code >= 400:
            logger.warning("Buffer API HTTP error status %s", response.status_code)
            raise BufferAPIError(
                f"Buffer API request failed with HTTP {response.status_code}.",
                status_code=response.status_code,
                response_text=response.text[:500] if response.text else None,
            )

        # Parse JSON payload
        try:
            data = response.json()
        except Exception as exc:
            raise BufferAPIError(
                f"Failed to parse Buffer API JSON response: {type(exc).__name__}",
                status_code=response.status_code,
            ) from None

        # Process GraphQL errors
        errors = data.get("errors")
        if errors:
            messages = [e.get("message", "Unknown GraphQL error") for e in errors if isinstance(e, dict)]
            combined_msg = "; ".join(messages) if messages else "Buffer GraphQL returned errors"
            logger.warning("Buffer GraphQL error encountered: %s", combined_msg)

            lower_msg = combined_msg.lower()
            if any(term in lower_msg for term in ["unauthorized", "unauthenticated", "invalid token", "authentication required"]):
                raise BufferAuthError(
                    f"Buffer GraphQL authentication error: {combined_msg}",
                    status_code=401,
                )

            raise BufferGraphQLError(
                f"Buffer GraphQL error: {combined_msg}",
                errors=errors,
            )

        return data

    async def get_account_and_organizations(self) -> BufferAccount:
        """Fetch authenticated Buffer account details and associated organizations.

        Query:
            query GetOrganizations {
              account {
                id
                name
                email
                organizations {
                  id
                  name
                }
              }
            }

        Returns:
            BufferAccount: The authenticated account with its organizations.
        """
        response_json = await self._execute_query(
            query=GET_ORGANIZATIONS_QUERY,
            operation_name="GetOrganizations",
        )
        account_data = response_json.get("data", {}).get("account")
        if not account_data:
            raise BufferGraphQLError("Buffer GraphQL response did not contain 'account' data.")

        return BufferAccount.model_validate(account_data)

    async def get_channels(self, organization_id: str) -> List[BufferChannel]:
        """Fetch channels connected to a specific Buffer organization.

        Query:
            query GetChannels($organizationId: ID!) {
              channels(input: { organizationId: $organizationId }) {
                id
                name
                service
                avatar
                isQueuePaused
              }
            }

        Args:
            organization_id: Organization ID.

        Returns:
            List[BufferChannel]: Connected social channels.
        """
        if not organization_id or not str(organization_id).strip():
            raise ValueError("organization_id must be a non-empty string.")

        response_json = await self._execute_query(
            query=GET_CHANNELS_QUERY,
            variables={"organizationId": str(organization_id).strip()},
            operation_name="GetChannels",
        )
        channels_data = response_json.get("data", {}).get("channels")
        if channels_data is None:
            raise BufferGraphQLError("Buffer GraphQL response did not contain 'channels' data.")

        return [BufferChannel.model_validate(ch) for ch in channels_data]

    async def verify_connectivity(self) -> BufferAccountOverview:
        """Perform a complete read-only connectivity check against the Buffer API.

        Queries:
        1. Authenticated account and organizations via GetOrganizations.
        2. Connected channels for each organization via GetChannels.

        This method is strictly read-only and does not modify, create, schedule, or delete anything.

        Returns:
            BufferAccountOverview: Complete hierarchy of account, organizations, and channels.
        """
        account = await self.get_account_and_organizations()
        organizations_with_channels: List[BufferOrganizationWithChannels] = []

        for org in account.organizations:
            channels = await self.get_channels(org.id)
            organizations_with_channels.append(
                BufferOrganizationWithChannels(
                    organization=org,
                    channels=channels,
                )
            )

        return BufferAccountOverview(
            account=account,
            organizations_with_channels=organizations_with_channels,
        )

    async def create_post(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute createPost mutation on Buffer GraphQL API.

        Args:
            input_data: Dictionary conforming to Buffer's CreatePostInput schema.

        Returns:
            Dictionary containing the raw payload from the createPost mutation.

        Raises:
            BufferAPIError: If response data is empty or invalid.
        """
        response_json = await self._execute_query(
            query=CREATE_POST_MUTATION,
            variables={"input": input_data},
            operation_name="CreatePost",
        )
        data = response_json.get("data") or {}
        create_post_result = data.get("createPost")
        if not create_post_result:
            raise BufferAPIError("Buffer createPost mutation returned an empty result.")
        return create_post_result
