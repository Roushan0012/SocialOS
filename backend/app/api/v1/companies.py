"""Company (Brand) & Membership REST API Endpoints."""
import math
import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_async_db,
    get_authorized_company,
    get_current_user,
    require_admin,
)
from app.models.company import Company
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyMemberAddRequest,
    CompanyMemberResponse,
    CompanyResponse,
    CompanyUpdate,
)
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["Companies & Brands"])


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new company/brand (ADMIN only)",
)
async def create_company(
    payload: CompanyCreate,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Provision a new brand workspace. Strictly restricted to system administrators."""
    company = await CompanyService.create_company(db, payload, actor=admin_user)
    return company


@router.get(
    "",
    response_model=CompanyListResponse,
    status_code=status.HTTP_200_OK,
    summary="List accessible companies with authorization filtering",
)
async def list_companies(
    include_inactive: bool = Query(
        False, description="Include inactive companies (ADMIN only)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Retrieve companies accessible to the authenticated user.

    - ADMIN: returns all active companies (or inactive if include_inactive=True).
    - Non-admin: returns strictly the companies where the user holds an active membership.
    """
    items, total = await CompanyService.list_companies(
        db,
        user=current_user,
        include_inactive=include_inactive,
        page=page,
        page_size=page_size,
    )
    pages = math.ceil(total / page_size) if total > 0 else 0
    return CompanyListResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get company details by ID",
)
async def get_company(
    company: Company = Depends(get_authorized_company),
):
    """Retrieve company details. Enforces company-level isolation."""
    return company


@router.patch(
    "/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update company details (ADMIN only)",
)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Update company name, slug, logo URL, or active status (ADMIN only)."""
    company = await CompanyService.update_company(
        db, company_id=company_id, data=payload, actor=admin_user
    )
    return company


@router.delete(
    "/{company_id}",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft-deactivate company (ADMIN only)",
)
async def deactivate_company(
    company_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Soft-deactivate a company (is_active=false) to preserve data integrity (ADMIN only)."""
    company = await CompanyService.deactivate_company(
        db, company_id=company_id, actor=admin_user
    )
    return company


# -----------------------------------------------------------------------------
# Company Membership Management (ADMIN only)
# -----------------------------------------------------------------------------

@router.post(
    "/{company_id}/members",
    response_model=CompanyMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add user membership to company (ADMIN only)",
)
async def add_company_member(
    company_id: uuid.UUID,
    payload: CompanyMemberAddRequest,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Grant a user access to the specified company (ADMIN only)."""
    membership = await CompanyService.add_member(
        db,
        company_id=company_id,
        user_id=payload.user_id,
        actor=admin_user,
    )
    return CompanyMemberResponse(
        membership_id=membership.id,
        company_id=membership.company_id,
        user_id=membership.user_id,
        name=membership.user.name,
        email=membership.user.email,
        role=membership.user.role.name if membership.user.role else "UNKNOWN",
        is_active=membership.user.is_active,
        joined_at=membership.created_at,
    )


@router.delete(
    "/{company_id}/members/{user_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove user membership from company (ADMIN only)",
)
async def remove_company_member(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Revoke user access from a company without deleting user or company data (ADMIN only)."""
    await CompanyService.remove_member(
        db,
        company_id=company_id,
        user_id=user_id,
        actor=admin_user,
    )
    return MessageResponse(detail="Member removed from company successfully")


@router.get(
    "/{company_id}/members",
    response_model=List[CompanyMemberResponse],
    status_code=status.HTTP_200_OK,
    summary="List all company members (ADMIN only)",
)
async def list_company_members(
    company_id: uuid.UUID,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """List all users holding membership in the company (ADMIN only)."""
    memberships = await CompanyService.list_members(db, company_id=company_id)
    return [
        CompanyMemberResponse(
            membership_id=m.id,
            company_id=m.company_id,
            user_id=m.user_id,
            name=m.user.name,
            email=m.user.email,
            role=m.user.role.name if m.user.role else "UNKNOWN",
            is_active=m.user.is_active,
            joined_at=m.created_at,
        )
        for m in memberships
    ]
