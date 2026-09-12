"""Request schemas for canonical places and events."""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class PlaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None


class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_accuracy: str = "approximate"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self
