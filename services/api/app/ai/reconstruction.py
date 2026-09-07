"""Turn processed sources into AI memory drafts (spec §7.3, §18).

process_source() runs the deterministic extractors, marks the source
COMPLETED, and records what was found (graph nodes/edges + face matches)
— always as SUGGESTED/UNIDENTIFIED, never as confirmed.

reconstruct_memories() then builds one AI_RECONSTRUCTED MemoryCard per
completed source: it gathers the extractor signals, scores confidence
with the §8.2 engine, records Evidence rows, links the graph, flags any
sensitive categories, and leaves the draft for family review.

Nothing an AI creates is ever shown to the patient as fact: drafts only
reach patient-facing surfaces after approve_memory() (§21 guardrail).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.ai import simulators
from app.models.base import utcnow
from app.models.constants import (
    DateAccuracy,
    EvidenceType,
    FaceMatchState,
    GraphNodeType,
    IdentityStatus,
    MemoryStatus,
    PipelineType,
    SensitivityCategory,
    SourceStatus,
)
from app.models.memory import Evidence, MemoryCard, Source
from app.models.people import FaceMatch, Person, Person
from app.services import confidence_service, evidence_service, graph_service

# Keyword -> sensitivity category for deterministic flagging (§16).
_SENSITIVITY_RULES: list[tuple[list[str], str]] = [
    (["war", "partition", "army service"], SensitivityCategory.WAR.value),
    (["passed away", "death of", "funeral", "he passed", "she passed"], SensitivityCategory.DEATH.value),
    (["abuse"], SensitivityCategory.ABUSE.value),
    (["divorce", "separated"], SensitivityCategory.DIVORCE.value),
    (["accident"], SensitivityCategory.ACCIDENT.value),
    (["cancer", "illness", "hospital", "diagnosis"], SensitivityCategory.SERIOUS_ILLNESS.value),
    (["estranged"], SensitivityCategory.ESTRANGEMENT.value),
    (["violence", "violent"], SensitivityCategory.VIOLENCE.value),
    (["trauma", "traumatic"], SensitivityCategory.TRAUMA.value),
]

_EDGE_RELATION_FOR_MEMORY = {
    "person": "depicts",
    "place": "happened_at",
    "event": "documents",
    "topic": "about",
}


def _flag_sensitivity(text: str) -> list[str]:
    lowered = (text or "").lower()
    flags = []
    for keywords, category in _SENSITIVITY_RULES:
        if any(k in lowered for k in keywords):
            flags.append(category)
    return flags


def _date_from_results(nlp: dict | None, source: Source):
    """Best-guess date + accuracy from nlp.dates (deterministic)."""
    if not nlp or not nlp.get("dates"):
        return None, None
    candidate = nlp["dates"][0]  # "1992" | "1992-05" | "1992-05-14"
    parts = [int(p) for p in candidate.split("-")]
    year = parts[0]
    if len(parts) == 3 and all(p > 0 for p in parts):
        return date(year, parts[1], parts[2]), DateAccuracy.EXACT.value
    if len(parts) == 2 and parts[1] > 0:
        return date(year, parts[1], 1), DateAccuracy.MONTH.value
    return date(year, 1, 1), DateAccuracy.YEAR.value


# ---------------------------------------------------------------------------
# Stage 1: process a source
# ---------------------------------------------------------------------------


def process_source(db: Session, source_id: str) -> Source:
    """Run the extraction pipeline over one source and persist findings."""
    source = db.get(Source, source_id)
    if source is None:
        raise ValueError(f"Source {source_id} not found")

    source.status = SourceStatus.PROCESSING.value
    source.pipeline_type = "+".join(simulators.extractors_for(source.file_type))
    db.flush()

    try:
        results = simulators.run_all_extractors(source, source.context_tags)
    except Exception as exc:  # a real pipeline would report model errors here
        source.status = SourceStatus.FAILED.value
        db.flush()
        raise RuntimeError(f"pipeline failed for {source_id}") from exc

    source.pipeline_results = results
    source.extraction_method = f"simulated::{results.get('model_version')}"
    source.status = SourceStatus.COMPLETED.value
    source.completed_at = utcnow()
    db.flush()

    _link_graph(db, source, results)
    _link_face_matches(db, source, results)
    db.flush()
    return source


def _link_graph(db: Session, source: Source, results: dict) -> None:
    """Create SUGGESTED person/place/event nodes + edges to the source."""
    nlp = results.get("nlp", {})
    source_node = graph_service.create_node(
        db, source.patient_id, GraphNodeType.SOURCE.value, source.file_name
    )

    for name in nlp.get("people", []):
        person = (
            db.query(Person)
            .filter(Person.patient_id == source.patient_id, Person.name == name)
            .first()
        )
        if person is None:
            person = Person(
                patient_id=source.patient_id,
                name=name,
                identity_status=IdentityStatus.UNIDENTIFIED.value,
                created_by=source.uploaded_by,
            )
            db.add(person)
            db.flush()
        node = graph_service.find_nodes(db, source.patient_id, GraphNodeType.PERSON.value, name)
        if not node:
            node = graph_service.create_node(
                db, source.patient_id, GraphNodeType.PERSON.value, name
            )
        edge = graph_service.create_edge(
            db, source.patient_id, node.id, source_node.id, "appears_in",
            weight=0.5, model_version=simulators.MODEL_VERSION,
        )
        graph_service.add_edge_evidence(
            db, edge.id, f"nlp::{source.file_name}",
            contribution=0.5, detail={"entity": name},
        )

    for place in nlp.get("places", []):
        node = graph_service.find_nodes(db, source.patient_id, GraphNodeType.PLACE.value, place)
        if not node:
            node = graph_service.create_node(
                db, source.patient_id, GraphNodeType.PLACE.value, place
            )
        edge = graph_service.create_edge(
            db, source.patient_id, node.id, source_node.id, "shows",
            weight=0.4, model_version=simulators.MODEL_VERSION,
        )
        graph_service.add_edge_evidence(
            db, edge.id, f"nlp::{source.file_name}", contribution=0.4, detail={"place": place},
        )


def _link_face_matches(db: Session, source: Source, results: dict) -> None:
    """Record AI face matches; only POSSIBLE/LIKELY, never confirmed."""
    vision = results.get("vision", {})
    nlp = results.get("nlp", {})
    people_names = nlp.get("people", [])

    for i, face in enumerate(vision.get("faces", [])):
        person = None
        if i < len(people_names):
            person = (
                db.query(Person)
                .filter(Person.patient_id == source.patient_id,
                        Person.name == people_names[i])
                .first()
            )
        match = FaceMatch(
            source_id=source.id,
            person_id=person.id if person else None,
            patient_id=source.patient_id,
            face_match_state=face["face_match_state"],
            confidence=face["confidence"],
            model_version=simulators.MODEL_VERSION,
        )
        db.add(match)
    db.flush()


# ---------------------------------------------------------------------------
# Stage 2: reconstruct memories from completed sources
# ---------------------------------------------------------------------------


def reconstruct_memories(
    db: Session, patient_id: str, source_ids: list[str] | None = None
) -> list[MemoryCard]:
    """Build AI_RECONSTRUCTED drafts for completed, unreconstructed sources."""
    query = db.query(Source).filter(
        Source.patient_id == patient_id,
        Source.status == SourceStatus.COMPLETED.value,
    )
    if source_ids:
        query = query.filter(Source.id.in_(source_ids))

    drafts: list[MemoryCard] = []
    for source in query.all():
        if _already_reconstructed(db, source.id):
            continue
        memory = _build_draft(db, source)
        if memory:
            drafts.append(memory)
    db.flush()
    return drafts


def _already_reconstructed(db: Session, source_id: str) -> bool:
    return (
        db.query(Evidence)
        .filter(Evidence.source_id == source_id)
        .first()
        is not None
    )


def _build_draft(db: Session, source: Source) -> MemoryCard | None:
    results = source.pipeline_results or {}
    nlp = results.get("nlp", {})
    vision = results.get("vision", {})
    loc = results.get("location", {})
    speech = results.get("speech", {})

    people = nlp.get("people", [])
    places = nlp.get("places", [])
    date_value, date_accuracy = _date_from_results(nlp, source)
    context_text = " ".join(str(t) for t in (source.context_tags or []))

    title = _build_title(people, places, date_value, source.file_name)
    narrative = _build_narrative(people, places, date_value, vision, speech, context_text)

    face_confidences = [f["confidence"] for f in vision.get("faces", [])]
    face_confidence = max(face_confidences) if face_confidences else None

    identity_status = None
    if people:
        person = (
            db.query(Person)
            .filter(Person.patient_id == source.patient_id, Person.name == people[0])
            .first()
        )
        identity_status = person.identity_status if person else None

    dates_list = nlp.get("dates", [])
    contradictions = []
    years = sorted({int(d.split("-")[0]) for d in dates_list})
    if len(years) > 1:
        contradictions.append(f"extractor found conflicting years: {', '.join(map(str, years))}")

    confidence = confidence_service.score_from_signals(
        date_accuracy=date_accuracy,
        face_confidence=face_confidence,
        identity_status=identity_status,
        has_exif=bool(loc.get("has_exif")),
        has_location_context=bool(loc.get("has_context_place") or places),
        independent_sources=1,
        review_state=MemoryStatus.AI_RECONSTRUCTED.value,
        contradictions=contradictions,
    )

    sensitivity = _flag_sensitivity(context_text)
    if speech.get("transcript"):
        sensitivity += _flag_sensitivity(speech["transcript"])

    from app.services import memory_service
    memory = memory_service.create_memory_card(
        db,
        patient_id=source.patient_id,
        title=title,
        narrative=narrative,
        media_urls=[source.storage_path or source.file_name],
        memory_date=date_value,
        date_accuracy=date_accuracy,
        confidence_score=confidence["overall_score"],
        confidence_breakdown=confidence["breakdown"],
        explanation=confidence["explanation"],
        contradictions=contradictions,
        sensitivity_flags=sorted(set(sensitivity)),
        tags=list(source.context_tags or []),
        status=MemoryStatus.AI_RECONSTRUCTED.value,
        model_version=simulators.MODEL_VERSION,
        created_by=source.uploaded_by,
    )

    _record_evidence(db, memory, source, results, confidence)
    _link_memory_graph(db, memory, people, places, date_value, source)
    return memory


def _build_title(people, places, date_value, file_name) -> str:
    person_part = f" with {people[0]}" if people else ""
    place_part = f" at {places[0]}" if places else ""
    year = f" ({date_value.year})" if date_value else ""
    if person_part or place_part:
        return f"Memory{person_part}{place_part}{year}".strip()
    return f"Memory from {file_name}"


def _build_narrative(people, places, date_value, vision, speech, context_text) -> str:
    bits = []
    if vision.get("scene"):
        bits.append(f"Shows a {vision['scene']}.")
    if speech.get("transcript"):
        bits.append(f"Recording: \"{speech['transcript']}\"")
    if places:
        bits.append(f"Likely at {places[0]}.")
    if date_value:
        bits.append(f"Dated around {date_value.isoformat()}.")
    if context_text:
        bits.append(f"Family notes: {context_text}")
    return " ".join(bits) or "A memory reconstructed from an uploaded source."


def _record_evidence(db, memory, source, results, confidence) -> None:
    nlp = results.get("nlp", {})
    vision = results.get("vision", {})
    loc = results.get("location", {})
    speech = results.get("speech", {})

    for face in vision.get("faces", []):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.FACE_MATCH.value,
            f"Face match at confidence {face['confidence']}",
            confidence=face["confidence"],
            extractor_version=results.get("model_version"),
        )
    if speech.get("transcript"):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.TRANSCRIPT.value,
            f"Transcript: {speech['transcript']}",
            extractor_version=results.get("model_version"),
        )
    for place in nlp.get("places", []):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.SEMANTIC.value,
            f"Place '{place}' extracted from family tags",
            extractor_version=results.get("model_version"),
        )
    if loc.get("has_exif"):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.LOCATION_EXIF.value,
            f"EXIF location {loc['gps']}",
            extractor_version=results.get("model_version"),
        )
    for tag in (source.context_tags or []):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.FAMILY_STATEMENT.value,
            f"Family statement: {tag}",
            confidence=None,
            extractor_version=results.get("model_version"),
        )
    # Always keep at least one semantic anchor so provenance is non-empty.
    if not vision and not speech and not nlp.get("places") and not loc.get("has_exif"):
        evidence_service.add_evidence(
            db, memory.id, source.id, EvidenceType.SEMANTIC.value,
            f"Memory reconstructed from {source.file_name}",
            extractor_version=results.get("model_version"),
        )


def _link_memory_graph(db, memory, people, places, date_value, source) -> None:
    memory_node = graph_service.create_node(
        db, source.patient_id, GraphNodeType.MEMORY.value, memory.title
    )
    for name in people:
        node = graph_service.find_nodes(
            db, source.patient_id, GraphNodeType.PERSON.value, name
        )
        if not node:
            node = [graph_service.create_node(
                db, source.patient_id, GraphNodeType.PERSON.value, name
            )]
        edge = graph_service.create_edge(
            db, source.patient_id, memory_node.id, node[0].id, "depicts",
            weight=0.6, created_by=source.uploaded_by,
            model_version=simulators.MODEL_VERSION,
            confidence=memory.confidence_score / 100.0,
        )
        graph_service.add_edge_evidence(
            db, edge.id, f"reconstruction::{memory.id}", contribution=0.6,
            detail={"memory_title": memory.title},
        )
    for place in places:
        node = graph_service.find_nodes(
            db, source.patient_id, GraphNodeType.PLACE.value, place
        )
        if not node:
            node = [graph_service.create_node(
                db, source.patient_id, GraphNodeType.PLACE.value, place
            )]
        edge = graph_service.create_edge(
            db, source.patient_id, memory_node.id, node[0].id, "happened_at",
            weight=0.4, created_by=source.uploaded_by,
            model_version=simulators.MODEL_VERSION,
        )
        graph_service.add_edge_evidence(
            db, edge.id, f"reconstruction::{memory.id}", contribution=0.4,
        )
    if date_value:
        date_node = graph_service.find_nodes(
            db, source.patient_id, GraphNodeType.DATE_RANGE.value, str(date_value.year)
        )
        if not date_node:
            date_node = [graph_service.create_node(
                db, source.patient_id, GraphNodeType.DATE_RANGE.value, str(date_value.year)
            )]
        graph_service.create_edge(
            db, source.patient_id, memory_node.id, date_node[0].id, "occurred_in",
            weight=0.2, created_by=source.uploaded_by,
            model_version=simulators.MODEL_VERSION,
        )
