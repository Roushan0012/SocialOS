"""Step 9 — Social Account Connections & OAuth Foundation Comprehensive Test Suite.

Covers:
- AES-256-GCM token encryption, decryption, tamper detection, zero plaintext leakage
- OAuth state creation, single-use invalidation, TTL expiration, CSRF defense
- Provider adapters (Instagram, Facebook, LinkedIn, YouTube) URL generation, mocked code exchange, identity fetching, refresh
- API endpoints:
  - GET /api/v1/social/oauth/{platform}/start
  - GET /api/v1/social/oauth/{platform}/callback
  - GET /api/v1/social/accounts
  - DELETE /api/v1/social/accounts/{id}
  - POST /api/v1/social/accounts/{id}/refresh
- Company isolation, RBAC permissions, and audit logging
"""
from datetime import datetime, timedelta, timezone
from typing import Tuple
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient, Response
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
from app.models.oauth_state import OAuthState
from app.models.role import Role
from app.models.social_account import SocialAccount
from app.models.user import User
from app.services.encryption_service import (
    TokenDecryptionError,
    TokenEncryptionService,
    decrypt_token,
    encrypt_token,
)
from app.services.oauth_state_manager import (
    ExpiredOAuthStateError,
    InvalidOAuthStateError,
    OAuthStateManager,
)
from app.services.social import (
    FacebookProvider,
    LinkedInProvider,
    OAuthTokenResult,
    SocialAccountIdentity,
    get_social_provider,
)

# Test in-memory engine with StaticPool for fast, isolated async testing
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
    """Clean tables and seed the 5 standard system roles for each test."""
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
    """Independent session for direct database queries in tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    """AsyncClient bound to FastAPI app with test database override."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def create_user_helper(
    db: AsyncSession,
    email: str,
    role_name: str = "SOCIAL_MEDIA_MANAGER",
    name: str = "Test User",
) -> Tuple[User, str]:
    stmt = select(Role).where(Role.name == role_name)
    result = await db.execute(stmt)
    role = result.scalar_one()

    user = User(
        email=email,
        name=name,
        password_hash=hash_password("Password123!"),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user_id=user.id, role=role_name)
    return user, token


async def create_company_helper(db: AsyncSession, name: str, slug: str) -> Company:
    company = Company(name=name, slug=slug, is_active=True)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def add_membership_helper(
    db: AsyncSession, user_id: uuid.UUID, company_id: uuid.UUID
) -> CompanyMembership:
    membership = CompanyMembership(user_id=user_id, company_id=company_id)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


# ==============================================================================
# 1. ENCRYPTION SERVICE UNIT TESTS
# ==============================================================================

def test_encryption_roundtrip():
    token = "ya29.a0AfH6SMCx123456789_very_secret_token"
    encrypted = encrypt_token(token)
    assert encrypted is not None
    assert encrypted.startswith("v1:")
    assert encrypted != token

    decrypted = decrypt_token(encrypted)
    assert decrypted == token


def test_encryption_random_nonce():
    token = "static_token_value"
    enc1 = encrypt_token(token)
    enc2 = encrypt_token(token)
    # Different nonces ensure distinct ciphertexts
    assert enc1 != enc2
    assert decrypt_token(enc1) == token
    assert decrypt_token(enc2) == token


def test_encryption_tamper_detection():
    token = "secret_access_token"
    encrypted = encrypt_token(token)
    # Flip a character in ciphertext portion
    prefix, b64_payload = encrypted.split(":", 1)
    tampered_payload = b64_payload[:-3] + ("A" if b64_payload[-3] != "A" else "B") + b64_payload[-2:]
    tampered_encrypted = f"{prefix}:{tampered_payload}"

    with pytest.raises(TokenDecryptionError) as exc_info:
        decrypt_token(tampered_encrypted)
    # Ensure raw token is NEVER leaked in error message
    assert token not in str(exc_info.value)


def test_encryption_handles_none_and_empty():
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_encryption_invalid_format():
    with pytest.raises(TokenDecryptionError):
        decrypt_token("invalid_format_without_prefix")


