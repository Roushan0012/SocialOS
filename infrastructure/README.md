# SocialOS Infrastructure Architecture

This directory houses infrastructure-as-code, Docker configuration, and deployment manifests.

## Database & Persistence Layer (Supabase PostgreSQL)

* **Primary Database Target:** Supabase Managed PostgreSQL (Region: Southeast Asia - Singapore, Project Ref: `nsgpjfjziuedhnjkpucp`).
* **Connection Routing:**
  * **Application Runtime (`DATABASE_URL`):** Connects through the Supabase Supavisor connection pooler (Transaction pooler on port 6543 or Session pooler on port 5432). Configured with `statement_cache_size=0` in SQLAlchemy 2.0 Async (`asyncpg`) to avoid prepared statement caching conflicts.
  * **Database Migrations (`DIRECT_URL`):** Reserved exclusively for Alembic migrations via direct connection (port 5432) or session pooler, enabling DDL transactional execution.
* **Security & Secret Isolation:**
  * Credentials and passwords must be stored solely in `.env` (strictly ignored by Git).
  * `SUPABASE_SECRET_KEY` is strictly backend-only and never exposed to client applications.
  * Zero business tables exist during the foundation phase. All future schema migrations will execute via Alembic.

## Storage Architecture

* **Production Media Storage:** **AWS S3 + Amazon CloudFront** (Singular production standard).
  * Private S3 bucket with AWS *Block Public Access* enabled.
  * Amazon CloudFront global CDN fronting S3 using *Origin Access Control (OAC)*.
  * Supabase Storage is **NOT** used for media storage.
* **Local Development Storage:** **MinIO** via Docker Compose (reserved strictly for offline local S3 emulation).

## Environments

1. **Local Development:**
   - Handled via `docker-compose.yml` in the project root.
   - Services: Redis 7.2, MinIO (S3-compatible local emulator), FastAPI backend, Next.js frontend, Celery workers, Celery Beat, and optional offline PostgreSQL 16.
2. **Production:**
   - **Application Compute:** Containerized deployment (AWS ECS / Kubernetes).
   - **Database:** Supabase Managed PostgreSQL.
   - **Queue & Cache:** AWS ElastiCache / Managed Redis 7.2+.
   - **Media Storage:** AWS S3 (Private Bucket) + Amazon CloudFront CDN (OAC).
