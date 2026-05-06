# Campus Copilot — Phase 1 Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 호남대학교 학사 안내 키오스크 시스템의 전체 프로젝트 골격(디렉터리, 설정 파일, Docker Compose, 패키지 설정, 진입점)을 생성하고 `docker compose up` 으로 모든 서비스가 기동되는 상태를 만든다.

**Architecture:** 2-tier 구조 — `backend`(FastAPI + RAG), `worker`(APScheduler + Crawl4AI), `frontend`(React/Vite + nginx), `pi-setup`(라즈베리파이 전용). PostgreSQL·ChromaDB·Redis는 Docker로 실행. 모든 서비스는 `docker compose` 기준으로 기동한다.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic, React 19 + TypeScript + Vite, Tailwind CSS v4, Docker Compose v2, PostgreSQL 16, ChromaDB 1.5, Redis 8

---

## 파일 맵

```
campus-copilot/
├── docker-compose.yml            # 로컬 개발용 전체 스택
├── docker-compose.prod.yml       # AWS 운영용 (nginx + HTTPS)
├── chromadb/
│   ├── Dockerfile                # curl 포함 ChromaDB 파생 이미지
│   └── chroma.config.yaml        # ChromaDB 단일 노드 설정 (port, persist path)
├── nginx.conf                    # 운영용 reverse proxy
├── .env.example                  # 환경변수 템플릿
├── .gitignore                    # Python/Node/Docker 제외 목록
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # uv 기반 의존성
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/            # (비어 있음, 마이그레이션은 Task 5에서)
│   ├── scripts/
│   │   └── entrypoint.sh        # migrate 후 uvicorn 실행
│   └── app/
│       ├── main.py              # FastAPI 앱 진입점
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── chat.py      # POST /api/v1/chat (stub)
│       │       ├── categories.py
│       │       └── admin.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py        # pydantic-settings
│       │   └── db.py            # SQLAlchemy async engine + session
│       ├── models/
│       │   ├── __init__.py
│       │   └── document.py      # Document, DocumentChunk ORM 모델
│       └── schemas/
│           ├── __init__.py
│           └── chat.py          # ChatRequest, ChatResponse Pydantic 스키마
│
├── worker/
│   ├── Dockerfile               # Python 3.12 + Java 11 JDK
│   ├── pyproject.toml
│   └── tasks/
│       ├── __init__.py
│       ├── scheduler.py         # APScheduler 진입점
│       ├── crawl.py             # stub
│       ├── parse.py             # stub
│       ├── embed.py             # stub
│       └── conflict_scan.py     # stub
│
├── frontend/
│   ├── Dockerfile               # Node 빌드 → nginx 서빙
│   ├── nginx.conf               # frontend static serving 설정
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── index.css
│       ├── App.tsx              # 라우팅 (/ → KioskPage, /admin → AdminPage)
│       ├── pages/
│       │   ├── KioskPage.tsx    # stub
│       │   └── AdminPage.tsx    # stub
│       └── components/
│           └── .gitkeep
│
└── pi-setup/
    ├── README.md
    ├── kiosk.sh
    └── print-service/
        ├── print_server.py      # python-escpos FastAPI stub
        ├── requirements.txt
        └── print-service.service
```

---

## Task 1: 루트 인프라 파일

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.prod.yml`
- Create: `chromadb/chroma.config.yaml`
- Create: `chromadb/Dockerfile`
- Create: `nginx.conf`
- Create: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1-1: `.gitignore` 작성**

```
# Python
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
dist/
build/
.mypy_cache/
.ruff_cache/
.worktrees/
worktrees/

# Node
node_modules/
dist/
.cache/

