"""User Management Service Layer."""
import uuid
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import hash_password, validate_password_strength
from app.models.activity_log import ActivityLog
from app.models.auth_session import AuthSession
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.role import Role
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.auth_service import AuthService
from app.services.company_service import CompanyService


class UserService:
    """Handles user CRUD, role management, session revocation, and audit logging."""

    @staticmethod
    async def create_user(
        db: AsyncSession,
        data: UserCreate,
        actor: User,
    ) -> User:
        """Create a new system user (ADMIN only)."""
        normalized_email = data.email.strip().lower()

        # 1. Validate email uniqueness
        existing_stmt = select(User).where(func.lower(User.email) == normalized_email)
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{data.email}' already exists",
            )

        # 2. Validate role exists
        role_stmt = select(Role).where(Role.name == data.role.upper())
        role_res = await db.execute(role_stmt)
        role = role_res.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{data.role}'. Role does not exist.",
            )

        # 3. Validate password strength
        try:
            validate_password_strength(data.password)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

        # 4. Hash password with Argon2id
        hashed = hash_password(data.password)

        user = User(
            name=data.name,
            email=normalized_email,
            password_hash=hashed,
            role_id=role.id,
            role=role,
            is_active=data.is_active,
        )
        db.add(user)
        await db.flush()

        # 5. Audit log
        audit_log = ActivityLog(
            user_id=actor.id,
            action="USER_CREATED",
            entity_type="user",
            entity_id=user.id,
            log_metadata={
                "name": user.name,
                "email": user.email,
                "role": role.name,
            },
        )
        db.add(audit_log)

        await db.commit()
        # Eager reload with role
        res = await db.execute(
            select(User).options(joinedload(User.role)).where(User.id == user.id)
        )
        return res.scalar_one()

    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        data: UserUpdate,
        actor: User,
    ) -> User:
        """Update an existing user's attributes, password, or role (ADMIN only)."""
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # 1. Update email
        if data.email is not None:
            normalized_email = data.email.strip().lower()
            if normalized_email != user.email:
                chk_stmt = select(User).where(
                    func.lower(User.email) == normalized_email,
                    User.id != user_id,
                )
                chk_res = await db.execute(chk_stmt)
                if chk_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"User with email '{data.email}' already exists",
                    )
                user.email = normalized_email

        # 2. Update name
        if data.name is not None:
            user.name = data.name

        # 3. Update password
        if data.password is not None:
            try:
                validate_password_strength(data.password)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                )
            user.password_hash = hash_password(data.password)
            # Invalidate all active sessions for security
            await AuthService.revoke_session(db, user_id=user.id)

        # 4. Status change
        if data.is_active is not None and data.is_active != user.is_active:
            user.is_active = data.is_active
            action = "USER_ACTIVATED" if user.is_active else "USER_DEACTIVATED"
            if not user.is_active:
                await AuthService.revoke_session(db, user_id=user.id)
            db.add(ActivityLog(
                user_id=actor.id,
                action=action,
                entity_type="user",
                entity_id=user.id,
                log_metadata={"email": user.email},
            ))

        # 5. Role change
        if data.role is not None:
            role_stmt = select(Role).where(Role.name == data.role.upper())
            role_res = await db.execute(role_stmt)
            new_role = role_res.scalar_one_or_none()
            if not new_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role '{data.role}'. Role does not exist.",
                )
            old_role_name = user.role.name if user.role else "UNKNOWN"
            if new_role.id != user.role_id:
                user.role_id = new_role.id
                user.role = new_role
                # Revoke active sessions when role changes so new JWT claims take effect
                await AuthService.revoke_session(db, user_id=user.id)
                db.add(ActivityLog(
                    user_id=actor.id,
                    action="USER_ROLE_CHANGED",
                    entity_type="user",
                    entity_id=user.id,
                    log_metadata={
                        "email": user.email,
                        "old_role": old_role_name,
                        "new_role": new_role.name,
                    },
                ))

        # General update audit
        db.add(ActivityLog(
            user_id=actor.id,
            action="USER_UPDATED",
            entity_type="user",
            entity_id=user.id,
            log_metadata={"email": user.email},
        ))

        await db.commit()
        # Eager reload
        reload_stmt = select(User).options(joinedload(User.role)).where(User.id == user.id)
        reload_res = await db.execute(reload_stmt)
        return reload_res.scalar_one()

    @staticmethod
    async def deactivate_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        actor: User,
    ) -> User:
        """Deactivate user account and revoke active sessions (ADMIN only)."""
        stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user.is_active:
            user.is_active = False
            await AuthService.revoke_session(db, user_id=user.id)
            db.add(ActivityLog(
                user_id=actor.id,
                action="USER_DEACTIVATED",
                entity_type="user",
                entity_id=user.id,
                log_metadata={"email": user.email},
            ))
            await db.commit()
            await db.refresh(user)

        return user

    @staticmethod
    async def activate_user(
        db: AsyncSession,
        user_id: uuid.UUID,
        actor: User,
    ) -> User:
        """Reactivate user account (ADMIN only)."""
        stmt = select(User).options(joinedload(User.role)).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if not user.is_active:
            user.is_active = True
            db.add(ActivityLog(
                user_id=actor.id,
                action="USER_ACTIVATED",
                entity_type="user",
                entity_id=user.id,
                log_metadata={"email": user.email},
            ))
            await db.commit()
            await db.refresh(user)

        return user

    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Tuple[User, List[Company]]:
        """Retrieve user details and accessible companies."""
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        companies = await CompanyService.get_user_accessible_companies(db, user)
        return user, companies

    @staticmethod
    async def list_users(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[User], int]:
        """List users with filtering and pagination (ADMIN only)."""
        count_stmt = select(func.count(User.id))
        query_stmt = select(User).options(joinedload(User.role))

        if role:
            role_subquery = select(Role.id).where(Role.name == role.upper())
            count_stmt = count_stmt.where(User.role_id.in_(role_subquery))
            query_stmt = query_stmt.where(User.role_id.in_(role_subquery))

        if is_active is not None:
            count_stmt = count_stmt.where(User.is_active == is_active)
            query_stmt = query_stmt.where(User.is_active == is_active)

        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        query_stmt = (
            query_stmt.order_by(User.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_res = await db.execute(query_stmt)
        items = list(items_res.scalars().all())

        return items, total
