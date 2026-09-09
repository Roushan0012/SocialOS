"""User Management & Profile Pydantic Schemas."""
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.auth import UserResponse
from app.schemas.company import CompanySummary


class UserCreate(BaseModel):
    """Payload for administrator creating a new system user."""
    name: str = Field(..., min_length=1, max_length=255, description="Full display name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=8, description="Initial plaintext password (will be hashed)")
    role: str = Field(..., description="System role name (ADMIN, SOCIAL_MEDIA_MANAGER, etc.)")
    is_active: bool = Field(True, description="Account active status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Name cannot be blank")
        return s

    @field_validator("role")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        return v.strip().upper()


class UserUpdate(BaseModel):
    """Payload for administrator updating an existing user."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="Optional new password to set")
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Name cannot be blank")
            return s
        return v

    @field_validator("role")
    @classmethod
    def normalize_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip().upper()
        return v


class UserDetailResponse(BaseModel):
    """Detailed user profile including accessible companies."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    companies: List[CompanySummary] = []


class UserProfileResponse(BaseModel):
    """Self user profile returned by /users/me or /auth/me."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    companies: List[CompanySummary] = []


class UserListResponse(BaseModel):
    """Paginated list of users."""
    items: List[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int