# Docker
*.log

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Alembic
alembic/versions/*.pyc

# 로컬 서비스 데이터
.data/
```

- [ ] **Step 1-2: `.env.example` 작성**

```bash
# ── 공통 ──────────────────────────────────────────
ENVIRONMENT=development        # development | production

# ── Backend ────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://campus:campus@postgres:5432/campus_copilot
CHROMA_HOST=chromadb
CHROMA_PORT=8001
REDIS_URL=redis://redis:6379/0

# LLM Provider: ollama (로컬) | gemini (운영)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma3:12b
GEMINI_API_KEY=

# ── Worker ─────────────────────────────────────────
CRAWL_TARGET_URL=https://www.honam.ac.kr
CRAWL_CONTENT_SELECTOR=article.articleBox
CRAWL_MENU_SELECTOR=ul#mainMenu
CRAWL_SCHEDULE=0 3 * * *      # 매일 새벽 3시

# ── Frontend ───────────────────────────────────────
# 로컬 개발: 백엔드가 docker-compose 내부에 있으면 http://localhost:8000
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 1-3: `chromadb/chroma.config.yaml` 작성**

```yaml
port: 8001
listen_address: "0.0.0.0"
persist_path: "/data"
allow_reset: false
```

- [ ] **Step 1-4: `docker-compose.yml` 작성**

```yaml
name: campus-copilot

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: campus
      POSTGRES_PASSWORD: campus
      POSTGRES_DB: campus_copilot
    volumes:
      - ./.data/postgres:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U campus -d campus_copilot"]
      interval: 5s
      timeout: 5s
      retries: 5

  chromadb:
    build:
      context: ./chromadb
      dockerfile: Dockerfile
    volumes:
      - ./.data/chromadb:/data
      - ./chromadb/chroma.config.yaml:/config.yaml:ro
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8001/api/v2/healthcheck"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:8-alpine
    volumes:
      - ./.data/redis:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      chromadb:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: ["sh", "/app/scripts/entrypoint.sh", "--reload"]

  worker:
    build:
      context: ./worker
      dockerfile: Dockerfile
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    volumes:
      - ./worker:/app

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: dev
    env_file: .env
    ports:
      - "5173:5173"
    volumes:
      - ./frontend/src:/app/src

```

- [ ] **Step 1-5: `nginx.conf` 작성**

```nginx
events {}

http {
  upstream frontend_upstream {
    server frontend:80;
  }

  upstream backend_upstream {
    server backend:8000;
  }

  server {
    listen 80;
    server_name _;

    location /api/ {
      proxy_pass http://backend_upstream;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
      proxy_pass http://frontend_upstream;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
    }
  }
}
```

- [ ] **Step 1-6: `docker-compose.prod.yml` 작성 (AWS 운영용 오버라이드)**

```yaml
name: campus-copilot-prod

services:
  backend:
    restart: unless-stopped
    volumes: []                     # 운영에서는 볼륨 마운트 제거
    command: ["sh", "/app/scripts/entrypoint.sh", "--workers", "2"]

  worker:
    restart: unless-stopped
    volumes: []

  frontend:
    build:
      target: prod                  # nginx 서빙 스테이지
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
```

- [ ] **Step 1-6: 커밋**

```bash
git add .gitignore .env.example docker-compose.yml docker-compose.prod.yml chromadb/Dockerfile chromadb/chroma.config.yaml nginx.conf
git commit \
  -m "chore(infra): add root scaffold config" \
  -m "- add compose files for local and production environments" \
  -m "- add env template, nginx reverse proxy, and gitignore updates" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 2: Backend — pyproject.toml + Dockerfile

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/Dockerfile`

- [ ] **Step 2-1: `backend/pyproject.toml` 작성**

```toml
[project]
name = "campus-copilot-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # Web
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    # DB
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.13",
    # Settings
    "pydantic-settings>=2.5",
    # Redis cache
    "aiocache[redis]>=0.12",
    # HTTP client
    "httpx>=0.27",
    # RAG
    "chromadb==1.5.8",
    "sentence-transformers>=3.3",
    "rank-bm25>=0.2",
    # LLM
    "google-genai>=1.33",
    "ollama>=0.4",
    # SSE
    "sse-starlette>=2.1",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",       # TestClient
    "ruff>=0.7",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2-2: `backend/Dockerfile` 작성**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# uv 설치
RUN pip install uv --no-cache-dir

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
```

- [ ] **Step 2-3: 커밋**

```bash
git add backend/pyproject.toml backend/Dockerfile
git commit \
  -m "chore(backend): add runtime packaging" \
  -m "- add backend pyproject with core dependencies" \
  -m "- add container image bootstrap for uv-based environment" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 3: Backend — 앱 뼈대 (config, db, main)

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/db.py`
- Create: `backend/app/main.py`

- [ ] **Step 3-1: `backend/app/core/config.py` 작성**

pydantic-settings로 `.env` 파일을 읽는다.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"

    # DB
    database_url: str

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    llm_provider: str = "ollama"  # "ollama" | "gemini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:12b"
    gemini_api_key: str = ""

    # Crawler
    crawl_target_url: str = "https://www.honam.ac.kr"
    crawl_content_selector: str = "article.articleBox"
    crawl_menu_selector: str = "ul#mainMenu"
    crawl_schedule: str = "0 3 * * *"


settings = Settings()
```

- [ ] **Step 3-2: `backend/app/core/db.py` 작성**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=settings.environment == "development")

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3-3: `backend/app/main.py` 작성**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, categories, admin

app = FastAPI(title="Campus Copilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 운영에서 프론트 도메인으로 교체
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 3-4: 라우트 stub 작성**

`backend/app/api/__init__.py` — 빈 파일

`backend/app/api/routes/__init__.py` — 빈 파일

`backend/app/api/routes/chat.py`:
```python
from fastapi import APIRouter

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat():
    return {"message": "not implemented"}
```

`backend/app/api/routes/categories.py`:
```python
from fastapi import APIRouter

router = APIRouter(tags=["categories"])


@router.get("/categories")
async def list_categories():
    return []


@router.get("/recent")
async def list_recent():
    return []
```

`backend/app/api/routes/admin.py`:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def status():
    return {"documents": 0, "last_crawled": None}


@router.post("/crawl")
async def trigger_crawl():
    return {"status": "triggered"}


@router.get("/conflicts")
async def list_conflicts():
    return []


@router.get("/logs")
async def list_logs():
    return []
```

- [ ] **Step 3-5: `backend/app/models/__init__.py`, `backend/app/schemas/__init__.py` — 빈 파일 생성**

```bash
touch backend/app/models/__init__.py backend/app/schemas/__init__.py
```

- [ ] **Step 3-6: 커밋**

```bash
git add backend/app/
git commit \
  -m "feat(backend): add app skeleton" \
  -m "- add settings, database session, health route, and API stubs" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 4: Backend — ORM 모델 + Pydantic 스키마

**Files:**
- Create: `backend/app/models/document.py`
- Create: `backend/app/schemas/chat.py`

- [ ] **Step 4-1: `backend/app/models/document.py` 작성**

```python
import uuid
from datetime import datetime

from sqlalchemy import UUID, Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    menu_path: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'html' | 'pdf'
    content_hash: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_type: Mapped[str] = mapped_column(Text, nullable=False)  # 'text' | 'table'
    chroma_id: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class ConflictPair(Base):
    __tablename__ = "conflict_pairs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    chunk_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False
    )
    chunk_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id"), nullable=False
    )
    conflict_type: Mapped[str] = mapped_column(Text)  # 'date' | 'procedure' | 'condition'
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text, default="warning")  # 'warning' | 'critical'
    detected_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list | None] = mapped_column(JSONB)
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    response_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    status: Mapped[str] = mapped_column(Text, default="running")  # running | completed | failed
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    pages_changed: Mapped[int] = mapped_column(Integer, default=0)
    conflicts_found: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMPTZ)
    error: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 4-2: `backend/app/schemas/chat.py` 작성**

```python
from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    crawled_at: str


class ConflictWarning(BaseModel):
    exists: bool
    description: str | None = None


class ChatRequest(BaseModel):
    question: str
    category: str | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source] = Field(default_factory=list)
    procedure_steps: list[str] = Field(default_factory=list)
    conflict_warning: ConflictWarning = ConflictWarning(exists=False)
    freshness: str = "recent"  # 'recent' | 'stale' | 'unknown'
```

- [ ] **Step 4-3: 커밋**

```bash
git add backend/app/models/document.py backend/app/schemas/chat.py
git commit \
  -m "feat(backend): add data models and schemas" \
  -m "- add scaffold ORM models for documents, chunks, conflicts, logs, and jobs" \
  -m "- add chat request and response schemas" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 5: Backend — Alembic 마이그레이션 설정

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/` (directory)

- [ ] **Step 5-1: `backend/alembic.ini` 작성**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5-2: `backend/alembic/env.py` 작성**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.db import Base
from app.models import document  # noqa: F401 — 모델 임포트로 메타데이터 등록

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5-3: `backend/alembic/versions/.gitkeep` 생성**

```bash
mkdir -p backend/alembic/versions && touch backend/alembic/versions/.gitkeep
```

- [ ] **Step 5-4: 커밋**

```bash
git add backend/alembic/
git commit \
  -m "chore(backend): configure alembic" \
  -m "- add async migration environment and version directory scaffold" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 6: Worker — pyproject.toml + Dockerfile + 뼈대

**Files:**
- Create: `worker/pyproject.toml`
- Create: `worker/Dockerfile`
- Create: `worker/tasks/scheduler.py`
- Create: `worker/tasks/crawl.py` (stub)
- Create: `worker/tasks/parse.py` (stub)
- Create: `worker/tasks/embed.py` (stub)
- Create: `worker/tasks/conflict_scan.py` (stub)

- [ ] **Step 6-1: `worker/pyproject.toml` 작성**

```toml
[project]
name = "campus-copilot-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # Scheduler
    "apscheduler>=3.10",
    # Crawling
    "crawl4ai>=0.8.6",
    "curl-cffi>=0.15.0",
    "beautifulsoup4>=4.12",
    # PDF
    "langchain-opendataloader-pdf>=2.0.0",
    # Embedding
    "sentence-transformers>=3.3",
    "chromadb==1.5.8",
    "rank-bm25>=0.2",
    # DB
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    # Settings (백엔드와 동일 .env 공유)
    "pydantic-settings>=2.5",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.7",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 6-2: `worker/Dockerfile` 작성**

Java 17 JDK를 포함하는 것은 `opendataloader-pdf`가 JVM을 사용하기 때문이다.

```dockerfile
FROM python:3.12-slim

# Java 17 JDK 설치 (opendataloader-pdf 의존성)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "tasks.scheduler"]
```

- [ ] **Step 6-3: `worker/tasks/__init__.py` — 빈 파일 생성**

```bash
mkdir -p worker/tasks && touch worker/tasks/__init__.py
```

- [ ] **Step 6-4: `worker/tasks/scheduler.py` 작성**

```python
"""APScheduler 진입점 — worker 컨테이너에서 실행"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from tasks.crawl import run_crawl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    scheduler = AsyncIOScheduler()

    # 크롤 스케줄 (기본: 매일 03:00 KST)
    # CRAWL_SCHEDULE 환경변수로 오버라이드 가능
    import os
    cron_expr = os.getenv("CRAWL_SCHEDULE", "0 3 * * *")
    minute, hour, day, month, day_of_week = cron_expr.split()

    scheduler.add_job(
        run_crawl,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week),
        id="crawl_job",
        max_instances=1,
        misfire_grace_time=600,
    )

    scheduler.start()
    logger.info("Scheduler started. Waiting for jobs...")

    import asyncio
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

- [ ] **Step 6-5: Worker stub 파일들 작성**

`worker/tasks/crawl.py`:
```python
"""크롤링 태스크 — Crawl4AI + curl-cffi"""

import logging

logger = logging.getLogger(__name__)


async def run_crawl() -> None:
    """호남대학교 홈페이지 크롤링 및 문서 인덱싱."""
    logger.info("Crawl started (stub)")
    # TODO: Phase 2 — 크롤러 구현
```

`worker/tasks/parse.py`:
```python
"""파싱 태스크 — HTML (Crawl4AI + BeautifulSoup4), PDF (opendataloader-pdf)"""

import logging

logger = logging.getLogger(__name__)


async def parse_html(url: str, html: str) -> list[dict]:
    """HTML 페이지를 청크 목록으로 변환."""
    logger.info("parse_html stub: %s", url)
    return []


async def parse_pdf(url: str, content: bytes) -> list[dict]:
    """PDF 파일을 청크 목록으로 변환."""
    logger.info("parse_pdf stub: %s", url)
    return []
```

`worker/tasks/embed.py`:
```python
"""임베딩 태스크 — ko-sroberta + ChromaDB + BM25"""

import logging

logger = logging.getLogger(__name__)


async def embed_chunks(chunks: list[dict]) -> None:
    """청크를 ChromaDB에 임베딩."""
    logger.info("embed_chunks stub: %d chunks", len(chunks))
```

`worker/tasks/conflict_scan.py`:
```python
"""충돌 탐지 태스크 — 크롤링 후 실행"""

import logging

logger = logging.getLogger(__name__)


async def scan_conflicts() -> None:
    """새로 추가된 청크에서 충돌 쌍 탐지."""
    logger.info("scan_conflicts stub")
```

- [ ] **Step 6-6: 커밋**

```bash
git add worker/
git commit \
  -m "feat(worker): add scheduler scaffold" \
  -m "- add worker packaging and container setup" \
  -m "- add APScheduler entrypoint and task stubs" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 7: Frontend — Vite + React + TypeScript + Tailwind 설정

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/pages/KioskPage.tsx`
- Create: `frontend/src/pages/AdminPage.tsx`
- Create: `frontend/nginx.conf`
- Create: `frontend/Dockerfile`

- [ ] **Step 7-1: `frontend/package.json` 작성**

```json
{
  "name": "campus-copilot-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.0",
    "zustand": "^5.0.0",
    "@tanstack/react-query": "^5.60.0",
    "@microsoft/fetch-event-source": "^2.0.1",
    "react-simple-keyboard": "^3.8.0",
    "react-qr-code": "^2.0.15",
    "lucide-react": "^0.460.0",
    "sonner": "^1.7.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^6.0.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "eslint": "^9.15.0",
    "@eslint/js": "^9.15.0",
    "typescript-eslint": "^8.15.0"
  }
}
```

- [ ] **Step 7-2: `frontend/tsconfig.json` 작성**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 7-3: `frontend/vite.config.ts` 작성**

```typescript
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
```

- [ ] **Step 7-4: `frontend/index.html` 작성**

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Campus Copilot — 호남대학교</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 7-5: `frontend/src/main.tsx` 작성**

```typescript
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 7-6: `frontend/src/index.css` 작성 (Tailwind v4)**

```css
@import "tailwindcss";
```

- [ ] **Step 7-7: `frontend/src/App.tsx` 작성**

```typescript
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import KioskPage from './pages/KioskPage'
import AdminPage from './pages/AdminPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<KioskPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 7-8: 페이지 stub 작성**

`frontend/src/pages/KioskPage.tsx`:
```typescript
export default function KioskPage() {
  return (
    <div className="flex h-screen items-center justify-center bg-blue-900 text-white">
      <h1 className="text-4xl font-bold">Campus Copilot</h1>
    </div>
  )
}
```

`frontend/src/pages/AdminPage.tsx`:
```typescript
export default function AdminPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">관리자 화면</h1>
    </div>
  )
}
```

- [ ] **Step 7-9: `frontend/Dockerfile` 작성 (멀티스테이지)**

```dockerfile
# ── dev 스테이지 (docker-compose.yml에서 사용) ───────
FROM node:24-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ── build 스테이지 ──────────────────────────────────
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# ── prod 스테이지 (docker-compose.prod.yml에서 사용) ─
FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

- [ ] **Step 7-10: `frontend/nginx.conf` 작성**

```nginx
server {
  listen 80;
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

- [ ] **Step 7-11: `frontend/src/components/.gitkeep` 생성**

```bash
touch frontend/src/components/.gitkeep
```

- [ ] **Step 7-12: 커밋**

```bash
git add frontend/
git commit \
  -m "feat(frontend): add kiosk web scaffold" \
  -m "- add Vite, React, TypeScript, Tailwind, and router skeleton" \
  -m "- add nginx config for static SPA serving" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 8: Pi-setup 뼈대

**Files:**
- Create: `pi-setup/README.md`
- Create: `pi-setup/kiosk.sh`
- Create: `pi-setup/print-service/print_server.py`
- Create: `pi-setup/print-service/requirements.txt`
- Create: `pi-setup/print-service/print-service.service`

- [ ] **Step 8-1: `pi-setup/README.md` 작성**

```markdown
# Raspberry Pi 키오스크 설정

## 전제 조건
- Raspberry Pi OS (64-bit, Bookworm 이상)
- Python 3.11+
- USB 열전사 프린터 연결

## 설정 순서

1. `kiosk.sh` 에서 `FRONTEND_URL` 을 AWS 운영 URL 로 변경
2. 시작 프로그램에 `kiosk.sh` 등록 (자동 로그인 후 실행)
3. print-service 설치 및 systemd 등록

## Print Service 설치

```bash
cd ~/campus-copilot/pi-setup/print-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

sudo cp print-service.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable print-service
sudo systemctl start print-service
```
```

- [ ] **Step 8-2: `pi-setup/kiosk.sh` 작성**

```bash
#!/bin/bash
# Chromium 키오스크 모드 실행 스크립트

FRONTEND_URL="https://campus-copilot.com"   # 운영 URL로 변경

# 마우스 커서 숨기기
unclutter -idle 0.1 -root &

# Chromium 키오스크 모드 실행
chromium-browser \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --disable-translate \
  --disable-features=TranslateUI \
  --autoplay-policy=no-user-gesture-required \
  --disable-session-crashed-bubble \
  "$FRONTEND_URL"
```

- [ ] **Step 8-3: `pi-setup/print-service/requirements.txt` 작성**

```
python-escpos==3.1
fastapi==0.115.0
uvicorn[standard]==0.32.0
```

- [ ] **Step 8-4: `pi-setup/print-service/print_server.py` 작성**

```python
"""localhost:6310 에서 열전사 프린터 출력 요청을 처리하는 서비스"""

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Campus Copilot Print Service")


@app.post("/print")
def print_receipt(payload: dict):
    data = payload
    question = data.get("question", "")
    answer = data.get("answer", "")
    sources = data.get("sources", [])
    qr_url = data.get("qr_url", "")

    try:
        from escpos.printer import Usb  # type: ignore
        # 프린터 VID/PID는 실제 기기에 맞게 수정 필요
        printer = Usb(0x04B8, 0x0202)  # Epson TM-T20 예시
        printer.set(align="center", bold=True)
        printer.text("Campus Copilot\n")
        printer.set(align="left", bold=False)
        printer.text(f"\n[질문]\n{question}\n")
        printer.text(f"\n[답변]\n{answer}\n")
        if sources:
            printer.text("\n[출처]\n")
            for s in sources:
                printer.text(f"  - {s.get('title', '')}\n")
        if qr_url:
            printer.qr(qr_url, size=6)
        printer.cut()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8-5: `pi-setup/print-service/print-service.service` 작성**

```ini
[Unit]
Description=Campus Copilot Print Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/campus-copilot/pi-setup/print-service
ExecStart=/home/pi/campus-copilot/pi-setup/print-service/.venv/bin/uvicorn print_server:app --host 127.0.0.1 --port 6310
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 8-6: 커밋**

```bash
git add pi-setup/
git commit \
  -m "feat(pi-setup): add kiosk support scaffold" \
  -m "- add Raspberry Pi kiosk bootstrap script and print service skeleton" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## Task 9: 통합 검증 — `docker compose up`

- [ ] **Step 9-1: `.env` 파일 생성**

```bash
cp .env.example .env
```

`.env` 에서 아래 항목 확인 (기본값 그대로 사용 가능):
- `DATABASE_URL=postgresql+asyncpg://campus:campus@postgres:5432/campus_copilot`
- `LLM_PROVIDER=ollama`

- [ ] **Step 9-2: 이미지 빌드**

```bash
docker compose build
```

예상 출력: 빌드 대상인 3개 서비스(`backend`, `worker`, `frontend`)가 모두 성공적으로 완료된다.

- [ ] **Step 9-3: 전체 스택 기동**

```bash
docker compose up -d
```

- [ ] **Step 9-4: 헬스체크**

```bash
docker compose ps
```

예상 출력: 모든 서비스 `STATUS = healthy` 또는 `Up`

```bash
curl http://localhost:8000/health
```

예상 출력: `{"status":"ok"}`

```bash
curl http://localhost:8000/api/v1/categories
```

예상 출력: `[]`

- [ ] **Step 9-5: 브라우저에서 프론트엔드 확인**

`http://localhost:5173` 접속 → "Campus Copilot" 타이틀이 보이면 성공.

- [ ] **Step 9-6: Alembic 마이그레이션 생성 및 적용**

```bash
docker compose exec backend alembic revision --autogenerate -m "initial schema"
docker compose exec backend alembic upgrade head
```

예상 출력: `INFO  [alembic.runtime.migration] Running upgrade  -> <hash>, initial schema`

- [ ] **Step 9-7: 최종 커밋**

```bash
git add .
git commit \
  -m "chore: finalize phase 1 scaffold" \
  -m "- verify compose stack boots and base endpoints respond" \
  -m "- generate initial migration and record scaffold completion" \
  -m "Co-Authored-By: Codex <codex@openai.com>"
```

---

## 자체 검토 (Spec 커버리지)

| 스펙 항목 | 계획 태스크 |
|-----------|-----------|
| 2-tier 구조 (backend + worker) | Task 1 docker-compose.yml |
| PostgreSQL, ChromaDB, Redis | Task 1 docker-compose.yml |
| FastAPI + pydantic-settings | Task 2, 3 |
| SQLAlchemy async + 5개 테이블 | Task 4, 5 |
| Alembic 마이그레이션 | Task 5, 9 |
| APScheduler 크론 | Task 6 |
| React + Vite + Tailwind v4 | Task 7 |
| react-router-dom (/ + /admin) | Task 7 |
| @tanstack/react-query | Task 7 package.json |
| Pi-setup (kiosk.sh + print-service) | Task 8 |
| docker-compose.prod.yml | Task 1 |
| .env 기반 환경 전환 | Task 1 |

## 셀프리뷰 메모

- `docker-compose.prod.yml` 과 `frontend/Dockerfile` 이 참조하던 `nginx.conf` 파일들이 계획에 없어서 생성 단계를 추가했습니다.
- `uv sync` 뒤 실행 파일 경로가 잡히지 않던 Dockerfile 초안을 보정하기 위해 backend/worker Dockerfile 에 `PATH` 설정을 추가했습니다.
- `frontend` 빌드 스테이지는 lockfile 생성 단계가 없으므로 `npm ci` 대신 `npm install` 기준으로 정리했습니다.
- `pi-setup` print-service 는 아키텍처 문서와 맞추기 위해 Flask stub 대신 FastAPI stub 으로 통일했습니다.
- 커밋 예시는 현재 저장소 `AGENTS.md` 규칙에 맞게 Conventional Commits 본문과 `Co-Authored-By` trailer 를 포함하도록 보정했습니다.
