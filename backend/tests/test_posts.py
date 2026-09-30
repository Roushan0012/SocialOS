"""Step 12A — Post Creation Foundation Test Suite.

Covers:
1. Authenticated user can create a post
2. Post with Facebook target succeeds
3. Post with Instagram target succeeds
4. Post with Facebook + Instagram targets succeeds
5. User without company membership receives 403 Forbidden
6. Nonexistent company returns 404 Not Found
7. Social account from another company is rejected (400 Bad Request)
8. Mixed-company targets reject the entire request (atomic rejection)
9. Disconnected social account is rejected (400 Bad Request)
10. Unknown social account is rejected (404 Not Found)
11. Duplicate target IDs handled correctly (deduplicated)
12. Database transaction rolls back on target validation failure
13. Response does not expose credentials/tokens/secrets
14. Audit event is created with safe metadata
15. Post with scheduled_at metadata succeeds
16. Unauthenticated request rejected (401 Unauthorized)
"""
from datetime import datetime, timezone
import json
from typing import Tuple
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
from app.models.enums import Platform, PostStatus, PostTargetStatus, SocialAccountStatus
from app.models.post import Post
from app.models.post_target import PostTarget
from app.models.role import Role
from app.models.social_account import SocialAccount
from app.models.user import User

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
    """Seed test admin, regular user, two companies, memberships, and social accounts."""
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
    # Manager user (belongs to Company A only)
    manager_user = User(
        email="manager@socialos.local",
        password_hash=hash_password("ManagerPass123!"),
        name="Social Media Manager",
        role_id=role_map["SOCIAL_MEDIA_MANAGER"].id,
        is_active=True,
    )
    # Outsider user (belongs to Company B only)
    outsider_user = User(
        email="outsider@socialos.local",
        password_hash=hash_password("OutsiderPass123!"),
        name="Outsider User",
        role_id=role_map["CONTENT_CREATOR"].id,
        is_active=True,
    )
    # Company A (Primary brand)
    company_a = Company(
        name="Acme Brand A",
        slug="acme-brand-a",
        is_active=True,
    )
    # Company B (Secondary brand)
    company_b = Company(
        name="Beta Brand B",
        slug="beta-brand-b",
        is_active=True,
    )
    db_session.add_all([admin_user, manager_user, outsider_user, company_a, company_b])
    await db_session.flush()

    # Memberships
    # Manager -> Company A
    db_session.add(
        CompanyMembership(company_id=company_a.id, user_id=manager_user.id)
    )
    # Outsider -> Company B
    db_session.add(
        CompanyMembership(company_id=company_b.id, user_id=outsider_user.id)
    )

    # Social Accounts for Company A
    fb_account_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.FACEBOOK,
        account_name="Acme FB Page",
        platform_account_id="fb_page_1001",
        buffer_channel_id="buf_fb_1001",
        status=SocialAccountStatus.ACTIVE,
        encrypted_access_token="enc_secret_access_token_fb",
        encrypted_refresh_token="enc_secret_refresh_token_fb",
    )
    ig_account_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.INSTAGRAM,
        account_name="acme_instagram",
        platform_account_id="ig_page_1002",
        buffer_channel_id="buf_ig_1002",
        status=SocialAccountStatus.ACTIVE,
        encrypted_access_token="enc_secret_access_token_ig",
    )
    disconnected_acc_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.LINKEDIN,
        account_name="Acme LinkedIn Corp",
        platform_account_id="li_page_1003",
        status=SocialAccountStatus.DISCONNECTED,
    )

    # Social Account for Company B
    fb_account_b = SocialAccount(
        company_id=company_b.id,
        platform=Platform.FACEBOOK,
        account_name="Beta FB Page",
        platform_account_id="fb_page_2001",
        buffer_channel_id="buf_fb_2001",
        status=SocialAccountStatus.ACTIVE,
        encrypted_access_token="enc_secret_access_token_b",
    )

    db_session.add_all([fb_account_a, ig_account_a, disconnected_acc_a, fb_account_b])
    await db_session.commit()

    # Eager load users with roles to avoid async lazyload MissingGreenlet issues
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
        "fb_account_b": fb_account_b,
    }


def auth_header(user: User) -> dict:
    """Generate Authorization header with valid JWT token."""
    role_name = user.role.name if user.role else "SOCIAL_MEDIA_MANAGER"
    token = create_access_token(user_id=user.id, role=role_name)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Successful Post Creation Scenarios
# =============================================================================


