"""Pydantic schemas for the people / face-match domain (spec §6, §18.2)."""

from pydantic import BaseModel, Field


class PersonCreate(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = []
    relationship_to_patient: str | None = None
    notes: str | None = None


class PersonUpdate(BaseModel):
    aliases: list[str] | None = None
    relationship_to_patient: str | None = None
    identity_status: str | None = None
    notes: str | None = None


class FaceMatchConfirm(BaseModel):
    person_id: str
