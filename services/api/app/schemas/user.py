"""Pydantic schemas for the user / auth domain."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """Public view of a user, safe to return to any authenticated client."""

    id: str
    email: str
    full_name: str
    role: str
    patient_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Administrator creates a user (spec §23)."""

    email: str
    full_name: str = Field(min_length=1)
    role: str
    password: str = Field(min_length=8)
    patient_id: str | None = None


class UserUpdate(BaseModel):
    """Partial update performed by an administrator."""

    full_name: str | None = None
    role: str | None = None
    password: str | None = Field(default=None, min_length=8)
    patient_id: str | None = None
    is_active: bool | None = None


class UserAdminOut(BaseModel):
    """Administrator view: adds account state to the public view."""

    id: str
    email: str
    full_name: str
    role: str
    patient_ids: list[str] = Field(default_factory=list)
    phone: str | None = None
    mfa_enabled: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
