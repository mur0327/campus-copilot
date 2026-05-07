import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

from app.core.config import Settings


def test_phase_four_backend_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

    settings = Settings(_env_file=None)

    assert settings.chroma_collection == "campus_copilot_chunks"
    assert settings.retriever_semantic_top_n == 20
    assert settings.retriever_bm25_top_n == 20
    assert settings.retriever_final_top_k == 6
    assert settings.retriever_semantic_weight == 0.7
    assert settings.retriever_bm25_weight == 0.3
    assert settings.retriever_bm25_cache_dir == ".data/bm25"
    assert settings.freshness_stale_days == 180
    assert settings.chat_cache_ttl_seconds == 3600
    assert settings.worker_crawl_url == "http://worker:8088/internal/crawl"


def test_gemini_provider_requires_model_and_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "gemini"
    assert settings.gemini_api_key == ""
    assert settings.gemini_model == ""


def test_llama_cpp_provider_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost/db")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "llama_cpp"
    assert settings.llama_cpp_base_url == "http://localhost:8080"
    assert settings.llama_cpp_model == "local"
