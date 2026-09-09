# SocialOS — Enterprise Social Media Command Center & Team Operations System

SocialOS is an enterprise multi-brand social media command center and team operations platform designed for marketing agencies, content creators, and distributed social teams.

> **Current Project Status:** Step 4 — Project Foundation & Development Infrastructure Scaffolding.  
> *Notice: No business features (OAuth, multi-brand publishing, analytics, LMS, attendance) are active yet. This repository currently contains the foundation, configuration, Docker development stack, and baseline health endpoints.*

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
│   │   ├── api/v1/               # API version 1 routers (/api/v1/healthz)
│   │   ├── core/                 # Config (Pydantic v2), Database (asyncpg), Redis
│   │   ├── models/               # SQLAlchemy 2.0 declarative models
│   │   ├── schemas/              # Pydantic v2 validation DTOs
│   │   ├── services/             # Domain business logic services (scaffolded)
│   │   ├── repositories/         # Database access layer (scaffolded)
│   │   ├── workers/              # Celery worker configuration & Celery Beat
│   │   │   ├── celery_app.py     # Celery app, queue routing, and beat schedule
│   │   │   └── tasks/            # Background tasks (test ping & heartbeat)
│   │   └── main.py               # ASGI application entrypoint with GET /healthz
│   ├── alembic/                  # Database migration scripts (Async SQLAlchemy 2.0)
│   ├── tests/                    # Pytest asynchronous API & worker test suite
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
* **Database & ORM:** PostgreSQL 16 (Target Production: Supabase PostgreSQL) + SQLAlchemy 2.0 Async (`asyncpg`) + Alembic.
* **Caching & Broker:** Redis 7.2+ (Session cache, token bucket rate limits, Celery message broker).
* **Distributed Tasks & Scheduler:** Celery 5.4+ with Celery Beat scheduler.
  * Configured Queues: `default`, `publish_queue`, `analytics_queue`, `maintenance_queue`, `dead_letter_queue`.
* **Production Media Storage & Delivery:** **AWS S3 + Amazon CloudFront**.
  * **AWS S3:** Private bucket with *Block Public Access* enabled; direct browser uploads via backend-generated presigned PUT URLs; automated 24-hour lifecycle deletion for unattached staging uploads.
  * **Amazon CloudFront:** Global CDN delivery fronting the private S3 bucket via **Origin Access Control (OAC)**.
  * **PostgreSQL:** Stores object keys and metadata only (`storage_key`, `cdn_url`); zero binary media in the database.
* **Local Media Storage:** **MinIO** container in Docker Compose (strictly for local development offline parity; never used in production).

---

## 3. Environment Variables Configuration

Copy `.env.example` to create your local `.env` file in the project root:

```bash
cp .env.example .env
```

Key environment groups configured in `.env`:
* `DATABASE_URL`: Asynchronous connection string (e.g., `postgresql+asyncpg://postgres:postgres@localhost:5432/socialos`).
* `REDIS_URL`: Redis cache connection string (`redis://localhost:6379/0`).
* `CELERY_BROKER_URL`: Redis queue broker URL (`redis://localhost:6379/1`).
* `CELERY_RESULT_BACKEND`: Redis task backend URL (`redis://localhost:6379/2`).
* `SECRET_KEY`: Application cryptographic secret.
* `USE_LOCAL_STORAGE`: Set to `true` for local MinIO emulation; `false` in staging/production for AWS S3.
* `MINIO_ENDPOINT`: Local MinIO S3 API URL (`http://localhost:9000`).
* `AWS_*` & `CLOUDFRONT_DOMAIN`: Production media storage credentials (placeholders only; never commit real secrets).

---

## 4. How to Start the Local Development Environment

### Option A: Using Docker Compose (Recommended for Full Stack)

Run the entire stack with a single command:

```bash
docker compose up -d
```

This provisions and starts:
1. `socialos-postgres`: PostgreSQL 16 database on port `5432`
2. `socialos-redis`: Redis 7.2 cache & broker on port `6379`
3. `socialos-minio`: MinIO S3-compatible storage on ports `9000` (API) & `9001` (Console)
4. `socialos-minio-init`: Automated local bucket provisioner (`socialos-media-local`)
5. `socialos-backend`: FastAPI with hot-reload on port `8000`
6. `socialos-worker`: Celery worker listening on all application queues
7. `socialos-beat`: Celery Beat periodic scheduler
8. `socialos-frontend`: Next.js 15 App Router web server on port `3000`

To stop all services:
```bash
docker compose down
```

---

### Option B: Running Services Locally on Host Machine

#### 1. Start Support Infrastructure (Redis, MinIO, PostgreSQL)
Ensure Redis and PostgreSQL are running locally or start them via Docker:
```bash
docker compose up -d socialos-redis socialos-postgres socialos-minio socialos-minio-init
```

#### 2. Backend (FastAPI)
```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
* Health Endpoint: [http://localhost:8000/healthz](http://localhost:8000/healthz)

#### 3. Frontend (Next.js 15)
```bash
cd frontend
npm install
npm run dev
```
* Application Interface: [http://localhost:3000](http://localhost:3000)

#### 4. Celery Worker Fleet
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app worker -l info -Q default,publish_queue,analytics_queue,maintenance_queue
```

#### 5. Celery Beat Scheduler
```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app.celery_app beat -l info
```

Alternatively, use the convenience runner script:
```bash
./scripts/dev.sh backend   # Launch FastAPI
./scripts/dev.sh frontend  # Launch Next.js
./scripts/dev.sh worker    # Launch Celery worker
./scripts/dev.sh beat      # Launch Celery Beat
./scripts/dev.sh test      # Run pytest suite
./scripts/dev.sh lint      # Run ESLint
```

---

## 5. Verification & Testing

### Backend Health & Unit Tests
```bash
cd backend
source .venv/bin/activate
pytest -v
```

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

* **Step 4 (Current):** Foundational architecture scaffolding, configuration, containerization, and health check endpoints.
* **Upcoming Steps:**
  * Authentication, JWT & RBAC layer
  * Database schema migrations (Brands, Social Accounts, Posts, Post Targets, Tasks, Attendance)
  * Direct-to-S3 Presigned Media Upload Service
  * Social OAuth Handshake (Meta, LinkedIn, YouTube)
  * Multi-Brand Composer & Scheduled Publishing Engine
  * Team Task LMS & Daily Attendance Ledger