# ==============================================================================
# 2. OAUTH STATE MANAGER UNIT TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_oauth_state_lifecycle(db_session: AsyncSession):
    user, _ = await create_user_helper(db_session, "user1@example.com")
    company = await create_company_helper(db_session, "Acme Brand", "acme-brand")

    # 1. Create state
    token = await OAuthStateManager.create_state(
        db=db_session,
        user_id=user.id,
        company_id=company.id,
        platform=Platform.INSTAGRAM,
        ttl_minutes=10,
    )
    assert len(token) > 30

    # 2. Consume state
    consumed = await OAuthStateManager.verify_and_consume_state(
        db=db_session,
        state_token=token,
        platform=Platform.INSTAGRAM,
        expected_user_id=user.id,
    )
    assert consumed.used_at is not None
    assert consumed.company_id == company.id
    assert consumed.platform == Platform.INSTAGRAM

    # 3. Single-use: attempt to re-consume must raise InvalidOAuthStateError
    with pytest.raises(InvalidOAuthStateError):
        await OAuthStateManager.verify_and_consume_state(
            db=db_session,
            state_token=token,
            platform=Platform.INSTAGRAM,
        )


@pytest.mark.asyncio
async def test_oauth_state_platform_mismatch(db_session: AsyncSession):
    user, _ = await create_user_helper(db_session, "user2@example.com")
    company = await create_company_helper(db_session, "Brand Two", "brand-two")

    token = await OAuthStateManager.create_state(
        db=db_session,
        user_id=user.id,
        company_id=company.id,
        platform=Platform.INSTAGRAM,
    )

    with pytest.raises(InvalidOAuthStateError):
        await OAuthStateManager.verify_and_consume_state(
            db=db_session,
            state_token=token,
            platform=Platform.FACEBOOK,
        )


@pytest.mark.asyncio
async def test_oauth_state_expiration(db_session: AsyncSession):
    user, _ = await create_user_helper(db_session, "user3@example.com")
    company = await create_company_helper(db_session, "Brand Three", "brand-three")

    # Create expired state (negative TTL)
    token = await OAuthStateManager.create_state(
        db=db_session,
        user_id=user.id,
        company_id=company.id,
        platform=Platform.LINKEDIN,
        ttl_minutes=-5,
    )

    with pytest.raises(ExpiredOAuthStateError):
        await OAuthStateManager.verify_and_consume_state(
            db=db_session,
            state_token=token,
            platform=Platform.LINKEDIN,
        )


# ==============================================================================
# 3. PROVIDER ADAPTER UNIT TESTS (ALL 4 PLATFORMS)
# ==============================================================================

@pytest.mark.parametrize(
    "platform",
    [Platform.INSTAGRAM, Platform.FACEBOOK, Platform.LINKEDIN, Platform.YOUTUBE],
)
def test_provider_authorization_url(platform: Platform):
    provider = get_social_provider(platform)
    url = provider.get_authorization_url(state="random_state_xyz", redirect_uri="http://localhost:3000/callback")
    assert "random_state_xyz" in url
    assert "http://localhost:3000/callback" in url or "http%3A%2F%2Flocalhost%3A3000%2Fcallback" in url


@pytest.mark.asyncio
async def test_instagram_provider_flow():
    provider = get_social_provider(Platform.INSTAGRAM)
    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.get") as mock_get:
        # Mock token exchange
        mock_post.return_value = Response(
            200,
            json={"access_token": "ig_token_123", "user_id": 12345, "expires_in": 3600},
        )
        tokens = await provider.exchange_code_for_tokens("code_abc")
        assert tokens.access_token == "ig_token_123"

        # Mock identity fetch
        mock_get.return_value = Response(
            200,
            json={"id": "12345", "username": "socialos_insta", "account_type": "BUSINESS"},
        )
        identity = await provider.get_account_identity("ig_token_123")
        assert identity.platform == Platform.INSTAGRAM
        assert identity.platform_account_id == "12345"
        assert identity.account_name == "socialos_insta"

        # Mock refresh
        mock_get.return_value = Response(
            200,
            json={"access_token": "ig_refreshed_token", "expires_in": 7200},
        )
        refreshed = await provider.refresh_tokens("ig_token_123")
        assert refreshed.access_token == "ig_refreshed_token"


