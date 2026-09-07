"""Per-process test resources; never reuse application storage or tables."""

import os
import tempfile
import uuid

from sqlalchemy.engine import make_url


def test_database_url(value: str) -> str:
    url = make_url(value)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must name a dedicated PostgreSQL database ending in _test")
    if url.query.get("options"):
        raise RuntimeError("TEST_DATABASE_URL must not override PostgreSQL session options")
    return url.render_as_string(hide_password=False)


DATABASE_URL = test_database_url(os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://remind:remind_dev@localhost:5432/remind_test",
))
SCHEMA = "remind_test_" + uuid.uuid4().hex
STORAGE_DIR = tempfile.mkdtemp(prefix="remind_test_storage_")
SCOPED_DATABASE_URL = make_url(DATABASE_URL).update_query_dict(
    {"options": f"-csearch_path={SCHEMA}"}
).render_as_string(hide_password=False)
