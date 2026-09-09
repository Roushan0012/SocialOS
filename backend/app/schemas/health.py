from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall health status")
    app: str = Field(default="SocialOS", description="Application name")
    version: str = Field(default="0.1.0", description="Application semantic version")
    environment: str = Field(default="development", description="Runtime environment")
