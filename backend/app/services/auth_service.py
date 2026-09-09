"""Authentication & Session Business Logic Service Layer."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.models.activity_log import ActivityLog
from app.models.auth_session import AuthSession
from app.models.user import User

# Dummy hash for constant-time comparison when email is not found
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=2,p=1$c29tZXNhbHQ$5eC10qP7j4q7W4K8o5u4+A"


class AuthService:
    """Handles credential authentication, refresh token rotation, session lifecycle, and audit logging."""

    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate user credentials using constant-time password verification.

        Returns:
            User instance if credentials match, None otherwise.
        """
        normalized_email = email.strip().lower()
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.email == normalized_email)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            # Perform dummy verify to mitigate timing attacks
            verify_password(password, _DUMMY_HASH)
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    @staticmethod
    async def create_user_session(
        db: AsyncSession,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Issue access token and persist a cryptographically hashed refresh token session.

        Returns:
            Tuple[access_token, raw_refresh_token]
        """
        role_name = user.role.name if user.role else "CONTENT_CREATOR"
        access_token = create_access_token(user_id=user.id, role=role_name)

        raw_refresh_token = generate_refresh_token()
        token_hash = hash_refresh_token(raw_refresh_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        session = AuthSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
        )
        db.add(session)

        # Audit log entry (sanitized metadata, zero passwords/tokens)
        audit_log = ActivityLog(
            user_id=user.id,
            action="USER_LOGIN",
            entity_type="auth_session",
            entity_id=session.id,
            log_metadata={
                "ip_address": ip_address,
                "user_agent": user_agent[:255] if user_agent else None,
            },
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(session)

        return access_token, raw_refresh_token

    @staticmethod
    async def rotate_refresh_session(
        db: AsyncSession,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str, User]:
        """Validate an existing refresh token, revoke it, and issue a rotated session.

        Raises:
            ValueError: If token is invalid, expired, revoked, or user inactive.
        Returns:
            Tuple[new_access_token, new_raw_refresh_token, user]
        """
        token_hash = hash_refresh_token(raw_refresh_token)
        now = datetime.now(timezone.utc)

        stmt = (
            select(AuthSession)
            .options(joinedload(AuthSession.user).joinedload(User.role))
            .where(AuthSession.token_hash == token_hash)
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError("Invalid or expired refresh token")

        if session.revoked_at is not None:
            # Token reuse detected: session already revoked
            raise ValueError("Refresh token has been revoked")

        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            raise ValueError("Refresh token has expired")

        user = session.user
        if not user or not user.is_active:
            raise ValueError("User account is deactivated")

        # 1. Revoke the presented token
        session.revoked_at = now

        # 2. Issue rotated credentials
        role_name = user.role.name if user.role else "CONTENT_CREATOR"
        new_access_token = create_access_token(user_id=user.id, role=role_name)
        new_raw_refresh = generate_refresh_token()
        new_hash = hash_refresh_token(new_raw_refresh)
        new_expires_at = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        new_session = AuthSession(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=new_expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:255] if user_agent else None,
        )
        db.add(new_session)

        # Audit log entry
        audit_log = ActivityLog(
            user_id=user.id,
            action="TOKEN_REFRESH",
            entity_type="auth_session",
            entity_id=new_session.id,
            log_metadata={"previous_session_id": str(session.id)},
        )
        db.add(audit_log)

        await db.commit()
        return new_access_token, new_raw_refresh, user

    @staticmethod
    async def revoke_session(
        db: AsyncSession,
        raw_refresh_token: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Revoke a refresh session by raw token or revoke user sessions upon logout."""
        now = datetime.now(timezone.utc)
        revoked_any = False

        if raw_refresh_token:
            token_hash = hash_refresh_token(raw_refresh_token)
            stmt = select(AuthSession).where(AuthSession.token_hash == token_hash)
            result = await db.execute(stmt)
            session = result.scalar_one_or_none()
            if session and session.revoked_at is None:
                session.revoked_at = now
                revoked_any = True
                if not user_id:
                    user_id = session.user_id

        if user_id:
            audit_log = ActivityLog(
                user_id=user_id,
                action="USER_LOGOUT",
                entity_type="auth_session",
            )
            db.add(audit_log)

        await db.commit()
        return revoked_any
