"""User Management & Profile REST API Endpoints."""
import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_async_db,
    get_current_user,
    require_admin,
)
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.company import CompanySummary
from app.schemas.user import (
    UserCreate,
    UserDetailResponse,
    UserListResponse,
    UserProfileResponse,
    UserUpdate,
)
from app.services.company_service import CompanyService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users & Profiles"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile and accessible brands",
)
async def get_my_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve profile of authenticated user including accessible brands/companies.

    Never exposes password_hash or secret tokens.
    """
    companies = await CompanyService.get_user_accessible_companies(db, current_user)
    return UserProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role.name if current_user.role else "UNKNOWN",
        is_active=current_user.is_active,
        companies=[CompanySummary.model_validate(c) for c in companies],
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (ADMIN only)",
)
async def create_user(
    payload: UserCreate,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Provision a new user account with Argon2id encrypted password (ADMIN only)."""
    user = await UserService.create_user(db, data=payload, actor=admin_user)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "UNKNOWN",
        is_active=user.is_active,
    )


@router.get(
    "",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all users with pagination (ADMIN only)",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    role: Optional[str] = Query(None, description="Filter by role name"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """List system users with optional role and status filters (ADMIN only)."""
    users, total = await UserService.list_users(
        db,
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return UserListResponse(
        items=[
            UserResponse(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role.name if u.role else "UNKNOWN",
                is_active=u.is_active,
            )
            for u in users
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user details by ID (ADMIN only)",
)
async def get_user_by_id(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve detailed user account information and accessible brands (ADMIN only)."""
    user, companies = await UserService.get_user_by_id(db, user_id=user_id)
    return UserDetailResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "UNKNOWN",
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        companies=[CompanySummary.model_validate(c) for c in companies],
    )


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user details, role, or password (ADMIN only)",
)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Update user information, assign roles, or reset passwords (ADMIN only)."""
    user = await UserService.update_user(
        db, user_id=user_id, data=payload, actor=admin_user
    )
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "UNKNOWN",
        is_active=user.is_active,
    )


@router.post(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Deactivate user account (ADMIN only)",
)
async def deactivate_user(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Deactivate a user account and immediately revoke all active sessions (ADMIN only)."""
    user = await UserService.deactivate_user(
        db, user_id=user_id, actor=admin_user
    )
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "UNKNOWN",
        is_active=user.is_active,
    )


@router.post(
    "/{user_id}/activate",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate user account (ADMIN only)",
)
async def activate_user(
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Reactivate a suspended user account (ADMIN only)."""
    user = await UserService.activate_user(
        db, user_id=user_id, actor=admin_user
    )
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "UNKNOWN",
        is_active=user.is_active,
    )
