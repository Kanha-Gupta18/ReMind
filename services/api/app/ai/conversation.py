"""Conversational interface to the knowledge graph (spec §21).

The agent exposes ten tools — the same surface a real LLM agent would be
given — and a deterministic intent router that picks tools from the
patient's words. All replies are composed ONLY from tool results; the
guardrails below make that a hard rule:

  1. Never fabricate: if no tool result backs a claim, the agent says so.
  2. Express uncertainty: suggested-only facts are labelled "not fully sure".
  3. Respect consent/visibility: memory tools run the safety release gate.
  4. Restricted content is never surfaced: blocked queries are logged as
     safety events and answered with a neutral redirect (§18.5).
  5. Never diagnose: medical questions are declined and pointed to the
     caregiver/clinician.
  6. Never coach or confirm the patient's guesses about restricted topics.

Every turn is persisted as ConversationMessage rows (patient / tool /
system) with the tool_calls recorded, so answers stay auditable (§5).
"""

import re

from sqlalchemy.orm import Session

from app.models.base import utcnow
from app.models.constants import (
    ConversationSessionStatus,
    ConversationSessionType,
    DeletionStatus,
    EdgeStatus,
    EvidenceReviewStatus,
    FaceMatchState,
    IdentityStatus,
    MemoryStatus,
    MessageRole,
    NotificationType,
    Role,
    SensitivityCategory,
)
from app.models.conversation import ConversationMessage, ConversationSession
from app.models.memory import MemoryCard, Source as SourceModel
from app.models.people import FaceMatch, Person
from app.services import (
    evidence_service,
    graph_service,
    memory_service,
    notification_service,
    patient_delivery_service,
    safety_service,
)

UNCERTAINTY_PREFIXES = ["I think", "I'm not fully sure, but"]
STOPWORDS = {"the", "a", "an", "about", "of", "and", "for", "with", "that", "this", "is", "was"}
UNCERTAINTY_FALLBACK = (
    "I'm sorry — I don't have a clear memory of that, and I don't want to guess. "
    "Would you like to talk about something else?"
)
MEDICAL_DECLINE = (
    "That's a question for your doctor or your care team, not for me — "
    "I only talk about memories. Should I ask your family to set that up?"
)

# Sensitive categories the agent must never surface to the patient (§16, §21).
_RESTRICTED_TOPICS = {
    SensitivityCategory.DEATH.value: ["death of", "passed away", "funeral", "died"],
    SensitivityCategory.ABUSE.value: ["abuse", "abused"],
    SensitivityCategory.WAR.value: ["war", "partition"],
    SensitivityCategory.TRAUMA.value: ["trauma", "traumatic"],
    SensitivityCategory.VIOLENCE.value: ["violence", "violent", "assault"],
}

_MEDICAL_PATTERNS = [
    "diagnos", "alzheimer", "dementia", "medicin", "medicine", "pill",
    "should i take", "do i have", "is something wrong with me",
]

_TOOL_NAMES = [
    "get_person", "get_relationship", "get_memory", "search_memories",
    "get_photo_context", "get_event", "get_place", "get_evidence",
    "get_safety_policy", "request_family_help",
]


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def start_session(
    db: Session,
    patient_id: str,
    session_type: str = ConversationSessionType.CHAT.value,
    started_by: str | None = None,
) -> ConversationSession:
    session = ConversationSession(
        patient_id=patient_id,
        session_type=session_type,
        status=ConversationSessionStatus.ACTIVE.value,
        started_by=started_by,
    )
    db.add(session)
    db.flush()
    return session


def stop_session(db: Session, session_id: str) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    session.status = ConversationSessionStatus.ENDED.value
    session.ended_at = utcnow()
    db.flush()
    return session


def session_history(db: Session, session_id: str) -> list[ConversationMessage]:
    return (
        db.query(ConversationMessage)
        .filter(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at)
        .all()
    )


HISTORY_UNAVAILABLE = "This earlier response is no longer available because its source changed."