async def test_authenticated_user_can_create_post(client: AsyncClient, seed_env: dict):
    """Scenario 1: Authenticated member user can create a post with target channel."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Exciting new product launch announcement!",
        "social_account_ids": [str(fb_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["company_id"] == str(company.id)
    assert data["caption"] == "Exciting new product launch announcement!"
    assert data["status"] == "DRAFT"
    assert data["scheduled_at"] is None
    assert len(data["targets"]) == 1

    target = data["targets"][0]
    assert target["social_account_id"] == str(fb_acc.id)
    assert target["platform"] == "FACEBOOK"
    assert target["account_name"] == "Acme FB Page"
    assert target["status"] == "PENDING"


async def test_post_with_facebook_target_succeeds(client: AsyncClient, seed_env: dict):
    """Scenario 2: Post with Facebook target channel succeeds."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Post exclusively for Facebook",
        "social_account_ids": [str(fb_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["targets"]) == 1
    assert data["targets"][0]["platform"] == "FACEBOOK"
    assert data["targets"][0]["status"] == "PENDING"


async def test_post_with_instagram_target_succeeds(client: AsyncClient, seed_env: dict):
    """Scenario 3: Post with Instagram target channel succeeds."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    ig_acc = seed_env["ig_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Photo caption for Instagram #brand",
        "social_account_ids": [str(ig_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["targets"]) == 1
    assert data["targets"][0]["platform"] == "INSTAGRAM"
    assert data["targets"][0]["account_name"] == "acme_instagram"
    assert data["targets"][0]["status"] == "PENDING"


async def test_post_with_facebook_and_instagram_targets_succeeds(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 4: Multi-platform post with Facebook + Instagram targets succeeds."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]
    ig_acc = seed_env["ig_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Omnichannel announcement across FB and IG!",
        "social_account_ids": [str(fb_acc.id), str(ig_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["targets"]) == 2

    platforms = {t["platform"] for t in data["targets"]}
    assert platforms == {"FACEBOOK", "INSTAGRAM"}
    for t in data["targets"]:
        assert t["status"] == "PENDING"

    # Verify database persistence
    post_id = uuid.UUID(data["id"])
    db_post = await db_session.get(Post, post_id)
    assert db_post is not None
    assert db_post.company_id == company.id

    targets_stmt = select(PostTarget).where(PostTarget.post_id == post_id)
    db_targets = list((await db_session.execute(targets_stmt)).scalars().all())
    assert len(db_targets) == 2


async def test_post_with_scheduled_at_metadata(client: AsyncClient, seed_env: dict):
    """Scenario 15: Post with optional scheduled_at metadata succeeds with SCHEDULED status."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    future_time = datetime(2026, 12, 25, 12, 0, 0, tzinfo=timezone.utc)
    payload = {
        "company_id": str(company.id),
        "caption": "Holiday greeting post",
        "social_account_ids": [str(fb_acc.id)],
        "scheduled_at": future_time.isoformat(),
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SCHEDULED"
    assert data["scheduled_at"] is not None


# =============================================================================
# 2. Authorization & Company Isolation Scenarios (CRITICAL BOUNDARY)
# =============================================================================


async def test_user_without_company_membership_receives_403(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 5: User without membership in the target company receives 403 Forbidden."""
    outsider = seed_env["outsider_user"]  # Member of Company B only
    company_a = seed_env["company_a"]
    fb_acc_a = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company_a.id),
        "caption": "Unauthorized post attempt",
        "social_account_ids": [str(fb_acc_a.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(outsider),
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]

    # Verify no post was created
    count_stmt = select(func.count(Post.id))
    assert (await db_session.execute(count_stmt)).scalar() == 0


async def test_nonexistent_company_returns_404(client: AsyncClient, seed_env: dict):
    """Scenario 6: Nonexistent company ID returns 404 Not Found."""
    user = seed_env["manager_user"]
    fb_acc = seed_env["fb_account_a"]
    random_company_id = uuid.uuid4()

    payload = {
        "company_id": str(random_company_id),
        "caption": "Post for ghost company",
        "social_account_ids": [str(fb_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 404
    assert "Company not found" in resp.json()["detail"]


async def test_social_account_from_another_company_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 7: Targeting a social account belonging to another company is strictly rejected."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    fb_acc_b = seed_env["fb_account_b"]  # Belongs to Company B!

    payload = {
        "company_id": str(company_a.id),
        "caption": "Attempting cross-brand dispatch",
        "social_account_ids": [str(fb_acc_b.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "Brand isolation violation" in resp.json()["detail"]

    # Verify no post created
    count_stmt = select(func.count(Post.id))
    assert (await db_session.execute(count_stmt)).scalar() == 0


async def test_mixed_company_targets_reject_entire_request(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 8: Mixed-company targets reject the ENTIRE request (no partial post)."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    fb_acc_a = seed_env["fb_account_a"]  # Company A
    fb_acc_b = seed_env["fb_account_b"]  # Company B

    payload = {
        "company_id": str(company_a.id),
        "caption": "Sneaking foreign target into valid batch",
        "social_account_ids": [str(fb_acc_a.id), str(fb_acc_b.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "Brand isolation violation" in resp.json()["detail"]

    # CRITICAL: Verify NO post or target was created for Company A
    assert (await db_session.execute(select(func.count(Post.id)))).scalar() == 0
    assert (await db_session.execute(select(func.count(PostTarget.id)))).scalar() == 0


# =============================================================================
# 3. Account Status & Target Validation Scenarios
# =============================================================================


async def test_disconnected_social_account_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 9: Targeting a disconnected or inactive social account is rejected."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    disconnected_acc = seed_env["disconnected_acc_a"]

    payload = {
        "company_id": str(company_a.id),
        "caption": "Post to disconnected LinkedIn",
        "social_account_ids": [str(disconnected_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 400
    assert "disconnected or inactive" in resp.json()["detail"]

    assert (await db_session.execute(select(func.count(Post.id)))).scalar() == 0


async def test_unknown_social_account_rejected(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 10: Unknown/nonexistent social account ID returns 404."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    fake_acc_id = uuid.uuid4()

    payload = {
        "company_id": str(company_a.id),
        "caption": "Post to ghost account",
        "social_account_ids": [str(fake_acc_id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]

    assert (await db_session.execute(select(func.count(Post.id)))).scalar() == 0


async def test_duplicate_target_ids_handled_correctly(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 11: Duplicate target IDs in request are safely deduplicated."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company_a.id),
        "caption": "Post with duplicate target list",
        # Same account supplied twice
        "social_account_ids": [str(fb_acc.id), str(fb_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()

    # Deduplicated to exactly 1 target
    assert len(data["targets"]) == 1

    post_id = uuid.UUID(data["id"])
    targets_count = (
        await db_session.execute(
            select(func.count(PostTarget.id)).where(PostTarget.post_id == post_id)
        )
    ).scalar()
    assert targets_count == 1


async def test_database_transaction_rolls_back_on_target_validation_failure(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 12: DB transaction rolls back completely on validation failure."""
    user = seed_env["manager_user"]
    company_a = seed_env["company_a"]
    fb_acc_a = seed_env["fb_account_a"]
    fake_acc_id = uuid.uuid4()

    payload = {
        "company_id": str(company_a.id),
        "caption": "Valid caption",
        "social_account_ids": [str(fb_acc_a.id), str(fake_acc_id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 404

    # Ensure zero residual posts or targets
    assert (await db_session.execute(select(func.count(Post.id)))).scalar() == 0
    assert (await db_session.execute(select(func.count(PostTarget.id)))).scalar() == 0


# =============================================================================
# 4. Security, Non-Leakage & Audit Logging Scenarios
# =============================================================================


async def test_response_does_not_expose_credentials_or_tokens(
    client: AsyncClient, seed_env: dict
):
    """Scenario 13: Response never exposes tokens, secrets, or internal keys."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Checking for security leaks",
        "social_account_ids": [str(fb_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    resp_text = resp.text

    # Verify no tokens or sensitive tokens leaked
    assert "enc_secret_access_token" not in resp_text
    assert "enc_secret_refresh_token" not in resp_text
    assert "password_hash" not in resp_text
    assert "encrypted_access_token" not in resp_text
    assert "encrypted_refresh_token" not in resp_text


async def test_audit_event_is_created_on_post_creation(
    client: AsyncClient, seed_env: dict, db_session: AsyncSession
):
    """Scenario 14: Audit event is recorded with action 'POST_CREATED' and safe metadata."""
    user = seed_env["manager_user"]
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]
    ig_acc = seed_env["ig_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Audited post creation",
        "social_account_ids": [str(fb_acc.id), str(ig_acc.id)],
    }

    resp = await client.post(
        "/api/v1/posts",
        json=payload,
        headers=auth_header(user),
    )
    assert resp.status_code == 201
    data = resp.json()
    post_id = uuid.UUID(data["id"])

    # Query audit logs
    stmt = select(ActivityLog).where(
        ActivityLog.action == "POST_CREATED",
        ActivityLog.entity_id == post_id,
    )
    audit = (await db_session.execute(stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.user_id == user.id
    assert audit.entity_type == "post"
    assert audit.log_metadata["company_id"] == str(company.id)
    assert audit.log_metadata["target_count"] == 2
    assert set(audit.log_metadata["platforms"]) == {"FACEBOOK", "INSTAGRAM"}


async def test_unauthenticated_request_rejected(client: AsyncClient, seed_env: dict):
    """Scenario 16: Request without valid authentication token is rejected with 401."""
    company = seed_env["company_a"]
    fb_acc = seed_env["fb_account_a"]

    payload = {
        "company_id": str(company.id),
        "caption": "Unauthenticated attempt",
        "social_account_ids": [str(fb_acc.id)],
    }

    resp = await client.post("/api/v1/posts", json=payload)
    assert resp.status_code == 401
