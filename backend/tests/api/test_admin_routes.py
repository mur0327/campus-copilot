import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.api.routes import admin as admin_route  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.main import app  # noqa: E402


class FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class FakeResult:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.values)


class FakeSession:
    def __init__(
        self,
        *,
        scalar_results: list[object] | None = None,
        execute_results: list[FakeResult] | None = None,
    ) -> None:
        self.scalar_results = scalar_results or []
        self.execute_results = execute_results or []
        self.scalar_statements: list[object] = []
        self.execute_statements: list[object] = []

    async def scalar(self, statement: object) -> object:
        self.scalar_statements.append(statement)
        return self.scalar_results.pop(0)

    async def execute(self, statement: object) -> FakeResult:
        self.execute_statements.append(statement)
        return self.execute_results.pop(0)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None]:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def override_session(fake_session: object) -> None:
    async def override_get_db() -> AsyncGenerator[object, None]:
        yield fake_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_admin_crawl_trigger_delegates_to_worker(monkeypatch):
    recorded: dict[str, object] = {}

    async def fake_trigger_worker_crawl():
        recorded["called"] = True
        return {"status": "triggered"}

    monkeypatch.setattr(admin_route, "trigger_worker_crawl", fake_trigger_worker_crawl)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/crawl")

    assert response.status_code == 200
    assert response.json() == {"status": "triggered"}
    assert recorded["called"] is True


@pytest.mark.asyncio
async def test_admin_crawl_trigger_exposes_already_running(monkeypatch):
    async def fake_trigger_worker_crawl():
        return {"status": "already_running"}

    monkeypatch.setattr(admin_route, "trigger_worker_crawl", fake_trigger_worker_crawl)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/admin/crawl")

    assert response.status_code == 200
    assert response.json() == {"status": "already_running"}


@pytest.mark.asyncio
async def test_admin_status_maps_database_counts_and_last_crawled():
    last_crawled = datetime(2026, 5, 6, 10, 0, tzinfo=UTC)
    fake_session = FakeSession(scalar_results=[12, 34, 20, last_crawled])
    override_session(fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/status")

    assert response.status_code == 200
    body = response.json()
    assert body["documents"] == 12
    assert body["chunks"] == 34
    assert body["indexed_chunks"] == 20
    assert body["last_crawled"].startswith("2026-05-06T10:00:00")
    assert len(fake_session.scalar_statements) == 4


@pytest.mark.asyncio
async def test_admin_conflicts_maps_unresolved_conflict_rows():
    conflict_id = UUID("00000000-0000-0000-0000-000000000101")
    chunk_a_id = UUID("00000000-0000-0000-0000-000000000102")
    chunk_b_id = UUID("00000000-0000-0000-0000-000000000103")
    fake_session = FakeSession(
        execute_results=[
            FakeResult(
                [
                    SimpleNamespace(
                        id=conflict_id,
                        chunk_a_id=chunk_a_id,
                        chunk_b_id=chunk_b_id,
                        conflict_type="content_mismatch",
                        severity="warning",
                        is_resolved=False,
                        description="서로 다른 학사 일정 설명",
                    )
                ]
            )
        ]
    )
    override_session(fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/conflicts")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(conflict_id),
            "chunk_a_id": str(chunk_a_id),
            "chunk_b_id": str(chunk_b_id),
            "conflict_type": "content_mismatch",
            "severity": "warning",
            "is_resolved": False,
            "summary": "서로 다른 학사 일정 설명",
        }
    ]


@pytest.mark.asyncio
async def test_admin_logs_maps_query_log_rows():
    log_id = UUID("00000000-0000-0000-0000-000000000201")
    created_at = datetime(2026, 5, 6, 11, 30, tzinfo=UTC)
    fake_session = FakeSession(
        execute_results=[
            FakeResult(
                [
                    SimpleNamespace(
                        id=log_id,
                        query="휴학 신청",
                        answer="휴학 신청 안내입니다.",
                        has_conflict=True,
                        response_ms=321,
                        created_at=created_at,
                    )
                ]
            )
        ]
    )
    override_session(fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/logs")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "id": str(log_id),
            "query": "휴학 신청",
            "answer": "휴학 신청 안내입니다.",
            "has_conflict": True,
            "response_ms": 321,
            "created_at": body[0]["created_at"],
        }
    ]
    assert body[0]["created_at"].startswith("2026-05-06T11:30:00")