def patient_session_history(db: Session, session: ConversationSession) -> list[dict]:
    """Recheck stored answers and omit internal tool records before delivery."""
    tools = _build_tools(db, session.patient_id, session.id, Role.PATIENT.value)
    pending_tool = None
    items = []
    for message in session_history(db, session.id):
        if message.role == MessageRole.TOOL.value:
            pending_tool = message.tool_calls[0] if message.tool_calls else None
            continue

        content = message.content
        if message.role == MessageRole.SYSTEM.value:
            record = message.tool_calls[0] if message.tool_calls else pending_tool
            pending_tool = None
            if record:
                tool_name = record.get("tool")
                if tool_name not in {"blocked", "request_family_help"}:
                    if tool_name not in tools:
                        content = HISTORY_UNAVAILABLE
                    else:
                        try:
                            current_result = tools[tool_name](**(record.get("params") or {}))
                            current_reply = _compose_reply(tool_name, current_result, Role.PATIENT.value)
                        except (KeyError, TypeError, ValueError):
                            content = HISTORY_UNAVAILABLE
                        else:
                            if current_reply != message.content:
                                content = HISTORY_UNAVAILABLE
            elif message.content != MEDICAL_DECLINE:
                content = HISTORY_UNAVAILABLE

        items.append({
            "id": message.id,
            "role": message.role,
            "content": content,
            "tool_calls": None,
            "safety_flag": message.safety_flag,
            "created_at": message.created_at.isoformat(),
        })
    return items


def _add_message(
    db: Session, session_id: str, role: str, content: str | None,
    tool_calls: list | None = None, safety_flag: bool = False,
) -> ConversationMessage:
    message = ConversationMessage(
        session_id=session_id, role=role, content=content,
        tool_calls=tool_calls, safety_flag=safety_flag,
    )
    db.add(message)
    db.flush()
    return message


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def _restricted_topic(text: str) -> str | None:
    """Return the sensitivity category the text touches, or None."""
    lowered = text.lower()
    for category, phrases in _RESTRICTED_TOPICS.items():
        if any(p in lowered for p in phrases):
            return category
    return None


