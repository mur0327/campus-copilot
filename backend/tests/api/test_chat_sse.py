import json
import os
from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.api.routes import chat as chat_route  # noqa: E402
from app.api.routes.chat import (
    _cache_key,  # noqa: E402
    get_chat_dependencies,  # noqa: E402
)
from app.main import app  # noqa: E402
from app.schemas import ChatResponse, ConflictWarning  # noqa: E402
from app.services.retriever import RetrievalResult  # noqa: E402


@pytest.fixture(autouse=True)
def clear_chat_test_state():
    keys = [
        "test_retrieval_results",
        "test_tokens",
        "test_procedure_steps",
        "test_query_logs",
    ]
    for key in keys:
        if hasattr(app.state, key):
            delattr(app.state, key)
    app.dependency_overrides.clear()
    yield
    for key in keys:
        if hasattr(app.state, key):
            delattr(app.state, key)
    app.dependency_overrides.clear()


class FakeSession:
    pass


class FakeSessionFactory:
    def __init__(self):
        self.open_sessions = []

    def __call__(self):
        session = FakeSession()
        self.open_sessions.append(session)
        return FakeSessionContext(session)


class FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        global active_test_session
        active_test_session = self.session
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        global active_test_session
        active_test_session = None
        return False


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.sessions = []

    async def retrieve(self, session, *, question, category, semantic_top_n, bm25_top_n):
        self.sessions.append(session)
        return self.results


class FakeStatusRetriever:
    def __init__(self, results, status):
        self.results = results
        self.status = status

    async def retrieve_with_status(self, session, *, question, category, semantic_top_n, bm25_top_n):
        return SimpleNamespace(results=self.results, status=self.status)


class FakeProvider:
    def __init__(self, tokens):
        self.tokens = tokens
        self.closed = False
        self.session_during_stream = None

    async def stream(self, messages):
        for token in self.tokens:
            self.session_during_stream = active_test_session
            yield token

    async def aclose(self):
        self.closed = True


class FailingProvider:
    def __init__(self):
        self.closed = False

    async def stream(self, messages):
        raise RuntimeError("provider failed")
        yield ""

    async def aclose(self):
        self.closed = True


class FakeCache:
    def __init__(self, value=None):
        self.value = value
        self.set_calls = []

    async def get(self, key):
        return self.value

    async def set(self, key, value, ttl=None):
        self.set_calls.append({"key": key, "value": value, "ttl": ttl})


class FailingGetCache:
    async def get(self, key):
        raise ConnectionError("redis unavailable")

    async def set(self, key, value, ttl=None):
        return None


active_test_session = None


def make_retrieval_result(*, crawled_at=None):
    return RetrievalResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="1. 포털에 로그인합니다.\n2. 휴학 신청은 포털에서 진행합니다.",
        chunk_type="text",
        score=1.0,
        title=None,
        url="https://example.test/leave",
        menu_path="학사 > 휴학",
        category="academic",
        crawled_at=crawled_at or datetime(2026, 5, 1, 12, 0, 0),
        meta=None,
    )


def parse_events(body):
    events = []
    normalized_body = body.replace("\r\n", "\n")
    for chunk in normalized_body.strip().split("\n\n"):
        event_name = None
        data = ""
        for line in chunk.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            if line.startswith("data: "):
                data += line.removeprefix("data: ")
        events.append({"event": event_name, "data": json.loads(data)})
    return events


def test_default_chat_dependencies_include_lazy_redis_cache(monkeypatch):
    created_urls = []

    class FakeCacheFactory:
        @staticmethod
        def from_url(url):
            created_urls.append(url)
            return {"redis_url": url}

    monkeypatch.setattr(chat_route, "Cache", FakeCacheFactory)
    monkeypatch.setattr(chat_route, "_default_cache", None)

    dependencies = get_chat_dependencies()

    assert dependencies["cache"] == {"redis_url": chat_route.settings.redis_url}
    assert created_urls == [chat_route.settings.redis_url]


def test_chat_cache_key_uses_versioned_category_and_question_hash():
    digest = sha256("휴학 신청은?".encode()).hexdigest()

    assert _cache_key("휴학 신청은?", "academic") == f"chat:v1:academic:{digest}"


@pytest.mark.asyncio
async def test_chat_rejects_blank_question():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat", json={"question": ""})

    assert response.status_code in {400, 422}


@pytest.mark.asyncio
async def test_chat_stream_returns_named_events():
    app.state.test_retrieval_results = ["fake-result"]
    app.state.test_tokens = ["휴학", " 신청은", " 포털에서"]
    app.state.test_procedure_steps = ["포털에 로그인합니다."]
    app.state.test_query_logs = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert body.index("event: metadata") < body.index("event: token")
    assert body.index("event: token") < body.index("event: procedure_steps")
    assert body.index("event: procedure_steps") < body.index("event: done")
    assert app.state.test_query_logs[-1]["query"] == "휴학 신청은?"


