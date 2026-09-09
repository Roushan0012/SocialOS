"""Company (Brand) & Company Membership Pydantic Schemas."""
import re
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_slug(v: str) -> str:
    """Normalize string to lowercase, hyphen-separated alphanumeric slug."""
    if not v:
        raise ValueError("Slug cannot be empty")
    s = v.strip().lower()
    # Replace spaces, underscores, and consecutive hyphens
    s = re.sub(r"[\s_]+", "-", s)
    # Remove any character not in [a-z0-9-]
    s = re.sub(r"[^a-z0-9-]", "", s)
    # Strip leading/trailing hyphens
    s = s.strip("-")
    if not s:
        raise ValueError("Slug must contain alphanumeric characters")
    return s


class CompanyCreate(BaseModel):
    """Payload for creating a new company/brand."""
    name: str = Field(..., min_length=1, max_length=255, description="Brand/Company display name")
    slug: str = Field(..., min_length=1, max_length=100, description="Unique URL-safe brand identifier")
    logo_url: Optional[str] = Field(None, max_length=512, description="Optional public brand logo URL")
    is_active: bool = Field(True, description="Brand status flag")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Company name cannot be blank")
        return s

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        return normalize_slug(v)


class CompanyUpdate(BaseModel):
    """Payload for updating an existing company/brand."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    logo_url: Optional[str] = Field(None, max_length=512)
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            s = v.strip()
            if not s:
                raise ValueError("Company name cannot be blank")
            return s
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return normalize_slug(v)
        return v


class CompanySummary(BaseModel):
    """Lightweight brand reference for embedded responses."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    is_active: bool


class CompanyResponse(BaseModel):
    """Full company representation excluding internal metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompanyListResponse(BaseModel):
    """Paginated list of companies."""
    items: List[CompanyResponse]
    total: int
    page: int
    page_size: int
    pages: int


class CompanyMemberAddRequest(BaseModel):
    """Payload to associate a user with a company."""
    user_id: uuid.UUID = Field(..., description="ID of the user to grant company access")


class CompanyMemberResponse(BaseModel):
    """User membership representation within a company."""
    membership_id: uuid.UUID
    company_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: str
    is_active: bool
    joined_at: datetime