@pytest.mark.asyncio
async def test_facebook_provider_flow():
    provider = get_social_provider(Platform.FACEBOOK)
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = Response(
            200,
            json={"access_token": "fb_token_123", "expires_in": 5184000},
        )
        tokens = await provider.exchange_code_for_tokens("fb_code")
        assert tokens.access_token == "fb_token_123"

        mock_get.return_value = Response(
            200,
            json={"id": "fb_acc_999", "name": "SocialOS Brand FB", "picture": {"data": {"url": "https://fb.com/pic.jpg"}}},
        )
        identity = await provider.get_account_identity("fb_token_123")
        assert identity.platform == Platform.FACEBOOK
        assert identity.platform_account_id == "fb_acc_999"
        assert identity.account_name == "SocialOS Brand FB"
        assert identity.avatar_url == "https://fb.com/pic.jpg"


@pytest.mark.asyncio
async def test_linkedin_provider_flow():
    provider = get_social_provider(Platform.LINKEDIN)
    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.get") as mock_get:
        mock_post.return_value = Response(
            200,
            json={"access_token": "li_token_123", "refresh_token": "li_ref_123", "expires_in": 5184000},
        )
        tokens = await provider.exchange_code_for_tokens("li_code")
        assert tokens.access_token == "li_token_123"
        assert tokens.refresh_token == "li_ref_123"

        mock_get.return_value = Response(
            200,
            json={"sub": "li_sub_555", "name": "LinkedIn Company Page", "picture": "https://li.com/avatar.jpg"},
        )
        identity = await provider.get_account_identity("li_token_123")
        assert identity.platform == Platform.LINKEDIN
        assert identity.platform_account_id == "li_sub_555"
        assert identity.account_name == "LinkedIn Company Page"


@pytest.mark.asyncio
async def test_youtube_provider_flow():
    provider = get_social_provider(Platform.YOUTUBE)
    with patch("httpx.AsyncClient.post") as mock_post, patch("httpx.AsyncClient.get") as mock_get:
        mock_post.return_value = Response(
            200,
            json={"access_token": "yt_token_123", "refresh_token": "yt_ref_123", "expires_in": 3600},
        )
        tokens = await provider.exchange_code_for_tokens("yt_code")
        assert tokens.access_token == "yt_token_123"
        assert tokens.refresh_token == "yt_ref_123"

        mock_get.return_value = Response(
            200,
            json={
                "items": [
                    {
                        "id": "UC_TEST_CHANNEL_123",
                        "snippet": {
                            "title": "SocialOS Official Channel",
                            "customUrl": "@socialos",
                            "thumbnails": {"default": {"url": "https://yt.com/thumb.jpg"}},
                        },
                    }
                ]
            },
        )
        identity = await provider.get_account_identity("yt_token_123")
        assert identity.platform == Platform.YOUTUBE
        assert identity.platform_account_id == "UC_TEST_CHANNEL_123"
        assert identity.account_name == "SocialOS Official Channel"


