"""OAuth State Manager.

Handles high-entropy cryptographic CSRF state generation, storage,
expiration (TTL), and single-use validation for OAuth flows.
"""
from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Platform
from app.models.oauth_state import OAuthState


class OAuthStateError(Exception):
    """Base exception for OAuth state validation errors."""
    pass


class InvalidOAuthStateError(OAuthStateError):
    """Raised when an OAuth state token is unknown, already consumed, or invalid."""
    pass


class ExpiredOAuthStateError(OAuthStateError):
    """Raised when an OAuth state token has exceeded its validity TTL."""
    pass


class OAuthStateManager:
    """Manages creation and single-use consumption of OAuth state tokens."""

    DEFAULT_TTL_MINUTES = 10

    @classmethod
    async def create_state(
        cls,
        db: AsyncSession,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        platform: Platform,
        ttl_minutes: int = DEFAULT_TTL_MINUTES,
    ) -> str:
        """Generate and persist a high-entropy OAuth state token bound to user, company, and platform."""
        token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl_minutes)

        oauth_state = OAuthState(
            state_token=token,
            user_id=user_id,
            company_id=company_id,
            platform=platform,
            expires_at=expires_at,
            used_at=None,
        )
        db.add(oauth_state)
        await db.commit()
        await db.refresh(oauth_state)
        return token

    @classmethod
    async def verify_and_consume_state(
        cls,
        db: AsyncSession,
        state_token: str,
        platform: Platform,
        expected_user_id: Optional[uuid.UUID] = None,
    ) -> OAuthState:
        """Validate an OAuth state token and mark it as consumed (single-use).
        
        Enforces:
        1. Token existence
        2. Platform match
        3. Single-use (not already used)
        4. Expiration check
        5. User match (if provided)
        """
        if not state_token or not state_token.strip():
            raise InvalidOAuthStateError("OAuth state parameter is missing or empty.")

        stmt = select(OAuthState).where(OAuthState.state_token == state_token.strip())
        result = await db.execute(stmt)
        oauth_state = result.scalar_one_or_none()

        if not oauth_state:
            raise InvalidOAuthStateError("Invalid or unknown OAuth state token.")

        if oauth_state.used_at is not None:
            raise InvalidOAuthStateError("OAuth state token has already been consumed.")

        now = datetime.now(timezone.utc)
        # Handle naive or timezone-aware datetimes safely
        expires_at = oauth_state.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            raise ExpiredOAuthStateError("OAuth state token has expired. Please initiate connection again.")

        if oauth_state.platform != platform:
            raise InvalidOAuthStateError(
                f"OAuth state platform mismatch: expected {platform.value}, got {oauth_state.platform.value}."
            )

        if expected_user_id and oauth_state.user_id != expected_user_id:
            raise InvalidOAuthStateError("OAuth state user mismatch: initiated by a different user session.")

        # Mark consumed atomically
        oauth_state.used_at = now
        await db.commit()
        await db.refresh(oauth_state)

        return oauth_state
