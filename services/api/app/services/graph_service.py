"""Knowledge graph operations (spec §9).

Nodes are people, places, events, memories, sources, media, topics...
Edges relate nodes with a confidence, review status, and dispute state.
Every edge is traceable: GraphEvidence rows say exactly which data points
support it (spec §5), and evidence_ids references the Evidence table.

All operations are scoped to a patient (tenant isolation, §24).
"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.constants import EdgeStatus
from app.models.graph import GraphEdge, GraphEvidence, GraphNode


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def create_node(
    db: Session,
    patient_id: str,
    node_type: str,
    name: str,
    metadata: dict | None = None,
) -> GraphNode:
    node = GraphNode(
        patient_id=patient_id,
        node_type=node_type,
        name=name,
        metadata_json=metadata or {},
    )
    db.add(node)
    db.flush()
    return node


def get_node(db: Session, node_id: str) -> GraphNode | None:
    return db.get(GraphNode, node_id)


def find_nodes(
    db: Session,
    patient_id: str,
    node_type: str | None = None,
    name_contains: str | None = None,
) -> list[GraphNode]:
    query = db.query(GraphNode).filter(GraphNode.patient_id == patient_id)
    if node_type:
        query = query.filter(GraphNode.node_type == node_type)
    if name_contains:
        query = query.filter(GraphNode.name.ilike(f"%{name_contains}%"))
    return query.order_by(GraphNode.name).all()


def list_patient_nodes(db: Session, patient_id: str) -> list[GraphNode]:
    return find_nodes(db, patient_id)


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


def create_edge(
    db: Session,
    patient_id: str,
    source_node_id: str,
    target_node_id: str,
    relation_type: str,
    weight: float = 0.0,
    created_by: str | None = None,
    model_version: str | None = None,
    confidence: float | None = None,
) -> GraphEdge:
    """Create an edge. Defaults to SUGGESTED until a reviewer confirms it."""
    edge = GraphEdge(
        patient_id=patient_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relation_type=relation_type,
        weight=weight,
        confidence=confidence,
        status=EdgeStatus.SUGGESTED.value,
        created_by=created_by,
        model_version=model_version,
    )
    db.add(edge)
    db.flush()
    return edge


def get_edge(db: Session, edge_id: str) -> GraphEdge | None:
    return db.get(GraphEdge, edge_id)


def update_edge_review(
    db: Session,
    edge_id: str,
    status: str,
    reviewed_by: str,
    disputed: bool = False,
) -> GraphEdge:
    """Reviewer action: confirm, dispute, or reject an edge."""
    edge = get_edge(db, edge_id)
    if edge is None:
        raise ValueError(f"Edge {edge_id} not found")
    edge.status = status
    edge.disputed = disputed
    edge.reviewed_by = reviewed_by
    edge.reviewed_at = utcnow()
    db.flush()
    return edge


def list_edges_for_node(db: Session, patient_id: str, node_id: str) -> list[GraphEdge]:
    """All edges touching a node — how the conversational interface answers
    'who is that man?' by walking the graph."""
    return (
        db.query(GraphEdge)
        .filter(GraphEdge.patient_id == patient_id)
        .filter(or_(GraphEdge.source_node_id == node_id, GraphEdge.target_node_id == node_id))
        .all()
    )


def get_patient_graph(db: Session, patient_id: str) -> dict:
    """Full graph export for a patient (frontend visualisation)."""
    nodes = list_patient_nodes(db, patient_id)
    edges = db.query(GraphEdge).filter(GraphEdge.patient_id == patient_id).all()
    return {
        "nodes": nodes,
        "edges": edges,
    }


def resolve_relations_for_person(
    db: Session, patient_id: str, person_node_id: str
) -> list[dict]:
    """The people/places/memories directly connected to a person node."""
    edges = list_edges_for_node(db, patient_id, person_node_id)
    results = []
    for edge in edges:
        other_id = (
            edge.target_node_id if edge.source_node_id == person_node_id else edge.source_node_id
        )
        other = get_node(db, other_id)
        if other is None:
            continue
        direction = "outgoing" if edge.source_node_id == person_node_id else "incoming"
        results.append(
            {
                "edge_id": edge.id,
                "relation_type": edge.relation_type,
                "direction": direction,
                "other_node_id": other.id,
                "other_node_type": other.node_type,
                "other_name": other.name,
                "confidence": edge.confidence,
                "status": edge.status,
                "disputed": edge.disputed,
            }
        )
    return results


# ---------------------------------------------------------------------------
# Edge evidence (traceability, §5)
# ---------------------------------------------------------------------------


def add_edge_evidence(
    db: Session,
    edge_id: str,
    source_data_ref: str,
    contribution: float = 0.0,
    detail: dict | None = None,
) -> GraphEvidence:
    ev = GraphEvidence(
        edge_id=edge_id,
        source_data_ref=source_data_ref,
        contribution=contribution,
        detail=detail or {},
    )
    db.add(ev)
    db.flush()
    return ev


def trace_edge(db: Session, edge_id: str) -> list[GraphEvidence]:
    """Why does this edge exist? Return the exact supporting data points."""
    return db.query(GraphEvidence).filter(GraphEvidence.edge_id == edge_id).all()
