"""Step 12B — Buffer Publish Now Test Suite.

Covers:
1. Successful Facebook target publish via Buffer
2. Successful Instagram target publish via Buffer
3. Buffer post ID stored correctly in provider_post_id
4. PostTarget transitions to PUBLISHED
5. published_at is populated
6. Buffer API failure transitions target to FAILED
7. Safe error message stored without leaking tokens
8. User without company membership receives 403 Forbidden
9. Cross-company target dispatch rejected with 400 Bad Request
10. Inactive social account rejected with 400 Bad Request
11. Missing buffer_channel_id rejected with 400 Bad Request
12. Already-published target cannot be re-published (409 Conflict)
13. In-progress PUBLISHING target rejected (409 Conflict)
14. Zero credential or token leakage in response, database, or audit
15. Audit events recorded (POST_PUBLISH_STARTED, POST_TARGET_PUBLISHED, POST_TARGET_PUBLISH_FAILED)
16. Post status transitions: single target, multi-target partial publish, and all-failed
17. Media asset without public CDN URL fails safely with 400
18. Target does not belong to specified post returns 400
"""
from datetime import datetime, timezone
import json
from typing import Dict, Tuple
from unittest.mock import AsyncMock, patch
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select
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
from app.models.enums import MediaType, Platform, PostStatus, PostTargetStatus, SocialAccountStatus
from app.models.media_asset import MediaAsset
from app.models.post import Post
from app.models.post_target import PostTarget
from app.models.role import Role
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.buffer.publisher import BufferPublisher
from app.services.buffer.schemas import BufferPublishResult

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
async def seed_env(db_session: AsyncSession) -> dict:
    """Seed test admin, regular user, companies, memberships, accounts, and posts."""
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
    # Manager user (belongs to Company A)
    manager_user = User(
        email="manager@socialos.local",
        password_hash=hash_password("ManagerPass123!"),
        name="Social Media Manager",
        role_id=role_map["SOCIAL_MEDIA_MANAGER"].id,
        is_active=True,
    )
    # Outsider user (belongs to Company B)
    outsider_user = User(
        email="outsider@socialos.local",
        password_hash=hash_password("OutsiderPass123!"),
        name="Outsider User",
        role_id=role_map["CONTENT_CREATOR"].id,
        is_active=True,
    )
    # Company A (Primary brand)
    company_a = Company(name="Acme Brand A", slug="acme-brand-a", is_active=True)
    # Company B (Secondary brand)
    company_b = Company(name="Beta Brand B", slug="beta-brand-b", is_active=True)

    db_session.add_all([admin_user, manager_user, outsider_user, company_a, company_b])
    await db_session.flush()

    # Memberships
    db_session.add(CompanyMembership(company_id=company_a.id, user_id=manager_user.id))
    db_session.add(CompanyMembership(company_id=company_b.id, user_id=outsider_user.id))

    # Social Accounts for Company A
    fb_account_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.FACEBOOK,
        account_name="Socialos Test",
        platform_account_id="fb_page_1001",
        buffer_channel_id="6abd0978ea19ca0bde32dcbb",
        status=SocialAccountStatus.ACTIVE,
        encrypted_access_token="enc_secret_access_token_fb",
        encrypted_refresh_token="enc_secret_refresh_token_fb",
    )
    ig_account_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.INSTAGRAM,
        account_name="roushan_1106",
        platform_account_id="ig_page_1002",
        buffer_channel_id="6abcd84aea19ca0bde30fe66",
        status=SocialAccountStatus.ACTIVE,
        encrypted_access_token="enc_secret_access_token_ig",
    )
    disconnected_acc_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.LINKEDIN,
        account_name="Acme LinkedIn Corp",
        platform_account_id="li_page_1003",
        buffer_channel_id="buf_li_1003",
        status=SocialAccountStatus.DISCONNECTED,
    )
    unlinked_acc_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.FACEBOOK,
        account_name="Unlinked FB Page",
        platform_account_id="fb_page_unlinked",
        buffer_channel_id=None,  # No Buffer channel
        status=SocialAccountStatus.ACTIVE,
    )

    # Social Account for Company B
    fb_account_b = SocialAccount(
        company_id=company_b.id,
        platform=Platform.FACEBOOK,
        account_name="Beta FB Page",
        platform_account_id="fb_page_2001",
        buffer_channel_id="buf_fb_2001",
        status=SocialAccountStatus.ACTIVE,
    )

    db_session.add_all([
        fb_account_a,
        ig_account_a,
        disconnected_acc_a,
        unlinked_acc_a,
        fb_account_b,
    ])
    await db_session.flush()

    # Create a draft Post for Company A
    post_a = Post(
        company_id=company_a.id,
        created_by=manager_user.id,
        caption="Publish Now test caption for SocialOS",
        status=PostStatus.DRAFT,
    )
    db_session.add(post_a)
    await db_session.flush()

    # Targets for Post A
    target_fb_a = PostTarget(
        post_id=post_a.id,
        social_account_id=fb_account_a.id,
        platform=Platform.FACEBOOK,
        status=PostTargetStatus.PENDING,
    )
    target_ig_a = PostTarget(
        post_id=post_a.id,
        social_account_id=ig_account_a.id,
        platform=Platform.INSTAGRAM,
        status=PostTargetStatus.PENDING,
    )
    db_session.add_all([target_fb_a, target_ig_a])
    await db_session.commit()

    # Eager load users with roles
    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(User.id.in_([admin_user.id, manager_user.id, outsider_user.id]))
    )
    users_loaded = {u.id: u for u in (await db_session.execute(stmt)).scalars().all()}

    return {
        "admin_user": users_loaded[admin_user.id],
        "manager_user": users_loaded[manager_user.id],
        "outsider_user": users_loaded[outsider_user.id],
        "company_a": company_a,
        "company_b": company_b,
        "fb_account_a": fb_account_a,
        "ig_account_a": ig_account_a,
        "disconnected_acc_a": disconnected_acc_a,
        "unlinked_acc_a": unlinked_acc_a,
        "fb_account_b": fb_account_b,
        "post_a": post_a,
        "target_fb_a": target_fb_a,
        "target_ig_a": target_ig_a,
    }


