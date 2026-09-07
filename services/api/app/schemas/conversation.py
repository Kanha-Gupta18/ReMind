"""Pydantic schemas for the conversation domain (spec §21)."""

from pydantic import BaseModel, Field


class SessionStart(BaseModel):
    session_type: str = "chat"  # chat|reminiscence|support


class MessageSend(BaseModel):
    content: str = Field(min_length=1)
