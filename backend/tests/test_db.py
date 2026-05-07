import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.core.db import engine


def test_database_engine_pre_pings_connections_before_reuse():
    assert engine.pool._pre_ping is True
