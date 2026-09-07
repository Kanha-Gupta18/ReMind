"""Pydantic schemas for the memory domain (spec §7, §18, §39)."""

from datetime import date

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    narrative: str | None = None
    memory_date: date | None = None
    date_accuracy: str | None = None
    tags: list[str] = []
    sensitivity_flags: list[str] = []
    visibility: str | None = None
    media_urls: list[str] = []


class MemoryEdit(BaseModel):
    title: str | None = None
    narrative: str | None = None
    tags: list[str] | None = None
    note: str | None = None


class ReviewAction(BaseModel):
    reason: str | None = None


class EngageAction(BaseModel):
    action: str  # viewed|dwell|asked_question|closed
    duration_ms: int | None = None
