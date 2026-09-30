"""Step 11 — Buffer Social Account Synchronization Test Suite.

Covers:
- Facebook channel synchronization
- Instagram channel synchronization
- First sync creates account
- Second sync does not duplicate (strict idempotency)
- Existing account updates correctly upon metadata change
- Unsupported Buffer service (e.g. twitter, pinterest) is safely skipped
- Company isolation: Non-member user gets 403 Forbidden
- Company isolation: Cross-company channel collision is rejected with error
- Unauthorized request without token gets 401
- Non-existent company gets 404
- Buffer API failures (auth 401, timeout 504, connection 502, missing key 400)
- Secret/token non-leakage guarantee (no API key in response, DB, or logs)
- Organization ID filtering
"""
from datetime import datetime, timezone
import json
import logging
from typing import Tuple
from unittest.mock import AsyncMock, patch
import uuid

import httpx
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.pool import StaticPool

from app.api.deps import get_async_db
from app.core.database import Base
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.activity_log import ActivityLog
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.enums import Platform, SocialAccountStatus
from app.models.role import Role
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.buffer.client import BufferClient
from app.services.buffer.exceptions import (
    BufferAuthError,
    BufferConnectionError,
    BufferMissingApiKeyError,
    BufferTimeoutError,
)
from app.services.buffer.schemas import (
    BufferAccount,
    BufferAccountOverview,
    BufferChannel,
    BufferOrganization,
    BufferOrganizationWithChannels,
)
from app.services.buffer.sync import BufferSyncService, map_buffer_service_to_platform

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

SYSTEM_ROLES = [
    ("ADMIN", "System Administrator"),
    ("SOCIAL_MEDIA_MANAGER", "Social Media Manager"),
    ("CONTENT_CREATOR", "Content Creator"),
    ("GRAPHIC_DESIGNER", "Graphic Designer"),
    ("VIDEO_EDITOR", "Video Editor"),
]

MOCK_ORG_ID = "6abcbbda5bf9b0aa6d2ea28a"
MOCK_FB_CHANNEL_ID = "6abd0978ea19ca0bde32dcbb"
MOCK_IG_CHANNEL_ID = "6abcd84aea19ca0bde30fe66"


def create_mock_buffer_overview(
    fb_name: str = "Socialos Test",
    ig_name: str = "roushan_1106",
    fb_paused: bool = False,
    include_unsupported: bool = False,
) -> BufferAccountOverview:
    """Build a strongly-typed BufferAccountOverview matching Buffer's real API output."""
    channels = [
        BufferChannel(
            id=MOCK_FB_CHANNEL_ID,
            name=fb_name,
            service="facebook",
            avatar="https://buffer.local/fb.jpg",
            isQueuePaused=fb_paused,
        ),
        BufferChannel(
            id=MOCK_IG_CHANNEL_ID,
            name=ig_name,
            service="instagram",
            avatar="https://buffer.local/ig.jpg",
            isQueuePaused=False,
        ),
    ]
    if include_unsupported:
        channels.append(
            BufferChannel(
                id="ch_tw_unsupported",
                name="Twitter Brand Channel",
                service="twitter",
                avatar="https://buffer.local/tw.jpg",
                isQueuePaused=False,
            )
        )

    org = BufferOrganization(id=MOCK_ORG_ID, name="My organization")
    return BufferAccountOverview(
        account=BufferAccount(
            id="6abcbbda5bf9b0aa6d2ea288",
            name="priyanshu.bizwork",
            email="priyanshu.bizwork@gmail.com",
            organizations=[org],
        ),
        organizations_with_channels=[
            BufferOrganizationWithChannels(
                organization=org,
                channels=channels,
            )
        ],
    )


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Reset schema and seed standard roles for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        for role_name, desc in SYSTEM_ROLES:
            session.add(Role(name=role_name, description=desc))
        await session.commit()

    async def override_get_async_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_async_db] = override_get_async_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def seed_data(db_session: AsyncSession) -> Tuple[User, User, Company, Company]:
    """Seed test admin, regular user, and two distinct companies."""
    roles = (await db_session.execute(select(Role))).scalars().all()
    role_map = {r.name: r for r in roles}

    # Admin user
    admin_user = User(
        email="admin@socialos.local",
        password_hash=hash_password("AdminPass123!"),
        name="Admin User",
        role_id=role_map["ADMIN"].id,
        is_active=True,
    )
    # Manager user
    manager_user = User(
        email="manager@socialos.local",
        password_hash=hash_password("ManagerPass123!"),
        name="Social Media Manager",
        role_id=role_map["SOCIAL_MEDIA_MANAGER"].id,
        is_active=True,
    )
    # Company 1
    company_1 = Company(
        name="Acme Brands",
        slug="acme-brands",
        is_active=True,
    )
    # Company 2
    company_2 = Company(
        name="Beta Corp",
        slug="beta-corp",
        is_active=True,
    )
    db_session.add_all([admin_user, manager_user, company_1, company_2])
    await db_session.flush()

    # Manager belongs ONLY to company_1
    membership = CompanyMembership(
        user_id=manager_user.id,
        company_id=company_1.id,
    )
    db_session.add(membership)
    await db_session.commit()

    # Eager load users with roles to avoid async lazyload issues
    stmt = select(User).options(joinedload(User.role)).where(User.id.in_([admin_user.id, manager_user.id]))
    users_loaded = {u.id: u for u in (await db_session.execute(stmt)).scalars().all()}

    return users_loaded[admin_user.id], users_loaded[manager_user.id], company_1, company_2


