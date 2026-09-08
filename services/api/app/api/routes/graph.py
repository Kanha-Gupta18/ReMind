"""Knowledge graph routes: export, nodes, edges, review, trace (spec §9, §24).

RBAC:
  - family and support roles may read the review graph; patient-facing graph
    facts are delivered through filtered people and conversation routes
  - reviewer/guardian/admin confirm or dispute edges (review lifecycle)
  - contributor may create suggested edges
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_patient_scope, require_consent_action, require_roles
from app.core.database import get_db
from app.models.constants import ConsentAction, EdgeStatus, Role
from app.models.graph import GraphEdge, GraphNode
from app.models.user import User
from app.schemas.graph import EdgeCreate, EdgeReview, NodeCreate
from app.services import audit_service, graph_service

router = APIRouter(prefix="/graph", tags=["graph"])

_REVIEW_ROLES = [Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value]
_CREATE_ROLES = _REVIEW_ROLES + [Role.FAMILY_CONTRIBUTOR.value, Role.CLINICIAN.value,
                                 Role.CAREGIVER.value]
_READ_ROLES = _CREATE_ROLES


def _resolve_scope(scope: str | None, patient_id: str | None = None) -> str:
    """Scope resolution: linked roles use their patient; administrator must
    pass patient_id explicitly (cross-patient)."""
    if scope is not None:
        if patient_id and patient_id != scope:
            raise HTTPException(status_code=403, detail="Not your patient")
        return scope
    if patient_id is None:
        raise HTTPException(status_code=403, detail="Administrator must pick a patient")
    return patient_id


@router.get("")
def get_graph(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.GRAPH_VIEW)
    graph = graph_service.get_patient_graph(db, pid)
    return {
        "nodes": [_node_json(n) for n in graph["nodes"]],
        "edges": [_edge_json(e) for e in graph["edges"]],
    }


@router.get("/nodes")
def list_nodes(
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
    node_type: str | None = None,
    name: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.GRAPH_VIEW)
    nodes = graph_service.find_nodes(db, pid, node_type=node_type, name_contains=name)
    return {"items": [_node_json(n) for n in nodes], "count": len(nodes)}


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_node(
    body: NodeCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_CREATE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.GRAPH_EDIT)
    node = graph_service.create_node(db, pid, body.node_type, body.name, body.metadata)
    audit_service.log_action(db, current.id, "created", "graph_node", node.id)
    db.commit()
    return _node_json(node)


@router.post("/edges", status_code=status.HTTP_201_CREATED)
def create_edge(
    body: EdgeCreate,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_CREATE_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    patient_id: str | None = None,
):
    pid = _resolve_scope(scope, patient_id)
    require_consent_action(db, current, pid, ConsentAction.GRAPH_EDIT)
    for node_id in (body.source_node_id, body.target_node_id):
        node = db.get(GraphNode, node_id)
        if node is None or node.patient_id != pid:
            raise HTTPException(status_code=404, detail="Node not found in your graph")
    edge = graph_service.create_edge(
        db, pid, body.source_node_id, body.target_node_id,
        body.relation_type, weight=body.weight,
        created_by=current.id, confidence=body.confidence,
    )
    audit_service.log_action(db, current.id, "created", "graph_edge", edge.id)
    db.commit()
    return _edge_json(edge)


@router.post("/edges/{edge_id}/review")
def review_edge(
    edge_id: str,
    body: EdgeReview,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_REVIEW_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    edge = graph_service.get_edge(db, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    if scope is not None and edge.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your edge")
    require_consent_action(db, current, edge.patient_id, ConsentAction.GRAPH_REVIEW)
    if body.status not in {EdgeStatus.CONFIRMED.value, EdgeStatus.DISPUTED.value,
                           EdgeStatus.REJECTED.value}:
        raise HTTPException(status_code=400, detail="Invalid status")
    graph_service.update_edge_review(db, edge_id, body.status, current.id, body.disputed)
    audit_service.log_action(db, current.id, body.status.lower(), "graph_edge", edge.id)
    db.commit()
    return _edge_json(graph_service.get_edge(db, edge_id))


@router.get("/edges/{edge_id}/trace")
def trace_edge(
    edge_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    edge = graph_service.get_edge(db, edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    if scope is not None and edge.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your edge")
    require_consent_action(db, current, edge.patient_id, ConsentAction.GRAPH_VIEW)
    evidence = graph_service.trace_edge(db, edge_id)
    return {"items": [
        {"id": ev.id, "source_data_ref": ev.source_data_ref,
         "contribution": ev.contribution, "detail": ev.detail}
        for ev in evidence
    ]}


@router.get("/people/{person_id}/relations")
def person_relations(
    person_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_READ_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    node = db.get(GraphNode, person_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if scope is not None and node.patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your graph")
    require_consent_action(db, current, node.patient_id, ConsentAction.GRAPH_VIEW)
    return {"items": graph_service.resolve_relations_for_person(db, scope or node.patient_id, person_id)}


def _node_json(n: GraphNode) -> dict:
    return {"id": n.id, "node_type": n.node_type, "name": n.name,
            "metadata": n.metadata_json, "created_at": n.created_at.isoformat()}


def _edge_json(e: GraphEdge) -> dict:
    return {
        "id": e.id,
        "patient_id": e.patient_id,
        "source_node_id": e.source_node_id,
        "target_node_id": e.target_node_id,
        "relation_type": e.relation_type,
        "weight": e.weight,
        "confidence": e.confidence,
        "status": e.status,
        "disputed": e.disputed,
        "reviewed_by": e.reviewed_by,
        "reviewed_at": e.reviewed_at.isoformat() if e.reviewed_at else None,
        "evidence_ids": e.evidence_ids or [],
        "model_version": e.model_version,
    }
