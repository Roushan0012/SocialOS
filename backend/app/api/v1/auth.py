"""Authentication & RBAC REST API Endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_async_db,
    get_current_user,
    require_admin,
    require_manager,
    require_team,
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


def _extract_client_info(request: Request):
    """Extract client IP and User-Agent safely from request."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    return ip, ua


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue tokens",
)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Authenticate with email and password.

    Issues short-lived JWT access token and securely hashed refresh token.
    Generic error returned on failure to prevent user enumeration attacks.
    """
    user = await AuthService.authenticate_user(
        db,
        email=credentials.email,
        password=credentials.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    ip_address, user_agent = _extract_client_info(request)
    access_token, refresh_token = await AuthService.create_user_session(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.name if user.role else "UNKNOWN",
            is_active=user.is_active,
        ),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
)
async def refresh_tokens(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Rotate an active refresh token session.

    Old refresh token is invalidated immediately and replaced with a new one.
    """
    ip_address, user_agent = _extract_client_info(request)
    try:
        new_access, new_refresh, user = await AuthService.rotate_refresh_session(
            db,
            raw_refresh_token=payload.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role.name if user.role else "UNKNOWN",
            is_active=user.is_active,
        ),
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token and log out session",
)
async def logout(
    payload: LogoutRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Revoke refresh token session to invalidate further token issuing."""
    await AuthService.revoke_session(
        db,
        raw_refresh_token=payload.refresh_token,
    )
    return MessageResponse(detail="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Retrieve profile of authenticated user via Bearer token.

    Never exposes password_hash or internal secrets.
    """
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.name if current_user.role else "UNKNOWN",
        is_active=current_user.is_active,
    )


# -----------------------------------------------------------------------------
# Protected RBAC Test Endpoints (Step 7 Verification Only)
# -----------------------------------------------------------------------------

@router.get(
    "/test/admin",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="RBAC test endpoint: requires ADMIN role",
)
async def test_admin_access(current_user: User = Depends(require_admin)):
    """Access restricted strictly to users with the ADMIN role."""
    return MessageResponse(detail=f"Admin access granted to {current_user.name}")


@router.get(
    "/test/manager",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="RBAC test endpoint: requires ADMIN or SOCIAL_MEDIA_MANAGER",
)
async def test_manager_access(current_user: User = Depends(require_manager)):
    """Access restricted to ADMIN or SOCIAL_MEDIA_MANAGER roles."""
    return MessageResponse(detail=f"Manager access granted to {current_user.name}")


@router.get(
    "/test/team",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="RBAC test endpoint: requires any of the 5 team roles",
)
async def test_team_access(current_user: User = Depends(require_team)):
    """Access open to all five authenticated system roles."""
    return MessageResponse(detail=f"Team access granted to {current_user.name} ({current_user.role.name})")
