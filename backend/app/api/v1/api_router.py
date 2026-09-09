from fastapi import APIRouter, Response, status

from app.api.v1 import auth, companies, users
from app.core.config import settings
from app.core.database import check_database_health
from app.schemas.health import HealthResponse, DatabaseHealthResponse

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(users.router)


@api_router.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def health_check_v1() -> HealthResponse:
    """API v1 Health check endpoint."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@api_router.get(
    "/healthz/db",
    response_model=DatabaseHealthResponse,
    responses={
        200: {"model": DatabaseHealthResponse, "description": "Database reachable"},
        503: {"model": DatabaseHealthResponse, "description": "Database unreachable"},
    },
    tags=["Health"],
)
async def database_health_check_v1(response: Response) -> DatabaseHealthResponse:
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
