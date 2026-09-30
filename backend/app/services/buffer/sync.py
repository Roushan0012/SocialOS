"""Buffer Channel Synchronization Service.

Idempotently synchronizes connected Buffer organizations and channels into SocialOS
social_accounts. Enforces company isolation, role-based access control, duplicate prevention,
unsupported channel skipping, and audit logging with zero secret leakage.
"""
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.models.enums import Platform, SocialAccountStatus
from app.models.social_account import SocialAccount
from app.models.user import User
from app.schemas.social import BufferSyncResponse, SyncAccountSummaryItem
from app.services.buffer.client import BufferClient
from app.services.buffer.exceptions import (
    BufferAuthError,
    BufferConnectionError,
    BufferError,
    BufferMissingApiKeyError,
    BufferTimeoutError,
)
from app.services.company_service import CompanyService

logger = logging.getLogger(__name__)

# Service string (Buffer) -> Platform enum (SocialOS)
BUFFER_SERVICE_MAP: Dict[str, Platform] = {
    "facebook": Platform.FACEBOOK,
    "instagram": Platform.INSTAGRAM,
    "linkedin": Platform.LINKEDIN,
    "youtube": Platform.YOUTUBE,
}


def map_buffer_service_to_platform(service: Optional[str]) -> Optional[Platform]:
    """Map Buffer channel service string to SocialOS Platform enum.

    Args:
        service: Raw service name from Buffer (e.g. 'facebook', 'instagram', 'twitter').

    Returns:
        Platform enum if supported by SocialOS, None otherwise.
    """
    if not service or not isinstance(service, str):
        return None
    return BUFFER_SERVICE_MAP.get(service.strip().lower())


