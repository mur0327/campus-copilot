from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    database_url: str
    crawl_target_urls: Annotated[list[str], NoDecode] = ["https://www.honam.ac.kr"]
    crawl_main_path: str = "/main"
    crawl_content_selector: str = "article.articleBox"
    crawl_article_link_selector: str = "article.articleBox a[href]"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_menu_link_selector: str = 'a:not([data-link="true"])'
    crawl_department_selector: str = "ul#universityTop"
    crawl_department_link_selector: str = "a[href]"
    crawl_graduation_path: str = "/GraduateGrades"
    crawl_pdf_year_selector: str = "select#selectYear"
    crawl_pdf_year_limit: int = 5
    crawl_timeout_seconds: int = 30
    crawl_validation_concurrency: int = 12
    crawl_retry_validation_concurrency: int = 3
    crawl_ingestion_concurrency: int = 6
    crawl_impersonate: str = "chrome120"
    crawl_schedule: str = "0 3 * * *"
    crawl4ai_base_directory: str = "/tmp/crawl4ai"
    pdf_hybrid_backend: str | None = None
    pdf_hybrid_mode: str = "auto"
    pdf_hybrid_url: str = "http://localhost:5002"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "campus_copilot_chunks"
    embedding_model: str = "jhgan/ko-sroberta-multitask"
    index_batch_size: int = 64

    @field_validator("crawl_target_urls", mode="before")
    @classmethod
    def parse_crawl_target_urls(cls, value: object) -> object:
        if isinstance(value, str):
            return [url.strip().rstrip("/") for url in value.split(",") if url.strip()]
        if isinstance(value, list):
            return [
                url.strip().rstrip("/") if isinstance(url, str) else url
                for url in value
            ]
        return value


settings = WorkerSettings()  # pyright: ignore[reportCallIssue]
