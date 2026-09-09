"""Step 7 — Authentication & RBAC Comprehensive Test Suite.

Covers:
- Section 19 required test coverage (Argon2id hashing, JWT access tokens, refresh sessions,
  API endpoints /login, /refresh, /logout, /me, RBAC enforcement, Admin Bootstrap idempotency).
- Uses isolated in-memory SQLite database with StaticPool for fast, hermetic execution.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.pool import StaticPool

from app.api.deps import get_async_db
from app.cli.bootstrap_admin import bootstrap_admin_user
from app.core.config import settings
from app.core.database import Base
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    validate_password_strength,
    verify_password,
)
from app.main import app
from app.models.activity_log import ActivityLog
from app.models.auth_session import AuthSession
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import _DUMMY_HASH, AuthService

# Test Database Engine & Session Factory
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
    """Setup clean tables and seed the 5 standard system roles for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed the 5 system roles
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
    """Yield an independent session for direct DB operations in tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    """Yield an AsyncClient bound to the FastAPI app with test DB override."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


async def create_test_user(
    db: AsyncSession,
    email: str = "test@socialos.io",
    password: str = "SecurePass123!",
    role_name: str = "CONTENT_CREATOR",
    name: str = "Test Creator",
    is_active: bool = True,
) -> User:
    """Helper to create an active test user in the test database."""
    role_res = await db.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalar_one()

    user = User(
        name=name,
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role_id=role.id,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.commit()
    res = await db.execute(
        select(User).options(joinedload(User.role)).where(User.id == user.id)
    )
    return res.scalar_one()


# =============================================================================
# 1. Password Hashing & Verification Tests
# =============================================================================

def test_hash_password_argon2id():
    """1. hash_password creates valid Argon2id hash."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert hashed != password


def test_verify_password_matching():
    """2. verify_password returns True for matching password."""
    password = "CorrectPassword123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_non_matching():
    """3. verify_password returns False for non-matching password."""
    password = "CorrectPassword123!"
    hashed = hash_password(password)
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_verify_password_dummy_hash_prevents_timing_leaks():
    """4. Password verification with dummy hash executes and returns False."""
    assert verify_password("AnyPassword123!", _DUMMY_HASH) is False


def test_validate_password_strength():
    """Password strength policy enforcement (min 8 chars)."""
    validate_password_strength("12345678")  # exactly 8 chars ok
    with pytest.raises(ValueError, match="at least 8 characters"):
        validate_password_strength("short")
    with pytest.raises(ValueError, match="at least 8 characters"):
        validate_password_strength("")


# =============================================================================
# 2. JWT Access Token Tests
# =============================================================================

def test_create_access_token_claims():
    """5. create_access_token produces valid JWT with claims (sub, role, type=access, exp, iat, jti)."""
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role="ADMIN")
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "iat" in payload
    assert "jti" in payload
    assert payload["exp"] > payload["iat"]


def test_decode_access_token_success():
    """6. decode_token verifies valid access token and returns payload."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id=user_id, role="SOCIAL_MEDIA_MANAGER")
    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "SOCIAL_MEDIA_MANAGER"


def test_decode_access_token_expired():
    """7. decode_token raises error for expired token."""
    user_id = str(uuid.uuid4())
    expired_token = create_access_token(
        user_id=user_id,
        role="ADMIN",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)


def test_decode_access_token_invalid_signature():
    """8. decode_token raises error for token with invalid signature."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id=user_id, role="ADMIN")
    tampered_token = token[:-5] + "abcde"
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered_token)


def test_decode_access_token_wrong_token_type():
    """9. decode_token raises error for refresh token used as access token (type check)."""
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "ADMIN",
        "type": "refresh",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError, match="Invalid token type"):
        decode_access_token(encoded)


# =============================================================================
# 3. Refresh Tokens & Session Persistence Tests
# =============================================================================

def test_create_refresh_token_and_hash():
    """10. create_refresh_token produces raw token and valid SHA-256 hash."""
    raw = generate_refresh_token()
    assert len(raw) >= 32
    digest = hash_refresh_token(raw)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_hash_refresh_token_consistency():
    """11. hash_refresh_token creates consistent SHA-256 hex digest."""
    token = "fixed_token_value_for_testing"
    assert hash_refresh_token(token) == hash_refresh_token(token)


@pytest.mark.asyncio
async def test_auth_service_create_user_session(db_session: AsyncSession):
    """12. AuthService.create_user_session stores session in DB with hashed token and activity log."""
    user = await create_test_user(db_session, email="session@socialos.io")
    access_token, raw_refresh = await AuthService.create_user_session(
        db_session, user, ip_address="127.0.0.1", user_agent="PytestBrowser"
    )

    assert access_token is not None
    assert raw_refresh is not None

    token_hash = hash_refresh_token(raw_refresh)
    res = await db_session.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    )
    session = res.scalar_one_or_none()
    assert session is not None
    assert session.user_id == user.id
    assert session.revoked_at is None
    assert session.ip_address == "127.0.0.1"

    # Verify ActivityLog audit record
    log_res = await db_session.execute(
        select(ActivityLog).where(ActivityLog.user_id == user.id, ActivityLog.action == "USER_LOGIN")
    )
    log_entry = log_res.scalar_one_or_none()
    assert log_entry is not None
    assert "password" not in str(log_entry.log_metadata)
    assert raw_refresh not in str(log_entry.log_metadata)


@pytest.mark.asyncio
async def test_auth_service_rotate_refresh_session_success(db_session: AsyncSession):
    """13. AuthService.rotate_refresh_session rotates tokens, creates new session, revokes old session."""
    user = await create_test_user(db_session, email="rotate@socialos.io")
    _, initial_refresh = await AuthService.create_user_session(db_session, user)

    new_access, new_refresh, returned_user = await AuthService.rotate_refresh_session(
        db_session, raw_refresh_token=initial_refresh
    )
    assert new_access is not None
    assert new_refresh != initial_refresh
    assert returned_user.id == user.id

    # Verify old session is revoked
    old_hash = hash_refresh_token(initial_refresh)
    old_res = await db_session.execute(
        select(AuthSession).where(AuthSession.token_hash == old_hash)
    )
    old_session = old_res.scalar_one()
    assert old_session.revoked_at is not None

    # Verify new session is active
    new_hash = hash_refresh_token(new_refresh)
    new_res = await db_session.execute(
        select(AuthSession).where(AuthSession.token_hash == new_hash)
    )
    new_session = new_res.scalar_one()
    assert new_session.revoked_at is None


@pytest.mark.asyncio
async def test_auth_service_rotate_refresh_session_already_revoked(db_session: AsyncSession):
    """14. AuthService.rotate_refresh_session fails on already-revoked session (token reuse prevention)."""
    user = await create_test_user(db_session, email="reuse@socialos.io")
    _, initial_refresh = await AuthService.create_user_session(db_session, user)

    # First rotation succeeds
    await AuthService.rotate_refresh_session(db_session, raw_refresh_token=initial_refresh)

    # Attempting to reuse the revoked token must fail
    with pytest.raises(ValueError, match="Refresh token has been revoked"):
        await AuthService.rotate_refresh_session(db_session, raw_refresh_token=initial_refresh)


@pytest.mark.asyncio
async def test_auth_service_rotate_refresh_session_expired(db_session: AsyncSession):
    """15. AuthService.rotate_refresh_session fails on expired session."""
    user = await create_test_user(db_session, email="expired@socialos.io")
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    # Create directly expired session
    expired_session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(expired_session)
    await db_session.commit()

    with pytest.raises(ValueError, match="Refresh token has expired"):
        await AuthService.rotate_refresh_session(db_session, raw_refresh_token=raw_token)


@pytest.mark.asyncio
async def test_auth_service_revoke_session(db_session: AsyncSession):
    """16. AuthService.revoke_session sets revoked_at."""
    user = await create_test_user(db_session, email="revoke@socialos.io")
    _, raw_refresh = await AuthService.create_user_session(db_session, user)

    revoked = await AuthService.revoke_session(db_session, raw_refresh_token=raw_refresh)
    assert revoked is True

    old_hash = hash_refresh_token(raw_refresh)
    res = await db_session.execute(
        select(AuthSession).where(AuthSession.token_hash == old_hash)
    )
    session = res.scalar_one()
    assert session.revoked_at is not None


# =============================================================================
# 4. Auth API Endpoints (Integration Tests)
# =============================================================================

@pytest.mark.asyncio
async def test_api_login_success(client: AsyncClient, db_session: AsyncSession):
    """17. POST /api/v1/auth/login succeeds with valid credentials and returns access + refresh + user."""
    password = "ValidUserPassword123!"
    user = await create_test_user(
        db_session,
        email="login_success@socialos.io",
        password=password,
        role_name="ADMIN",
        name="Admin Boss",
    )

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_success@socialos.io"
    assert data["user"]["role"] == "ADMIN"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


@pytest.mark.asyncio
async def test_api_login_invalid_password(client: AsyncClient, db_session: AsyncSession):
    """18. POST /api/v1/auth/login fails with 401 for invalid password (generic message)."""
    user = await create_test_user(
        db_session, email="login_bad_pw@socialos.io", password="CorrectPassword123!"
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "WrongPassword999!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_api_login_nonexistent_email(client: AsyncClient):
    """19. POST /api/v1/auth/login fails with 401 for non-existent email (generic message)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@socialos.io", "password": "RandomPassword123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_api_login_inactive_user(client: AsyncClient, db_session: AsyncSession):
    """20. POST /api/v1/auth/login fails with 403 for inactive user."""
    password = "DeactivatedPassword123!"
    user = await create_test_user(
        db_session,
        email="inactive@socialos.io",
        password=password,
        is_active=False,
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_refresh_endpoint_success(client: AsyncClient, db_session: AsyncSession):
    """21. POST /api/v1/auth/refresh succeeds with valid refresh token, returns rotated tokens."""
    password = "RefreshUserPass123!"
    user = await create_test_user(db_session, email="refresh_api@socialos.io", password=password)

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    assert new_data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_api_refresh_endpoint_revoked_token(client: AsyncClient, db_session: AsyncSession):
    """22. POST /api/v1/auth/refresh fails with 401 for revoked/invalid refresh token."""
    password = "RefreshRevokePass123!"
    user = await create_test_user(db_session, email="refresh_revoked@socialos.io", password=password)

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # First refresh succeeds
    await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    # Second refresh with the now-revoked token must fail with 401
    second_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second_resp.status_code == 401
    assert "revoked" in second_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_logout_endpoint_success(client: AsyncClient, db_session: AsyncSession):
    """23. POST /api/v1/auth/logout succeeds with valid credentials and revokes session."""
    password = "LogoutPassword123!"
    user = await create_test_user(db_session, email="logout_api@socialos.io", password=password)

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["detail"] == "Successfully logged out"

    # Further refresh attempts with this token must fail
    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


@pytest.mark.asyncio
async def test_api_me_endpoint_profile_no_password_hash(client: AsyncClient, db_session: AsyncSession):
    """24. GET /api/v1/auth/me returns current user without password_hash."""
    user = await create_test_user(
        db_session, email="profile@socialos.io", role_name="GRAPHIC_DESIGNER"
    )
    token = create_access_token(user_id=user.id, role="GRAPHIC_DESIGNER")

    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "profile@socialos.io"
    assert data["role"] == "GRAPHIC_DESIGNER"
    assert data["is_active"] is True
    assert "password_hash" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_api_me_endpoint_unauthenticated(client: AsyncClient):
    """GET /api/v1/auth/me returns 401 Unauthorized when missing token."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


# =============================================================================
# 5. RBAC & Authorization Tests
# =============================================================================

@pytest.mark.asyncio
async def test_rbac_admin_endpoint(client: AsyncClient, db_session: AsyncSession):
    """25. GET /api/v1/auth/test/admin accessible by ADMIN, returns 403 for other roles."""
    admin_user = await create_test_user(db_session, email="admin@socialos.io", role_name="ADMIN")
    admin_token = create_access_token(user_id=admin_user.id, role="ADMIN")

    non_admin_user = await create_test_user(
        db_session, email="creator@socialos.io", role_name="CONTENT_CREATOR"
    )
    non_admin_token = create_access_token(user_id=non_admin_user.id, role="CONTENT_CREATOR")

    # ADMIN: 200 OK
    resp = await client.get(
        "/api/v1/auth/test/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200

    # Non-admin: 403 Forbidden
    resp = await client.get(
        "/api/v1/auth/test/admin",
        headers={"Authorization": f"Bearer {non_admin_token}"},
    )
    assert resp.status_code == 403

    # Unauthenticated: 401 Unauthorized
    resp = await client.get("/api/v1/auth/test/admin")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rbac_manager_endpoint(client: AsyncClient, db_session: AsyncSession):
    """26. GET /api/v1/auth/test/manager accessible by ADMIN and SOCIAL_MEDIA_MANAGER, returns 403 for others."""
    admin = await create_test_user(db_session, email="m_admin@socialos.io", role_name="ADMIN")
    manager = await create_test_user(
        db_session, email="m_manager@socialos.io", role_name="SOCIAL_MEDIA_MANAGER"
    )
    designer = await create_test_user(
        db_session, email="m_designer@socialos.io", role_name="GRAPHIC_DESIGNER"
    )

    admin_token = create_access_token(user_id=admin.id, role="ADMIN")
    manager_token = create_access_token(user_id=manager.id, role="SOCIAL_MEDIA_MANAGER")
    designer_token = create_access_token(user_id=designer.id, role="GRAPHIC_DESIGNER")

    # Admin: 200 OK
    res1 = await client.get("/api/v1/auth/test/manager", headers={"Authorization": f"Bearer {admin_token}"})
    assert res1.status_code == 200

    # Social Media Manager: 200 OK
    res2 = await client.get("/api/v1/auth/test/manager", headers={"Authorization": f"Bearer {manager_token}"})
    assert res2.status_code == 200

    # Graphic Designer: 403 Forbidden
    res3 = await client.get("/api/v1/auth/test/manager", headers={"Authorization": f"Bearer {designer_token}"})
    assert res3.status_code == 403


@pytest.mark.asyncio
async def test_rbac_team_endpoint(client: AsyncClient, db_session: AsyncSession):
    """27. GET /api/v1/auth/test/team accessible by all 5 roles, returns 401 if unauthenticated."""
    for role_name, _ in SYSTEM_ROLES:
        user = await create_test_user(
            db_session,
            email=f"{role_name.lower()}@socialos.io",
            role_name=role_name,
        )
        token = create_access_token(user_id=user.id, role=role_name)
        res = await client.get("/api/v1/auth/test/team", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Role {role_name} failed to access /test/team"

    # Unauthenticated returns 401
    unauth = await client.get("/api/v1/auth/test/team")
    assert unauth.status_code == 401


# =============================================================================
# 6. Admin Bootstrap Tests
# =============================================================================

@pytest.mark.asyncio
async def test_bootstrap_admin_user_creates_new_admin(db_session: AsyncSession):
    """28. bootstrap_admin_user creates new admin user if not exists."""
    email = "first_bootstrap_admin@socialos.io"
    password = "BootstrapAdminPassword123!"
    user, created = await bootstrap_admin_user(
        db=db_session,
        email=email,
        password=password,
        name="Bootstrapped Administrator",
    )
    assert created is True
    assert user.email == email
    assert user.role.name == "ADMIN"
    assert verify_password(password, user.password_hash) is True
    assert user.password_hash != password


@pytest.mark.asyncio
async def test_bootstrap_admin_user_is_idempotent(db_session: AsyncSession):
    """29. bootstrap_admin_user is idempotent and does not overwrite existing admin."""
    email = "idempotent_admin@socialos.io"
    password_initial = "InitialPassword123!"
    user1, created1 = await bootstrap_admin_user(
        db=db_session,
        email=email,
        password=password_initial,
        name="Admin One",
    )
    assert created1 is True

    # Attempt to bootstrap again with different password & name
    user2, created2 = await bootstrap_admin_user(
        db=db_session,
        email=email,
        password="DifferentAttemptPassword999!",
        name="Admin Overwrite Attempt",
    )
    assert created2 is False
    assert user2.id == user1.id
    # Password hash must remain unchanged
    assert verify_password(password_initial, user2.password_hash) is True
    assert verify_password("DifferentAttemptPassword999!", user2.password_hash) is False