# ==============================================================================
# 4. REST API ENDPOINTS & COMPANY ISOLATION INTEGRATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_oauth_start_endpoint_success(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "member@example.com")
    company = await create_company_helper(db_session, "Company Alpha", "company-alpha")
    await add_membership_helper(db_session, user.id, company.id)

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(
        f"/api/v1/social/oauth/instagram/start?company_id={company.id}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    assert "state" in data
    assert data["platform"] == "INSTAGRAM"
    assert data["state"] in data["authorization_url"]

    # Verify state was saved to database
    stmt = select(OAuthState).where(OAuthState.state_token == data["state"])
    result = await db_session.execute(stmt)
    state_rec = result.scalar_one_or_none()
    assert state_rec is not None
    assert state_rec.company_id == company.id
    assert state_rec.user_id == user.id
    assert state_rec.used_at is None

    # Verify audit log
    stmt_log = select(ActivityLog).where(ActivityLog.action == "OAUTH_CONNECTION_STARTED")
    res_log = await db_session.execute(stmt_log)
    log_rec = res_log.scalar_one_or_none()
    assert log_rec is not None
    assert log_rec.user_id == user.id


@pytest.mark.asyncio
async def test_oauth_start_unauthorized_non_member(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "stranger@example.com")
    company = await create_company_helper(db_session, "Private Company", "private-company")
    # Do NOT add membership

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(
        f"/api/v1/social/oauth/facebook/start?company_id={company.id}",
        headers=headers,
    )
    assert response.status_code == 403
    assert "Forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_start_invalid_platform(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "member2@example.com")
    company = await create_company_helper(db_session, "Company Beta", "company-beta")
    await add_membership_helper(db_session, user.id, company.id)

    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get(
        f"/api/v1/social/oauth/myspace/start?company_id={company.id}",
        headers=headers,
    )
    assert response.status_code == 400
    assert "Unsupported platform" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_flow_success(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "connector@example.com")
    company = await create_company_helper(db_session, "Brand Gamma", "brand-gamma")
    await add_membership_helper(db_session, user.id, company.id)

    # 1. Start flow to get valid state
    state_token = await OAuthStateManager.create_state(
        db=db_session,
        user_id=user.id,
        company_id=company.id,
        platform=Platform.LINKEDIN,
    )

    # 2. Mock provider calls during callback
    mock_token_result = OAuthTokenResult(
        access_token="real_linkedin_access_token_12345",
        refresh_token="real_linkedin_refresh_token_67890",
        expires_in=3600,
    )
    mock_identity = SocialAccountIdentity(
        platform=Platform.LINKEDIN,
        platform_account_id="li_account_9988",
        account_name="Acme Corp LinkedIn",
        avatar_url="https://linkedin.com/avatar.jpg",
    )

    with patch.object(
        LinkedInProvider,
        "exchange_code_for_tokens",
        AsyncMock(return_value=mock_token_result),
    ), patch.object(
        LinkedInProvider,
        "get_account_identity",
        AsyncMock(return_value=mock_identity),
    ):
        headers = {"Authorization": f"Bearer {token}"}
        callback_resp = await client.get(
            f"/api/v1/social/oauth/linkedin/callback?code=mock_code_abc&state={state_token}",
            headers=headers,
        )
        assert callback_resp.status_code == 200
        data = callback_resp.json()
        assert "account" in data
        acc = data["account"]
        assert acc["platform"] == "LINKEDIN"
        assert acc["account_name"] == "Acme Corp LinkedIn"
        assert acc["platform_account_id"] == "li_account_9988"
        assert acc["status"] == "ACTIVE"
        assert "access_token" not in acc
        assert "refresh_token" not in acc

    # 3. Verify in database: tokens are encrypted and NOT stored in plaintext!
    stmt = select(SocialAccount).where(SocialAccount.platform_account_id == "li_account_9988")
    result = await db_session.execute(stmt)
    db_account = result.scalar_one()

    assert db_account.encrypted_access_token is not None
    assert db_account.encrypted_access_token.startswith("v1:")
    assert "real_linkedin_access_token_12345" not in db_account.encrypted_access_token
    # Decrypt to ensure validity
    assert decrypt_token(db_account.encrypted_access_token) == "real_linkedin_access_token_12345"
    assert decrypt_token(db_account.encrypted_refresh_token) == "real_linkedin_refresh_token_67890"

    # 4. Verify state is marked used
    stmt_state = select(OAuthState).where(OAuthState.state_token == state_token)
    res_state = await db_session.execute(stmt_state)
    db_state = res_state.scalar_one()
    assert db_state.used_at is not None

    # 5. Single-use replay attack: calling again with same state must fail with 400
    replay_resp = await client.get(
        f"/api/v1/social/oauth/linkedin/callback?code=mock_code_abc&state={state_token}",
        headers=headers,
    )
    assert replay_resp.status_code == 400
    assert "already been consumed" in replay_resp.json()["detail"]


@pytest.mark.asyncio
async def test_oauth_callback_provider_error(client: AsyncClient, db_session: AsyncSession):
    response = await client.get(
        "/api/v1/social/oauth/instagram/callback?error=access_denied&error_description=User+cancelled+dialog",
    )
    assert response.status_code == 400
    assert "OAuth authorization failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_social_accounts_isolation(client: AsyncClient, db_session: AsyncSession):
    user1, token1 = await create_user_helper(db_session, "user1_iso@example.com")
    user2, token2 = await create_user_helper(db_session, "user2_iso@example.com")
    admin_user, admin_token = await create_user_helper(db_session, "admin_iso@example.com", role_name="ADMIN")

    company_a = await create_company_helper(db_session, "Company A", "comp-a")
    company_b = await create_company_helper(db_session, "Company B", "comp-b")

    await add_membership_helper(db_session, user1.id, company_a.id)
    await add_membership_helper(db_session, user2.id, company_b.id)

    # Seed an account in Company A
    acc_a = SocialAccount(
        company_id=company_a.id,
        platform=Platform.INSTAGRAM,
        account_name="company_a_insta",
        platform_account_id="acc_a_id",
        encrypted_access_token=encrypt_token("tok_a"),
        status=SocialAccountStatus.ACTIVE,
    )
    db_session.add(acc_a)
    await db_session.commit()

    # User 1 lists Company A -> 200, 1 account
    headers1 = {"Authorization": f"Bearer {token1}"}
    resp1 = await client.get(f"/api/v1/social/accounts?company_id={company_a.id}", headers=headers1)
    assert resp1.status_code == 200
    assert len(resp1.json()) == 1
    assert resp1.json()[0]["account_name"] == "company_a_insta"
    assert "access_token" not in resp1.json()[0]

    # User 2 lists Company A -> 403 Forbidden (cross-company isolation)
    headers2 = {"Authorization": f"Bearer {token2}"}
    resp2 = await client.get(f"/api/v1/social/accounts?company_id={company_a.id}", headers=headers2)
    assert resp2.status_code == 403

    # Admin lists Company A -> 200 (system ADMIN has global access)
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    resp_admin = await client.get(f"/api/v1/social/accounts?company_id={company_a.id}", headers=headers_admin)
    assert resp_admin.status_code == 200
    assert len(resp_admin.json()) == 1


@pytest.mark.asyncio
async def test_disconnect_social_account(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "disco@example.com")
    company = await create_company_helper(db_session, "Disco Brand", "disco-brand")
    await add_membership_helper(db_session, user.id, company.id)

    account = SocialAccount(
        company_id=company.id,
        platform=Platform.YOUTUBE,
        account_name="Disco Channel",
        platform_account_id="yt_channel_111",
        encrypted_access_token=encrypt_token("raw_yt_token"),
        encrypted_refresh_token=encrypt_token("raw_yt_refresh"),
        status=SocialAccountStatus.ACTIVE,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.delete(f"/api/v1/social/accounts/{account.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "DISCONNECTED"

    # Verify tokens cleared in database
    await db_session.refresh(account)
    assert account.status == SocialAccountStatus.DISCONNECTED
    assert account.encrypted_access_token is None
    assert account.encrypted_refresh_token is None

    # Verify audit log
    stmt_log = select(ActivityLog).where(
        ActivityLog.action == "SOCIAL_ACCOUNT_DISCONNECTED",
        ActivityLog.entity_id == account.id,
    )
    res_log = await db_session.execute(stmt_log)
    assert res_log.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_refresh_social_account_tokens(client: AsyncClient, db_session: AsyncSession):
    user, token = await create_user_helper(db_session, "refresher@example.com")
    company = await create_company_helper(db_session, "Refresher Co", "refresher-co")
    await add_membership_helper(db_session, user.id, company.id)

    initial_refresh_token = "valid_refresh_token_abc"
    account = SocialAccount(
        company_id=company.id,
        platform=Platform.FACEBOOK,
        account_name="FB Page Refresh",
        platform_account_id="fb_page_333",
        encrypted_access_token=encrypt_token("old_fb_access"),
        encrypted_refresh_token=encrypt_token(initial_refresh_token),
        status=SocialAccountStatus.ACTIVE,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)

    mock_refreshed_tokens = OAuthTokenResult(
        access_token="new_refreshed_fb_access_token_999",
        refresh_token="new_refreshed_fb_exchange_token_999",
        expires_in=5184000,
    )

    with patch.object(
        FacebookProvider,
        "refresh_tokens",
        AsyncMock(return_value=mock_refreshed_tokens),
    ) as mock_refresh_method:
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.post(f"/api/v1/social/accounts/{account.id}/refresh", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "FACEBOOK token refreshed successfully"
        assert data["account"]["status"] == "ACTIVE"
        # Check mock was called with the decrypted token
        mock_refresh_method.assert_awaited_once_with(initial_refresh_token)

    # Verify new encrypted tokens saved in DB
    await db_session.refresh(account)
    assert decrypt_token(account.encrypted_access_token) == "new_refreshed_fb_access_token_999"
    assert decrypt_token(account.encrypted_refresh_token) == "new_refreshed_fb_exchange_token_999"
