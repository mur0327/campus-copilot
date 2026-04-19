from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    database_url: str
    crawl_target_url: str = "https://www.honam.ac.kr"
    crawl_main_path: str = "/main"
    crawl_content_selector: str = "article.articleBox"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_graduation_path: str = "/GraduateGrades"
    crawl_pdf_year_limit: int = 5
    crawl_timeout_seconds: int = 30
    crawl_impersonate: str = "chrome120"
    crawl_schedule: str = "0 3 * * *"
    crawl4ai_base_directory: str = "/tmp/crawl4ai"
    pdf_hybrid_backend: str | None = None
    pdf_hybrid_mode: str = "auto"
    pdf_hybrid_url: str = "http://localhost:5002"


settings = WorkerSettings()  # pyright: ignore[reportCallIssue]
