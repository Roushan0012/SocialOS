"""Social Account Service Layer.

Orchestrates social OAuth initiation, callback handling, token encryption at rest,
company isolation, account listing, manual/automatic token refresh, and audit logging.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.enums import Platform, SocialAccountStatus
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.company_service import CompanyService
from app.services.encryption_service import decrypt_token, encrypt_token
from app.services.oauth_state_manager import (
    ExpiredOAuthStateError,
    InvalidOAuthStateError,
    OAuthStateManager,
)
from app.services.social import (
    SocialAPIError,
    SocialAuthError,
    SocialProviderError,
    SocialTokenExchangeError,
    SocialTokenRefreshError,
    get_social_provider,
)


class SocialAccountService:
    """Service layer for social accounts, OAuth connections, and company-scoped isolation."""

    @staticmethod
    async def start_oauth_connection(
        db: AsyncSession,
        current_user: User,
        company_id: uuid.UUID,
        platform: Platform,
        redirect_uri: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Validate company authorization and generate an external OAuth authorization URL with CSRF state."""
        # 1. Enforce strict company access control
        company = await CompanyService.get_authorized_company(db, company_id, current_user)

        # 2. Generate high-entropy single-use CSRF state token bound to user, company, and platform
        state_token = await OAuthStateManager.create_state(
            db=db,
            user_id=current_user.id,
            company_id=company.id,
            platform=platform,
            ttl_minutes=10,
        )

        # 3. Retrieve platform adapter and construct authorization URL
        provider = get_social_provider(platform)
        authorization_url = provider.get_authorization_url(state=state_token, redirect_uri=redirect_uri)

        # 4. Audit logging
        db.add(
            ActivityLog(
                user_id=current_user.id,
                action="OAUTH_CONNECTION_STARTED",
                entity_type="social_account",
                entity_id=None,
                log_metadata={
                    "company_id": str(company.id),
                    "platform": platform.value,
                },
            )
        )
        await db.commit()

        return authorization_url, state_token

    @staticmethod
    async def handle_oauth_callback(
        db: AsyncSession,
        platform: Platform,
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> SocialAccount:
        """Verify CSRF state, exchange authorization code, fetch account identity, and upsert encrypted credentials."""
        # 1. Verify and consume state (enforces single-use and expiration)
        try:
            expected_user_id = current_user.id if current_user else None
            oauth_state = await OAuthStateManager.verify_and_consume_state(
                db=db,
                state_token=state,
                platform=platform,
                expected_user_id=expected_user_id,
            )
        except InvalidOAuthStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        except ExpiredOAuthStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        # 2. Exchange code for tokens via platform adapter
        provider = get_social_provider(platform)
        try:
            token_result = await provider.exchange_code_for_tokens(code=code, redirect_uri=redirect_uri)
        except SocialTokenExchangeError as exc:
            # Audit failure
            db.add(
                ActivityLog(
                    user_id=oauth_state.user_id,
                    action="OAUTH_CONNECTION_FAILED",
                    entity_type="social_account",
                    entity_id=None,
                    log_metadata={
                        "company_id": str(oauth_state.company_id),
                        "platform": platform.value,
                        "stage": "token_exchange",
                    },
                )
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange authorization code with {platform.value}.",
            )

        # 3. Retrieve account identity from platform
        try:
            identity = await provider.get_account_identity(access_token=token_result.access_token)
        except SocialAPIError as exc:
            db.add(
                ActivityLog(
                    user_id=oauth_state.user_id,
                    action="OAUTH_CONNECTION_FAILED",
                    entity_type="social_account",
                    entity_id=None,
                    log_metadata={
                        "company_id": str(oauth_state.company_id),
                        "platform": platform.value,
                        "stage": "identity_retrieval",
                    },
                )
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to retrieve account profile from {platform.value}.",
            )

        # 4. Encrypt sensitive tokens using AES-256-GCM before database write
        encrypted_access = encrypt_token(token_result.access_token)
        encrypted_refresh = encrypt_token(token_result.refresh_token) if token_result.refresh_token else None

        token_expires_at = None
        if token_result.expires_in:
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_result.expires_in)

        # 5. Upsert social_account record bound to company_id
        now = datetime.now(timezone.utc)
        stmt = select(SocialAccount).where(
            SocialAccount.company_id == oauth_state.company_id,
            SocialAccount.platform == platform,
            SocialAccount.platform_account_id == identity.platform_account_id,
        )
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if account:
            account.account_name = identity.account_name
            account.encrypted_access_token = encrypted_access
            account.encrypted_refresh_token = encrypted_refresh or account.encrypted_refresh_token
            account.token_expires_at = token_expires_at
            account.status = SocialAccountStatus.ACTIVE
            account.last_connected_at = now
        else:
            account = SocialAccount(
                company_id=oauth_state.company_id,
                platform=platform,
                account_name=identity.account_name,
                platform_account_id=identity.platform_account_id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                token_expires_at=token_expires_at,
                status=SocialAccountStatus.ACTIVE,
                last_connected_at=now,
            )
            db.add(account)

        await db.commit()
        await db.refresh(account)

        # 6. Audit log successful connection
        db.add(
            ActivityLog(
                user_id=oauth_state.user_id,
                action="SOCIAL_ACCOUNT_CONNECTED",
                entity_type="social_account",
                entity_id=account.id,
                log_metadata={
                    "company_id": str(oauth_state.company_id),
                    "platform": platform.value,
                    "account_name": identity.account_name,
                    "platform_account_id": identity.platform_account_id,
                },
            )
        )
        await db.commit()

        return account

    @staticmethod
    async def list_social_accounts(
        db: AsyncSession,
        current_user: User,
        company_id: uuid.UUID,
    ) -> List[SocialAccount]:
        """List all connected social accounts for an authorized company with zero token exposure."""
        # Enforce company isolation
        await CompanyService.get_authorized_company(db, company_id, current_user)

        stmt = (
            select(SocialAccount)
            .where(SocialAccount.company_id == company_id)
            .order_by(SocialAccount.platform.asc(), SocialAccount.account_name.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def disconnect_social_account(
        db: AsyncSession,
        current_user: User,
        social_account_id: uuid.UUID,
    ) -> SocialAccount:
        """Disconnect a social account, clearing stored access and refresh tokens."""
        stmt = select(SocialAccount).where(SocialAccount.id == social_account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Social account not found",
            )

        # Enforce company authorization
        await CompanyService.get_authorized_company(db, account.company_id, current_user)

        # Clear credentials and update status
        account.status = SocialAccountStatus.DISCONNECTED
        account.encrypted_access_token = None
        account.encrypted_refresh_token = None
        account.token_expires_at = None

        await db.commit()
        await db.refresh(account)

        # Audit log disconnection
        db.add(
            ActivityLog(
                user_id=current_user.id,
                action="SOCIAL_ACCOUNT_DISCONNECTED",
                entity_type="social_account",
                entity_id=account.id,
                log_metadata={
                    "company_id": str(account.company_id),
                    "platform": account.platform.value,
                    "account_name": account.account_name,
                },
            )
        )
        await db.commit()

        return account

    @staticmethod
    async def refresh_social_account_tokens(
        db: AsyncSession,
        current_user: User,
        social_account_id: uuid.UUID,
    ) -> SocialAccount:
        """Decrypt existing refresh token, exchange with platform for new tokens, and re-encrypt at rest."""
        stmt = select(SocialAccount).where(SocialAccount.id == social_account_id)
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Social account not found",
            )

        # Enforce company authorization
        await CompanyService.get_authorized_company(db, account.company_id, current_user)

        token_to_refresh = account.encrypted_refresh_token or account.encrypted_access_token
        if not token_to_refresh:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Social account has no valid credentials to refresh.",
            )

        try:
            raw_token = decrypt_token(token_to_refresh)
        except Exception:
            account.status = SocialAccountStatus.ERROR
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Stored credentials could not be decrypted. Please reconnect the account.",
            )

        provider = get_social_provider(account.platform)
        try:
            new_tokens = await provider.refresh_tokens(raw_token)
        except SocialTokenRefreshError:
            account.status = SocialAccountStatus.ERROR
            await db.commit()

            db.add(
                ActivityLog(
                    user_id=current_user.id,
                    action="TOKEN_REFRESH_FAILED",
                    entity_type="social_account",
                    entity_id=account.id,
                    log_metadata={
                        "company_id": str(account.company_id),
                        "platform": account.platform.value,
                    },
                )
            )
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Token refresh failed with {account.platform.value}. Please reconnect the account.",
            )

        # Encrypt refreshed tokens
        account.encrypted_access_token = encrypt_token(new_tokens.access_token)
        if new_tokens.refresh_token:
            account.encrypted_refresh_token = encrypt_token(new_tokens.refresh_token)
        if new_tokens.expires_in:
            account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=new_tokens.expires_in)

        account.status = SocialAccountStatus.ACTIVE
        account.last_connected_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(account)

        # Audit log token refresh
        db.add(
            ActivityLog(
                user_id=current_user.id,
                action="TOKEN_REFRESH_SUCCEEDED",
                entity_type="social_account",
                entity_id=account.id,
                log_metadata={
                    "company_id": str(account.company_id),
                    "platform": account.platform.value,
                },
            )
        )
        await db.commit()

        return account
