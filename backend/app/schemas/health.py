from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall application health status")
    app: str = Field(default="SocialOS", description="Application name")
    version: str = Field(default="0.1.0", description="Application semantic version")
    environment: str = Field(default="development", description="Runtime environment")
    database: Optional[str] = Field(default=None, description="Database connectivity status: 'connected' or 'disconnected'")


class DatabaseHealthResponse(BaseModel):
    status: str = Field(description="Database health check status: 'ok' or 'error'")
    database: str = Field(description="Database connection state: 'connected' or 'disconnected'")
    engine: str = Field(default="postgresql+asyncpg", description="Database dialect and driver")
