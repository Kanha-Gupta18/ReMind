from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import admin, auth, consent, conversation, graph, knowledge, memories, notifications, patients, people, safety, sources, timeline
from app.core.config import settings
from app.core.database import engine

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

    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "database": database_status,
    }