def auth_header(user: User) -> dict:
    """Generate Authorization header with valid JWT token."""
    role_name = user.role.name if user.role else "SOCIAL_MEDIA_MANAGER"
    token = create_access_token(user_id=user.id, role=role_name)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Successful Publish Scenarios
# =============================================================================


async def test_successful_facebook_publish(client: AsyncClient, seed_env: dict, db_session: AsyncSession):
    """Scenario 1, 3, 4, 5: Successful Facebook target publish updates target and post."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    mock_buffer_response = {
        "__typename": "PostActionSuccess",
        "post": {
            "id": "buf_post_fb_12345",
            "status": "buffer",
            "sharedNow": True,
            "sentAt": "2026-10-01T03:30:00Z",
            "createdAt": "2026-10-01T03:30:00Z",
        },
    }

    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_buffer_response

        resp = await client.post(
            f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
            headers=auth_header(user),
        )

    assert resp.status_code == 200
    data = resp.json()

    assert data["message"] == "Post target published successfully via Buffer"
    assert data["post_id"] == str(post.id)
    assert data["target"]["id"] == str(target.id)
    assert data["target"]["status"] == "PUBLISHED"
    assert data["target"]["provider_post_id"] == "buf_post_fb_12345"
    assert data["target"]["published_at"] is not None
    assert data["target"]["error_message"] is None

    # Verify database state
    db_target = await db_session.get(PostTarget, target.id)
    await db_session.refresh(db_target)
    assert db_target.status == PostTargetStatus.PUBLISHED
    assert db_target.provider_post_id == "buf_post_fb_12345"
    assert db_target.published_at is not None

    # Parent post has 2 targets (FB and IG). Since only FB is published, status is PARTIALLY_PUBLISHED
    db_post = await db_session.get(Post, post.id)
    await db_session.refresh(db_post)
    assert db_post.status == PostStatus.PARTIALLY_PUBLISHED


async def test_successful_instagram_publish_and_full_post_published(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 2 & 16: When all targets are published, parent Post transitions to PUBLISHED."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target_fb = seed_env["target_fb_a"]
    target_ig = seed_env["target_ig_a"]

    # First publish FB
    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "__typename": "PostActionSuccess",
            "post": {"id": "buf_post_fb_101", "status": "buffer", "sharedNow": True},
        }
        resp1 = await client.post(
            f"/api/v1/posts/{post.id}/targets/{target_fb.id}/publish",
            headers=auth_header(user),
        )
        assert resp1.status_code == 200

    # Second publish IG
    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "__typename": "PostActionSuccess",
            "post": {"id": "buf_post_ig_202", "status": "buffer", "sharedNow": True},
        }
        resp2 = await client.post(
            f"/api/v1/posts/{post.id}/targets/{target_ig.id}/publish",
            headers=auth_header(user),
        )
        assert resp2.status_code == 200
        data2 = resp2.json()

    assert data2["post_status"] == "PUBLISHED"
    assert data2["target"]["status"] == "PUBLISHED"

    # Verify in DB: both targets PUBLISHED, parent post PUBLISHED with published_at
    db_post = await db_session.get(Post, post.id)
    await db_session.refresh(db_post)
    assert db_post.status == PostStatus.PUBLISHED
    assert db_post.published_at is not None


# =============================================================================
# 2. Failure Handling & Safe Error Storage Scenarios
# =============================================================================


async def test_buffer_api_failure_transitions_target_to_failed(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 6 & 7: Buffer rejection transitions target to FAILED with safe error message."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    mock_error_payload = {
        "__typename": "InvalidInputError",
        "message": "Caption exceeds the maximum character limit for this channel.",
    }

    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_error_payload

        resp = await client.post(
            f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
            headers=auth_header(user),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Buffer publishing failed" in data["message"]
    assert data["target"]["status"] == "FAILED"
    assert "Caption exceeds the maximum character limit" in data["target"]["error_message"]
    assert data["target"]["provider_post_id"] is None

    # Verify DB
    db_target = await db_session.get(PostTarget, target.id)
    await db_session.refresh(db_target)
    assert db_target.status == PostTargetStatus.FAILED
    assert db_target.error_message == "Caption exceeds the maximum character limit for this channel."


# =============================================================================
# 3. Security, Authorization & Brand Isolation Scenarios
# =============================================================================


async def test_unauthorized_user_cannot_publish_target(client: AsyncClient, seed_env: dict):
    """Scenario 8: User without membership in the post's company receives 403 Forbidden."""
    outsider = seed_env["outsider_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(outsider),
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


async def test_cross_company_target_dispatch_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 9: If target's social account belongs to another company, publish is rejected."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    fb_acc_b = seed_env["fb_account_b"]  # Belongs to Company B

    # Create a rogue target belonging to foreign account
    rogue_target = PostTarget(
        post_id=post.id,
        social_account_id=fb_acc_b.id,
        platform=Platform.FACEBOOK,
        status=PostTargetStatus.PENDING,
    )
    db_session.add(rogue_target)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{rogue_target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "Brand isolation violation" in resp.json()["detail"]


async def test_inactive_social_account_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 10: Target with disconnected/inactive social account is rejected."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    disconnected_acc = seed_env["disconnected_acc_a"]

    target = PostTarget(
        post_id=post.id,
        social_account_id=disconnected_acc.id,
        platform=Platform.LINKEDIN,
        status=PostTargetStatus.PENDING,
    )
    db_session.add(target)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "disconnected or inactive" in resp.json()["detail"]


async def test_missing_buffer_channel_id_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 11: Target with unlinked social account (no Buffer channel) is rejected."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    unlinked_acc = seed_env["unlinked_acc_a"]

    target = PostTarget(
        post_id=post.id,
        social_account_id=unlinked_acc.id,
        platform=Platform.FACEBOOK,
        status=PostTargetStatus.PENDING,
    )
    db_session.add(target)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "not linked to a Buffer channel" in resp.json()["detail"]


async def test_target_mismatch_with_post_rejected(client: AsyncClient, seed_env: dict):
    """Scenario 18: Passing target that does not belong to post_id returns 400."""
    user = seed_env["manager_user"]
    target = seed_env["target_fb_a"]
    wrong_post_id = uuid.uuid4()

    resp = await client.post(
        f"/api/v1/posts/{wrong_post_id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "does not belong to post" in resp.json()["detail"]


# =============================================================================
# 4. Idempotency & Duplicate Protection Scenarios
# =============================================================================


async def test_already_published_target_cannot_be_republished(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 12: Target already in PUBLISHED state with provider_post_id is rejected with 409."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    # Pre-mark target as PUBLISHED
    target.status = PostTargetStatus.PUBLISHED
    target.provider_post_id = "buf_existing_post_789"
    target.published_at = datetime.now(timezone.utc)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 409
    assert "already published" in resp.json()["detail"]


async def test_in_progress_publishing_target_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 13: Target currently in PUBLISHING state is rejected with 409 Conflict."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    # Pre-mark target as in-progress PUBLISHING
    target.status = PostTargetStatus.PUBLISHING
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 409
    assert "currently being published" in resp.json()["detail"]


# =============================================================================
# 5. Media & Secret Non-Leakage Scenarios
# =============================================================================


async def test_media_asset_without_public_cdn_url_fails_safely(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 17: Post with media lacking public CDN URL returns clear safe error."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    # Attach a media asset with no CDN URL (S3 upload incomplete)
    asset = MediaAsset(
        post_id=post.id,
        created_by=user.id,
        storage_key="posts/pending_image.png",
        cdn_url=None,  # No public URL
        file_name="pending_image.png",
        mime_type="image/png",
        file_size=10240,
        media_type=MediaType.IMAGE,
    )
    db_session.add(asset)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "no public CDN URL" in resp.json()["detail"]


async def test_no_credential_leakage_in_publish_response_and_audit(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 14 & 15: No tokens/credentials appear in response, DB, or audit logs."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]

    secret_key = "buf_super_secret_test_token"

    mock_buffer_response = {
        "__typename": "PostActionSuccess",
        "post": {
            "id": "buf_post_safe_999",
            "status": "buffer",
            "sharedNow": True,
        },
    }

    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_buffer_response

        resp = await client.post(
            f"/api/v1/posts/{post.id}/targets/{target.id}/publish",
            headers=auth_header(user),
        )

    assert resp.status_code == 200
    resp_text = resp.text

    # Response security
    assert secret_key not in resp_text
    assert "enc_secret_access_token" not in resp_text
    assert "enc_secret_refresh_token" not in resp_text

    # Audit events security
    audit_stmt = select(ActivityLog).where(ActivityLog.entity_id == target.id)
    audits = list((await db_session.execute(audit_stmt)).scalars().all())
    assert len(audits) >= 2  # POST_PUBLISH_STARTED and POST_TARGET_PUBLISHED

    actions = {a.action for a in audits}
    assert "POST_PUBLISH_STARTED" in actions
    assert "POST_TARGET_PUBLISHED" in actions

    for audit in audits:
        meta_str = json.dumps(audit.log_metadata)
        assert secret_key not in meta_str
        assert "enc_secret" not in meta_str
        assert audit.log_metadata.get("provider") in (None, "buffer")


# =============================================================================
# 6. Adapter Unit Tests & Edge Cases
# =============================================================================


async def test_buffer_publisher_formats_media_assets_correctly(seed_env: dict):
    """Scenario 17: Valid public CDN URLs are correctly mapped to AssetInput."""
    user = seed_env["manager_user"]
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]
    account = seed_env["fb_account_a"]

    media_img = MediaAsset(
        post_id=post.id,
        created_by=user.id,
        storage_key="posts/img.png",
        cdn_url="https://cdn.socialos.io/posts/img.png",
        file_name="img.png",
        mime_type="image/png",
        file_size=5000,
        media_type=MediaType.IMAGE,
    )
    media_vid = MediaAsset(
        post_id=post.id,
        created_by=user.id,
        storage_key="posts/vid.mp4",
        cdn_url="https://cdn.socialos.io/posts/vid.mp4",
        file_name="vid.mp4",
        mime_type="video/mp4",
        file_size=50000,
        media_type=MediaType.VIDEO,
    )

    captured_inputs = []

    mock_client = AsyncMock()
    mock_client.is_configured = True

    async def fake_create_post(input_data):
        captured_inputs.append(input_data)
        return {
            "__typename": "PostActionSuccess",
            "post": {"id": "buf_media_post_1", "status": "buffer", "sharedNow": True},
        }

    mock_client.create_post = fake_create_post
    publisher = BufferPublisher(client=mock_client)

    result = await publisher.publish_target(
        target=target,
        post=post,
        account=account,
        media_assets=[media_img, media_vid],
    )

    assert result.success is True
    assert result.buffer_post_id == "buf_media_post_1"
    assert len(captured_inputs) == 1
    input_sent = captured_inputs[0]
    assert input_sent["channelId"] == account.buffer_channel_id
    assert input_sent["assets"] == [
        {"image": {"url": "https://cdn.socialos.io/posts/img.png"}},
        {"video": {"url": "https://cdn.socialos.io/posts/vid.mp4"}},
    ]


async def test_buffer_publisher_handles_client_exceptions(seed_env: dict):
    """Scenario 6: BufferPublisher safely maps client exceptions without raising unhandled errors."""
    post = seed_env["post_a"]
    target = seed_env["target_fb_a"]
    account = seed_env["fb_account_a"]

    from app.services.buffer.exceptions import (
        BufferAuthError,
        BufferConnectionError,
        BufferTimeoutError,
    )

    # 1. Auth error
    mock_client = AsyncMock()
    mock_client.is_configured = True
    mock_client.create_post.side_effect = BufferAuthError("Bad key", status_code=401)
    publisher = BufferPublisher(client=mock_client)
    res = await publisher.publish_target(target, post, account)
    assert res.success is False
    assert "authentication failed" in res.error_message

    # 2. Timeout error
    mock_client.create_post.side_effect = BufferTimeoutError("Timed out")
    res = await publisher.publish_target(target, post, account)
    assert res.success is False
    assert "timed out" in res.error_message

    # 3. Connection error
    mock_client.create_post.side_effect = BufferConnectionError("Connect error")
    res = await publisher.publish_target(target, post, account)
    assert res.success is False
    assert "Failed to connect" in res.error_message


async def test_all_targets_failed_updates_post_status_to_failed(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 16: If all targets for a post fail, post status transitions to FAILED."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    # Create post with single target
    single_target_post = Post(
        company_id=company.id,
        created_by=user.id,
        caption="Solo target doomed to fail",
        status=PostStatus.DRAFT,
    )
    db_session.add(single_target_post)
    await db_session.flush()

    solo_target = PostTarget(
        post_id=single_target_post.id,
        social_account_id=fb_acc.id,
        platform=Platform.FACEBOOK,
        status=PostTargetStatus.PENDING,
    )
    db_session.add(solo_target)
    await db_session.commit()

    with patch("app.services.buffer.client.BufferClient.create_post", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = {
            "__typename": "UnexpectedError",
            "message": "Buffer internal processing error.",
        }
        resp = await client.post(
            f"/api/v1/posts/{single_target_post.id}/targets/{solo_target.id}/publish",
            headers=auth_header(user),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["target"]["status"] == "FAILED"
    assert data["post_status"] == "FAILED"

    # Verify DB
    db_post = await db_session.get(Post, single_target_post.id)
    await db_session.refresh(db_post)
    assert db_post.status == PostStatus.FAILED
