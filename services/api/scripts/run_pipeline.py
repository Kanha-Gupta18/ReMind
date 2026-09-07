"""CLI runner for the simulated AI pipeline (Phase 6).

Usage (from services/api):
  venv\\Scripts\\python.exe -m scripts.run_pipeline --source <source_id>
  venv\\Scripts\\python.exe -m scripts.run_pipeline --patient <patient_id> [--submit]

Processes the given source (or all pending sources for a patient),
reconstructs AI drafts, and optionally submits them for family review.
"""

import argparse

from app.core.database import SessionLocal
from app.services import memory_service
from app.ai import reconstruction
from app.models.constants import MemoryStatus, SourceStatus
from app.models.memory import Source


def process_source_or_patient(source_id: str | None, patient_id: str | None) -> None:
    db = SessionLocal()
    try:
        if source_id:
            source = reconstruction.process_source(db, source_id)
            db.commit()
            print(f"processed {source.id} ({source.file_name}) "
                  f"-> {source.status} via {source.pipeline_type}")
        elif patient_id:
            pending = (
                db.query(Source)
                .filter(Source.patient_id == patient_id,
                        Source.status.in_([SourceStatus.PENDING.value,
                                           SourceStatus.QUEUED.value]))
                .all()
            )
            for source in pending:
                reconstruction.process_source(db, source.id)
                print(f"processed {source.file_name} -> {source.status}")
            db.commit()
        else:
            print("nothing to do; pass --source or --patient")
            return

        drafts = reconstruction.reconstruct_memories(db, patient_id or _patient_of(db, source_id))
        db.commit()
        for draft in drafts:
            print(f"draft {draft.title} confidence={draft.confidence_score} "
                  f"status={draft.status} flags={draft.sensitivity_flags}")
        print(f"{len(drafts)} AI draft(s) created")
    finally:
        db.close()


def _patient_of(db, source_id: str | None) -> str | None:
    if not source_id:
        return None
    source = db.get(Source, source_id)
    return source.patient_id if source else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the simulated AI pipeline")
    parser.add_argument("--source", help="source id to process")
    parser.add_argument("--patient", help="process all pending sources for a patient")
    parser.add_argument("--submit", action="store_true",
                        help="submit drafts for family review")
    args = parser.parse_args()

    process_source_or_patient(args.source, args.patient)

    if args.submit:
        db = SessionLocal()
        try:
            pid = args.patient or _patient_of(db, args.source)
            if pid:
                for m in memory_service.list_memories(
                    db, pid, status=MemoryStatus.AI_RECONSTRUCTED.value
                ):
                    memory_service.submit_for_review(db, m)
                    print(f"submitted {m.title} for review")
                db.commit()
        finally:
            db.close()
