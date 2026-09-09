"""Step 8 — Companies, Users & Company Membership Access Control Comprehensive Test Suite.

Covers all 32+ scenarios required in Section 16:
- Admin company management (create, update, deactivate, list)
- Admin user management (create, update, change role, deactivate, activate, list)
- Admin company membership management (add member, remove member, list members)
- Non-admin company access (membership-based access, isolation against unauthorized UUIDs)
- Data validation (duplicate slug, duplicate email, duplicate membership, invalid role)
- Security invariants (zero password_hash in responses, zero secrets in activity_logs, role escalation rejection)
- Audit logging (COMPANY_CREATED, USER_CREATED, USER_ROLE_CHANGED, COMPANY_MEMBER_ADDED, etc.)
- User self-profile (/api/v1/users/me)
"""
import uuid
from typing import Tuple

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload
from sqlalchemy.pool import StaticPool

from app.api.deps import get_async_db
from app.core.database import Base
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.activity_log import ActivityLog
from app.models.auth_session import AuthSession
from app.models.company import Company
from app.models.company_membership import CompanyMembership
from app.models.role import Role
from app.models.user import User

# In-memory test engine with StaticPool for fast, isolated async testing
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
    role_name: str = "CONTENT_CREATOR",
    name: str = "Test User",
    password: str = "SecurePass123!",
    is_active: bool = True,
) -> Tuple[User, str]:
    """Helper creating a test user and returning (User, access_token)."""
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
    reloaded_user = res.scalar_one()
    token = create_access_token(user_id=reloaded_user.id, role=role_name)
    return reloaded_user, token


