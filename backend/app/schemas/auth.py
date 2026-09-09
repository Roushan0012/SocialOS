"""Authentication and User Pydantic Schemas."""
import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Payload for user credentials login."""
    email: EmailStr = Field(..., description="User account email address")
    password: str = Field(..., min_length=8, description="Plaintext account password")


class RefreshRequest(BaseModel):
    """Payload for access token refresh."""
    refresh_token: str = Field(..., min_length=16, description="Opaque raw refresh token")


class LogoutRequest(BaseModel):
    """Payload for session logout and revocation."""
    refresh_token: Optional[str] = Field(None, description="Optional raw refresh token to revoke explicitly")


class UserResponse(BaseModel):
    """Safe authenticated user profile view excluding credentials."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    """Authentication token response issued upon successful login or refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic status and confirmation message response."""
    detail: str
