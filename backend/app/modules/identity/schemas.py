import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_BYTES

Language = Literal["es", "en"]


def _check_password(value: str) -> str:
    if len(value) < 10:
        raise ValueError("Password must have at least 10 characters")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_BYTES} bytes")
    if value.isalpha() or value.isdigit():
        raise ValueError("Password must combine letters with digits or symbols")
    return value


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=200)
    plant_code: str = Field(min_length=1, max_length=30)
    plant_name: str = Field(min_length=2, max_length=200)
    timezone: str = Field(default="UTC", max_length=64)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str
    preferred_language: Language = "es"

    _pw = field_validator("password")(_check_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PlantRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str


class MembershipOut(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    role_code: str
    role_name: str
    permissions: list[str]
    # Empty list = access to every plant of the organization.
    plants: list[PlantRef]


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    preferred_language: str
    memberships: list[MembershipOut]


class MeUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    preferred_language: Language | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    # Initial password; only used when the e-mail does not exist yet.
    password: str
    role_code: str
    plant_ids: list[uuid.UUID] = []

    _pw = field_validator("password")(_check_password)


class UserUpdate(BaseModel):
    role_code: str | None = None
    plant_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


class OrgUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role_code: str
    role_name: str
    is_active: bool
    plants: list[PlantRef]
    last_login_at: datetime | None


class RoleOut(BaseModel):
    code: str
    name: str
    permissions: list[str]
