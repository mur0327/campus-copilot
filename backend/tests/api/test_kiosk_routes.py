import os
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.sql import operators

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

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

    def all(self) -> list[object]:
        return self.values

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.values)


class FakeSession:
    def __init__(self, execute_results: list[FakeResult]) -> None:
        self.execute_results = execute_results
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeResult:
        self.statements.append(statement)
        return self.execute_results.pop(0)


@dataclass(frozen=True)
class PopularLogRow:
    id: UUID
    query: str
    created_at: datetime


class PopularFakeSession:
    def __init__(self, rows: list[PopularLogRow]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> FakeResult:
        self.statement = statement
        cutoff = self._created_at_cutoff(statement)
        filtered_rows = [row for row in self.rows if cutoff is None or row.created_at >= cutoff]

        order_by = [str(clause) for clause in getattr(statement, "_order_by_clauses", ())]
        if order_by == ["query_logs.created_at DESC", "query_logs.id DESC"]:
            filtered_rows = sorted(
                filtered_rows,
                key=lambda row: (row.created_at, row.id),
                reverse=True,
            )

        return FakeResult([row.query for row in filtered_rows])

    @staticmethod
    def _created_at_cutoff(statement: object) -> datetime | None:
        for criterion in getattr(statement, "_where_criteria", ()):
            if (
                str(getattr(criterion, "left", "")) == "query_logs.created_at"
                and getattr(criterion, "operator", None) is operators.ge
            ):
                return getattr(getattr(criterion, "right", None), "value", None)
        return None


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
async def test_categories_returns_curated_and_active_database_categories():
    fake_session = FakeSession(
        [
            FakeResult(
                [
                    ("academic",),
                    ("graduate",),
                    (None,),
                ]
            )
        ]
    )
    override_session(fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert any(item["id"] == "academic" and item["name"] == "학사행정" for item in body)
    assert any(item["id"] == "graduate" and item["name"] == "graduate" for item in body)
    assert all({"id", "name"} <= item.keys() for item in body)


@pytest.mark.asyncio
async def test_faq_route_exists():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/faq")

    assert response.status_code == 200
    assert any(item["id"] == "academic-leave" for item in response.json())


@pytest.mark.asyncio
async def test_faq_filters_by_category():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/faq?category=academic")

    assert response.status_code == 200
    assert response.json()
    assert all(item["category_id"] == "academic" for item in response.json())


@pytest.mark.asyncio
async def test_popular_groups_recent_normalized_questions_and_uses_latest_display_question():
    now = datetime.now(UTC)
    fake_session = PopularFakeSession(
        [
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                query="  도서관   시간?  ",
                created_at=now - timedelta(hours=2),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000006"),
                query="장학금 신청",
                created_at=now - timedelta(minutes=1),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000003"),
                query="도서관 시간?",
                created_at=now - timedelta(minutes=10),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000004"),
                query=" 장학금   신청 ",
                created_at=now - timedelta(hours=1),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000005"),
                query="장학금 신청",
                created_at=now - timedelta(days=2),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000009"),
                query="장학금 신청",
                created_at=now - timedelta(days=31),
            ),
            PopularLogRow(
                id=UUID("00000000-0000-0000-0000-000000000008"),
                query="졸업 요건",
                created_at=now - timedelta(days=31),
            ),
        ]
    )
    override_session(fake_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/popular")

    assert response.status_code == 200
    assert response.json() == [
        {"rank": 1, "question": "장학금 신청", "view_count": 3},
        {"rank": 2, "question": "도서관 시간?", "view_count": 2},
    ]

    assert fake_session.statement is not None
    assert _has_recent_query_log_cutoff(fake_session.statement)
    assert [str(clause) for clause in fake_session.statement._order_by_clauses] == [
        "query_logs.created_at DESC",
        "query_logs.id DESC",
    ]


def _has_recent_query_log_cutoff(statement: object) -> bool:
    for criterion in getattr(statement, "_where_criteria", ()):
        if (
            str(getattr(criterion, "left", "")) == "query_logs.created_at"
            and getattr(criterion, "operator", None) is operators.ge
        ):
            cutoff = getattr(getattr(criterion, "right", None), "value", None)
            return isinstance(cutoff, datetime) and cutoff.tzinfo is not None
    return False
