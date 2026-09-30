"""Buffer API client exceptions.

Strict security guarantee:
Exception messages and attributes NEVER include raw API keys, Authorization headers,
or sensitive credentials.
"""
from typing import Any, Dict, List, Optional


class BufferError(Exception):
    """Base exception for all Buffer API client errors."""
    pass


class BufferMissingApiKeyError(BufferError):
    """Raised when BUFFER_API_KEY is missing, empty, or not configured."""
    pass


class BufferAuthError(BufferError):
    """Raised when Buffer API authentication fails (HTTP 401 Unauthorized or auth failure)."""

    def __init__(
        self,
        message: str = "Buffer authentication failed (HTTP 401 Unauthorized). Verify BUFFER_API_KEY.",
        status_code: int = 401,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class BufferAPIError(BufferError):
    """Raised when Buffer API returns an HTTP error (4xx or 5xx other than 401)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class BufferGraphQLError(BufferError):
    """Raised when Buffer GraphQL endpoint returns GraphQL errors in response body."""

    def __init__(
        self,
        message: str,
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        self.errors = errors or []


class BufferTimeoutError(BufferError):
    """Raised when Buffer API request times out."""
    pass


class BufferConnectionError(BufferError):
    """Raised when network connection to Buffer API fails."""
    pass
