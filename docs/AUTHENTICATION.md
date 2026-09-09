# SocialOS Authentication & RBAC Architecture (Step 7)

## 1. Overview & Security Invariants

SocialOS implements a secure, standards-compliant authentication and Role-Based Access Control (RBAC) foundation built directly into the FastAPI backend with PostgreSQL (Supabase) persistence.

### Core Security Invariants
- **Never Store Plaintext Passwords:** Passwords are encrypted using **Argon2id** (OWASP recommended parameters).
- **Never Store Raw Refresh Tokens:** Only high-entropy cryptographically hashed digests (**SHA-256**) are stored in the database.
- **Constant-Time Verification:** Login verification uses constant-time comparison. Non-existent email queries trigger dummy password hashing verification to eliminate user-enumeration timing leaks.
- **Short-Lived Access Tokens:** Signed JWT access tokens expire after **15 minutes**.
- **Opaque Refresh Tokens with Rotation:** Refresh tokens expire after **7 days** and are strictly rotated upon each refresh invocation. Reuse of a revoked or previously rotated token is immediately blocked.
- **Zero Secrets in Logs or Exceptions:** Passwords, tokens, database connection strings, and credentials are never logged in `activity_logs`, server logs, or error responses.

---

## 2. Password Security (Argon2id)

Located in `backend/app/core/security.py`:
- **Algorithm:** Argon2id (`argon2-cffi`)
- **Parameters:**
  - `time_cost`: 2
  - `memory_cost`: 65536 KiB (64 MiB)
  - `parallelism`: 1
  - `hash_len`: 32 bytes
- **Validation:** Minimum 8 characters enforced before hashing.
- **Timing Leak Protection:** When an email does not exist in the database, `AuthService.authenticate_user` executes `verify_password(password, _DUMMY_HASH)` against a precomputed dummy hash, equalizing response times.

---

## 3. JWT Access Tokens

- **Algorithm:** HMAC-SHA256 (`HS256`)
- **Secret Key:** Configured via `JWT_SECRET_KEY` (minimum 32 characters required in production).
- **Expiration:** Configured via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15 minutes).
- **Claims:**
  - `sub`: User UUID string
  - `role`: Assigned system role name (`ADMIN`, `SOCIAL_MEDIA_MANAGER`, etc.)
  - `type`: `"access"`
  - `iat`: UNIX timestamp issued at
  - `exp`: UNIX timestamp expiration
  - `jti`: Unique token identifier UUID (prevents replay)

---

## 4. Refresh Tokens & Session Persistence

Located in `backend/app/models/auth_session.py`:

```sql
CREATE TABLE auth_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

### Rotation & Lifecycle Workflow
1. **Login:** Client provides valid credentials. System generates a 48-byte URL-safe raw refresh token, computes its SHA-256 hex digest, stores the session record in `auth_sessions`, logs `USER_LOGIN` in `activity_logs`, and returns `(access_token, raw_refresh_token, user_profile)`.
2. **Refresh:** Client sends `refresh_token`. The system computes its SHA-256 hash and looks up the session in `auth_sessions`:
   - If session not found: Returns `401 Unauthorized`.
   - If `revoked_at` is set: Returns `401 Unauthorized` (Token reuse detected).
   - If `expires_at <= now`: Returns `401 Unauthorized` (Token expired).
   - If user is inactive: Returns `401 Unauthorized` (Account deactivated).
   - Otherwise: Sets `revoked_at = now` on current session, issues a new access token and a brand new refresh token, saves new session in `auth_sessions`, and logs `TOKEN_REFRESH`.
3. **Logout:** Client provides `refresh_token`. System marks `revoked_at = now` and logs `USER_LOGOUT`.

---

## 5. System Roles & RBAC Foundation

The 5 seeded system roles (`roles` table):

| Role Name | Description | Access Level |
| :--- | :--- | :--- |
| `ADMIN` | System Administrator | Full access to all endpoints, user management, and system configs. |
| `SOCIAL_MEDIA_MANAGER` | Social Media Manager | Access to manager and team endpoints, post approval, analytics. |
| `CONTENT_CREATOR` | Content Creator | Access to team endpoints, drafting content, and media uploads. |
| `GRAPHIC_DESIGNER` | Graphic Designer | Access to team endpoints and design assets. |
| `VIDEO_EDITOR` | Video Editor | Access to team endpoints and video assets. |

### FastAPI Dependencies (`backend/app/api/deps.py`)
- `get_current_user`: Extracts Bearer token, validates claims, verifies user is active in DB.
- `require_roles(*roles)`: Factory verifying the authenticated user possesses one of the specified roles; raises `403 Forbidden` otherwise.
- `require_admin`: Restricts access to `ADMIN`.
- `require_manager`: Restricts access to `ADMIN` and `SOCIAL_MEDIA_MANAGER`.
- `require_team`: Permits access to all 5 system roles.

---

## 6. Auth REST API Endpoints (`/api/v1/auth`)

| Method | Endpoint | Protection | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Public | Authenticates credentials; returns access token, refresh token, and user profile. |
| `POST` | `/api/v1/auth/refresh` | Public | Rotates refresh token; returns new access token and new refresh token. |
| `POST` | `/api/v1/auth/logout` | Public (Token) | Revokes the presented refresh token session. |
| `GET` | `/api/v1/auth/me` | Bearer Auth | Returns current authenticated user profile (`password_hash` omitted). |
| `GET` | `/api/v1/auth/test/admin` | `require_admin` | RBAC test endpoint requiring `ADMIN` role. |
| `GET` | `/api/v1/auth/test/manager` | `require_manager` | RBAC test endpoint requiring `ADMIN` or `SOCIAL_MEDIA_MANAGER`. |
| `GET` | `/api/v1/auth/test/team` | `require_team` | RBAC test endpoint requiring any of the 5 system roles. |

---

## 7. Admin Bootstrap CLI Tool

An idempotent tool is provided to provision the initial administrator account:

```bash
# Using CLI flags
python -m app.cli.bootstrap_admin --email admin@socialos.io --password StrongPassword123! --name "System Administrator"

# Or using environment variables
BOOTSTRAP_ADMIN_EMAIL=admin@socialos.io BOOTSTRAP_ADMIN_PASSWORD=StrongPassword123! python -m app.cli.bootstrap_admin
```

- **Idempotent:** If an account with the specified email already exists, the tool outputs an informational message and cleanly exits without modifying the existing user or password hash.
- **Secure:** Plaintext password is never printed or saved unhashed.

---

## 8. Audit Logging

Every authentication milestone creates an audit record in `activity_logs`:
- `USER_LOGIN`: Records user ID, entity ID (session), client IP address, and client user-agent.
- `TOKEN_REFRESH`: Records user ID, new session entity ID, and previous session ID.
- `USER_LOGOUT`: Records user ID and session revocation event.
- `BOOTSTRAP_ADMIN`: Records admin creation with sanitized metadata.