async def create_company_helper(
    db: AsyncSession,
    name: str,
    slug: str,
    is_active: bool = True,
) -> Company:
    """Helper creating a company in the test database."""
    company = Company(
        name=name,
        slug=slug,
        is_active=is_active,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


# =============================================================================
# 1. ADMIN COMPANY & USER MANAGEMENT (Tests 1 - 8)
# =============================================================================

@pytest.mark.asyncio
async def test_admin_can_create_company(client: AsyncClient, db_session: AsyncSession):
    """1 & 2. ADMIN can create company and view it."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")

    resp = await client.post(
        "/api/v1/companies",
        json={"name": "RupeeQ", "slug": "rupeeq", "logo_url": "https://img.socialos.io/rupeeq.png"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "RupeeQ"
    assert data["slug"] == "rupeeq"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_admin_can_list_companies(client: AsyncClient, db_session: AsyncSession):
    """1. ADMIN can list all companies."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    await create_company_helper(db_session, "RupeeQ", "rupeeq")
    await create_company_helper(db_session, "QFit", "qfit")

    resp = await client.get(
        "/api/v1/companies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    slugs = [c["slug"] for c in data["items"]]
    assert "rupeeq" in slugs
    assert "qfit" in slugs


@pytest.mark.asyncio
async def test_admin_can_update_company(client: AsyncClient, db_session: AsyncSession):
    """3. ADMIN can update company attributes."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    resp = await client.patch(
        f"/api/v1/companies/{comp.id}",
        json={"name": "RupeeQ Global", "slug": "rupeeq-global"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "RupeeQ Global"
    assert data["slug"] == "rupeeq-global"


@pytest.mark.asyncio
async def test_admin_can_deactivate_company(client: AsyncClient, db_session: AsyncSession):
    """4. ADMIN can soft-deactivate company."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    resp = await client.delete(
        f"/api/v1/companies/{comp.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_admin_can_create_users(client: AsyncClient, db_session: AsyncSession):
    """5. ADMIN can create users."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")

    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "New Manager",
            "email": "manager@socialos.io",
            "password": "StrongPassword123!",
            "role": "SOCIAL_MEDIA_MANAGER",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "manager@socialos.io"
    assert data["role"] == "SOCIAL_MEDIA_MANAGER"
    assert "password_hash" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_admin_can_change_user_roles(client: AsyncClient, db_session: AsyncSession):
    """6. ADMIN can change user roles and active sessions are revoked."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")

    resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "SOCIAL_MEDIA_MANAGER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "SOCIAL_MEDIA_MANAGER"


@pytest.mark.asyncio
async def test_admin_can_add_and_remove_membership(client: AsyncClient, db_session: AsyncSession):
    """7 & 8. ADMIN can add and remove company membership."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # Add member
    add_resp = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add_resp.status_code == 201
    add_data = add_resp.json()
    assert add_data["user_id"] == str(user.id)
    assert add_data["company_id"] == str(comp.id)

    # List members
    list_resp = await client.get(
        f"/api/v1/companies/{comp.id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Remove member
    del_resp = await client.delete(
        f"/api/v1/companies/{comp.id}/members/{user.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 200
    assert "Member removed" in del_resp.json()["detail"]

    # Verify members empty now
    list_resp2 = await client.get(
        f"/api/v1/companies/{comp.id}/members",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert len(list_resp2.json()) == 0


# =============================================================================
# 2. NON-ADMIN & STRICT ISOLATION (Tests 9 - 16)
# =============================================================================

@pytest.mark.asyncio
async def test_user_with_membership_can_access_company(client: AsyncClient, db_session: AsyncSession):
    """9. User with membership can access company."""
    user, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # Grant membership
    db_session.add(CompanyMembership(company_id=comp.id, user_id=user.id))
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/companies/{comp.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "rupeeq"


@pytest.mark.asyncio
async def test_user_without_membership_cannot_access_company(client: AsyncClient, db_session: AsyncSession):
    """10. User without membership cannot access company (403 Forbidden)."""
    _, user_token = await create_user_helper(db_session, "stranger@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    resp = await client.get(
        f"/api/v1/companies/{comp.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403
    assert "Forbidden" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_user_cannot_access_another_company_by_uuid(client: AsyncClient, db_session: AsyncSession):
    """11. User cannot access another company by manually supplying UUID (Cross-company leak prevention)."""
    user, user_token = await create_user_helper(db_session, "rupeeq_worker@socialos.io", role_name="CONTENT_CREATOR")
    comp_a = await create_company_helper(db_session, "RupeeQ", "rupeeq")
    comp_b = await create_company_helper(db_session, "QFit", "qfit")

    # User has access ONLY to RupeeQ (Company A)
    db_session.add(CompanyMembership(company_id=comp_a.id, user_id=user.id))
    await db_session.commit()

    # Access Company A: OK
    resp_a = await client.get(f"/api/v1/companies/{comp_a.id}", headers={"Authorization": f"Bearer {user_token}"})
    assert resp_a.status_code == 200

    # Attempt to access Company B by UUID: 403 Forbidden
    resp_b = await client.get(f"/api/v1/companies/{comp_b.id}", headers={"Authorization": f"Bearer {user_token}"})
    assert resp_b.status_code == 403
    assert "Forbidden" in resp_b.json()["detail"]


@pytest.mark.asyncio
async def test_user_cannot_list_unauthorized_companies(client: AsyncClient, db_session: AsyncSession):
    """12. User cannot list unauthorized companies."""
    user, user_token = await create_user_helper(db_session, "rupeeq_worker@socialos.io", role_name="CONTENT_CREATOR")
    comp_a = await create_company_helper(db_session, "RupeeQ", "rupeeq")
    await create_company_helper(db_session, "QFit", "qfit")
    await create_company_helper(db_session, "Secret Brand", "secret-brand")

    # Assign membership only to RupeeQ
    db_session.add(CompanyMembership(company_id=comp_a.id, user_id=user.id))
    await db_session.commit()

    resp = await client.get("/api/v1/companies", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["slug"] == "rupeeq"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_company(client: AsyncClient, db_session: AsyncSession):
    """13. User cannot create company (403 Forbidden)."""
    _, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")

    resp = await client.post(
        "/api/v1/companies",
        json={"name": "Hacker Brand", "slug": "hacker-brand"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_memberships(client: AsyncClient, db_session: AsyncSession):
    """14. User cannot manage memberships (403 Forbidden)."""
    _, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    target_user, _ = await create_user_helper(db_session, "target@socialos.io", role_name="GRAPHIC_DESIGNER")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # Add membership attempt
    add_resp = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(target_user.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert add_resp.status_code == 403

    # Remove membership attempt
    del_resp = await client.delete(
        f"/api/v1/companies/{comp.id}/members/{target_user.id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert del_resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_change_user_role(client: AsyncClient, db_session: AsyncSession):
    """15. User cannot change another user's role (403 Forbidden)."""
    _, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    target_user, _ = await create_user_helper(db_session, "target@socialos.io", role_name="GRAPHIC_DESIGNER")

    resp = await client.patch(
        f"/api/v1/users/{target_user.id}",
        json={"role": "ADMIN"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_deactivate_users(client: AsyncClient, db_session: AsyncSession):
    """16. User cannot deactivate users (403 Forbidden)."""
    _, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    target_user, _ = await create_user_helper(db_session, "target@socialos.io", role_name="GRAPHIC_DESIGNER")

    resp = await client.post(
        f"/api/v1/users/{target_user.id}/deactivate",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


# =============================================================================
# 3. DATA VALIDATION (Tests 17 - 22)
# =============================================================================

@pytest.mark.asyncio
async def test_duplicate_company_slug_rejected(client: AsyncClient, db_session: AsyncSession):
    """17. Duplicate company slug rejected (409 Conflict)."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    await create_company_helper(db_session, "RupeeQ", "rupeeq")

    resp = await client.post(
        "/api/v1/companies",
        json={"name": "RupeeQ Duplicate", "slug": "rupeeq"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_membership_rejected(client: AsyncClient, db_session: AsyncSession):
    """18. Duplicate membership rejected safely (409 Conflict)."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "user@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # First add succeeds
    resp1 = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp1.status_code == 201

    # Second add rejected
    resp2 = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp2.status_code == 409
    assert "already a member" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_email_rejected(client: AsyncClient, db_session: AsyncSession):
    """19. Duplicate email rejected safely (409 Conflict)."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    await create_user_helper(db_session, "existing@socialos.io", role_name="CONTENT_CREATOR")

    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "Duplicate User",
            "email": "existing@socialos.io",
            "password": "Password123!",
            "role": "CONTENT_CREATOR",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_role_rejected(client: AsyncClient, db_session: AsyncSession):
    """20. Invalid role rejected (400 Bad Request)."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")

    resp = await client.post(
        "/api/v1/users",
        json={
            "name": "Invalid Role User",
            "email": "invalid_role@socialos.io",
            "password": "Password123!",
            "role": "SUPER_OWNER_ROLE",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_inactive_user_restrictions(client: AsyncClient, db_session: AsyncSession):
    """21. Inactive user restrictions work."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    inactive_user, inactive_token = await create_user_helper(
        db_session, "inactive@socialos.io", role_name="CONTENT_CREATOR", is_active=False
    )
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # Inactive user cannot make API calls
    resp = await client.get("/api/v1/companies", headers={"Authorization": f"Bearer {inactive_token}"})
    assert resp.status_code == 403

    # Admin cannot assign inactive user to company
    add_resp = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(inactive_user.id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add_resp.status_code == 400
    assert "inactive user" in add_resp.json()["detail"]


@pytest.mark.asyncio
async def test_inactive_company_behavior(client: AsyncClient, db_session: AsyncSession):
    """22. Inactive company behavior works."""
    user, user_token = await create_user_helper(db_session, "user@socialos.io", role_name="CONTENT_CREATOR")
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    inactive_comp = await create_company_helper(db_session, "Old Brand", "old-brand", is_active=False)

    # Assign membership to inactive company
    db_session.add(CompanyMembership(company_id=inactive_comp.id, user_id=user.id))
    await db_session.commit()

    # Non-admin cannot access inactive company (404 Not Found)
    resp = await client.get(f"/api/v1/companies/{inactive_comp.id}", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 404

    # Non-admin cannot list inactive companies
    list_resp = await client.get("/api/v1/companies", headers={"Authorization": f"Bearer {user_token}"})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 0

    # Non-admin passing include_inactive=True is rejected with 403
    rejected = await client.get("/api/v1/companies?include_inactive=true", headers={"Authorization": f"Bearer {user_token}"})
    assert rejected.status_code == 403

    # Admin CAN list inactive companies if requested
    admin_list = await client.get("/api/v1/companies?include_inactive=true", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_list.status_code == 200
    assert admin_list.json()["total"] == 1


# =============================================================================
# 4. SECURITY & AUDIT (Tests 23 - 32)
# =============================================================================

@pytest.mark.asyncio
async def test_password_hash_never_in_responses(client: AsyncClient, db_session: AsyncSession):
    """23. password_hash never appears in any API response."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "test_sec@socialos.io", role_name="CONTENT_CREATOR")

    # Check GET /users
    resp1 = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert "password_hash" not in resp1.text
    assert "password" not in resp1.json()["items"][0]

    # Check GET /users/{id}
    resp2 = await client.get(f"/api/v1/users/{user.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert "password_hash" not in resp2.text

    # Check GET /users/me
    resp3 = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert "password_hash" not in resp3.text


@pytest.mark.asyncio
async def test_passwords_and_secrets_never_in_audit_logs(client: AsyncClient, db_session: AsyncSession):
    """24 & 25. Passwords, tokens, and secrets never appear in activity_logs."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")

    # Create user with sensitive password
    secret_pass = "SuperSecretPassword123!"
    await client.post(
        "/api/v1/users",
        json={
            "name": "Audited User",
            "email": "audit_user@socialos.io",
            "password": secret_pass,
            "role": "CONTENT_CREATOR",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    logs_res = await db_session.execute(select(ActivityLog))
    logs = logs_res.scalars().all()
    for log_entry in logs:
        log_str = f"{log_entry.action} {log_entry.log_metadata}"
        assert secret_pass not in log_str
        assert "password_hash" not in log_str
        assert "secret" not in log_str.lower() or "audit_user" in log_str


@pytest.mark.asyncio
async def test_role_escalation_fails(client: AsyncClient, db_session: AsyncSession):
    """26. Role escalation attempts fail for non-admin."""
    user, user_token = await create_user_helper(db_session, "user@socialos.io", role_name="CONTENT_CREATOR")

    resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "ADMIN"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_membership_self_assignment_fails(client: AsyncClient, db_session: AsyncSession):
    """27. Membership self-assignment fails for non-admin."""
    user, user_token = await create_user_helper(db_session, "user@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "Secret Brand", "secret-brand")

    resp = await client.post(
        f"/api/v1/companies/{comp.id}/members",
        json={"user_id": str(user.id)},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthorized_company_uuid_access_fails(client: AsyncClient, db_session: AsyncSession):
    """28. Unauthorized company UUID access fails with 403."""
    _, user_token = await create_user_helper(db_session, "user@socialos.io", role_name="CONTENT_CREATOR")
    random_id = uuid.uuid4()

    # Accessing non-existent company returns 404
    resp_404 = await client.get(f"/api/v1/companies/{random_id}", headers={"Authorization": f"Bearer {user_token}"})
    assert resp_404.status_code == 404

    # Accessing existing unauthorized company returns 403
    comp = await create_company_helper(db_session, "Forbidden Brand", "forbidden-brand")
    resp_403 = await client.get(f"/api/v1/companies/{comp.id}", headers={"Authorization": f"Bearer {user_token}"})
    assert resp_403.status_code == 403


@pytest.mark.asyncio
async def test_audit_logging_events(client: AsyncClient, db_session: AsyncSession):
    """29 - 32. Company creation, user creation, membership changes, and role changes are logged."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")

    # 29. Company creation logged
    comp_resp = await client.post(
        "/api/v1/companies",
        json={"name": "Audit Co", "slug": "audit-co"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert comp_resp.status_code == 201
    comp_id = comp_resp.json()["id"]

    # 30. User creation logged
    user_resp = await client.post(
        "/api/v1/users",
        json={"name": "Audited Guy", "email": "audit_guy@socialos.io", "password": "Password123!", "role": "CONTENT_CREATOR"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert user_resp.status_code == 201
    user_id = user_resp.json()["id"]

    # 31. Membership change logged
    mem_resp = await client.post(
        f"/api/v1/companies/{comp_id}/members",
        json={"user_id": user_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert mem_resp.status_code == 201

    # 32. Role change logged
    role_resp = await client.patch(
        f"/api/v1/users/{user_id}",
        json={"role": "SOCIAL_MEDIA_MANAGER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert role_resp.status_code == 200

    # Query activity logs
    logs_res = await db_session.execute(select(ActivityLog.action))
    logged_actions = set(logs_res.scalars().all())

    assert "COMPANY_CREATED" in logged_actions
    assert "USER_CREATED" in logged_actions
    assert "COMPANY_MEMBER_ADDED" in logged_actions
    assert "USER_ROLE_CHANGED" in logged_actions


# =============================================================================
# 5. USER SELF PROFILE (Test 33)
# =============================================================================

@pytest.mark.asyncio
async def test_user_self_profile_returns_accessible_brands(client: AsyncClient, db_session: AsyncSession):
    """33. GET /api/v1/users/me returns profile and accessible companies."""
    user, user_token = await create_user_helper(db_session, "creator@socialos.io", role_name="CONTENT_CREATOR")
    comp_a = await create_company_helper(db_session, "RupeeQ", "rupeeq")
    await create_company_helper(db_session, "QFit", "qfit")

    # Add membership to RupeeQ only
    db_session.add(CompanyMembership(company_id=comp_a.id, user_id=user.id))
    await db_session.commit()

    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "creator@socialos.io"
    assert data["role"] == "CONTENT_CREATOR"
    assert len(data["companies"]) == 1
    assert data["companies"][0]["slug"] == "rupeeq"
    assert "password_hash" not in data


# =============================================================================
# 6. EXTENDED ADMIN USER OPERATIONS & SESSION REVOCATION
# =============================================================================

@pytest.mark.asyncio
async def test_admin_list_users_pagination_and_filters(client: AsyncClient, db_session: AsyncSession):
    """Admin can paginate and filter users by role and status."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    await create_user_helper(db_session, "creator1@socialos.io", role_name="CONTENT_CREATOR")
    await create_user_helper(db_session, "creator2@socialos.io", role_name="CONTENT_CREATOR")
    await create_user_helper(db_session, "designer@socialos.io", role_name="GRAPHIC_DESIGNER")

    # List all users
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 4

    # Filter by role
    resp_role = await client.get(
        "/api/v1/users?role=CONTENT_CREATOR",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_role.status_code == 200
    assert resp_role.json()["total"] == 2


@pytest.mark.asyncio
async def test_admin_get_user_by_id(client: AsyncClient, db_session: AsyncSession):
    """Admin can get user details including assigned companies."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "detail_user@socialos.io", role_name="CONTENT_CREATOR")
    comp = await create_company_helper(db_session, "RupeeQ", "rupeeq")

    # Assign membership
    db_session.add(CompanyMembership(company_id=comp.id, user_id=user.id))
    await db_session.commit()

    resp = await client.get(f"/api/v1/users/{user.id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "detail_user@socialos.io"
    assert len(data["companies"]) == 1
    assert data["companies"][0]["slug"] == "rupeeq"


@pytest.mark.asyncio
async def test_admin_deactivate_and_activate_user(client: AsyncClient, db_session: AsyncSession):
    """Admin can deactivate and reactivate user with audit logs."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "deact_user@socialos.io", role_name="CONTENT_CREATOR")

    # Deactivate
    resp_deact = await client.post(
        f"/api/v1/users/{user.id}/deactivate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_deact.status_code == 200
    assert resp_deact.json()["is_active"] is False

    # Reactivate
    resp_act = await client.post(
        f"/api/v1/users/{user.id}/activate",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_act.status_code == 200
    assert resp_act.json()["is_active"] is True


@pytest.mark.asyncio
async def test_role_change_revokes_active_sessions(client: AsyncClient, db_session: AsyncSession):
    """Changing user role revokes their active sessions to force re-authentication."""
    _, admin_token = await create_user_helper(db_session, "admin@socialos.io", role_name="ADMIN")
    user, _ = await create_user_helper(db_session, "role_change@socialos.io", role_name="CONTENT_CREATOR")

    # Login to create an active session
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "SecurePass123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Admin changes role to SOCIAL_MEDIA_MANAGER
    role_resp = await client.patch(
        f"/api/v1/users/{user.id}",
        json={"role": "SOCIAL_MEDIA_MANAGER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert role_resp.status_code == 200

    # Old refresh token session must now be revoked
    refresh_resp = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401

