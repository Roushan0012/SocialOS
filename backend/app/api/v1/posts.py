"""Posts API Endpoints.

Handles post creation, multi-platform dispatch configuration, and schedule management.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.models.user import User
from app.schemas.post import PostCreateRequest, PostCreateResponse
from app.services.post_service import PostService

router = APIRouter(prefix="/posts", tags=["Posts & Publishing"])


@router.post(
    "",
    response_model=PostCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new post with platform targets",
)
async def create_post(
    data: PostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> PostCreateResponse:
    """Create a SocialOS post across one or more platform targets.

    Enforces strict company-level authorization and RBAC. Ensures every target social account
    belongs to the same company, is currently connected and active, and creates all platform
    targets atomically. Zero credential or token leakage.
    """
    return await PostService.create_post(
        db=db,
        data=data,
        current_user=current_user,
    )