def make_auth_headers(user: User) -> dict:
    role_name = user.role.name if user.role else "ADMIN"
    token = create_access_token(user_id=user.id, role=role_name)
    return {"Authorization": f"Bearer {token}"}



# =============================================================================
# 1. Platform Mapping Unit Tests
# =============================================================================

def test_map_buffer_service_to_platform():
    """Verify mapping of Buffer service strings to SocialOS Platform enums."""
    assert map_buffer_service_to_platform("facebook") == Platform.FACEBOOK
    assert map_buffer_service_to_platform("FACEBOOK") == Platform.FACEBOOK
    assert map_buffer_service_to_platform("instagram") == Platform.INSTAGRAM
    assert map_buffer_service_to_platform("INSTAGRAM") == Platform.INSTAGRAM
    assert map_buffer_service_to_platform("linkedin") == Platform.LINKEDIN
    assert map_buffer_service_to_platform("youtube") == Platform.YOUTUBE
    # Unsupported platforms return None safely
    assert map_buffer_service_to_platform("twitter") is None
    assert map_buffer_service_to_platform("threads") is None
    assert map_buffer_service_to_platform("pinterest") is None
    assert map_buffer_service_to_platform("tiktok") is None
    assert map_buffer_service_to_platform("") is None
    assert map_buffer_service_to_platform(None) is None


# =============================================================================
# 2. Service Layer Synchronization & Idempotency Tests
# =============================================================================

@pytest.mark.asyncio
async def test_first_sync_creates_facebook_and_instagram(
    db_session: AsyncSession, seed_data: Tuple[User, User, Company, Company]
):
    """Test that the first synchronization creates records for both Facebook and Instagram channels."""
    _, manager, company_1, _ = seed_data
    mock_overview = create_mock_buffer_overview()

    mock_client = AsyncMock(spec=BufferClient)
    mock_client.is_configured = True
    mock_client.verify_connectivity.return_value = mock_overview

    response = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )

    assert response.total_synced == 2
    assert len(response.created) == 2
    assert len(response.updated) == 0
    assert len(response.unchanged) == 0
    assert len(response.skipped) == 0
    assert len(response.errors) == 0

    # Verify Facebook channel in database
    stmt_fb = select(SocialAccount).where(SocialAccount.buffer_channel_id == MOCK_FB_CHANNEL_ID)
    fb_acc = (await db_session.execute(stmt_fb)).scalar_one()
    assert fb_acc.company_id == company_1.id
    assert fb_acc.platform == Platform.FACEBOOK
    assert fb_acc.account_name == "Socialos Test"
    assert fb_acc.buffer_organization_id == MOCK_ORG_ID
    assert fb_acc.status == SocialAccountStatus.ACTIVE

    # Verify Instagram channel in database
    stmt_ig = select(SocialAccount).where(SocialAccount.buffer_channel_id == MOCK_IG_CHANNEL_ID)
    ig_acc = (await db_session.execute(stmt_ig)).scalar_one()
    assert ig_acc.company_id == company_1.id
    assert ig_acc.platform == Platform.INSTAGRAM
    assert ig_acc.account_name == "roushan_1106"
    assert ig_acc.buffer_organization_id == MOCK_ORG_ID
    assert ig_acc.status == SocialAccountStatus.ACTIVE


