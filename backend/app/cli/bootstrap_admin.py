"""Admin User Bootstrap Utility.

Provides an idempotent mechanism to provision the initial administrator account.
SECURITY RULES:
- Never overwrites an existing user.
- Password is encrypted with Argon2id before database storage.
- Passwords are NEVER printed or logged.
"""
import argparse
import asyncio
import os
import sys
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, validate_password_strength
from app.models.activity_log import ActivityLog
from app.models.role import Role
from app.models.user import User


async def bootstrap_admin_user(
    db: AsyncSession,
    email: str,
    password: str,
    name: str = "Admin User",
) -> Tuple[User, bool]:
    """Provision the initial admin user idempotently.

    Returns:
        Tuple[User, bool]: The user record and whether a new user was created.
    """
    normalized_email = email.strip().lower()
    validate_password_strength(password)

    # 1. Check if user with this email already exists
    stmt = (
        select(User)
        .options(joinedload(User.role))
        .where(User.email == normalized_email)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return existing_user, False

    # 2. Query the ADMIN role
    role_stmt = select(Role).where(Role.name == "ADMIN")
    role_res = await db.execute(role_stmt)
    admin_role = role_res.scalar_one_or_none()

    if not admin_role:
        raise RuntimeError(
            "ADMIN role does not exist in the database. Please run Alembic migrations first."
        )

    # 3. Create administrator with Argon2id hash
    hashed = hash_password(password)
    new_user = User(
        role_id=admin_role.id,
        role=admin_role,
        name=name.strip(),
        email=normalized_email,
        password_hash=hashed,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    # 4. Audit log entry
    audit_log = ActivityLog(
        user_id=new_user.id,
        action="BOOTSTRAP_ADMIN",
        entity_type="user",
        entity_id=new_user.id,
        log_metadata={"email": normalized_email, "name": name.strip()},
    )
    db.add(audit_log)

    await db.commit()
    res = await db.execute(
        select(User).options(joinedload(User.role)).where(User.id == new_user.id)
    )
    new_user = res.scalar_one()
    return new_user, True


async def main_async(args: argparse.Namespace) -> int:
    email = args.email or settings.BOOTSTRAP_ADMIN_EMAIL or os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    name = args.name or settings.BOOTSTRAP_ADMIN_NAME or os.environ.get("BOOTSTRAP_ADMIN_NAME", "Admin User")
    password = args.password or settings.BOOTSTRAP_ADMIN_PASSWORD or os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")

    if not email:
        print("Error: Admin email must be provided via --email or BOOTSTRAP_ADMIN_EMAIL environment variable.", file=sys.stderr)
        return 1

    if not password:
        print("Error: Admin password must be provided via --password or BOOTSTRAP_ADMIN_PASSWORD environment variable.", file=sys.stderr)
        return 1

    try:
        async with AsyncSessionLocal() as db:
            user, created = await bootstrap_admin_user(
                db=db,
                email=email,
                password=password,
                name=name,
            )

            if created:
                print(f"[SUCCESS] Bootstrapped initial admin user: {user.email} (Role: ADMIN)")
            else:
                print(f"[INFO] User '{user.email}' already exists. Refusing to overwrite existing account (Idempotent).")
            return 0
    except Exception as e:
        print(f"[ERROR] Admin bootstrap failed: {type(e).__name__} - {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="SocialOS Initial Administrator Bootstrap Tool")
    parser.add_argument("--email", type=str, help="Administrator email address")
    parser.add_argument("--name", type=str, default=None, help="Administrator display name")
    parser.add_argument("--password", type=str, help="Administrator plaintext password (will be hashed)")

    args = parser.parse_args()
    exit_code = asyncio.run(main_async(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
