"""Cryptographic Security & Authentication Utilities.

Implements Argon2id password hashing, JWT access token generation and decoding,
and SHA-256 refresh token hashing.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from app.core.config import settings

# Argon2id password hasher (OWASP recommended parameters)
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Plaintext passwords must NEVER be logged or persisted directly.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash in constant time.

    Returns:
        bool: True if password matches the hash, False otherwise.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False
    except Exception:
        return False


def validate_password_strength(password: str) -> None:
    """Validate that a password meets minimum security policy.

    Minimum policy: At least 8 characters.
    Raises:
        ValueError: If password is too short or empty.
    """
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")


def create_access_token(
    user_id: uuid.UUID | str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token with standard claims.

    Claims:
    - sub: User ID string
    - role: User system role name
    - type: 'access'
    - iat: Issued-at UNIX timestamp
    - exp: Expiration UNIX timestamp
    - jti: Unique token UUID
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
      expire = now + expires_delta
    else:
      expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Raises:
        jwt.ExpiredSignatureError: If token has expired.
        jwt.InvalidTokenError: If signature or claims are invalid.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "iat", "type"]},
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type. Expected access token.")
    return payload


def generate_refresh_token() -> str:
    """Generate a high-entropy cryptographically random raw refresh token.

    This raw token is returned to the authenticated client but NEVER persisted raw.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Generate a SHA-256 digest of a raw refresh token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
