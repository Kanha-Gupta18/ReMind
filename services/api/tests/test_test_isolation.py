"""Verify the harness owns only its generated resources."""

from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.database import engine
from tests import runtime


@pytest.mark.parametrize("url", [
    "postgresql://localhost/remind",
    "postgresql://localhost/production",
    "sqlite:///remind_test",
    "postgresql://localhost/remind_test?options=-csearch_path=public",
])
def test_rejects_unsafe_database_configuration(url):
    with pytest.raises(RuntimeError):
        runtime.test_database_url(url)


def test_migrations_and_storage_are_isolated():
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == runtime.SCHEMA
        assert connection.scalar(text("SELECT version_num FROM alembic_version"))
    assert Path(runtime.STORAGE_DIR).is_dir()
    assert Path(runtime.STORAGE_DIR).name.startswith("remind_test_storage_")
