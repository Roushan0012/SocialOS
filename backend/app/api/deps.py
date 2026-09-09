"""FastAPI Authentication and RBAC Route Dependencies."""
import uuid
from typing import Callable, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import get_async_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """Validate bearer access token and retrieve current authenticated user.

    Raises:
        HTTPException(401): If token is missing, expired, or invalid.
        HTTPException(403): If user account is marked inactive.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user_id = uuid.UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    return user


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> Optional[User]:
    """Retrieve current user if bearer token is provided; returns None if omitted or invalid."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
        stmt = (
            select(User)
            .options(joinedload(User.role))
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    except Exception:
        pass
    return None


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC).

    Args:
        *allowed_roles: List of role names permitted to access the endpoint.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.name if current_user.role else ""
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient permissions",
            )
        return current_user

    return role_checker


# Pre-configured RBAC dependencies
require_authenticated_user = get_current_user
require_admin = require_roles("ADMIN")
require_manager = require_roles("ADMIN", "SOCIAL_MEDIA_MANAGER")
require_team = require_roles(
    "ADMIN",
    "SOCIAL_MEDIA_MANAGER",
    "CONTENT_CREATOR",
    "GRAPHIC_DESIGNER",
    "VIDEO_EDITOR",
)


async def get_authorized_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """FastAPI route dependency ensuring current user is authorized to access company_id.

    Raises:
        HTTPException(404): If company does not exist or is inactive.
        HTTPException(403): If user does not have membership access.
    """
    from app.services.company_service import CompanyService
    return await CompanyService.get_authorized_company(
        db=db,
        company_id=company_id,
        user=current_user,
    )


async def require_company_access(
    company_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> bool:
    """Helper verifying if user has access to company_id, raising 403/404 if not."""
    from app.services.company_service import CompanyService
    await CompanyService.get_authorized_company(
        db=db,
        company_id=company_id,
        user=user,
    )
    return True

