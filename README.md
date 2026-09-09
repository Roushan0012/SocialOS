# SocialOS — Enterprise Social Media Command Center & Team Operations System

SocialOS is an enterprise multi-brand social media command center and team operations platform designed for marketing agencies, content creators, and distributed social teams.

> **Current Project Status:** Step 5 — Supabase PostgreSQL Database & Alembic Migration Foundation.  
> *Notice: No business features (OAuth, multi-brand publishing, analytics, LMS, attendance) or business tables are active yet. This repository contains the backend database integration, asyncpg connection pooling, Alembic migration configuration, Docker development stack, and database health endpoints.*

---

## 1. Project Directory Structure

```
SocialOS/
├── frontend/                     # Next.js 15 App Router Frontend
│   ├── src/
│   │   ├── app/                  # Layout, globals.css, and root page
│   │   ├── components/           # UI, layout, composer, pipeline, team, analytics
│   │   ├── hooks/                # Custom React Query hooks
│   │   ├── lib/                  # Shared utilities & API client
│   │   ├── stores/               # Zustand state stores
│   │   └── types/                # TypeScript DTOs & interfaces
│   ├── public/                   # Static public assets
│   ├── Dockerfile                # Frontend container image definition
│   ├── package.json              # Node dependencies (Next.js 15, React 19, Tailwind)
│   └── tsconfig.json             # TypeScript compiler configuration
├── backend/                      # Python FastAPI Async Backend
│   ├── app/
│   │   ├── api/v1/               # API version 1 routers (/api/v1/healthz, /api/v1/healthz/db)
│   │   ├── core/                 # Config (Pydantic v2), Database (asyncpg), Redis
│   │   ├── models/               # SQLAlchemy 2.0 declarative models (Base only)
│   │   ├── schemas/              # Pydantic v2 validation DTOs (HealthResponse, DatabaseHealthResponse)
│   │   ├── services/             # Domain business logic services (scaffolded)
│   │   ├── repositories/         # Database access layer (scaffolded)
│   │   ├── workers/              # Celery worker configuration & Celery Beat
│   │   │   ├── celery_app.py     # Celery app, queue routing, and beat schedule
│   │   │   └── tasks/            # Background tasks (test ping & heartbeat)
│   │   └── main.py               # ASGI application entrypoint with GET /healthz & /healthz/db
│   ├── alembic/                  # Database migration scripts (configured for DIRECT_URL)
│   ├── tests/                    # Pytest asynchronous API, config & database test suite
│   ├── alembic.ini               # Alembic migration configuration
│   ├── Dockerfile                # Backend container image definition
│   └── requirements.txt          # Python dependencies
├── docs/                         # Architecture & Specification Documents
│   ├── ARCHITECTURE.md           # Approved Production Architecture Document
│   └── PROTOTYPE_SPECIFICATION.md# Single Source of Truth Prototype Specification
├── infrastructure/               # Infrastructure-as-code & container assets
├── scripts/                      # Local development helper CLI scripts
│   └── dev.sh                    # Multi-command runner (backend, frontend, worker, beat)
├── social-crm.html               # Visual prototype reference artifact (READ ONLY)
├── .env.example                  # Environment configuration template
├── .gitignore                    # Comprehensive Git ignore rules
├── docker-compose.yml            # Local development orchestration stack
└── README.md                     # Engineering and setup documentation
```

---

## 2. Core Architecture & Technology Stack

* **Frontend:** Next.js 15 (App Router) + React 19 + TypeScript 5 + Tailwind CSS + Lucide Icons.
* **Backend API Engine:** Python 3.12+ + FastAPI (Async ASGI) + Pydantic v2.
* **Database & Persistence:** **Supabase Managed PostgreSQL** + SQLAlchemy 2.0 Async (`asyncpg`) + Alembic.
  * **Runtime Engine:** Connected via Supabase Supavisor connection pooler (`DATABASE_URL`).
  * **Migration Engine:** Connected via Supabase direct connection (`DIRECT_URL`).
  * **Strict Isolation:** Zero business tables exist in this step; only schema foundation and health verification queries (`SELECT 1`).
* **Caching & Broker:** Redis 7.2+ (Session cache, token bucket rate limits, Celery message broker).
* **Distributed Tasks & Scheduler:** Celery 5.4+ with Celery Beat scheduler.
  * Configured Queues: `default`, `publish_queue`, `analytics_queue`, `maintenance_queue`, `dead_letter_queue`.
* **Production Media Storage & Delivery:** **AWS S3 + Amazon CloudFront** (Singular production standard).
  * Private S3 bucket with *Block Public Access* enabled; direct browser uploads via backend-generated presigned PUT URLs; automated 24-hour lifecycle deletion for unattached staging uploads.
  * Amazon CloudFront global CDN fronting the private S3 bucket via **Origin Access Control (OAC)**.
  * **Important:** Supabase Storage is **NOT** used for media assets.
* **Local Media Storage:** **MinIO** container in Docker Compose (strictly for local development offline parity; never used in production).

---

## 3. Supabase PostgreSQL Setup & Environment Configuration

SocialOS uses a dedicated Supabase PostgreSQL project located in the Singapore region (`ap-southeast-1`):