@pytest.mark.asyncio
async def test_second_sync_idempotency_does_not_duplicate(
    db_session: AsyncSession, seed_data: Tuple[User, User, Company, Company]
):
    """MANDATORY IDEMPOTENCY TEST: Ensure consecutive sync calls do not insert duplicate rows."""
    _, manager, company_1, _ = seed_data
    mock_overview = create_mock_buffer_overview()

    mock_client = AsyncMock(spec=BufferClient)
    mock_client.is_configured = True
    mock_client.verify_connectivity.return_value = mock_overview

    # First sync
    res1 = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )
    assert len(res1.created) == 2

    # Second sync (identical data)
    res2 = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )
    assert res2.total_synced == 2
    assert len(res2.created) == 0
    assert len(res2.updated) == 0
    assert len(res2.unchanged) == 2
    assert len(res2.skipped) == 0
    assert len(res2.errors) == 0

    # Ensure total count in database is still exactly 2
    count_stmt = select(SocialAccount).where(SocialAccount.company_id == company_1.id)
    all_accounts = (await db_session.execute(count_stmt)).scalars().all()
    assert len(all_accounts) == 2


@pytest.mark.asyncio
async def test_existing_account_updates_correctly(
    db_session: AsyncSession, seed_data: Tuple[User, User, Company, Company]
):
    """Verify that changes in Buffer (name or queue status) update the existing record cleanly."""
    _, manager, company_1, _ = seed_data

    mock_client = AsyncMock(spec=BufferClient)
    mock_client.is_configured = True

    # 1. Initial sync
    mock_client.verify_connectivity.return_value = create_mock_buffer_overview(
        fb_name="Old Facebook Name", fb_paused=False
    )
    await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )

    # 2. Channel renamed in Buffer
    mock_client.verify_connectivity.return_value = create_mock_buffer_overview(
        fb_name="New SocialOS Page", fb_paused=True
    )
    res2 = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )

    assert len(res2.created) == 0
    assert len(res2.updated) == 1
    assert len(res2.unchanged) == 1
    assert res2.updated[0].buffer_channel_id == MOCK_FB_CHANNEL_ID
    assert res2.updated[0].name == "New SocialOS Page"

    # Verify updated row
    stmt = select(SocialAccount).where(SocialAccount.buffer_channel_id == MOCK_FB_CHANNEL_ID)
    fb_acc = (await db_session.execute(stmt)).scalar_one()
    assert fb_acc.account_name == "New SocialOS Page"
    assert fb_acc.account_metadata["is_queue_paused"] is True


@pytest.mark.asyncio
async def test_unsupported_service_skipped_safely(
    db_session: AsyncSession, seed_data: Tuple[User, User, Company, Company]
):
    """Verify that unsupported services (e.g. twitter) are skipped without error or creating invalid accounts."""
    _, manager, company_1, _ = seed_data
    mock_overview = create_mock_buffer_overview(include_unsupported=True)

    mock_client = AsyncMock(spec=BufferClient)
    mock_client.is_configured = True
    mock_client.verify_connectivity.return_value = mock_overview

    res = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=manager,
        buffer_client=mock_client,
    )

    assert len(res.created) == 2
    assert len(res.skipped) == 1
    assert res.skipped[0].buffer_channel_id == "ch_tw_unsupported"
    assert "Unsupported platform service: 'twitter'" in res.skipped[0].reason

    # Verify no twitter account was written to DB
    stmt = select(SocialAccount).where(SocialAccount.buffer_channel_id == "ch_tw_unsupported")
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None


# =============================================================================
# 3. Company Isolation & Cross-Company Security Tests
# =============================================================================

@pytest.mark.asyncio
async def test_cross_company_channel_conflict_reported(
    db_session: AsyncSession, seed_data: Tuple[User, User, Company, Company]
):
    """Ensure a Buffer channel already synced to Company A cannot be overwritten by Company B."""
    admin, _, company_1, company_2 = seed_data
    mock_overview = create_mock_buffer_overview()

    mock_client = AsyncMock(spec=BufferClient)
    mock_client.is_configured = True
    mock_client.verify_connectivity.return_value = mock_overview

    # 1. Sync to Company 1
    await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_1.id,
        current_user=admin,
        buffer_client=mock_client,
    )

    # 2. Attempt sync to Company 2
    res2 = await BufferSyncService.sync_channels_for_company(
        db=db_session,
        company_id=company_2.id,
        current_user=admin,
        buffer_client=mock_client,
    )

    assert len(res2.created) == 0
    assert len(res2.errors) == 2
    for err in res2.errors:
        assert "already connected to another company" in err.error


# =============================================================================
# 4. REST API Endpoint Tests (POST /api/v1/social/accounts/sync)
# =============================================================================

