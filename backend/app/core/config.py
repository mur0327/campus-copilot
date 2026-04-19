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

    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:12b"
    gemini_api_key: str = ""

    crawl_target_url: str = "https://www.honam.ac.kr"
    crawl_content_selector: str = "article.articleBox"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_schedule: str = "0 3 * * *"


settings = Settings()
