from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.core.config import settings

api_router = APIRouter()


@api_router.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def health_check_v1() -> HealthResponse:
    """API v1 Health check endpoint."""
    return HealthResponse(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
