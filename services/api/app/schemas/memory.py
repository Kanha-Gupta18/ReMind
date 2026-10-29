"""Pydantic schemas for the memory domain (spec §7, §18, §39)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    narrative: str | None = None
    memory_date: date | None = None
    date_accuracy: str | None = None
    tags: list[str] = Field(default_factory=list)
    sensitivity_flags: list[str] = Field(default_factory=list)
    visibility: Literal["patient", "family_only", "both"] = "both"
    media_urls: list[str] = Field(default_factory=list)
    people_ids: list[str] = Field(default_factory=list)
    place_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)


class MemoryEdit(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    narrative: str | None = None
    tags: list[str] | None = None
    memory_date: date | None = None
    date_accuracy: str | None = None
    visibility: Literal["patient", "family_only", "both"] | None = None
    sensitivity_flags: list[str] | None = None
    media_urls: list[str] | None = None
    people_ids: list[str] | None = None
    place_ids: list[str] | None = None
    event_ids: list[str] | None = None
    note: str | None = None


class ReviewAction(BaseModel):
    reason: str | None = None


class EvidenceReviewAction(BaseModel):
    status: Literal["ACCEPTED", "REJECTED", "DISPUTED"]


class EngageAction(BaseModel):
    action: str  # viewed|dwell|asked_question|closed
    duration_ms: int | None = None
