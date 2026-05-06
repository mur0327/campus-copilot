import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.services.query_log import (  # noqa: E402
    build_sources_log_payload,
    normalize_query,
    write_query_log,
)


def test_normalize_query_trims_lowercases_and_collapses_spaces():
    assert normalize_query("  휴학   신청은?  ") == "휴학 신청은?"


def test_build_sources_log_payload_wraps_items_and_metadata():
    payload = build_sources_log_payload(
        items=[{"title": "휴학", "url": "https://example.test"}],
        status="success",
        cache_hit=True,
        category="academic",
        query="휴학 신청은?",
    )

    assert payload["_meta"]["status"] == "success"
    assert payload["_meta"]["cache_hit"] is True
    assert payload["_meta"]["category"] == "academic"
    assert payload["_meta"]["normalized_query"] == "휴학 신청은?"
    assert payload["items"][0]["title"] == "휴학"


async def test_write_query_log_adds_commits_refreshes_and_returns_log():
    calls = []

    class FakeSession:
        def add(self, log):
            calls.append(("add", log))

        async def commit(self):
            calls.append(("commit", None))

        async def refresh(self, log):
            calls.append(("refresh", log))

    log = await write_query_log(
        FakeSession(),
        query="휴학 신청은?",
        answer="포털에서 신청합니다.",
        sources={"items": []},
        has_conflict=False,
        response_ms=123,
    )

    assert log.query == "휴학 신청은?"
    assert log.sources == {"items": []}
    assert [call[0] for call in calls] == ["add", "commit", "refresh"]
    assert calls[0][1] is log
    assert calls[2][1] is log
