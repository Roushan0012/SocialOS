# SocialOS Company (Brand) & Membership Access Control Architecture (Step 8)

## 1. Terminology & Core Design Principles

- **Database Terminology:** `companies` and `company_memberships`.
- **UI / Product Terminology:** **Brands** and **Brand Access**.
- **Role vs. Membership Distinction:**
  - **System Role (`users.role_id`):** Dictates **WHAT** actions a user is authorized to perform (e.g., `ADMIN`, `SOCIAL_MEDIA_MANAGER`, `CONTENT_CREATOR`, `GRAPHIC_DESIGNER`, `VIDEO_EDITOR`).
  - **Company Membership (`company_memberships`):** Dictates **WHICH** companies/brands a user is permitted to access.
  - **System Administrator (`ADMIN`):** Possesses global administrative authority, automatically bypassing membership checks and having access to all companies.

---

## 2. Company Membership Database Model

Implemented in `backend/app/models/company_membership.py` and applied in migration `0003_add_company_memberships.py`:

```sql
CREATE TABLE company_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_company_memberships_company_user UNIQUE (company_id, user_id)
);

CREATE INDEX ix_company_memberships_company_id ON company_memberships (company_id);
CREATE INDEX ix_company_memberships_user_id ON company_memberships (user_id);
```

---

## 3. Access Control & Strict Company Isolation

### The Invariant
All business objects in SocialOS (e.g. posts, social accounts, tasks, analytics) are partitioned by `company_id`. A user who is not a member of a company must NEVER be able to:
1. Retrieve or view the company.
2. Access the company's social accounts, credentials, or posts.
3. Access the company's tasks or analytics.
4. Bypass isolation by guessing or manually providing the company's UUID in path, query, or body parameters.

### Reusable Authorization Helpers (`backend/app/api/deps.py` & `backend/app/services/company_service.py`)
- `CompanyService.user_can_access_company(db, user, company_id) -> bool`: Fast indexed count check.
- `CompanyService.get_authorized_company(db, company_id, user, include_inactive) -> Company`:
  - Returns 404 if company does not exist or is inactive.
  - Returns 403 Forbidden if user is non-admin and does not possess a membership.
- `get_authorized_company`: Route dependency injecting validated, authorized `Company`.
- `require_company_access(company_id, user, db)`: Reusable verification helper.

---

## 4. Concrete Multi-Brand Isolation Example

Suppose two companies exist:
- **Company A:** `RupeeQ` (`id: 11111111-1111-1111-1111-111111111111`, `slug: rupeeq`)
- **Company B:** `QFit` (`id: 22222222-2222-2222-2222-222222222222`, `slug: qfit`)

User `Alice` (`CONTENT_CREATOR`) has membership ONLY in `RupeeQ`.

| Request by Alice | Result | Security Enforcement |
| :--- | :--- | :--- |
| `GET /api/v1/companies` | Returns `[RupeeQ]` | Listing strictly filters by `company_memberships` for Alice. |
| `GET /api/v1/companies/11111111-...` | `200 OK` (RupeeQ) | Membership confirmed. |
| `GET /api/v1/companies/22222222-...` | `403 Forbidden` | Alice does not belong to QFit. Resource details are blocked. |
| `GET /api/v1/companies?include_inactive=true` | `403 Forbidden` | Inactive queries are restricted to system `ADMIN`. |

---

## 5. API Endpoints Overview

### Company Management (`/api/v1/companies`)
- `POST /api/v1/companies`: Create new brand workspace (`ADMIN` only).
- `GET /api/v1/companies`: List accessible brands (`ADMIN` sees all; non-admin sees member brands).
- `GET /api/v1/companies/{company_id}`: Retrieve company details (Strict isolation enforced).
- `PATCH /api/v1/companies/{company_id}`: Update brand name, slug, or logo (`ADMIN` only).
- `DELETE /api/v1/companies/{company_id}`: Soft-deactivate company (`is_active=false`) (`ADMIN` only).
- `POST /api/v1/companies/{company_id}/members`: Assign user membership (`ADMIN` only).
- `DELETE /api/v1/companies/{company_id}/members/{user_id}`: Revoke user membership (`ADMIN` only).
- `GET /api/v1/companies/{company_id}/members`: List brand members (`ADMIN` only).

### User Management (`/api/v1/users`)
- `POST /api/v1/users`: Create user with Argon2id encrypted password (`ADMIN` only).
- `GET /api/v1/users`: List users with pagination and role/active filters (`ADMIN` only).
- `GET /api/v1/users/me`: Authenticated user's self profile + list of authorized companies.
- `GET /api/v1/users/{user_id}`: Get user details and assigned brands (`ADMIN` only).
- `PATCH /api/v1/users/{user_id}`: Update user name, email, password, or role (`ADMIN` only).
  - Changing role immediately revokes all active refresh sessions to force token renewal with new claims.
- `POST /api/v1/users/{user_id}/deactivate`: Deactivate account and revoke all sessions (`ADMIN` only).
- `POST /api/v1/users/{user_id}/activate`: Reactivate account (`ADMIN` only).

---

## 6. Audit Logging (`activity_logs`)

All administrative and membership transitions record audit records:
- `COMPANY_CREATED`
- `COMPANY_UPDATED`
- `COMPANY_DEACTIVATED`
- `COMPANY_ACTIVATED`
- `USER_CREATED`
- `USER_UPDATED`
- `USER_ROLE_CHANGED`
- `USER_ACTIVATED`
- `USER_DEACTIVATED`
- `COMPANY_MEMBER_ADDED`
- `COMPANY_MEMBER_REMOVED`

All logs record the acting administrator's `user_id` and contain sanitized metadata free of passwords, tokens, or credentials.