* **Supabase Project URL:** `https://nsgpjfjziuedhnjkpucp.supabase.co`
* **Project Reference ID:** `nsgpjfjziuedhnjkpucp`
* **JWKS Verification URL:** `https://nsgpjfjziuedhnjkpucp.supabase.co/auth/v1/.well-known/jwks.json`

### Where to Obtain Connection Strings in Supabase

1. Open your project in the [Supabase Dashboard](https://supabase.com/dashboard/project/nsgpjfjziuedhnjkpucp).
2. Navigate to **Project Settings** → **Database** → **Connection string**.
3. **For `DATABASE_URL` (Application Runtime Pooler):**
   - Select the **Transaction** mode tab (Port `6543`) or **Session** mode tab (Port `5432`).
   - Copy the URI string and replace `[YOUR-PASSWORD]` with your actual database password.
   - Example format: `postgresql+asyncpg://postgres.nsgpjfjziuedhnjkpucp:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`
   - *Note: SQLAlchemy async engine automatically sets `statement_cache_size=0` to ensure safe operation with Supavisor transaction pooling.*
4. **For `DIRECT_URL` (Alembic Migrations):**
   - Select the **Direct connection** tab (Port `5432`).
   - Copy the URI string and replace `[YOUR-PASSWORD]` with your actual database password.
   - Example format: `postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.nsgpjfjziuedhnjkpucp.supabase.co:5432/postgres`

### Local `.env` Configuration

Copy `.env.example` to create your local `.env` file in the project root:

```bash
cp .env.example .env
```

Populate your local credentials in `.env`:
```ini
SUPABASE_URL=https://nsgpjfjziuedhnjkpucp.supabase.co
SUPABASE_PUBLISHABLE_KEY=<your-supabase-publishable-or-anon-key>
SUPABASE_SECRET_KEY=<your-supabase-service-role-secret-key>
SUPABASE_JWKS_URL=https://nsgpjfjziuedhnjkpucp.supabase.co/auth/v1/.well-known/jwks.json

DATABASE_URL=postgresql+asyncpg://postgres.nsgpjfjziuedhnjkpucp:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
DIRECT_URL=postgresql+asyncpg://postgres:[YOUR-PASSWORD]@db.nsgpjfjziuedhnjkpucp.supabase.co:5432/postgres
```

> **CRITICAL SECURITY REMINDER:**
> * Never commit `.env` or actual passwords to Git.
> * `.env` is strictly ignored by [`.gitignore`](file:///.gitignore).
> * `SUPABASE_SECRET_KEY` is strictly backend-only and must never be exposed to the frontend web application.

---

## 4. How to Start the Local Development Environment

### Option A: Using Docker Compose

Start local development support services:

```bash
docker compose up -d
```

This starts:
1. `socialos-redis`: Redis 7.2 cache & broker on port `6379`
2. `socialos-minio`: MinIO S3-compatible storage on ports `9000` (API) & `9001` (Console)
3. `socialos-minio-init`: Automated local bucket provisioner (`socialos-media-local`)
4. `socialos-backend`: FastAPI with hot-reload on port `8000` (connecting to Supabase PostgreSQL)
5. `socialos-worker`: Celery worker fleet
6. `socialos-beat`: Celery Beat periodic scheduler
7. `socialos-frontend`: Next.js 15 App Router web server on port `3000`

To stop all services:
```bash
docker compose down
```

---

### Option B: Running Services Locally on Host Machine

#### 1. Backend (FastAPI)
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* Application Health Check: [http://localhost:8000/healthz](http://localhost:8000/healthz)
* Database Health Check (SELECT 1): [http://localhost:8000/healthz/db](http://localhost:8000/healthz/db)

#### 2. Frontend (Next.js 15)
```bash
cd frontend
npm install
npm run dev
```
* Application Interface: [http://localhost:3000](http://localhost:3000)

#### 3. Celery Worker Fleet
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker -l info -Q default,publish_queue,analytics_queue,maintenance_queue
```

#### 4. Celery Beat Scheduler
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app beat -l info
```

---

## 5. Verification & Testing

### Backend Test Suite (19 Tests Passing)
```bash
cd backend
source .venv/bin/activate
pytest -v
```
Verifies:
* Supabase configuration loading & URL conversion
* Database connection health check (`SELECT 1`)
* Alembic migration configuration loading with `DIRECT_URL`
* Celery test ping & heartbeat tasks
* API health endpoints (`/healthz` and `/healthz/db`)
* Zero business tables invariant

### Frontend Type-Checking & Linting
```bash
cd frontend
npm run type-check
npm run lint
npm run build
```

### Docker Compose Configuration Validation
```bash
docker compose config --quiet
```

---

## 6. Scope & Roadmap

* **Step 4 (Completed):** Foundational architecture scaffolding, configuration, containerization.
* **Step 5 (Completed):** Supabase PostgreSQL database integration, asyncpg connection pooling, Alembic migration setup, and safe database health verification.
* **Upcoming Steps:**
  * Step 6: Authentication, JWT & RBAC layer
  * Step 7: Database schema migrations (Brands, Social Accounts, Posts, Post Targets, Tasks, Attendance)
  * Step 8: Direct-to-S3 Presigned Media Upload Service
  * Step 9: Social OAuth Handshake (Meta, LinkedIn, YouTube)
  * Step 10: Multi-Brand Composer & Scheduled Publishing Engine
  * Step 11: Team Task LMS & Daily Attendance Ledger