@pytest.mark.asyncio
async def test_chat_stream_uses_overridden_production_dependencies():
    global active_test_session
    active_test_session = None
    logs = []
    session_factory = FakeSessionFactory()
    retrieval_result = make_retrieval_result()
    retriever = FakeRetriever([retrieval_result])
    provider = FakeProvider(["휴학", " 신청은", " 포털에서 진행합니다."])
    cache = FakeCache()

    async def conflict_warning_loader(session, chunk_ids):
        return ConflictWarning(exists=False)

    async def query_log_writer(session, **kwargs):
        logs.append({"session": session, **kwargs})

    def override_dependencies():
        return {
            "retriever": retriever,
            "llm_provider_factory": lambda: provider,
            "cache": cache,
            "query_log_writer": query_log_writer,
            "conflict_warning_loader": conflict_warning_loader,
            "session_factory": session_factory,
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?", "category": "academic"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert response.status_code == 200
    assert [event["event"] for event in events] == ["metadata", "token", "token", "token", "procedure_steps", "done"]
    done = events[-1]["data"]
    assert done["answer"] == "휴학 신청은 포털에서 진행합니다."
    assert done["sources"][0]["title"] == "학사 > 휴학"
    assert done["sources"][0]["crawled_at"] == "2026-05-01T12:00:00+00:00"
    assert done["procedure_steps"] == []
    assert done["conflict_warning"] == {"exists": False, "description": None}
    assert done["freshness"] == "recent"
    assert done["retrieval_status"]["mode"] == "hybrid"
    assert logs[-1]["query"] == "휴학 신청은?"
    assert logs[-1]["sources"]["_meta"]["cache_hit"] is False
    assert logs[-1]["sources"]["_meta"]["retrieval_status"]["mode"] == "hybrid"
    assert provider.closed is True
    assert provider.session_during_stream is None


@pytest.mark.asyncio
async def test_chat_stream_deduplicates_sources_by_url():
    logs = []
    first = make_retrieval_result()
    second = make_retrieval_result().model_copy(
        update={
            "chunk_id": uuid4(),
            "document_id": first.document_id,
            "url": first.url,
            "title": "중복 휴학 안내",
        }
    )
    provider = FakeProvider(["휴학", " 답변"])
    conflict_chunk_ids = []

    async def conflict_warning_loader(session, chunk_ids):
        conflict_chunk_ids.extend(chunk_ids)
        return ConflictWarning(exists=False)

    async def query_log_writer(session, **kwargs):
        logs.append(kwargs)

    def override_dependencies():
        return {
            "retriever": FakeRetriever([first, second]),
            "llm_provider_factory": lambda: provider,
            "cache": FakeCache(),
            "query_log_writer": query_log_writer,
            "conflict_warning_loader": conflict_warning_loader,
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert response.status_code == 200
    assert len(events[0]["data"]["sources"]) == 1
    assert events[0]["data"]["sources"][0]["chunk_id"] == str(first.chunk_id)
    assert len(events[-1]["data"]["sources"]) == 1
    assert logs[-1]["sources"]["items"] == events[-1]["data"]["sources"]
    assert conflict_chunk_ids == [first.chunk_id, second.chunk_id]


@pytest.mark.asyncio
async def test_chat_stream_treats_cache_read_failure_as_miss():
    logs = []
    retrieval_result = make_retrieval_result()
    provider = FakeProvider(["휴학", " 신청은", " 포털에서 진행합니다."])

    async def query_log_writer(session, **kwargs):
        logs.append(kwargs)

    def override_dependencies():
        return {
            "retriever": FakeRetriever([retrieval_result]),
            "llm_provider_factory": lambda: provider,
            "cache": FailingGetCache(),
            "query_log_writer": query_log_writer,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert [event["event"] for event in events] == ["metadata", "token", "token", "token", "procedure_steps", "done"]
    assert logs[-1]["sources"]["_meta"]["cache_hit"] is False


@pytest.mark.asyncio
async def test_chat_metadata_reports_keyword_only_degraded_retrieval():
    retrieval_result = make_retrieval_result()
    provider = FakeProvider(["BM25", " 답변"])
    retrieval_status = {
        "mode": "keyword_only",
        "degraded": True,
        "semantic_available": False,
        "bm25_available": True,
        "semantic_error": "RuntimeError",
        "bm25_error": None,
    }

    def override_dependencies():
        return {
            "retriever": FakeStatusRetriever([retrieval_result], retrieval_status),
            "llm_provider_factory": lambda: provider,
            "cache": FakeCache(),
            "query_log_writer": None,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert events[0]["event"] == "metadata"
    assert events[0]["data"]["retrieval_status"] == retrieval_status
    assert events[-1]["data"]["retrieval_status"] == retrieval_status
    assert events[-1]["data"]["answer"] == "BM25 답변"


@pytest.mark.asyncio
async def test_chat_empty_retrieval_status_does_not_call_llm_provider():
    retrieval_status = {
        "mode": "empty",
        "degraded": True,
        "semantic_available": False,
        "bm25_available": False,
        "semantic_error": "RuntimeError",
        "bm25_error": "worker BM25 index is missing or stale",
    }

    def override_dependencies():
        return {
            "retriever": FakeStatusRetriever([], retrieval_status),
            "llm_provider_factory": lambda: FailingProvider(),
            "cache": FakeCache(),
            "query_log_writer": None,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert [event["event"] for event in events] == ["metadata", "procedure_steps", "done"]
    assert events[0]["data"]["retrieval_status"] == retrieval_status
    assert events[-1]["data"]["answer"] == "검색된 공식 문서 근거가 부족해 답변할 수 없습니다."


@pytest.mark.asyncio
async def test_chat_cache_hit_emits_metadata_and_done_without_tokens():
    logs = []
    session_factory = FakeSessionFactory()
    cached = ChatResponse(
        answer="캐시 답변입니다.",
        sources=[],
        procedure_steps=[],
        conflict_warning=ConflictWarning(exists=False),
        freshness="recent",
    ).model_dump(mode="json")

    async def query_log_writer(session, **kwargs):
        logs.append({"session": session, **kwargs})

    def override_dependencies():
        return {
            "retriever": FakeRetriever([make_retrieval_result()]),
            "llm_provider_factory": lambda: FakeProvider(["호출되면 안 됩니다."]),
            "cache": FakeCache(cached),
            "query_log_writer": query_log_writer,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": session_factory,
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert [event["event"] for event in events] == ["metadata", "done"]
    assert events[-1]["data"]["answer"] == "캐시 답변입니다."
    assert logs[-1]["query"] == "휴학 신청은?"
    assert logs[-1]["sources"]["_meta"]["cache_hit"] is True


@pytest.mark.asyncio
async def test_chat_cache_hit_deduplicates_sources_by_url():
    source = {
        "title": "졸업학점 2025",
        "url": "https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
        "crawled_at": "2026-05-07T12:20:43+00:00",
        "freshness": "recent",
        "chunk_id": str(uuid4()),
    }
    duplicate_source = {**source, "chunk_id": str(uuid4())}
    cached = ChatResponse(
        answer="캐시 답변입니다.",
        sources=[source, duplicate_source],
        procedure_steps=[],
        conflict_warning=ConflictWarning(exists=False),
        freshness="recent",
    ).model_dump(mode="json")

    def override_dependencies():
        return {
            "retriever": FakeRetriever([make_retrieval_result()]),
            "llm_provider_factory": lambda: FakeProvider(["호출되면 안 됩니다."]),
            "cache": FakeCache(cached),
            "query_log_writer": None,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "졸업학점"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert len(events[0]["data"]["sources"]) == 1
    assert len(events[-1]["data"]["sources"]) == 1
    assert events[-1]["data"]["sources"][0]["chunk_id"] == source["chunk_id"]


@pytest.mark.asyncio
async def test_chat_stream_emits_error_event_and_closes_provider_on_failure():
    logs = []
    provider = FailingProvider()
    retrieval_status = {
        "mode": "hybrid",
        "degraded": False,
        "semantic_available": True,
        "bm25_available": True,
        "semantic_error": None,
        "bm25_error": None,
    }

    async def query_log_writer(session, **kwargs):
        logs.append(kwargs)

    def override_dependencies():
        return {
            "retriever": FakeStatusRetriever([make_retrieval_result()], retrieval_status),
            "llm_provider_factory": lambda: provider,
            "cache": FakeCache(),
            "query_log_writer": query_log_writer,
            "conflict_warning_loader": lambda session, chunk_ids: ConflictWarning(exists=False),
            "session_factory": FakeSessionFactory(),
        }

    app.dependency_overrides[get_chat_dependencies] = override_dependencies

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"question": "휴학 신청은?"},
            headers={"Accept": "text/event-stream"},
        )

    events = parse_events(response.text)

    assert [event["event"] for event in events] == ["metadata", "error"]
    assert events[-1]["data"] == {"message": "답변 생성 중 오류가 발생했습니다.", "retryable": True}
    assert logs[-1]["sources"]["_meta"]["status"] == "failure"
    assert logs[-1]["sources"]["_meta"]["error_type"] == "RuntimeError"
    assert logs[-1]["sources"]["_meta"]["retrieval_status"] == retrieval_status
    assert provider.closed is True
