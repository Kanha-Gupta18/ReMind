"""Timeline construction and engagement stats for the patient/caregiver UIs.

The patient-facing timeline only ever contains memories that are APPROVED
and that pass the safety release gate (see safety_service). Groupings let
the patient web app render by decade and by place without duplicating
gating logic in the frontend.
"""

from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.clinical import EngagementLog
from app.models.constants import MemoryStatus
from app.models.memory import MemoryCard
from app.services import safety_service


def _releasable(
    db: Session,
    memory: MemoryCard,
    patient_id: str,
    viewer_role: str | None,
    caregiver_present: bool = False,
) -> bool:
    safety_level = safety_service.resolve_safety_level(db, patient_id)
    return safety_service.evaluate_release(
        memory,
        safety_level,
        caregiver_present=caregiver_present,
        viewer_role=viewer_role,
    )["allowed"]


def get_timeline(
    db: Session,
    patient_id: str,
    viewer_role: str | None = None,
    caregiver_present: bool = False,
    limit: int | None = None,
) -> list[MemoryCard]:
    """Approved memories, newest first, filtered by the safety gate."""
    memories = (
        db.query(MemoryCard)
        .filter(
            MemoryCard.patient_id == patient_id,
            MemoryCard.status == MemoryStatus.APPROVED.value,
        )
        .order_by(MemoryCard.memory_date.desc().nullslast(), MemoryCard.created_at.desc())
        .all()
    )
    released = [
        m for m in memories
        if _releasable(db, m, patient_id, viewer_role, caregiver_present)
    ]
    return released[:limit] if limit else released


def _year_of(memory: MemoryCard) -> int | None:
    return memory.memory_date.year if memory.memory_date else None


def group_by_decade(db: Session, patient_id: str) -> list[dict]:
    """Timeline grouped by decade: [{decade: 1990, count, memories}].

    Decades with no memories are omitted; ordering is oldest decade first.
    """
    memories = get_timeline(db, patient_id)
    groups: dict[int, list[MemoryCard]] = {}
    for memory in memories:
        year = _year_of(memory)
        if year is None:
            continue
        decade = (year // 10) * 10
        groups.setdefault(decade, []).append(memory)

    return [
        {
            "decade": decade,
            "count": len(items),
            "memories": sorted(items, key=lambda m: m.memory_date or m.created_at),
        }
        for decade, items in sorted(groups.items())
    ]


def group_by_place(db: Session, patient_id: str) -> list[dict]:
    """Memories clustered by place (from tags/graph). Falls back to 'Unknown'.

    [{place, count, memories}]. Places come from a memory's tags; graph
    place-nodes are the richer source used by the /places page later.
    """
    memories = get_timeline(db, patient_id)
    groups: dict[str, list[MemoryCard]] = {}
    for memory in memories:
        tags = memory.tags or []
        place = next((t for t in tags if str(t).lower().startswith("place:")), None)
        key = str(place).split(":", 1)[1] if place else "Unknown"
        groups.setdefault(key, []).append(memory)

    return [
        {
            "place": place,
            "count": len(items),
            "memories": sorted(items, key=lambda m: m.memory_date or m.created_at),
        }
        for place, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    ]


def engagement_stats(db: Session, patient_id: str) -> dict:
    """Caregiver dashboard numbers: totals and top memories.

    Rapid re-viewing of one memory is a distress signal the caregiver
    should watch (see safety_service.record_safety_event).
    """
    rows = (
        db.query(
            EngagementLog.action,
            func.count(EngagementLog.id),
        )
        .filter(EngagementLog.patient_id == patient_id)
        .group_by(EngagementLog.action)
        .all()
    )
    by_action = Counter(dict(rows))

    top = (
        db.query(
            EngagementLog.memory_card_id,
            func.count(EngagementLog.id).label("views"),
        )
        .filter(EngagementLog.patient_id == patient_id)
        .group_by(EngagementLog.memory_card_id)
        .order_by(func.count(EngagementLog.id).desc())
        .limit(5)
        .all()
    )

    return {
        "total_engagements": sum(by_action.values()),
        "by_action": dict(by_action),
        "top_memories": [
            {"memory_card_id": memory_id, "views": views}
            for memory_id, views in top
        ],
    }
