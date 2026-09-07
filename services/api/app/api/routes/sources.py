"""Source upload + AI pipeline routes (spec §5, §18, §41 Phase 1).

RBAC:
  - family_contributor/reviewer/guardian  upload + trigger processing
  - caregiver                            read
  - reviewer/guardian/admin              reconstruct drafts from sources
  - administrator                        everything (scope=None)
"""

import hashlib
import mimetypes
import os
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.ai import reconstruction
from app.api.deps import get_current_user, get_patient_scope, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.constants import DeletionStatus, Role
from app.models.memory import Source
from app.models.user import User
from app.schemas.source import SourceCreate
from app.services import audit_service, notification_service

router = APIRouter(prefix="/sources", tags=["sources"])

_UPLOAD_ROLES = [Role.FAMILY_CONTRIBUTOR.value, Role.FAMILY_REVIEWER.value,
                 Role.GUARDIAN.value, Role.ADMINISTRATOR.value]
_PROCESS_ROLES = [Role.FAMILY_CONTRIBUTOR.value, Role.FAMILY_REVIEWER.value,
                  Role.GUARDIAN.value, Role.ADMINISTRATOR.value]
_RECONSTRUCT_ROLES = [Role.FAMILY_REVIEWER.value, Role.GUARDIAN.value,
                      Role.ADMINISTRATOR.value]

_EXTENSION_TYPES = {
    ".jpg": "photo", ".jpeg": "photo", ".png": "photo", ".heic": "photo",
    ".gif": "photo", ".bmp": "photo", ".webp": "photo", ".tiff": "photo",
    ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
    ".webm": "video", ".wmv": "video",
    ".mp3": "audio", ".m4a": "audio", ".wav": "audio", ".aac": "audio",
    ".ogg": "audio", ".flac": "audio",
    ".pdf": "document", ".txt": "document", ".md": "document",
    ".docx": "document", ".doc": "document", ".rtf": "document",
    ".json": "message_export", ".zip": "message_export", ".html": "message_export",
}


def _infer_file_type(file_name: str) -> str | None:
    ext = os.path.splitext(file_name)[1].lower()
    return _EXTENSION_TYPES.get(ext)


def _scope_patient(scope: str | None, current: User, body_patient_id: str | None = None) -> str:
    if scope is None:
        if body_patient_id is None:
            raise HTTPException(status_code=400, detail="patient_id required")
        return body_patient_id
    if body_patient_id and body_patient_id != scope:
        raise HTTPException(status_code=403, detail="Not your patient")
    return scope


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_source_file(
    file: Annotated[UploadFile, File()],
    context_tags: Annotated[list[str] | None, Form()] = None,
    patient_id: str | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
    current: Annotated[User, Depends(require_roles(*_UPLOAD_ROLES))] = None,
    scope: Annotated[str | None, Depends(get_patient_scope)] = None,
):
    """Upload a real file. The API computes the checksum, stores the bytes
    under {storage_dir}/{patient_id}/{source_id}/, and infers file_type from
    the extension (spec §5 provenance: checksum, size, storage path)."""
    pid = _scope_patient(scope, current, patient_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    safe_name = Path(file.filename).name
    file_type = _infer_file_type(safe_name)
    if file_type is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type; expected one of: " +
                   ", ".join(sorted(_EXTENSION_TYPES)),
        )
    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    source = Source(
        patient_id=pid,
        uploaded_by=current.id,
        file_name=safe_name,
        file_type=file_type,
        file_size=len(content),
        context_tags=context_tags or [],
        checksum=checksum,
    )
    db.add(source)
    db.flush()

    storage_root = Path(settings.storage_dir) / pid / source.id
    storage_root.mkdir(parents=True, exist_ok=True)
    dest = storage_root / safe_name
    dest.write_bytes(content)
    source.storage_path = str(dest)

    audit_service.log_action(db, current.id, "uploaded", "source", source.id,
                             {"file_name": safe_name, "file_type": file_type,
                              "file_size": len(content)})
    db.commit()
    return _serialize(source, detail=True)


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_source(
    body: SourceCreate,
    patient_id: str | None = None,
    db: Annotated[Session, Depends(get_db)] = None,
    current: Annotated[User, Depends(require_roles(*_UPLOAD_ROLES))] = None,
    scope: Annotated[str | None, Depends(get_patient_scope)] = None,
):
    pid = _scope_patient(scope, current, patient_id)
    source = Source(
        patient_id=pid,
        uploaded_by=current.id,
        file_name=body.file_name,
        file_type=body.file_type,
        storage_path=body.storage_path,
        context_tags=body.context_tags,
        capture_date=body.capture_date,
        checksum=body.checksum,
    )
    db.add(source)
    db.flush()
    audit_service.log_action(db, current.id, "uploaded", "source", source.id,
                             {"file_name": body.file_name, "file_type": body.file_type})
    db.commit()
    return _serialize(source, detail=False)


