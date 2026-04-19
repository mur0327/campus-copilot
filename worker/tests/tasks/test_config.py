import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

from core.config import WorkerSettings


def test_worker_settings_phase_two_defaults(monkeypatch):
    monkeypatch.setenv("CRAWL_TARGET_URL", "https://www.honam.ac.kr")

    settings = WorkerSettings(_env_file=None)

    assert settings.crawl_target_url == "https://www.honam.ac.kr"
    assert settings.crawl_main_path == "/main"
    assert settings.crawl_graduation_path == "/GraduateGrades"
    assert settings.crawl_pdf_year_limit == 5
    assert settings.crawl_impersonate == "chrome120"
    assert settings.crawl4ai_base_directory == "/tmp/crawl4ai"


def test_worker_settings_ignores_empty_pdf_hybrid_backend(monkeypatch):
    monkeypatch.setenv("PDF_HYBRID_BACKEND", "")

    settings = WorkerSettings(_env_file=None)

    assert settings.pdf_hybrid_backend is None
