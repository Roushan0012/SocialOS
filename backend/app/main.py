from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api_router import api_router
from app.core.config import settings
from app.core.database import check_database_health
from app.schemas.health import HealthResponse, DatabaseHealthResponse

# Configure root logger
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("socialos")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} in [{settings.ENVIRONMENT}] mode...")
    sanitized_url = settings.sanitize_db_url(settings.DATABASE_URL)
    logger.info(f"Target Database endpoint: {sanitized_url}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SocialOS Enterprise Social Media Command Center & Team Operations API",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def root_health_check() -> HealthResponse:
    """Primary system health check endpoint required by production orchestration."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@app.get(
    "/healthz/db",
    response_model=DatabaseHealthResponse,
    responses={
        200: {"model": DatabaseHealthResponse, "description": "Database reachable"},
        503: {"model": DatabaseHealthResponse, "description": "Database unreachable"},
    },
    tags=["Health"],
)
async def root_database_health_check(response: Response) -> DatabaseHealthResponse:
    """Safe database connectivity health check (SELECT 1).
    Never exposes passwords, tokens, or connection strings.
    """
    is_connected = await check_database_health()
    if is_connected:
        return DatabaseHealthResponse(
            status="ok",
            database="connected",
            engine="postgresql+asyncpg",
        )
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return DatabaseHealthResponse(
        status="error",
        database="disconnected",
        engine="postgresql+asyncpg",
    )


@app.get("/", tags=["Root"])
async def root_info():
    """Root informative index."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "disabled",
        "health": "/healthz",
        "health_db": "/healthz/db",
    }


# Include versioned API routers
app.include_router(api_router, prefix=settings.API_V1_STR)
