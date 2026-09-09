"""Company & Brand Access Control Service Layer."""
import uuid
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.activity_log import ActivityLog
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyUpdate


class CompanyService:
    """Manages company (brand) entities, membership access control, and isolation."""

    @staticmethod
    async def user_can_access_company(
        db: AsyncSession,
        user: User,
        company_id: uuid.UUID,
    ) -> bool:
        """Check if user has access to the specified company.

        ADMIN role has access to all companies.
        Non-admin users require an active CompanyMembership.
        """
        if user.role and user.role.name == "ADMIN":
            return True

        stmt = select(func.count(CompanyMembership.id)).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user.id,
        )
        result = await db.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    @staticmethod
    async def get_user_accessible_companies(
        db: AsyncSession,
        user: User,
        include_inactive: bool = False,
    ) -> List[Company]:
        """Retrieve all active companies a user is authorized to access."""
        if user.role and user.role.name == "ADMIN":
            stmt = select(Company)
            if not include_inactive:
                stmt = stmt.where(Company.is_active == True)  # noqa: E712
            stmt = stmt.order_by(Company.name.asc())
            result = await db.execute(stmt)
            return list(result.scalars().all())

        # Non-admin: joined through company_memberships
        stmt = (
            select(Company)
            .join(CompanyMembership, CompanyMembership.company_id == Company.id)
            .where(
                CompanyMembership.user_id == user.id,
                Company.is_active == True,  # noqa: E712
            )
            .order_by(Company.name.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_authorized_company(
        db: AsyncSession,
        company_id: uuid.UUID,
        user: User,
        include_inactive: bool = False,
    ) -> Company:
        """Retrieve company and enforce strict isolation and authorization.

        Raises:
            HTTPException(404): If company does not exist or is inactive (and not requested by admin).
            HTTPException(403): If authenticated user lacks membership in this company.
        """
        stmt = select(Company).where(Company.id == company_id)
        result = await db.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        if not company.is_active and not include_inactive:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # Enforce company isolation
        is_admin = user.role and user.role.name == "ADMIN"
        if not is_admin:
            has_access = await CompanyService.user_can_access_company(db, user, company_id)
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have access to this company",
                )

        return company

    @staticmethod
    async def create_company(
        db: AsyncSession,
        data: CompanyCreate,
        actor: User,
    ) -> Company:
        """Create a new company/brand (ADMIN only)."""
        # Validate slug uniqueness
        existing_stmt = select(Company).where(func.lower(Company.slug) == data.slug.lower())
        existing = await db.execute(existing_stmt)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company with slug '{data.slug}' already exists",
            )

        company = Company(
            name=data.name,
            slug=data.slug,
            logo_url=data.logo_url,
            is_active=data.is_active,
        )
        db.add(company)
        await db.flush()

        # Audit log
        audit_log = ActivityLog(
            user_id=actor.id,
            action="COMPANY_CREATED",
            entity_type="company",
            entity_id=company.id,
            log_metadata={"name": company.name, "slug": company.slug},
        )
        db.add(audit_log)

        await db.commit()
        await db.refresh(company)
        return company

    @staticmethod
    async def update_company(
        db: AsyncSession,
        company_id: uuid.UUID,
        data: CompanyUpdate,
        actor: User,
    ) -> Company:
        """Update company attributes (ADMIN only)."""
        stmt = select(Company).where(Company.id == company_id)
        res = await db.execute(stmt)
        company = res.scalar_one_or_none()

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # If slug is changing, verify uniqueness
        if data.slug is not None and data.slug.lower() != company.slug.lower():
            slug_stmt = select(Company).where(
                func.lower(Company.slug) == data.slug.lower(),
                Company.id != company_id,
            )
            slug_res = await db.execute(slug_stmt)
            if slug_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Company with slug '{data.slug}' already exists",
                )
            company.slug = data.slug

        if data.name is not None:
            company.name = data.name
        if data.logo_url is not None:
            company.logo_url = data.logo_url

        metadata = {"company_id": str(company.id)}

        # Status transition audit
        if data.is_active is not None and data.is_active != company.is_active:
            company.is_active = data.is_active
            action = "COMPANY_ACTIVATED" if company.is_active else "COMPANY_DEACTIVATED"
            status_audit = ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type="company",
                entity_id=company.id,
                log_metadata=metadata,
            )
            db.add(status_audit)

        # General update audit
        update_audit = ActivityLog(
            user_id=actor.id,
            action="COMPANY_UPDATED",
            entity_type="company",
            entity_id=company.id,
            log_metadata=metadata,
        )
        db.add(update_audit)

        await db.commit()
        await db.refresh(company)
        return company

    @staticmethod
    async def deactivate_company(
        db: AsyncSession,
        company_id: uuid.UUID,
        actor: User,
    ) -> Company:
        """Soft-deactivate a company (ADMIN only)."""
        stmt = select(Company).where(Company.id == company_id)
        res = await db.execute(stmt)
        company = res.scalar_one_or_none()

        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        if company.is_active:
            company.is_active = False
            audit_log = ActivityLog(
                user_id=actor.id,
                action="COMPANY_DEACTIVATED",
                entity_type="company",
                entity_id=company.id,
                log_metadata={"company_id": str(company.id), "slug": company.slug},
            )
            db.add(audit_log)
            await db.commit()
            await db.refresh(company)

        return company

    @staticmethod
    async def list_companies(
        db: AsyncSession,
        user: User,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Company], int]:
        """List companies with authorization filtering and pagination."""
        is_admin = user.role and user.role.name == "ADMIN"

        if include_inactive and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only administrators may request inactive companies",
            )

        if is_admin:
            count_stmt = select(func.count(Company.id))
            query_stmt = select(Company)
            if not include_inactive:
                count_stmt = count_stmt.where(Company.is_active == True)  # noqa: E712
                query_stmt = query_stmt.where(Company.is_active == True)  # noqa: E712
        else:
            # Non-admin: strictly limited to companies where user has membership
            count_stmt = (
                select(func.count(Company.id))
                .join(CompanyMembership, CompanyMembership.company_id == Company.id)
                .where(
                    CompanyMembership.user_id == user.id,
                    Company.is_active == True,  # noqa: E712
                )
            )
            query_stmt = (
                select(Company)
                .join(CompanyMembership, CompanyMembership.company_id == Company.id)
                .where(
                    CompanyMembership.user_id == user.id,
                    Company.is_active == True,  # noqa: E712
                )
            )

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        query_stmt = (
            query_stmt.order_by(Company.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_res = await db.execute(query_stmt)
        items = list(items_res.scalars().all())

        return items, total

    @staticmethod
    async def add_member(
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User,
    ) -> CompanyMembership:
        """Assign a user to a company (ADMIN only)."""
        # 1. Verify company exists
        company_stmt = select(Company).where(Company.id == company_id)
        company_res = await db.execute(company_stmt)
        company = company_res.scalar_one_or_none()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        # 2. Verify target user exists
        user_stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # 3. Reject inactive users
        if not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot assign inactive user to company",
            )

        # 4. Check duplicate membership
        existing_stmt = select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user_id,
        )
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this company",
            )

        # 5. Create membership
        membership = CompanyMembership(
            company_id=company_id,
            user_id=user_id,
            user=target_user,
            company=company,
        )
        db.add(membership)
        await db.flush()

        # 6. Audit log
        audit_log = ActivityLog(
            user_id=actor.id,
            action="COMPANY_MEMBER_ADDED",
            entity_type="company_membership",
            entity_id=membership.id,
            log_metadata={
                "company_id": str(company_id),
                "user_id": str(user_id),
                "company_name": company.name,
                "user_email": target_user.email,
            },
        )
        db.add(audit_log)

        await db.commit()
        stmt = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.user).joinedload(User.role)
            )
            .where(CompanyMembership.id == membership.id)
        )
        res = await db.execute(stmt)
        return res.scalar_one()

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User,
    ) -> bool:
        """Remove a user from a company (ADMIN only)."""
        stmt = select(CompanyMembership).where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.user_id == user_id,
        )
        res = await db.execute(stmt)
        membership = res.scalar_one_or_none()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company membership not found",
            )

        await db.delete(membership)

        # Audit log
        audit_log = ActivityLog(
            user_id=actor.id,
            action="COMPANY_MEMBER_REMOVED",
            entity_type="company_membership",
            entity_id=membership.id,
            log_metadata={
                "company_id": str(company_id),
                "user_id": str(user_id),
            },
        )
        db.add(audit_log)

        await db.commit()
        return True

    @staticmethod
    async def list_members(
        db: AsyncSession,
        company_id: uuid.UUID,
    ) -> List[CompanyMembership]:
        """List all members associated with a company (ADMIN only)."""
        # Verify company exists
        company_stmt = select(Company).where(Company.id == company_id)
        comp_res = await db.execute(company_stmt)
        if not comp_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found",
            )

        stmt = (
            select(CompanyMembership)
            .options(
                joinedload(CompanyMembership.user).joinedload(User.role)
            )
            .where(CompanyMembership.company_id == company_id)
            .order_by(CompanyMembership.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