def _medical_question(text: str) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in _MEDICAL_PATTERNS)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def _build_tools(db, patient_id, session_id, viewer_role):
    """The ten tools, bound to this patient/session (spec §21)."""

    def _releasable(memory: MemoryCard) -> bool:
        level = safety_service.resolve_safety_level(db, patient_id)
        return safety_service.evaluate_release(
            memory, level, viewer_role=viewer_role
        )["allowed"]

    def _approved_releasable() -> list[MemoryCard]:
        return [
            m for m in memory_service.list_memories(
                db, patient_id, status=MemoryStatus.APPROVED.value
            )
            if _releasable(m)
        ]

    def _person_by_name(name: str) -> Person | None:
        query = db.query(Person).filter(
            Person.patient_id == patient_id,
            Person.name.ilike(f"%{name}%"),
        )
        if viewer_role == Role.PATIENT.value:
            query = query.filter(Person.identity_status == IdentityStatus.FAMILY_CONFIRMED.value)
        person = query.first()
        if person is None:
            person = (
                db.query(Person)
                .filter(Person.patient_id == patient_id)
                .all()
            )
            if viewer_role == Role.PATIENT.value:
                person = [p for p in person if patient_delivery_service.person_is_visible(p)]
            person = next(
                (p for p in person if name.lower() in [a.lower() for a in (p.aliases or [])]),
                None,
            )
        return person

    def get_person(name: str) -> dict:
        person = _person_by_name(name)
        if person is None:
            return {"found": False, "name": name}
        node = graph_service.find_nodes(
            db, patient_id, "person", person.name
        )
        relations = []
        if node:
            relations = patient_delivery_service.visible_relations(db, patient_id, node[0].id)
        return {
            "found": True,
            "person": {"name": person.name, "aliases": person.aliases or [],
                       "relationship": person.relationship_to_patient,
                       "identity_status": person.identity_status},
            "relations": relations,
        }

    def get_relationship(a: str, b: str) -> dict:
        pa, pb = _person_by_name(a), _person_by_name(b)
        if not pa or not pb:
            return {"found": False, "a": a, "b": b}
        nodes_a = graph_service.find_nodes(db, patient_id, "person", pa.name)
        nodes_b = graph_service.find_nodes(db, patient_id, "person", pb.name)
        if not nodes_a or not nodes_b:
            return {"found": False, "a": a, "b": b}
        shared = []
        for ea in graph_service.list_edges_for_node(db, patient_id, nodes_a[0].id):
            if ea.status != EdgeStatus.CONFIRMED.value or ea.disputed:
                continue
            for eb in graph_service.list_edges_for_node(db, patient_id, nodes_b[0].id):
                if ea.id == eb.id:
                    shared.append({"relation_type": ea.relation_type,
                                   "status": ea.status, "confidence": ea.confidence})
        return {"found": True, "a": pa.name, "b": pb.name, "relations": shared}

    def get_memory(query: str) -> dict:
        for m in _approved_releasable():
            if query.lower() in m.title.lower():
                return {"found": True, "memory": _memory_summary(m)}
        return {"found": False, "query": query}

    def search_memories(query: str) -> dict:
        results = []
        tokens = [t for t in re.split(r"\W+", query.lower())
                  if len(t) >= 3 and t not in STOPWORDS]
        for m in _approved_releasable():
            haystack = " ".join([
                m.title or "", m.narrative or "", " ".join(str(t) for t in (m.tags or []))
            ]).lower()
            if tokens and all(t in haystack for t in tokens):
                results.append(_memory_summary(m))
            elif not tokens and query.lower() in haystack:
                results.append(_memory_summary(m))
        return {"found": bool(results), "query": query, "results": results}

    def get_photo_context(source_name: str) -> dict:
        source = (
            db.query(SourceModel)
            .filter(SourceModel.patient_id == patient_id,
                    SourceModel.file_name.ilike(f"%{source_name}%"),
                    SourceModel.deletion_status == DeletionStatus.ACTIVE.value)
            .first()
        )
        if source is None or not patient_delivery_service.source_is_visible(db, source):
            return {"found": False, "source_name": source_name}
        faces = (
            db.query(FaceMatch)
            .filter(
                FaceMatch.source_id == source.id,
                FaceMatch.face_match_state == FaceMatchState.FAMILY_CONFIRMED.value,
            )
            .all()
        )
        people = []
        for face in faces:
            person = db.get(Person, face.person_id) if face.person_id else None
            if patient_delivery_service.person_is_visible(person):
                people.append({"name": person.name, "state": face.face_match_state})
        return {
            "found": True,
            "source_name": source.file_name,
            "people": people,
        }

    def get_event(name: str) -> dict:
        node = graph_service.find_nodes(db, patient_id, "event", name)
        if not node:
            return {"found": False, "name": name}
        relations = patient_delivery_service.visible_relations(db, patient_id, node[0].id)
        if not relations:
            return {"found": False, "name": name}
        memories = [r["other_name"] for r in relations
                    if r["other_node_type"] == "memory"]
        return {"found": True, "event": name, "memories": memories,
                "relations": relations}

    def get_place(name: str) -> dict:
        node = graph_service.find_nodes(db, patient_id, "place", name)
        if not node:
            return {"found": False, "name": name}
        relations = patient_delivery_service.visible_relations(db, patient_id, node[0].id)
        memories = []
        for m in _approved_releasable():
            tags = [str(t).lower() for t in (m.tags or [])]
            if any(name.lower() in t for t in tags):
                memories.append(_memory_summary(m))
        if not relations and not memories:
            return {"found": False, "name": name}
        return {"found": True, "place": name, "memories": memories,
                "relations": relations}

    def get_evidence(memory_title: str) -> dict:
        memory = None
        for m in _approved_releasable():
            if memory_title.lower() in m.title.lower():
                memory = m
                break
        if memory is None:
            tokens = [t for t in re.split(r"\W+", memory_title.lower())
                  if len(t) >= 3 and t not in STOPWORDS]
            for m in _approved_releasable():
                if tokens and all(t in m.title.lower() for t in tokens):
                    memory = m
                    break
        if memory is None:
            return {"found": False, "memory": memory_title}
        provenance = [
            p for p in evidence_service.get_memory_provenance(db, memory.id)
            if p["evidence"].review_status == EvidenceReviewStatus.ACCEPTED.value
            and (not p["evidence"].source_id or
                 (p["source"] and p["source"].deletion_status == DeletionStatus.ACTIVE.value
                  and p["source"].patient_id == patient_id))
        ]
        return {
            "found": True,
            "memory": memory.title,
            "evidence": [
                {"claim": p["evidence"].claim, "confidence": p["evidence"].confidence,
                 "source": p["source"].file_name if p["source"] else None}
                for p in provenance
            ],
        }

    def get_safety_policy() -> dict:
        level = safety_service.resolve_safety_level(db, patient_id)
        return {"safety_level": level,
                "restricted_topics": list(_RESTRICTED_TOPICS.keys())}

    def request_family_help(reason: str | None = None) -> dict:
        created = notification_service.notify_role(
            db, patient_id, Role.FAMILY_REVIEWER.value,
            NotificationType.FAMILY_HELP.value,
            "The patient asked for family help in conversation.",
        )
        created += notification_service.notify_role(
            db, patient_id, Role.FAMILY_CONTRIBUTOR.value,
            NotificationType.FAMILY_HELP.value,
            "The patient asked for family help in conversation.",
        )
        return {"notified": len(created), "reason": reason}

    def _memory_summary(m: MemoryCard) -> dict:
        return {
            "id": m.id, "title": m.title,
            "narrative": (m.narrative or "")[:200],
            "date": m.memory_date.isoformat() if m.memory_date else None,
            "confidence": m.confidence_score,
        }

    return {
        "get_person": get_person,
        "get_relationship": get_relationship,
        "get_memory": get_memory,
        "search_memories": search_memories,
        "get_photo_context": get_photo_context,
        "get_event": get_event,
        "get_place": get_place,
        "get_evidence": get_evidence,
        "get_safety_policy": get_safety_policy,
        "request_family_help": request_family_help,
    }


