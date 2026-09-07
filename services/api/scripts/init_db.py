"""Create all database tables defined by the SQLAlchemy models.

Run from services/api with the venv active:
    python scripts/init_db.py

In production you'd use a versioned migration tool (Alembic) instead
of create_all — create_all only creates missing tables and never alters
existing ones. It's perfect for a fresh v1.
"""

import sys
from pathlib import Path

# Make the api package importable no matter where this script is run from
# (when Python executes a script directly it only adds the script's own
# directory to sys.path, so we add the services/api root ourselves).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import Base, engine
from app import models  # noqa: F401  (registers every model)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")


if __name__ == "__main__":
    main()