@router.get("")
def list_sources(
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
    status_filter: str | None = None,
):
    query = db.query(Source).filter(Source.deletion_status == DeletionStatus.ACTIVE.value)
    if scope:
        query = query.filter(Source.patient_id == scope)
    if status_filter:
        query = query.filter(Source.status == status_filter)
    sources = query.order_by(Source.created_at.desc()).all()
    return {"items": [_serialize(s, detail=False) for s in sources], "count": len(sources)}


@router.get("/{source_id}")
def get_source(
    source_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    source = _get_scoped(db, source_id, scope)
    return _serialize(source, detail=True)


@router.post("/{source_id}/process")
def process_source(
    source_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_PROCESS_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    source = _get_scoped(db, source_id, scope)
    reconstruction.process_source(db, source.id)
    db.commit()
    notification_service.notify_upload_complete(db, source.patient_id)
    db.commit()
    audit_service.log_action(db, current.id, "processed", "source", source.id)
    db.commit()
    return _serialize(source, detail=True)


@router.post("/{source_id}/reconstruct")
def reconstruct_source(
    source_id: str,
    submit: bool = False,
    db: Annotated[Session, Depends(get_db)] = None,
    current: Annotated[User, Depends(require_roles(*_RECONSTRUCT_ROLES))] = None,
    scope: Annotated[str | None, Depends(get_patient_scope)] = None,
):
    source = _get_scoped(db, source_id, scope)
    drafts = reconstruction.reconstruct_memories(db, source.patient_id, source_ids=[source.id])
    if submit:
        from app.services import memory_service
        for draft in drafts:
            memory_service.submit_for_review(db, draft, submitted_by=current.id)
    db.commit()
    audit_service.log_action(db, current.id, "reconstructed", "source", source.id,
                             {"drafts": len(drafts)})
    db.commit()
    return {"items": [{"id": d.id, "title": d.title,
                       "confidence_score": d.confidence_score, "status": d.status}
                      for d in drafts], "count": len(drafts)}


@router.get("/{source_id}/file")
def get_source_file(
    source_id: str,
    db: Annotated[Session, Depends(get_db)],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    source = _get_scoped(db, source_id, scope)
    if not source.storage_path or not os.path.exists(source.storage_path):
        raise HTTPException(status_code=404, detail="Source file is not stored")
    media_type = mimetypes.guess_type(source.file_name)[0] or "application/octet-stream"
    return FileResponse(source.storage_path, media_type=media_type, filename=source.file_name)


@router.delete("/{source_id}")
def soft_delete_source(
    source_id: str,
    db: Annotated[Session, Depends(get_db)],
    current: Annotated[User, Depends(require_roles(*_UPLOAD_ROLES))],
    scope: Annotated[str | None, Depends(get_patient_scope)],
):
    source = _get_scoped(db, source_id, scope)
    source.deletion_status = DeletionStatus.SOFT_DELETED.value
    from app.models.base import utcnow
    source.deleted_at = utcnow()
    audit_service.log_action(db, current.id, "deleted", "source", source.id)
    db.commit()
    return {"ok": True}


def _get_scoped(db: Session, source_id: str, scope: str | None) -> Source:
    source = db.get(Source, source_id)
    if source is None or source.deletion_status != DeletionStatus.ACTIVE.value:
        raise HTTPException(status_code=404, detail="Source not found")
    if scope is not None and scope != source.patient_id:
        raise HTTPException(status_code=403, detail="Access to this source is not allowed")
    return source


def _serialize(s: Source, detail: bool) -> dict:
    data = {
        "id": s.id,
        "patient_id": s.patient_id,
        "file_name": s.file_name,
        "file_type": s.file_type,
        "file_size": s.file_size,
        "status": s.status,
        "pipeline_type": s.pipeline_type,
        "context_tags": s.context_tags or [],
        "created_at": s.created_at.isoformat(),
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
    }
    if detail:
        data.update({
            "uploaded_by": s.uploaded_by,
            "storage_path": s.storage_path,
            "capture_date": s.capture_date.isoformat() if s.capture_date else None,
            "checksum": s.checksum,
            "extraction_method": s.extraction_method,
            "pipeline_results": s.pipeline_results,
        })
    return data
