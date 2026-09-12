"""add canonical memory revisions and structured knowledge

Revision ID: c4a8e2f17b6d
Revises: 7b31d9f45a20
Create Date: 2026-09-12
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8e2f17b6d"
down_revision: Union[str, Sequence[str], None] = "7b31d9f45a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _snapshot(memory) -> dict:
    return {
        "title": memory.title,
        "narrative": memory.narrative,
        "media_urls": memory.media_urls or [],
        "people_ids": [],
        "place_ids": [],
        "event_ids": [],
        "tags": memory.tags or [],
        "memory_date": memory.memory_date.isoformat() if memory.memory_date else None,
        "date_accuracy": memory.date_accuracy,
        "visibility": memory.visibility,
        "sensitivity_flags": memory.sensitivity_flags or [],
        "confidence_score": memory.confidence_score or 0,
        "confidence_breakdown": memory.confidence_breakdown,
        "explanation": memory.explanation,
        "contradictions": memory.contradictions or [],
        "model_version": memory.model_version,
    }


def _backfill_revision_pointers() -> None:
    bind = op.get_bind()
    memories = bind.execute(sa.text("SELECT * FROM memory_cards")).mappings().all()
    for memory in memories:
        revisions = bind.execute(
            sa.text(
                "SELECT id, revision_number, status, content, superseded_by_id "
                "FROM memory_revisions WHERE memory_id = :memory_id "
                "ORDER BY revision_number"
            ),
            {"memory_id": memory.id},
        ).mappings().all()

        approved = next((item for item in reversed(revisions) if item.status == "approved"), None)
        candidate = next((item for item in reversed(revisions) if item.status == "draft"), None)

        # The previous edit implementation marked the published revision as
        # superseded before its replacement was approved. Restore that revision.
        if memory.status == "AWAITING_REVIEW" and approved is None:
            approved = next(
                (item for item in reversed(revisions) if item.status == "superseded"),
                None,
            )
            if approved is not None:
                bind.execute(
                    sa.text(
                        "UPDATE memory_revisions SET status = 'approved', "
                        "superseded_by_id = NULL WHERE id = :revision_id"
                    ),
                    {"revision_id": approved.id},
                )

        if approved is None and memory.status == "APPROVED":
            revision_id = str(uuid.uuid4())
            number = (revisions[-1].revision_number if revisions else 0) + 1
            bind.execute(
                sa.text(
                    "INSERT INTO memory_revisions "
                    "(id, memory_id, revision_number, content, status, authored_by, created_at) "
                    "VALUES (:id, :memory_id, :number, :content, 'approved', :actor, :created_at)"
                ).bindparams(sa.bindparam("content", type_=sa.JSON())),
                {
                    "id": revision_id,
                    "memory_id": memory.id,
                    "number": number,
                    "content": _snapshot(memory),
                    "actor": memory.approved_by or memory.created_by,
                    "created_at": memory.approved_at or memory.created_at,
                },
            )
            approved = {"id": revision_id}

        if approved is not None:
            stored = bind.execute(
                sa.text("SELECT content FROM memory_revisions WHERE id = :revision_id"),
                {"revision_id": approved["id"]},
            ).scalar_one()
            enriched = _snapshot(memory)
            enriched.update({
                key: value for key, value in dict(stored or {}).items()
                if key != "note"
            })
            bind.execute(
                sa.text(
                    "UPDATE memory_revisions SET content = :content WHERE id = :revision_id"
                ).bindparams(sa.bindparam("content", type_=sa.JSON())),
                {"content": enriched, "revision_id": approved["id"]},
            )

        if candidate is not None and memory.status in {
            "DRAFT", "AI_RECONSTRUCTED", "AWAITING_REVIEW"
        }:
            candidate_status = (
                "awaiting_review" if memory.status == "AWAITING_REVIEW" else "draft"
            )
            # The card held the edited candidate in the legacy implementation.
            bind.execute(
                sa.text(
                    "UPDATE memory_revisions SET content = :content, status = :status "
                    "WHERE id = :revision_id"
                ).bindparams(sa.bindparam("content", type_=sa.JSON())),
                {
                    "content": _snapshot(memory),
                    "status": candidate_status,
                    "revision_id": candidate.id,
                },
            )
        elif memory.status in {"DRAFT", "AI_RECONSTRUCTED", "AWAITING_REVIEW"}:
            revision_id = str(uuid.uuid4())
            number = (revisions[-1].revision_number if revisions else 0) + 1
            candidate_status = (
                "awaiting_review" if memory.status == "AWAITING_REVIEW" else "draft"
            )
            bind.execute(
                sa.text(
                    "INSERT INTO memory_revisions "
                    "(id, memory_id, revision_number, content, status, authored_by, created_at) "
                    "VALUES (:id, :memory_id, :number, :content, :status, :actor, :created_at)"
                ).bindparams(sa.bindparam("content", type_=sa.JSON())),
                {
                    "id": revision_id,
                    "memory_id": memory.id,
                    "number": number,
                    "content": _snapshot(memory),
                    "status": candidate_status,
                    "actor": memory.created_by,
                    "created_at": memory.updated_at or memory.created_at,
                },
            )
            candidate = {"id": revision_id}

        approved_id = approved["id"] if approved else None
        candidate_id = (
            candidate["id"]
            if candidate is not None
            and memory.status in {"DRAFT", "AI_RECONSTRUCTED", "AWAITING_REVIEW"}
            else None
        )
        bind.execute(
            sa.text(
                "UPDATE memory_cards SET approved_revision_id = :approved_id, "
                "candidate_revision_id = :candidate_id WHERE id = :memory_id"
            ),
            {
                "approved_id": approved_id,
                "candidate_id": candidate_id,
                "memory_id": memory.id,
            },
        )
        if approved_id and memory.approved_at:
            bind.execute(
                sa.text(
                    "INSERT INTO memory_review_records "
                    "(id, memory_id, revision_id, decision, actor_id, created_at) "
                    "VALUES (:id, :memory_id, :revision_id, 'approved', :actor, :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "memory_id": memory.id,
                    "revision_id": approved_id,
                    "actor": memory.approved_by,
                    "created_at": memory.approved_at,
                },
            )
        if candidate_id and memory.status == "AWAITING_REVIEW":
            bind.execute(
                sa.text(
                    "INSERT INTO memory_review_records "
                    "(id, memory_id, revision_id, decision, actor_id, created_at) "
                    "VALUES (:id, :memory_id, :revision_id, 'submitted', :actor, :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "memory_id": memory.id,
                    "revision_id": candidate_id,
                    "actor": memory.created_by,
                    "created_at": memory.updated_at or memory.created_at,
                },
            )
        evidence_revision_id = approved_id or candidate_id
        if evidence_revision_id:
            bind.execute(
                sa.text(
                    "UPDATE evidence SET revision_id = :revision_id "
                    "WHERE memory_id = :memory_id AND revision_id IS NULL"
                ),
                {"revision_id": evidence_revision_id, "memory_id": memory.id},
            )


def _backfill_legacy_places() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, patient_id, created_by, tags, created_at FROM memory_cards")
    ).mappings().all()
    place_ids: dict[tuple[str, str], str] = {}
    memory_place_ids: dict[str, list[str]] = {}
    for memory in rows:
        for tag in memory.tags or []:
            value = str(tag)
            if not value.lower().startswith("place:"):
                continue
            name = value.split(":", 1)[1].strip()
            if not name:
                continue
            key = (memory.patient_id, name.casefold())
            place_id = place_ids.get(key)
            if place_id is None:
                place_id = str(uuid.uuid4())
                place_ids[key] = place_id
                bind.execute(
                    sa.text(
                        "INSERT INTO places "
                        "(id, patient_id, name, aliases, created_by, created_at, updated_at) "
                        "VALUES (:id, :patient_id, :name, :aliases, :actor, :created_at, :created_at)"
                    ).bindparams(sa.bindparam("aliases", type_=sa.JSON())),
                    {
                        "id": place_id,
                        "patient_id": memory.patient_id,
                        "name": name,
                        "aliases": [],
                        "actor": memory.created_by,
                        "created_at": memory.created_at,
                    },
                )
            bind.execute(
                sa.text(
                    "INSERT INTO memory_places (id, memory_id, place_id, created_at) "
                    "VALUES (:id, :memory_id, :place_id, :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "memory_id": memory.id,
                    "place_id": place_id,
                    "created_at": memory.created_at,
                },
            )
            memory_place_ids.setdefault(memory.id, []).append(place_id)

    for memory_id, ids in memory_place_ids.items():
        pointers = bind.execute(
            sa.text(
                "SELECT approved_revision_id, candidate_revision_id FROM memory_cards "
                "WHERE id = :memory_id"
            ),
            {"memory_id": memory_id},
        ).mappings().one()
        for revision_id in {pointers.approved_revision_id, pointers.candidate_revision_id} - {None}:
            content = bind.execute(
                sa.text("SELECT content FROM memory_revisions WHERE id = :revision_id"),
                {"revision_id": revision_id},
            ).scalar_one()
            content = dict(content or {})
            content["place_ids"] = ids
            bind.execute(
                sa.text(
                    "UPDATE memory_revisions SET content = :content WHERE id = :revision_id"
                ).bindparams(sa.bindparam("content", type_=sa.JSON())),
                {"content": content, "revision_id": revision_id},
            )


def upgrade() -> None:
    op.add_column("memory_cards", sa.Column("approved_revision_id", sa.String(), nullable=True))
    op.add_column("memory_cards", sa.Column("candidate_revision_id", sa.String(), nullable=True))
    op.add_column("memory_revisions", sa.Column("change_note", sa.String(), nullable=True))
    op.add_column("evidence", sa.Column("revision_id", sa.String(), nullable=True))
    op.add_column("evidence", sa.Column("reviewed_by", sa.String(), nullable=True))
    op.add_column("evidence", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "places",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("date_accuracy", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memory_review_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("revision_id", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"]),
        sa.ForeignKeyConstraint(["revision_id"], ["memory_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "memory_people",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("person_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "person_id", name="uq_memory_person"),
    )
    op.create_table(
        "memory_places",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("place_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"]),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "place_id", name="uq_memory_place"),
    )
    op.create_table(
        "memory_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("memory_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memory_cards.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "event_id", name="uq_memory_event"),
    )

    _backfill_revision_pointers()
    _backfill_legacy_places()

    op.create_foreign_key(
        "fk_memory_cards_approved_revision",
        "memory_cards",
        "memory_revisions",
        ["approved_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_memory_cards_candidate_revision",
        "memory_cards",
        "memory_revisions",
        ["candidate_revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evidence_revision",
        "evidence",
        "memory_revisions",
        ["revision_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_evidence_reviewer",
        "evidence",
        "users",
        ["reviewed_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_evidence_reviewer", "evidence", type_="foreignkey")
    op.drop_constraint("fk_evidence_revision", "evidence", type_="foreignkey")
    op.drop_constraint("fk_memory_cards_candidate_revision", "memory_cards", type_="foreignkey")
    op.drop_constraint("fk_memory_cards_approved_revision", "memory_cards", type_="foreignkey")
    op.drop_table("memory_events")
    op.drop_table("memory_places")
    op.drop_table("memory_people")
    op.drop_table("memory_review_records")
    op.drop_table("events")
    op.drop_table("places")
    op.drop_column("evidence", "reviewed_at")
    op.drop_column("evidence", "reviewed_by")
    op.drop_column("evidence", "revision_id")
    op.drop_column("memory_cards", "candidate_revision_id")
    op.drop_column("memory_cards", "approved_revision_id")
    op.drop_column("memory_revisions", "change_note")
