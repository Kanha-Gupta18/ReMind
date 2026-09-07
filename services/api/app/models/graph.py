"""Knowledge graph: nodes, edges, and edge evidence (spec §9)."""

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, JSON, String

from app.core.database import Base
from app.models.base import new_id, utcnow
from app.models.constants import EdgeStatus, GraphNodeType


class GraphNode(Base):
    """A node in the knowledge graph (spec §9).

    Node types cover people, places, events, memories, sources, media,
    topics, and more; metadata_json holds type-specific detail.
    """

    __tablename__ = "graph_nodes"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    node_type = Column(String, nullable=False)  # GraphNodeType
    name = Column(String, nullable=False)
    metadata_json = Column(JSON, default=dict)

    created_at = Column(DateTime(timezone=True), default=utcnow)


class GraphEdge(Base):
    """A relationship between two nodes (spec §9).

    Edges carry confidence, review status, dispute state, the reviewer,
    and which evidence supports them (evidence_ids), so the graph is
    explainable end-to-end — and the conversational interface can answer
    "who is that man?" by walking these edges.
    """

    __tablename__ = "graph_edges"

    id = Column(String, primary_key=True, default=new_id)
    patient_id = Column(String, ForeignKey("users.id"), nullable=False)

    source_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False)
    target_node_id = Column(String, ForeignKey("graph_nodes.id"), nullable=False)

    relation_type = Column(String, nullable=False)  # spouse|child_of|visited|lived_in|attended...
    weight = Column(Float, default=0.0)
    confidence = Column(Float, nullable=True)
    status = Column(String, default=EdgeStatus.SUGGESTED.value)
    disputed = Column(Boolean, default=False)

    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    model_version = Column(String, nullable=True)
    evidence_ids = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GraphEvidence(Base):
    """Why an edge exists: the exact data points that support it.

    Every confidence score is traceable back to source data (§5).
    Example: edge Priya--spouse-->Arjun is supported by
      ("photo_001.jpg face-match 0.91", "chat_export_2020 line 42", ...)
    """

    __tablename__ = "graph_evidence"

    id = Column(String, primary_key=True, default=new_id)
    edge_id = Column(String, ForeignKey("graph_edges.id"), nullable=False)

    source_data_ref = Column(String, nullable=False)  # e.g. "vision::photo_001"
    contribution = Column(Float, default=0.0)  # this source's weight
    detail = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
