# SocialOS Infrastructure Architecture

This directory houses infrastructure-as-code, Docker configuration, and deployment manifests.

## Environments

1. **Local Development:**
   - Handled via `docker-compose.yml` in the project root.
   - Services: PostgreSQL 16, Redis 7.2, MinIO (S3-compatible local emulator), FastAPI backend, Next.js frontend, Celery workers, and Celery Beat.
   - **Important:** MinIO is used *strictly for local development* to allow developers to build and test direct S3-compatible upload flows offline.

2. **Production:**
   - **Application Compute:** Containerized deployment (AWS ECS / Kubernetes).
   - **Database:** Supabase Managed PostgreSQL.
   - **Queue & Cache:** AWS ElastiCache / Managed Redis 7.2+.
   - **Media Storage:** AWS S3 (Private Bucket with Block Public Access).
   - **CDN & Media Delivery:** Amazon CloudFront with Origin Access Control (OAC).
