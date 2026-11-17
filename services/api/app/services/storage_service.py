"""Private source bytes. Callers must authorize the source before reading it."""

from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import settings


class StorageUnavailable(Exception):
    """Provider/configuration failed; never include its response or credentials."""


class StoredFileMissing(Exception):
    """The reference is invalid or no longer exists."""


def _request(method: str, path: str, **kwargs) -> httpx.Response:
    missing_ok = kwargs.pop("missing_ok", False)
    secret = settings.supabase_service_role_key.get_secret_value()
    headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}
    headers.update(kwargs.pop("headers", {}))
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.request(
                method, settings.supabase_url.rstrip("/") + "/storage/v1/" + path,
                headers=headers, **kwargs,
            )
        if missing_ok and response.status_code in (400, 404):
            try:
                if response.status_code == 404 or response.json().get("code") in ("NoSuchKey", "not_found"):
                    raise StoredFileMissing()
            except ValueError:
                pass
        if not response.is_success:
            raise StorageUnavailable()
        return response
    except httpx.HTTPError:
        raise StorageUnavailable() from None


def check_storage() -> None:
    if settings.storage_backend == "local":
        root = Path(settings.storage_dir)
        root.mkdir(parents=True, exist_ok=True)
        return
    bucket = quote(settings.supabase_storage_bucket, safe="")
    response = _request("GET", f"bucket/{bucket}")
    try:
        metadata = response.json()
        if metadata.get("public") is not False or metadata.get("id") != settings.supabase_storage_bucket:
            raise StorageUnavailable()
    except (ValueError, AttributeError):
        raise StorageUnavailable() from None


def _object_key(source) -> str:
    # IDs are server-generated; reject unsafe legacy data before reaching storage.
    parts = (source.patient_id, source.id, source.file_name)
    if any(not part or part in (".", "..") or "/" in part or "\\" in part for part in parts):
        raise StoredFileMissing()
    return "/".join(parts)


def _remote_reference(source) -> str:
    return f"supabase://{settings.supabase_storage_bucket}/{_object_key(source)}"


def _local_path(source) -> Path:
    root = Path(settings.storage_dir).resolve()
    expected = (root / source.patient_id / source.id).resolve()
    path = Path(source.storage_path or "").resolve()
    if not expected.is_relative_to(root) or not path.is_relative_to(expected):
        raise StoredFileMissing()
    return path


def write_source(source, content: bytes) -> str:
    key = _object_key(source)
    if settings.storage_backend == "local":
        path = Path(settings.storage_dir) / key
        source_path = path.resolve()
        if not source_path.is_relative_to(Path(settings.storage_dir).resolve()):
            raise StoredFileMissing()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)
    check_storage()
    _request(
        "POST", f"object/{settings.supabase_storage_bucket}/{quote(key, safe='/')}",
        content=content, headers={"Content-Type": "application/octet-stream", "x-upsert": "false"},
    )
    return _remote_reference(source)


def read_source(source) -> bytes:
    if not source.storage_path:
        raise StoredFileMissing()
    if source.storage_path.startswith("supabase://"):
        if settings.storage_backend != "supabase" or source.storage_path != _remote_reference(source):
            raise StoredFileMissing()
        check_storage()
        response = _request(
            "GET", f"object/authenticated/{settings.supabase_storage_bucket}/{quote(_object_key(source), safe='/')}",
            missing_ok=True,
        )
        return response.content
    # Production must never read arbitrary legacy disk references.
    if settings.storage_backend != "local":
        raise StoredFileMissing()
    path = _local_path(source)
    if not path.is_file():
        raise StoredFileMissing()
    return path.read_bytes()


def remove_source(source) -> None:
    """Compensate a failed database commit after storing a new upload."""
    if source.storage_path and source.storage_path.startswith("supabase://"):
        if settings.storage_backend != "supabase" or source.storage_path != _remote_reference(source):
            raise StoredFileMissing()
        _request("DELETE", f"object/{settings.supabase_storage_bucket}", json={"prefixes": [_object_key(source)]})
    elif source.storage_path and settings.storage_backend == "local":
        _local_path(source).unlink(missing_ok=True)
