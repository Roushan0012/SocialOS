from typing import List, Optional
from urllib.parse import urlparse
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # 1. Application & Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "SocialOS"
    APP_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-this-in-production-use-a-strong-random-secret-key-32-chars"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # 2. Supabase Configuration (Region: Southeast Asia - Singapore)
    SUPABASE_URL: str = "https://nsgpjfjziuedhnjkpucp.supabase.co"
    SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    # Backend-only sensitive service role key; never exposed to frontend
    SUPABASE_SECRET_KEY: Optional[str] = None
    SUPABASE_JWKS_URL: str = "https://nsgpjfjziuedhnjkpucp.supabase.co/auth/v1/.well-known/jwks.json"

    # 3. Database (Supabase PostgreSQL via Supavisor Pooler & Direct Connection)
    # DATABASE_URL: Application runtime connection (uses Supabase connection pooler)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/socialos"
    # DIRECT_URL: Direct database connection reserved exclusively for Alembic migrations
    DIRECT_URL: Optional[str] = None

    @field_validator("DATABASE_URL", "DIRECT_URL", mode="before")
    @classmethod
    def assemble_async_db_connection(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        v = v.strip()
        # Convert postgres:// or postgresql:// to postgresql+asyncpg://
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def migration_database_url(self) -> str:
        """Connection string used by Alembic migrations. Uses DIRECT_URL if configured, otherwise DATABASE_URL."""
        return self.DIRECT_URL or self.DATABASE_URL

    @staticmethod
    def sanitize_db_url(url: Optional[str]) -> str:
        """Sanitize database URL by stripping out user credentials/passwords for safe logging."""
        if not url:
            return "not-configured"
        try:
            parsed = urlparse(url)
            netloc = parsed.hostname or "unknown"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            if parsed.username:
                netloc = f"{parsed.username}@{netloc}"
            return f"{parsed.scheme}://{netloc}{parsed.path}"
        except Exception:
            return "configured-hidden"

    # 4. Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # 5. Security & JWT
    JWT_SECRET_KEY: str = "socialos-dev-jwt-secret-key-change-in-production-min-32-chars-long"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    OAUTH_ENCRYPTION_KEY: Optional[str] = None

    # 5.1 Admin Bootstrap Configuration
    BOOTSTRAP_ADMIN_NAME: str = "Admin User"
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None

    # 5.2 Social Token Encryption (AES-256-GCM)
    SOCIAL_TOKEN_ENCRYPTION_KEY: str = "socialos-dev-social-token-encryption-key-32bytes!"

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            insecure_jwt = [
                "socialos-dev-jwt-secret-key-change-in-production-min-32-chars-long",
                "change-this",
                "secret",
            ]
            if any(bad in self.JWT_SECRET_KEY.lower() for bad in insecure_jwt) or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError(
                    "In production, JWT_SECRET_KEY must be a strong random secret with at least 32 characters."
                )
            if "change-this" in self.SECRET_KEY.lower() or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "In production, SECRET_KEY must be a strong random secret with at least 32 characters."
                )
            if (
                not self.SOCIAL_TOKEN_ENCRYPTION_KEY
                or len(self.SOCIAL_TOKEN_ENCRYPTION_KEY) < 32
                or "dev" in self.SOCIAL_TOKEN_ENCRYPTION_KEY.lower()
                or "change-this" in self.SOCIAL_TOKEN_ENCRYPTION_KEY.lower()
            ):
                raise ValueError(
                    "In production, SOCIAL_TOKEN_ENCRYPTION_KEY must be configured with a 256-bit (32-byte) strong random key."
                )
        return self

    # 6. Production Media Storage (AWS S3 + Amazon CloudFront)
    # Note: AWS S3 + Amazon CloudFront is the singular production architecture standard.
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    AWS_S3_BUCKET: str = "socialos-media-production"
    CLOUDFRONT_DOMAIN: Optional[str] = None

    # 7. Local Development Media Storage (MinIO Only)
    # MinIO is reserved strictly for local development offline parity.
    USE_LOCAL_STORAGE: bool = True
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "socialos-media-local"

    # 8. Social OAuth Providers Configuration
    # 8.1 Instagram
    INSTAGRAM_CLIENT_ID: Optional[str] = None
    INSTAGRAM_CLIENT_SECRET: Optional[str] = None
    INSTAGRAM_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/instagram/callback"
    INSTAGRAM_SCOPES: str = "instagram_basic,pages_show_list"

    # 8.2 Facebook
    FACEBOOK_CLIENT_ID: Optional[str] = None
    FACEBOOK_CLIENT_SECRET: Optional[str] = None
    FACEBOOK_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/facebook/callback"
    FACEBOOK_SCOPES: str = "pages_show_list,pages_read_engagement,pages_manage_posts,public_profile"

    # 8.3 LinkedIn
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/linkedin/callback"
    LINKEDIN_SCOPES: str = "openid,profile,email,w_member_social"

    # 8.4 YouTube / Google
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    YOUTUBE_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/oauth/youtube/callback"
    YOUTUBE_SCOPES: str = "https://www.googleapis.com/auth/youtube.readonly,https://www.googleapis.com/auth/userinfo.profile"

    # Meta & Google generic fallbacks
    META_CLIENT_ID: Optional[str] = None
    META_CLIENT_SECRET: Optional[str] = None
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None


settings = Settings()
