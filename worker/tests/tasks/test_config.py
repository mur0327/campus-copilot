import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.config import WorkerSettings


def test_worker_settings_phase_two_defaults(monkeypatch):
    monkeypatch.setenv("CRAWL_TARGET_URLS", "https://www.honam.ac.kr")

    settings = WorkerSettings(_env_file=None)

    assert settings.crawl_target_urls == ["https://www.honam.ac.kr"]
    assert settings.crawl_main_path == "/main"
    assert settings.crawl_graduation_path == "/GraduateGrades"
    assert settings.crawl_article_link_selector == "article.articleBox a[href]"
    assert settings.crawl_menu_link_selector == 'a:not([data-link="true"])'
    assert settings.crawl_department_selector == "ul#universityTop"
    assert settings.crawl_department_link_selector == "a[href]"
    assert settings.crawl_pdf_year_selector == "select#selectYear"
    assert settings.crawl_pdf_year_limit == 5
    assert settings.crawl_validation_concurrency == 12
    assert settings.crawl_retry_validation_concurrency == 3
    assert settings.crawl_final_validation_concurrency == 24
    assert settings.crawl_final_validation_timeout_seconds == 8
    assert settings.crawl_ingestion_concurrency == 6
    assert settings.crawl_markdown_concurrency == 1
    assert settings.crawl_markdown_timeout_seconds == 45
    assert settings.crawl_document_timeout_seconds == 120
    assert settings.crawl_impersonate == "chrome120"
    assert settings.crawl4ai_base_directory == "/tmp/crawl4ai"
    assert settings.embedding_model == "jhgan/ko-sroberta-multitask"
    assert settings.chroma_collection == "campus_copilot_chunks"
    assert settings.index_batch_size == 64
    assert settings.bm25_cache_dir == ".data/bm25"
    assert settings.trigger_host == "0.0.0.0"
    assert settings.trigger_port == 8088


def test_worker_settings_ignores_empty_pdf_hybrid_backend(monkeypatch):
    monkeypatch.setenv("PDF_HYBRID_BACKEND", "")

    settings = WorkerSettings(_env_file=None)

    assert settings.pdf_hybrid_backend is None


def test_worker_settings_parses_comma_separated_target_urls(monkeypatch):
    monkeypatch.setenv(
        "CRAWL_TARGET_URLS",
        "https://www.honam.ac.kr, https://enter.honam.ac.kr/",
    )

    settings = WorkerSettings(_env_file=None)

    assert settings.crawl_target_urls == [
        "https://www.honam.ac.kr",
        "https://enter.honam.ac.kr",
    ]