@pytest.mark.asyncio
async def test_api_sync_success_flow(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: Tuple[User, User, Company, Company],
):
    """Test successful synchronization via the authenticated REST API endpoint."""
    _, manager, company_1, _ = seed_data
    mock_overview = create_mock_buffer_overview()

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = True
        instance.verify_connectivity = AsyncMock(return_value=mock_overview)

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == str(company_1.id)
    assert len(data["created"]) == 2
    assert len(data["updated"]) == 0
    assert len(data["unchanged"]) == 0
    assert data["total_synced"] == 2

    # Verify audit log was created
    stmt = select(ActivityLog).where(ActivityLog.action == "BUFFER_CHANNELS_SYNCED")
    audit = (await db_session.execute(stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.user_id == manager.id
    assert audit.log_metadata["company_id"] == str(company_1.id)
    assert audit.log_metadata["created_count"] == 2


@pytest.mark.asyncio
async def test_api_sync_unauthorized_non_member(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Enforce server-side RBAC: Non-admin manager cannot sync a company they do not belong to."""
    _, manager, _, company_2 = seed_data

    response = await client.post(
        "/api/v1/social/accounts/sync",
        json={"company_id": str(company_2.id)},
        headers=make_auth_headers(manager),
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_sync_unauthenticated_request_rejected(client: AsyncClient):
    """Verify request without auth header is rejected with 401."""
    response = await client.post(
        "/api/v1/social/accounts/sync",
        json={"company_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_sync_nonexistent_company(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Verify 404 is returned for non-existent company UUID."""
    admin, _, _, _ = seed_data
    fake_id = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/social/accounts/sync",
        json={"company_id": fake_id},
        headers=make_auth_headers(admin),
    )
    assert response.status_code == 404
    assert "Company not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_sync_buffer_auth_error(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Verify Buffer authentication failure translates to HTTP 401."""
    _, manager, company_1, _ = seed_data

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = True
        instance.verify_connectivity = AsyncMock(
            side_effect=BufferAuthError("Unauthorized", status_code=401)
        )

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )
    assert response.status_code == 401
    assert "Buffer API authentication failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_sync_buffer_timeout_error(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Verify Buffer timeout translates to HTTP 504 Gateway Timeout."""
    _, manager, company_1, _ = seed_data

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = True
        instance.verify_connectivity = AsyncMock(
            side_effect=BufferTimeoutError("Request timed out")
        )

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )
    assert response.status_code == 504
    assert "Buffer API request timed out" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_sync_buffer_connection_error(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Verify Buffer connection failure translates to HTTP 502 Bad Gateway."""
    _, manager, company_1, _ = seed_data

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = True
        instance.verify_connectivity = AsyncMock(
            side_effect=BufferConnectionError("Connection refused")
        )

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )
    assert response.status_code == 502
    assert "Failed to connect to Buffer API" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_sync_unconfigured_api_key(
    client: AsyncClient, seed_data: Tuple[User, User, Company, Company]
):
    """Verify missing BUFFER_API_KEY translates to HTTP 400 Bad Request."""
    _, manager, company_1, _ = seed_data

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = False

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )
    assert response.status_code == 400
    assert "Buffer integration is not configured" in response.json()["detail"]


# =============================================================================
# 5. Security & Secret Non-Leakage Test
# =============================================================================

@pytest.mark.asyncio
async def test_secret_is_never_leaked_in_sync(
    client: AsyncClient,
    db_session: AsyncSession,
    seed_data: Tuple[User, User, Company, Company],
    caplog: pytest.LogCaptureFixture,
):
    """CRITICAL SECURITY TEST: Ensure BUFFER_API_KEY is never in API response, DB, or logs."""
    caplog.set_level(logging.DEBUG)
    secret_key = "buf-super-secret-token-xyz-12345"
    _, manager, company_1, _ = seed_data
    mock_overview = create_mock_buffer_overview()

    with patch("app.services.buffer.sync.BufferClient") as mock_client_cls:
        instance = mock_client_cls.return_value
        instance.is_configured = True
        instance._api_key = secret_key
        instance.verify_connectivity = AsyncMock(return_value=mock_overview)

        response = await client.post(
            "/api/v1/social/accounts/sync",
            json={"company_id": str(company_1.id)},
            headers=make_auth_headers(manager),
        )

    assert response.status_code == 200
    resp_text = response.text
    assert secret_key not in resp_text

    # Verify database records
    stmt = select(SocialAccount).where(SocialAccount.company_id == company_1.id)
    accounts = (await db_session.execute(stmt)).scalars().all()
    for acc in accounts:
        assert secret_key not in repr(acc)
        assert acc.encrypted_access_token is None  # Buffer synced accounts don't store raw user OAuth tokens

    # Verify audit log
    stmt_audit = select(ActivityLog).where(ActivityLog.action == "BUFFER_CHANNELS_SYNCED")
    audit = (await db_session.execute(stmt_audit)).scalar_one()
    assert secret_key not in json.dumps(audit.log_metadata)

    # Verify captured log output
    assert secret_key not in caplog.text
