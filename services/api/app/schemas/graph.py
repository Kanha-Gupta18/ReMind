"""Pydantic schemas for the knowledge graph domain (spec §9)."""

from pydantic import BaseModel, Field


class NodeCreate(BaseModel):
    node_type: str
    name: str = Field(min_length=1)
    metadata: dict = {}


class EdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    relation_type: str
    weight: float = 0.0
    confidence: float | None = None


class EdgeReview(BaseModel):
    status: str  # CONFIRMED|DISPUTED|REJECTED
    disputed: bool = False
