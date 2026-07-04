from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.types import SourceScope


class CrawlSeedSite(BaseModel):
    name: str
    url: str
    source_scope: SourceScope
    discover_department_sites: bool = False

    @field_validator("url", mode="before")
    @classmethod
    def normalize_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().rstrip("/")
        return value


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    database_url: str
    crawl_seed_sites: list[CrawlSeedSite] = [
        CrawlSeedSite(
            name="호남대학교",
            url="https://www.honam.ac.kr",
            source_scope="general_academic",
            discover_department_sites=True,
        ),
        CrawlSeedSite(
            name="입학안내",
            url="https://enter.honam.ac.kr",
            source_scope="admission",
        ),
    ]
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
    crawl_final_validation_concurrency: int = 24
    crawl_final_validation_timeout_seconds: int = 8
    crawl_ingestion_concurrency: int = 6
    crawl_markdown_concurrency: int = 1
    crawl_markdown_timeout_seconds: int = 45
    crawl_document_timeout_seconds: int = 120
    crawl_target_limit: int = 0
    crawl_impersonate: str = "chrome120"
    # fetch artifact 캐시. dir이 설정되면 document fetch 원본을 파일에 저장한다.
    # mode="network": 항상 네트워크 fetch 후 write-through(스케줄 크롤, 변경 감지).
    # mode="cache_first": 캐시 우선, 없을 때만 fetch(재파싱용, 네트워크 회피).
    crawl_fetch_cache_dir: str | None = None
    crawl_fetch_cache_mode: Literal["network", "cache_first"] = "network"
    # discovery가 만든 검증된 타깃 목록을 저장할 JSON 경로. 설정되면 DISCOVER가 쓰고
    # `--from parse` 재파싱이 네트워크 discovery 없이 이 파일을 읽는다.
    crawl_target_artifact_path: str | None = None
    crawl_schedule: str = "0 3 * * *"
    crawl4ai_base_directory: str = "/tmp/crawl4ai"
    pdf_hybrid_backend: str | None = None
    pdf_hybrid_mode: str = "auto"
    pdf_hybrid_url: str = "http://localhost:5002"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "campus_copilot_chunks"
    embedding_model: str = "voyage-4-large"
    voyage_api_key: str = ""
    index_batch_size: int = 64
    bm25_cache_dir: str = ".data/bm25"
    # 보조 LLM: 색인 시점 오프라인 유틸용(문서 검색 키워드 생성 등). 답변 생성 LLM과 별개.
    # 지연이 무관한 배치라 저가·고빈도 모델을 쓴다. 키가 없으면 키워드 생성은 스킵한다.
    aux_llm_provider: str = "gemini"
    aux_llm_model: str = "gemini-3.1-flash-lite"
    gemini_api_key: str = ""
    trigger_host: str = "0.0.0.0"
    trigger_port: int = 8088

    @model_validator(mode="after")
    def validate_unique_seed_urls(self) -> "WorkerSettings":
        if not self.crawl_seed_sites:
            raise ValueError("crawl_seed_sites must contain at least one seed")

        seen_urls: set[str] = set()
        for seed in self.crawl_seed_sites:
            if seed.url in seen_urls:
                raise ValueError(f"duplicate crawl seed url: {seed.url}")
            seen_urls.add(seed.url)

            parsed = urlparse(seed.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"invalid crawl seed url: {seed.url}")

        return self


settings = WorkerSettings()  # pyright: ignore[reportCallIssue]
