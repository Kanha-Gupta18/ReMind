from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path
from sqlalchemy import text

from app.api.routes import admin, auth, consent, conversation, graph, knowledge, memories, notifications, patients, people, safety, sources, timeline
from app.core.config import settings
from app.core.database import engine
from app.services import storage_service

app = FastAPI(title=settings.app_name, version=settings.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(memories.router)
app.include_router(sources.router)
app.include_router(graph.router)
app.include_router(knowledge.router)
app.include_router(conversation.router)
app.include_router(timeline.router)
app.include_router(notifications.router)
app.include_router(safety.router)
app.include_router(people.router)
app.include_router(consent.router)
app.include_router(patients.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    """Liveness check that also proves we can reach PostgreSQL."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "disconnected"

    return JSONResponse({
        "status": "ok" if database_status == "connected" else "unavailable",
        "service": settings.app_name,
        "version": settings.version,
        "database": database_status,
    }, status_code=200 if database_status == "connected" else 503)


@app.get("/ready")
def ready():
    """Readiness includes schema head and private persistent storage availability."""
    checks = {"database": "unavailable", "migrations": "unavailable", "storage": "unavailable"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            checks["database"] = "ready"
            versions = set(conn.scalars(text("SELECT version_num FROM alembic_version")))
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
        if versions == set(ScriptDirectory.from_config(config).get_heads()):
            checks["migrations"] = "ready"
    except Exception:
        pass  # Public health responses must not contain database details or secrets.
    try:
        storage_service.check_storage()
        checks["storage"] = "ready"
    except (storage_service.StorageUnavailable, OSError):
        pass
    available = all(value == "ready" for value in checks.values())
    return JSONResponse({"status": "ready" if available else "unavailable", "checks": checks},
                        status_code=200 if available else 503)
