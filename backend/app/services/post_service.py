"""Post Service Layer.

Domain service managing SocialOS post creation, platform target channel dispatch,
brand isolation enforcement, and audit event recording.
"""
from datetime import datetime, timezone
import logging
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.enums import PostStatus, PostTargetStatus, SocialAccountStatus
from app.models.post import Post
from app.models.post_target import PostTarget
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.post import PostCreateRequest, PostCreateResponse, PostTargetRead
from app.services.company_service import CompanyService

logger = logging.getLogger(__name__)


class PostService:
    """Manages post lifecycle, multi-platform dispatch targets, and company isolation."""

    @staticmethod
    async def create_post(
        db: AsyncSession,
        data: PostCreateRequest,
        current_user: User,
    ) -> PostCreateResponse:
        """Create a new post with multi-platform targets for an authorized company.

        Args:
            db: Async database session.
            data: Post creation request containing company_id, caption, targets, and optional scheduled_at.
            current_user: Authenticated user creating the post.

        Returns:
            PostCreateResponse containing the post metadata and target channel details.

        Raises:
            HTTPException(403): If user does not have permission for the target company.
            HTTPException(404): If company or any specified social account does not exist.
            HTTPException(400): If company isolation is violated, an account is disconnected,
                                or validation fails.
        """
        # 1. Enforce strict company authorization & RBAC
        await CompanyService.get_authorized_company(db, data.company_id, current_user)

        # 2. Validate and deduplicate target account IDs preserving order
        if not data.social_account_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one target social account must be specified.",
            )

        seen = set()
        unique_account_ids: List[uuid.UUID] = []
        for acc_id in data.social_account_ids:
            if acc_id not in seen:
                seen.add(acc_id)
                unique_account_ids.append(acc_id)

        # 3. Retrieve social accounts from database
        stmt = select(SocialAccount).where(SocialAccount.id.in_(unique_account_ids))
        result = await db.execute(stmt)
        accounts = list(result.scalars().all())
        account_map = {acc.id: acc for acc in accounts}

        # 4. Verify all requested target accounts exist
        for acc_id in unique_account_ids:
            if acc_id not in account_map:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Social account '{acc_id}' not found.",
                )

        # 5. Enforce strict brand/company isolation
        # Every target social account MUST belong to data.company_id.
        # If even ONE target belongs to another company, reject the entire request.
        for acc_id in unique_account_ids:
            acc = account_map[acc_id]
            if acc.company_id != data.company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Brand isolation violation: Social account '{acc.id}' ({acc.account_name}) "
                        f"belongs to company '{acc.company_id}', not '{data.company_id}'. "
                        "Cross-company post dispatch is strictly forbidden."
                    ),
                )
            # Model-level invariant check
            PostTarget.validate_brand_isolation(data.company_id, acc.company_id)

        # 6. Verify all target accounts are active and connected
        for acc_id in unique_account_ids:
            acc = account_map[acc_id]
            if acc.status != SocialAccountStatus.ACTIVE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Social account '{acc.id}' ({acc.account_name}) is disconnected or inactive "
                        f"(status: {acc.status.value}). Only active connected accounts can be targeted."
                    ),
                )

        # 7. Clean and prepare caption
        caption = data.caption.strip() if data.caption else None

        # 8. Determine initial post status
        initial_status = (
            PostStatus.SCHEDULED if data.scheduled_at is not None else PostStatus.DRAFT
        )

        try:
            # 9. Create Post entity
            post = Post(
                company_id=data.company_id,
                created_by=current_user.id,
                caption=caption,
                status=initial_status,
                scheduled_at=data.scheduled_at,
            )
            db.add(post)
            await db.flush()  # Populates post.id

            # 10. Create PostTarget entities
            created_targets: List[PostTarget] = []
            for acc_id in unique_account_ids:
                acc = account_map[acc_id]
                target = PostTarget(
                    post_id=post.id,
                    social_account_id=acc.id,
                    platform=acc.platform,
                    status=PostTargetStatus.PENDING,
                )
                db.add(target)
                created_targets.append(target)

            await db.flush()  # Populates target.id and validates constraints

            # 11. Record audit log
            audit_log = ActivityLog(
                user_id=current_user.id,
                action="POST_CREATED",
                entity_type="post",
                entity_id=post.id,
                log_metadata={
                    "company_id": str(data.company_id),
                    "target_count": len(created_targets),
                    "platforms": [t.platform.value for t in created_targets],
                    "scheduled_at": data.scheduled_at.isoformat() if data.scheduled_at else None,
                },
            )
            db.add(audit_log)

            await db.commit()

            # 12. Build safe typed response (zero credential leakage)
            target_reads = [
                PostTargetRead(
                    id=target.id,
                    social_account_id=target.social_account_id,
                    platform=target.platform,
                    account_name=account_map[target.social_account_id].account_name,
                    status=target.status,
                    provider_post_id=target.provider_post_id,
                    error_message=target.error_message,
                    published_at=target.published_at,
                    created_at=target.created_at,
                )
                for target in created_targets
            ]

            return PostCreateResponse(
                id=post.id,
                company_id=post.company_id,
                caption=post.caption,
                status=post.status,
                scheduled_at=post.scheduled_at,
                created_at=post.created_at,
                targets=target_reads,
            )

        except Exception:
            await db.rollback()
            raise