class BufferSyncService:
    """Service layer for idempotent synchronization of Buffer channels into SocialOS social_accounts."""

    @staticmethod
    async def sync_channels_for_company(
        db: AsyncSession,
        company_id: uuid.UUID,
        current_user: User,
        organization_id: Optional[str] = None,
        buffer_client: Optional[BufferClient] = None,
    ) -> BufferSyncResponse:
        """Fetch channels from Buffer and idempotently upsert into company's social_accounts.

        Args:
            db: Active async database session.
            company_id: Target brand company UUID.
            current_user: Authenticated user initiating synchronization.
            organization_id: Optional Buffer organization ID filter.
            buffer_client: Optional injected BufferClient (for testing/dependency injection).

        Returns:
            BufferSyncResponse containing counts and items for created, updated, unchanged, skipped, and errors.

        Raises:
            HTTPException(403): If user does not have permission to access the target company.
            HTTPException(404): If company is not found.
            HTTPException(400): If Buffer API key is missing or invalid.
            HTTPException(401): If Buffer API authentication fails.
            HTTPException(502): If Buffer API connection fails.
            HTTPException(504): If Buffer API request times out.
        """
        # 1. Enforce strict company isolation & authorization
        await CompanyService.get_authorized_company(db, company_id, current_user)

        # 2. Initialize Buffer client
        client = buffer_client or BufferClient()
        if not client.is_configured:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Buffer integration is not configured. BUFFER_API_KEY is not set.",
            )

        # 3. Retrieve Buffer organizations and channels
        try:
            overview = await client.verify_connectivity()
        except BufferMissingApiKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Buffer integration is not configured. BUFFER_API_KEY is missing.",
            ) from None
        except BufferAuthError as exc:
            logger.warning("Buffer sync authentication failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Buffer API authentication failed. Verify BUFFER_API_KEY.",
            ) from None
        except BufferTimeoutError as exc:
            logger.warning("Buffer sync timed out: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Buffer API request timed out during synchronization.",
            ) from None
        except BufferConnectionError as exc:
            logger.warning("Buffer sync connection error: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to Buffer API.",
            ) from None
        except BufferError as exc:
            logger.warning("Buffer API error during sync: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Buffer API error: {exc}",
            ) from None
        except Exception as exc:
            logger.error("Unexpected error during Buffer channel sync: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error occurred during Buffer synchronization.",
            ) from None

        # 4. Filter organizations if requested
        orgs_to_process = overview.organizations_with_channels
        if organization_id and organization_id.strip():
            clean_org_id = organization_id.strip()
            orgs_to_process = [
                org_ch for org_ch in orgs_to_process if org_ch.organization.id == clean_org_id
            ]

        # 5. Process channels idempotently
        created: List[SyncAccountSummaryItem] = []
        updated: List[SyncAccountSummaryItem] = []
        unchanged: List[SyncAccountSummaryItem] = []
        skipped: List[SyncAccountSummaryItem] = []
        errors: List[SyncAccountSummaryItem] = []

        now = datetime.now(timezone.utc)

        for org_with_ch in orgs_to_process:
            org = org_with_ch.organization
            for ch in org_with_ch.channels:
                # Map platform
                platform = map_buffer_service_to_platform(ch.service)
                if platform is None:
                    skipped.append(
                        SyncAccountSummaryItem(
                            buffer_channel_id=ch.id,
                            name=ch.name,
                            service=ch.service,
                            reason=f"Unsupported platform service: '{ch.service}'. Supported: {list(BUFFER_SERVICE_MAP.keys())}",
                        )
                    )
                    continue

                # Query existing account by buffer_channel_id or (company_id + platform + platform_account_id)
                stmt = select(SocialAccount).where(
                    (SocialAccount.buffer_channel_id == ch.id)
                    | (
                        (SocialAccount.company_id == company_id)
                        & (SocialAccount.platform == platform)
                        & (SocialAccount.platform_account_id == ch.id)
                    )
                )
                res = await db.execute(stmt)
                existing_account = res.scalar_one_or_none()

                # Company isolation check
                if existing_account and existing_account.company_id != company_id:
                    errors.append(
                        SyncAccountSummaryItem(
                            id=existing_account.id,
                            buffer_channel_id=ch.id,
                            name=ch.name,
                            platform=platform,
                            service=ch.service,
                            error="Channel is already connected to another company in SocialOS.",
                        )
                    )
                    continue

                if existing_account:
                    # Check whether an update is necessary (idempotency check)
                    old_meta = existing_account.account_metadata or {}
                    name_changed = existing_account.account_name != ch.name
                    status_changed = existing_account.status != SocialAccountStatus.ACTIVE
                    org_changed = existing_account.buffer_organization_id != org.id
                    channel_id_changed = existing_account.buffer_channel_id != ch.id
                    avatar_changed = old_meta.get("avatar") != ch.avatar
                    queue_changed = old_meta.get("is_queue_paused") != ch.is_queue_paused

                    has_changes = (
                        name_changed
                        or status_changed
                        or org_changed
                        or channel_id_changed
                        or avatar_changed
                        or queue_changed
                    )

                    if has_changes:
                        existing_account.account_name = ch.name
                        existing_account.buffer_channel_id = ch.id
                        existing_account.buffer_organization_id = org.id
                        existing_account.status = SocialAccountStatus.ACTIVE
                        existing_account.last_connected_at = now
                        existing_account.account_metadata = {
                            **old_meta,
                            "avatar": ch.avatar,
                            "is_queue_paused": ch.is_queue_paused,
                            "service": ch.service,
                            "buffer_organization_id": org.id,
                        }
                        updated.append(
                            SyncAccountSummaryItem(
                                id=existing_account.id,
                                buffer_channel_id=ch.id,
                                name=ch.name,
                                platform=platform,
                                service=ch.service,
                            )
                        )
                    else:
                        unchanged.append(
                            SyncAccountSummaryItem(
                                id=existing_account.id,
                                buffer_channel_id=ch.id,
                                name=ch.name,
                                platform=platform,
                                service=ch.service,
                            )
                        )
                else:
                    # Create new SocialAccount record
                    new_account = SocialAccount(
                        company_id=company_id,
                        platform=platform,
                        account_name=ch.name,
                        platform_account_id=ch.id,
                        buffer_channel_id=ch.id,
                        buffer_organization_id=org.id,
                        status=SocialAccountStatus.ACTIVE,
                        account_metadata={
                            "avatar": ch.avatar,
                            "is_queue_paused": ch.is_queue_paused,
                            "service": ch.service,
                            "buffer_organization_id": org.id,
                        },
                        last_connected_at=now,
                    )
                    db.add(new_account)
                    await db.flush()
                    created.append(
                        SyncAccountSummaryItem(
                            id=new_account.id,
                            buffer_channel_id=ch.id,
                            name=ch.name,
                            platform=platform,
                            service=ch.service,
                        )
                    )

        # 6. Audit log the sync event
        db.add(
            ActivityLog(
                user_id=current_user.id,
                action="BUFFER_CHANNELS_SYNCED",
                entity_type="social_account",
                entity_id=None,
                log_metadata={
                    "company_id": str(company_id),
                    "organization_filter": organization_id,
                    "created_count": len(created),
                    "updated_count": len(updated),
                    "unchanged_count": len(unchanged),
                    "skipped_count": len(skipped),
                    "errors_count": len(errors),
                },
            )
        )
        await db.commit()

        total_synced = len(created) + len(updated) + len(unchanged)

        return BufferSyncResponse(
            message=f"Buffer channels synchronized: {len(created)} created, {len(updated)} updated, {len(unchanged)} unchanged, {len(skipped)} skipped, {len(errors)} errors.",
            company_id=company_id,
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped=skipped,
            errors=errors,
            total_synced=total_synced,
        )
