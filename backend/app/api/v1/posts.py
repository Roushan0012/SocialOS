import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_async_db, get_current_user
from app.models.user import User
from app.schemas.post import (
    PostCreateRequest,
    PostCreateResponse,
    PostTargetPublishResponse,
)
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


@router.post(
    "/{post_id}/targets/{target_id}/publish",
    response_model=PostTargetPublishResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish an individual post target channel immediately via Buffer",
)
async def publish_post_target(
    post_id: uuid.UUID,
    target_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
) -> PostTargetPublishResponse:
    """Manually dispatch and publish an existing PostTarget through Buffer.

    Enforces strict company-level authorization and RBAC. Ensures target ownership,
    verifies connected Buffer channel ID, guards against duplicate publishing,
    and updates Post and PostTarget statuses atomically.
    """
    return await PostService.publish_target(
        db=db,
        post_id=post_id,
        target_id=target_id,
        current_user=current_user,
    )
