"""Shared eligibility checks for content delivered to a patient."""

from sqlalchemy.orm import Session

from app.models.constants import (
    DeletionStatus,
    EdgeStatus,
    EvidenceReviewStatus,
    FaceMatchState,
    GraphNodeType,
    IdentityStatus,
    Role,
)
from app.models.graph import GraphEdge, GraphNode
from app.models.memory import Evidence, MemoryCard, Source
from app.models.people import FaceMatch, Person
from app.services import consent_service, safety_service


def memory_is_visible(db: Session, memory: MemoryCard) -> bool:
    if not consent_service.content_categories_are_allowed(
        db,
        memory.patient_id,
        memory.sensitivity_flags,
    ):
        return False
    result = safety_service.evaluate_release(
        memory,
        safety_service.resolve_safety_level(db, memory.patient_id),
        viewer_role=Role.PATIENT.value,
    )
    return result["allowed"]


def source_is_visible(db: Session, source: Source | None) -> bool:
    if source is None or source.deletion_status != DeletionStatus.ACTIVE.value:
        return False
    identified_people = (
        db.query(Person)
        .join(FaceMatch, FaceMatch.person_id == Person.id)
        .filter(
            FaceMatch.source_id == source.id,
            FaceMatch.face_match_state == FaceMatchState.FAMILY_CONFIRMED.value,
        )
        .all()
    )
    if any(not person_is_visible(db, person) for person in identified_people):
        return False
    memories = (
        db.query(MemoryCard)
        .join(Evidence, Evidence.memory_id == MemoryCard.id)
        .filter(
            Evidence.source_id == source.id,
            Evidence.review_status == EvidenceReviewStatus.ACCEPTED.value,
            MemoryCard.patient_id == source.patient_id,
        )
        .all()
    )
    return any(memory_is_visible(db, memory) for memory in memories)


def person_is_visible(db: Session, person: Person | None) -> bool:
    return bool(
        person
        and person.identity_status == IdentityStatus.FAMILY_CONFIRMED.value
        and consent_service.person_visibility_is_allowed(db, person)
    )


def person_for_node(db: Session, node: GraphNode) -> Person | None:
    person_id = (node.metadata_json or {}).get("person_id")
    if person_id:
        person = db.get(Person, person_id)
        if person and person.patient_id == node.patient_id:
            return person
    return (
        db.query(Person)
        .filter(Person.patient_id == node.patient_id, Person.name == node.name)
        .first()
    )


def memory_for_node(db: Session, node: GraphNode) -> MemoryCard | None:
    memory_id = (node.metadata_json or {}).get("memory_id")
    if memory_id:
        memory = db.get(MemoryCard, memory_id)
        if memory and memory.patient_id == node.patient_id:
            return memory
    return (
        db.query(MemoryCard)
        .filter(MemoryCard.patient_id == node.patient_id, MemoryCard.title == node.name)
        .first()
    )


def visible_relations(db: Session, patient_id: str, node_id: str) -> list[dict]:
    edges = (
        db.query(GraphEdge)
        .filter(
            GraphEdge.patient_id == patient_id,
            GraphEdge.status == EdgeStatus.CONFIRMED.value,
            GraphEdge.disputed.is_(False),
        )
        .filter(
            (GraphEdge.source_node_id == node_id) |
            (GraphEdge.target_node_id == node_id)
        )
        .all()
    )
    relations = []
    for edge in edges:
        other_id = edge.target_node_id if edge.source_node_id == node_id else edge.source_node_id
        other = db.get(GraphNode, other_id)
        if other is None or other.patient_id != patient_id:
            continue
        if other.node_type in {
            GraphNodeType.PERSON.value,
            GraphNodeType.FAMILY_MEMBER.value,
        } and not person_is_visible(db, person_for_node(db, other)):
            continue
        if other.node_type == GraphNodeType.MEMORY.value:
            memory = memory_for_node(db, other)
            if memory is None or not memory_is_visible(db, memory):
                continue
        if other.node_type in {
            GraphNodeType.SOURCE.value,
            GraphNodeType.PHOTO.value,
            GraphNodeType.VIDEO.value,
            GraphNodeType.AUDIO.value,
            GraphNodeType.DOCUMENT.value,
            GraphNodeType.MESSAGE.value,
            GraphNodeType.SENSITIVE_CATEGORY.value,
            GraphNodeType.CONSENT_DIRECTIVE.value,
        }:
            continue
        relations.append({
            "edge_id": edge.id,
            "relation_type": edge.relation_type,
            "direction": "outgoing" if edge.source_node_id == node_id else "incoming",
            "other_node_id": other.id,
            "other_node_type": other.node_type,
            "other_name": other.name,
            "confidence": edge.confidence,
            "status": edge.status,
            "disputed": edge.disputed,
        })
    return relations
