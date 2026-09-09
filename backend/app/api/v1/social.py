"""Social Accounts & OAuth REST API Endpoints.

Provides endpoints for listing connected accounts, initiating external OAuth connections,
handling provider callbacks, disconnecting accounts, and refreshing credentials.
Zero-leakage guarantee: OAuth tokens are never returned in responses or logs.
"""
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_async_db,
    get_current_user,
    get_optional_current_user,
)
from app.models.enums import Platform
from app.models.user import User
from app.schemas.social import (
    OAuthCallbackResponse,
    OAuthStartResponse,
    SocialAccountRead,
    TokenRefreshResponse,
)
from app.services.social_account_service import SocialAccountService

router = APIRouter(prefix="/social", tags=["Social Media Accounts & OAuth"])


def parse_platform_or_400(platform_str: str) -> Platform:
    """Validate and convert platform path parameter to Platform enum."""
    try:
        return Platform(platform_str.upper())
    except ValueError:
        valid_platforms = [p.value for p in Platform]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform '{platform_str}'. Supported platforms: {valid_platforms}",
        )


@router.get(
    "/accounts",
    response_model=List[SocialAccountRead],
    status_code=status.HTTP_200_OK,
    summary="List connected social accounts for an authorized company",
)
async def list_social_accounts(
    company_id: uuid.UUID = Query(..., description="Target brand company UUID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve all social media accounts connected to the specified company.
    
    Access is strictly isolated to authorized company members and system administrators.
    Credentials and tokens are never exposed.
    """
    accounts = await SocialAccountService.list_social_accounts(
        db=db,
        current_user=current_user,
        company_id=company_id,
    )
    return accounts


@router.get(
    "/oauth/{platform}/start",
    response_model=OAuthStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate OAuth connection flow for a social platform",
)
async def start_oauth(
    platform: str,
    company_id: uuid.UUID = Query(..., description="Target brand company UUID"),
    redirect_uri: Optional[str] = Query(None, description="Optional OAuth redirect callback URI override"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Initiate OAuth 2.0 authorization handshake.
    
    Generates a secure, cryptographically random CSRF state token bound to
    the authenticated user, target company, and selected platform.
    Returns the platform-specific authorization redirect URL.
    """
    platform_enum = parse_platform_or_400(platform)
    auth_url, state_token = await SocialAccountService.start_oauth_connection(
        db=db,
        current_user=current_user,
        company_id=company_id,
        platform=platform_enum,
        redirect_uri=redirect_uri,
    )
    return OAuthStartResponse(
        authorization_url=auth_url,
        state=state_token,
        platform=platform_enum,
    )


@router.get(
    "/oauth/{platform}/callback",
    response_model=OAuthCallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Handle OAuth redirect callback from social platform",
)
async def oauth_callback(
    platform: str,
    code: Optional[str] = Query(None, description="Authorization code from provider"),
    state: Optional[str] = Query(None, description="CSRF state token returned from provider"),
    error: Optional[str] = Query(None, description="Error code from provider if authorization failed"),
    error_description: Optional[str] = Query(None, description="Error description from provider"),
    redirect_uri: Optional[str] = Query(None, description="Redirect URI used during authorization start"),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Process incoming OAuth callback redirect from an external social provider.
    
    Validates CSRF state against stored session, exchanges code for access/refresh tokens,
    retrieves account identity, encrypts credentials with AES-256-GCM, and upserts the account.
    """
    if error:
        detail = error_description or error or "OAuth authorization was denied or canceled by user."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth authorization failed: {detail}",
        )

    if not code or not code.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code 'code' parameter is missing.",
        )

    if not state or not state.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSRF state 'state' parameter is missing.",
        )

    platform_enum = parse_platform_or_400(platform)
    account = await SocialAccountService.handle_oauth_callback(
        db=db,
        platform=platform_enum,
        code=code.strip(),
        state=state.strip(),
        redirect_uri=redirect_uri,
        current_user=current_user,
    )

    return OAuthCallbackResponse(
        message=f"{platform_enum.value} account '{account.account_name}' connected successfully",
        account=account,
    )


@router.delete(
    "/accounts/{social_account_id}",
    response_model=SocialAccountRead,
    status_code=status.HTTP_200_OK,
    summary="Disconnect a social account",
)
async def disconnect_social_account(
    social_account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Disconnect a social account, permanently clearing stored credentials and marking as DISCONNECTED."""
    account = await SocialAccountService.disconnect_social_account(
        db=db,
        current_user=current_user,
        social_account_id=social_account_id,
    )
    return account


@router.post(
    "/accounts/{social_account_id}/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh social account tokens",
)
async def refresh_social_account(
    social_account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Refresh expired access credentials for a connected social account using encrypted refresh token."""
    account = await SocialAccountService.refresh_social_account_tokens(
        db=db,
        current_user=current_user,
        social_account_id=social_account_id,
    )
    return TokenRefreshResponse(
        message=f"{account.platform.value} token refreshed successfully",
        account=account,
    )