# ---------------------------------------------------------------------------
# Intent routing
# ---------------------------------------------------------------------------


_EVENT_WORDS = ("wedding", "trip", "birthday", "party", "anniversary", "holiday")


def _route_intent(text: str) -> tuple[str, dict]:
    """Map patient words to (tool_name, params). Deterministic heuristics."""
    lowered = text.lower().strip()

    if "call" in lowered or "contact family" in lowered or "help" in lowered \
            or "reach" in lowered:
        return "request_family_help", {}

    who = re.search(r"who (?:was|is)\s+(?:that|this)?\s*([a-zA-Z]+)", text)
    if who:
        return "get_person", {"name": who.group(1).capitalize()}

    relate = re.search(r"how (?:was|is|were) ([a-zA-Z]+) (?:related to|connected to) ([a-zA-Z]+)", lowered)
    if relate:
        return "get_relationship", {"a": relate.group(1).capitalize(),
                                    "b": relate.group(2).capitalize()}

    rel2 = re.search(r"(?:relationship between|relation between) ([a-zA-Z]+) and ([a-zA-Z]+)", lowered)
    if rel2:
        return "get_relationship", {"a": rel2.group(1).capitalize(),
                                    "b": rel2.group(2).capitalize()}

    if "where" in lowered:
        place = re.search(r"(?:in|at) ([a-zA-Z ]+)", text)
        return "get_place", {"name": (place.group(1).strip() if place else "trip")}

    if "why" in lowered or "evidence" in lowered or "how do you know" in lowered \
            or "where did you" in lowered:
        ev = re.search(r"(?:how do you know about|why do you think|evidence for|what makes you say)\s+(.+)", lowered)
        memory_title = ev.group(1).strip() if ev else text
        return "get_evidence", {"memory_title": memory_title}

    if "photo" in lowered or "picture" in lowered:
        return "get_photo_context", {"source_name": text.replace("photo", "").replace("picture", "").strip()}

    tell = re.search(r"(?:tell me about|what about|talk about|remember|what do you know about)\s+(.+)", lowered)
    if tell:
        subject = tell.group(1).strip()
        place = re.search(r"(?:in|at)\s+([a-zA-Z ]+)$", subject)
        if place and place.group(1).strip():
            return "get_place", {"name": place.group(1).strip()}
        if subject in _EVENT_WORDS or (subject.startswith("the ") and subject[4:] in _EVENT_WORDS):
            return "get_event", {"name": subject}
        return "search_memories", {"query": subject}

    if any(w in lowered for w in ("the wedding", "the trip", "the birthday", "the party")):
        event = next(w for w in _EVENT_WORDS if f"the {w}" in lowered)
        return "get_event", {"name": f"the {event}"}

    if "safety" in lowered or "what are you allowed" in lowered:
        return "get_safety_policy", {}

    return "search_memories", {"query": text}


# ---------------------------------------------------------------------------
# Reply composition
# ---------------------------------------------------------------------------


