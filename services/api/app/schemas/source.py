"""Pydantic schemas for the source / pipeline domain (spec §5, §18)."""

from datetime import date

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    file_name: str = Field(min_length=1)
    file_type: str  # photo|video|audio|document|message_export
    context_tags: list[str] = []
    storage_path: str | None = None
    capture_date: date | None = None
    checksum: str | None = None
