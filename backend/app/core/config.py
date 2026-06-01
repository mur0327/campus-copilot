from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    database_url: str

    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "campus_copilot_chunks"
    embedding_model: str = "voyage-4-large"
    voyage_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"

    retriever_semantic_top_n: int = 20
    retriever_bm25_top_n: int = 20
    retriever_final_top_k: int = 6
    retriever_semantic_weight: float = 0.7
    retriever_bm25_weight: float = 0.3
    retriever_bm25_cache_dir: str = ".data/bm25"

    freshness_stale_days: int = 180
    chat_cache_ttl_seconds: int = 3600

    llm_provider: str = "llama_cpp"
    llama_cpp_base_url: str = "http://localhost:8080"
    llama_cpp_model: str = "local"
    gemini_api_key: str = ""
    gemini_model: str = ""

    crawl_target_url: str = "https://www.honam.ac.kr"
    crawl_content_selector: str = "article.articleBox"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_schedule: str = "0 3 * * *"
    worker_crawl_url: str = "http://worker:8088/internal/crawl"
    worker_crawl_status_url: str = "http://worker:8088/internal/crawl/status"


settings = Settings()
