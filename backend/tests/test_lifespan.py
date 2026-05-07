import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.main import app, lifespan


@pytest.mark.asyncio
async def test_lifespan_warms_database_connection(monkeypatch):
    calls = 0

    async def fake_warm_database_connection() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr("app.main.warm_database_connection", fake_warm_database_connection)

    async with lifespan(app):
        pass

    assert calls == 1