def _compose_reply(tool_name: str, result: dict, viewer_role: str) -> str:
    if tool_name == "get_person":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        person = result["person"]
        parts = [f"{person['name']}"]
        if person.get("relationship"):
            parts.append(f"your {person['relationship']}")
        bits = []
        for r in result["relations"]:
            label = f"{r['other_name']} ({r['relation_type']})"
            if r["status"] == "CONFIRMED":
                bits.append(label)
            else:
                bits.append(f"{label} — not fully confirmed")
        if bits:
            parts.append(": " + ", ".join(bits[:6]))
        reply = " ".join(parts) + "."
        if not bits:
            reply += " I don't have a confirmed connection yet, so I'm not sure."
        return reply

    if tool_name == "get_relationship":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        if not result["relations"]:
            return f"I don't see a clear connection between {result['a']} and {result['b']}."
        return f"{result['a']} and {result['b']}: " + ", ".join(
            f"{r['relation_type']} ({r['status']})" for r in result["relations"][:4]
        ) + "."

    if tool_name in ("get_memory", "search_memories"):
        results = ([result["memory"]] if result.get("found") else []) \
            if tool_name == "get_memory" else result.get("results", [])
        if not results:
            return UNCERTAINTY_FALLBACK
        if len(results) == 1:
            m = results[0]
            out = f"{m['title']}. "
            if m.get("date"):
                out += f"That's from {m['date']}. "
            if m.get("narrative"):
                out += m["narrative"].rstrip(".") + "."
            return out
        titles = "; ".join(m["title"] for m in results[:5])
        return f"I found a few things: {titles}. Want me to tell you more about one?"

    if tool_name == "get_photo_context":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        parts = [f"That photo — {result['source_name']}"]
        if result.get("scene"):
            parts.append(f"looks like a {result['scene']}")
        if result.get("people"):
            names = [p["name"] if p["state"] != "UNIDENTIFIED" else "someone I can't identify"
                     for p in result["people"]]
            parts.append("shows " + " and ".join(names))
        return ". ".join(parts) + "."

    if tool_name == "get_event":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        return f"About {result['event']}: I have {len(result['memories'])} memory or two to share. " + (
            "One of them is " + result["memories"][0] + "." if result["memories"] else "I don't have a full picture yet."
        )

    if tool_name == "get_place":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        titles = "; ".join(m["title"] for m in result["memories"][:5])
        if not titles:
            return f"I don't have memories tied to {result['place']} yet."
        return f"{result['place']} comes up in: {titles}."

    if tool_name == "get_evidence":
        if not result.get("found"):
            return UNCERTAINTY_FALLBACK
        claims = result["evidence"]
        if not claims:
            return f"I don't have a note of where '{result['memory']}' came from yet."
        lines = " ".join(
            f"\"{c['claim']}\" (source: {c['source'] or 'unknown'})" for c in claims[:4]
        )
        return f"This is what I have on record for {result['memory']}: {lines}"

    if tool_name == "get_safety_policy":
        return (
            f"Right now your content is shown at the {result['safety_level']} level. "
            "Some topics are kept from me to protect you, and I never discuss them."
        )

    if tool_name == "request_family_help":
        return (
            "Of course. I've let your family know you'd like to talk — someone will "
            "reach out soon. Is there anything else you'd like to remember together?"
        )

    return UNCERTAINTY_FALLBACK


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def respond(
    db: Session,
    session_id: str,
    patient_text: str,
    viewer_role: str = Role.PATIENT.value,
) -> dict:
    """One turn of conversation. Returns {reply, tool_calls, safety_flag}."""
    session = db.get(ConversationSession, session_id)
    if session is None:
        raise ValueError(f"Session {session_id} not found")
    if session.status != ConversationSessionStatus.ACTIVE.value:
        raise ValueError("Conversation session is not active")

    _add_message(db, session_id, MessageRole.PATIENT.value, patient_text)

    if _medical_question(patient_text):
        _add_message(db, session_id, MessageRole.SYSTEM.value, MEDICAL_DECLINE)
        return {"reply": MEDICAL_DECLINE, "tool_calls": [], "safety_flag": False}

    restricted = _restricted_topic(patient_text)
    if restricted:
        event, message = safety_service.record_restricted_query(
            db, session.patient_id, session_id, patient_text,
            reason=f"query touches restricted topic {restricted}",
        )
        _add_message(db, session_id, MessageRole.SYSTEM.value, message,
                     tool_calls=[{"tool": "blocked", "topic": restricted}],
                     safety_flag=True)
        return {"reply": message, "tool_calls": [], "safety_flag": True}

    tool_name, params = _route_intent(patient_text)
    tools = _build_tools(db, session.patient_id, session_id, viewer_role)
    tool_fn = tools[tool_name]
    result = tool_fn(**params)

    tool_record = {"tool": tool_name, "params": params, "result": result}
    _add_message(db, session_id, MessageRole.TOOL.value, str(tool_name),
                 tool_calls=[tool_record])
    reply = _compose_reply(tool_name, result, viewer_role)
    _add_message(db, session_id, MessageRole.SYSTEM.value, reply, tool_calls=[tool_record])
    return {"reply": reply, "tool_calls": [tool_record], "safety_flag": False}
