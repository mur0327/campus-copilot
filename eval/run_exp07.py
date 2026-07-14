"""Run the frozen EXP-07 production-path final-response evaluation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.check_v4_invariants import (  # noqa: E402
    CHUNK_FIELDS,
    PAGE_REQUIRED_FIELDS,
    QUESTION_FIELDS,
    collect_top5_pairs,
    find_invariant_failures,
    load_actual_chunks,
    load_csv,
    load_question_ids,
)
from eval.exp07_common import (  # noqa: E402
    RUN_SCHEMA_VERSION,
    canonical_json_hash,
    sha256_file,
    sha256_text,
    write_private_text,
)
from eval.exp07_corpus import corpus_fingerprint, fingerprints_match  # noqa: E402
from eval.run_questions import (  # noqa: E402
    DEFAULT_QUESTIONS_PATH,
    configure_runtime_env,
    content_signature,
    load_questions,
)

DEFAULT_RESULTS_DIR = REPO_ROOT / "eval" / "results"
QREL_MANIFEST_PATH = REPO_ROOT / "eval" / "qrel-v4-manifest.sha256"
QREL_PATH = REPO_ROOT / "eval" / "qrel-v4-adjudicated.json"
RUBRIC_PATH = REPO_ROOT / "eval" / "exp07-answer-rubric.md"
PROMPT_PATH = BACKEND_ROOT / "app" / "prompts" / "chat_answer.md"
GOLD_PAGES_PATH = REPO_ROOT / "eval" / "gold_pages_v4.csv"
GOLD_EVIDENCE_PATH = REPO_ROOT / "eval" / "gold_evidence_v4.csv"
QUESTION_JUDGMENTS_PATH = REPO_ROOT / "eval" / "question_judgments_v4.csv"

DEFAULT_SEED = 20260715
DEFAULT_ROUNDS = 3
SAFETY_FACTOR = 0.8
MAX_EXECUTION_ATTEMPTS = 2
SYSTEMIC_FAILURE_THRESHOLD = 3
KOREA_TZ = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run three cache-free production-path EXP-07 rounds sequentially.",
    )
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Smoke-test only; canonical run uses all 50.",
    )
    parser.add_argument(
        "--llm-rpm-limit",
        type=float,
        required=True,
        help="Account LLM RPM ceiling. The runner uses 80 percent of this value.",
    )
    parser.add_argument(
        "--embedding-rpm-limit",
        type=float,
        required=True,
        help="Account embedding RPM ceiling. The runner uses 80 percent of this value.",
    )
    parser.add_argument(
        "--local-services",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the repository Docker Compose services on localhost.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print the shuffled order without API calls.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.rounds < 1:
        raise ValueError("--rounds must be positive")
    if args.llm_rpm_limit <= 0 or args.embedding_rpm_limit <= 0:
        raise ValueError("RPM limits must be positive")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")


class AsyncStartRateLimiter:
    def __init__(
        self,
        rpm_limit: float,
        *,
        safety_factor: float = SAFETY_FACTOR,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self.effective_rpm = rpm_limit * safety_factor
        self.minimum_interval = 60.0 / self.effective_rpm
        self.clock = clock
        self.sleep = sleep
        self.next_start = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> float:
        async with self._lock:
            now = self.clock()
            delay = max(0.0, self.next_start - now)
            if delay:
                await self.sleep(delay)
            started = self.clock()
            self.next_start = max(self.next_start, started) + self.minimum_interval
            return delay

    def defer(self, seconds: float | None) -> None:
        if seconds is None or seconds <= 0:
            return
        self.next_start = max(self.next_start, self.clock() + seconds)


class SyncStartRateLimiter:
    def __init__(
        self,
        rpm_limit: float,
        *,
        safety_factor: float = SAFETY_FACTOR,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.effective_rpm = rpm_limit * safety_factor
        self.minimum_interval = 60.0 / self.effective_rpm
        self.clock = clock
        self.sleep = sleep
        self.next_start = 0.0

    def wait(self) -> float:
        now = self.clock()
        delay = max(0.0, self.next_start - now)
        if delay:
            self.sleep(delay)
        started = self.clock()
        self.next_start = max(self.next_start, started) + self.minimum_interval
        return delay

    def defer(self, seconds: float | None) -> None:
        if seconds is None or seconds <= 0:
            return
        self.next_start = max(self.next_start, self.clock() + seconds)


class RecordingLLMProvider:
    def __init__(
        self,
        provider: Any,
        limiter: AsyncStartRateLimiter,
        calls: list[dict[str, Any]] | None = None,
    ) -> None:
        self.provider = provider
        self.limiter = limiter
        self.calls = calls if calls is not None else []

    async def generate(self, messages: list[Any]) -> str:
        waited = await self.limiter.wait()
        started_at = utc_now()
        kind = (
            "json_repair"
            if messages and getattr(messages[-1], "role", "") == "user"
            else "initial"
        )
        call: dict[str, Any] = {
            "kind": kind,
            "started_at": started_at,
            "waited_seconds": round(waited, 6),
            "message_count": len(messages),
            "messages_sha256": canonical_json_hash(
                [
                    {"role": message.role, "content": message.content}
                    for message in messages
                ]
            ),
        }
        try:
            raw_output = await self.provider.generate(messages)
        except Exception as exc:
            retry_after = retry_after_seconds(exc)
            self.limiter.defer(retry_after)
            call.update(
                {
                    "completed_at": utc_now(),
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": safe_error_message(exc),
                    "retry_after_seconds": retry_after,
                }
            )
            self.calls.append(call)
            raise
        call.update(
            {
                "completed_at": utc_now(),
                "status": "success",
                "raw_output": raw_output,
                "raw_output_sha256": sha256_text(raw_output),
            }
        )
        self.calls.append(call)
        return raw_output

    async def aclose(self) -> None:
        close = getattr(self.provider, "aclose", None)
        if close is not None:
            await close()


class RecordingVoyageClient:
    def __init__(self, client: Any, limiter: SyncStartRateLimiter) -> None:
        self.client = client
        self.limiter = limiter
        self.calls: list[dict[str, Any]] = []

    def embed(self, texts: list[str], *, model: str, input_type: str):
        waited = self.limiter.wait()
        call: dict[str, Any] = {
            "started_at": utc_now(),
            "waited_seconds": round(waited, 6),
            "text_count": len(texts),
            "texts_sha256": canonical_json_hash(texts),
            "model": model,
            "input_type": input_type,
        }
        try:
            response = self.client.embed(texts, model=model, input_type=input_type)
        except Exception as exc:
            retry_after = retry_after_seconds(exc)
            self.limiter.defer(retry_after)
            call.update(
                {
                    "completed_at": utc_now(),
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_message": safe_error_message(exc),
                    "retry_after_seconds": retry_after,
                }
            )
            self.calls.append(call)
            raise
        call.update({"completed_at": utc_now(), "status": "success"})
        self.calls.append(call)
        return response


def retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or getattr(exc, "headers", None)
    if headers is None:
        return None
    value = headers.get("Retry-After") or headers.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(str(value))
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


def safe_error_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return message[:500]


def exception_status_code(exc: Exception) -> int | None:
    for value in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
        getattr(exc, "code", None),
    ):
        if isinstance(value, int):
            return value
        enum_value = getattr(value, "value", None)
        if isinstance(enum_value, int):
            return enum_value
    return None


def is_retryable_execution_error(exc: Exception) -> bool:
    status_code = exception_status_code(exc)
    if status_code is not None:
        return status_code == 429 or status_code >= 500
    name = type(exc).__name__.lower()
    return any(
        marker in name
        for marker in (
            "timeout",
            "connection",
            "network",
            "ratelimit",
            "resourceexhausted",
            "serviceunavailable",
            "transport",
            "temporar",
        )
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def runtime_package_versions() -> dict[str, str]:
    packages = ("google-genai", "voyageai", "chromadb", "asyncpg")
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def load_qrel_expected_behaviors(path: Path = QREL_PATH) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(row["question_id"]): str(row["expected_behavior"])
        for row in payload.get("questions", [])
    }


def asyncpg_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def assert_qrel_invariants(dsn: str) -> None:
    pages = load_csv(GOLD_PAGES_PATH, PAGE_REQUIRED_FIELDS)
    evidence = load_csv(GOLD_EVIDENCE_PATH, CHUNK_FIELDS)
    questions = load_csv(QUESTION_JUDGMENTS_PATH, QUESTION_FIELDS)
    top5_pages, top5_chunks = collect_top5_pairs()
    actual_chunks = await load_actual_chunks(evidence, dsn=dsn)
    failures = find_invariant_failures(
        pages,
        evidence,
        questions,
        top5_page_pairs=top5_pages,
        top5_chunk_pairs=top5_chunks,
        actual_chunks=actual_chunks,
        expected_question_ids=load_question_ids(),
    )
    if failures:
        rendered = "\n".join(f"- {failure}" for failure in failures)
        raise ValueError(f"qrel v4 invariant failed:\n{rendered}")


def result_item(result: Any) -> dict[str, Any]:
    return {
        "chunk_id": str(result.chunk_id),
        "document_id": str(result.document_id),
        "content": result.content,
        "content_hash": content_signature(result.content),
        "chunk_type": result.chunk_type,
        "chunk_index": result.chunk_index,
        "score": result.score,
        "relevance": getattr(result.relevance, "value", result.relevance),
        "title": result.title,
        "url": result.url,
        "menu_path": result.menu_path,
        "category": result.category,
        "source_scope": getattr(result.source_scope, "value", result.source_scope),
        "page_kind": getattr(result.page_kind, "value", result.page_kind),
        "crawled_at": result.crawled_at.isoformat() if result.crawled_at else None,
        "meta": result.meta,
    }


def evidence_item(candidate: Any) -> dict[str, Any]:
    return {
        "source_number": candidate.source_number,
        "overlap": candidate.overlap,
        "display_result": result_item(candidate.display_result),
        "context_results": [
            result_item(result) for result in candidate.context_results
        ],
    }


def call_slice(calls: list[dict[str, Any]], start: int) -> list[dict[str, Any]]:
    return [dict(call) for call in calls[start:]]


async def run_attempt(
    *,
    question: Any,
    retriever: Any,
    llm_limiter: AsyncStartRateLimiter,
    llm_calls: list[dict[str, Any]],
    embedding_client: RecordingVoyageClient,
    session: Any,
    settings: Any,
) -> dict[str, Any]:
    from app.schemas.chat import RetrievalStatusPayload
    from app.services.conflict import load_conflict_warning
    from app.services.rag import (
        assemble_chat_response,
        generate_answer_draft,
        insufficient_response,
    )
    from app.services.retriever import filter_evidence_candidates

    embedding_start = len(embedding_client.calls)
    llm_start = len(llm_calls)
    started_at = utc_now()
    try:
        retrieval = await retriever.retrieve_with_status(
            session,
            question=question.question,
            category=None,
            semantic_top_n=settings.retriever_semantic_top_n,
            bm25_top_n=settings.retriever_bm25_top_n,
        )
        conflict_warning = await load_conflict_warning(
            session,
            [result.chunk_id for result in retrieval.results],
        )
        evidence_candidates = filter_evidence_candidates(
            question.question, retrieval.results
        )
        retrieval_status = RetrievalStatusPayload.model_validate(
            retrieval.status.model_dump()
        )
        if evidence_candidates:
            llm_provider = build_provider(
                settings,
                llm_limiter,
                calls=llm_calls,
            )
            try:
                draft = await generate_answer_draft(
                    question=question.question,
                    evidence_candidates=evidence_candidates,
                    conflict_warning=conflict_warning,
                    provider=llm_provider,
                )
            finally:
                with suppress(Exception):
                    await llm_provider.aclose()
            response = assemble_chat_response(
                draft=draft,
                evidence_candidates=evidence_candidates,
                conflict_warning=conflict_warning,
                stale_days=settings.freshness_stale_days,
                retrieval_status=retrieval_status,
            )
        else:
            response = insufficient_response(
                conflict_warning=conflict_warning,
                retrieval_status=retrieval_status,
            )
        return {
            "started_at": started_at,
            "completed_at": utc_now(),
            "status": "success",
            "retrieval_status": retrieval.status.model_dump(mode="json"),
            "retrieved": [result_item(result) for result in retrieval.results],
            "evidence_candidates": [
                evidence_item(candidate) for candidate in evidence_candidates
            ],
            "conflict_warning": conflict_warning.model_dump(mode="json"),
            "embedding_calls": call_slice(embedding_client.calls, embedding_start),
            "llm_calls": call_slice(llm_calls, llm_start),
            "final_response": response.model_dump(mode="json"),
        }
    except Exception as exc:
        return {
            "started_at": started_at,
            "completed_at": utc_now(),
            "status": "error",
            "error_type": type(exc).__name__,
            "error_message": safe_error_message(exc),
            "retryable": is_retryable_execution_error(exc),
            "retry_after_seconds": retry_after_seconds(exc),
            "embedding_calls": call_slice(embedding_client.calls, embedding_start),
            "llm_calls": call_slice(llm_calls, llm_start),
        }


async def run_question(
    *,
    run_id: str,
    round_number: int,
    ordinal: int,
    question: Any,
    retriever: Any,
    llm_limiter: AsyncStartRateLimiter,
    llm_calls: list[dict[str, Any]],
    embedding_client: RecordingVoyageClient,
    session: Any,
    settings: Any,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for _attempt_number in range(1, MAX_EXECUTION_ATTEMPTS + 1):
        attempt = await run_attempt(
            question=question,
            retriever=retriever,
            llm_limiter=llm_limiter,
            llm_calls=llm_calls,
            embedding_client=embedding_client,
            session=session,
            settings=settings,
        )
        attempts.append(attempt)
        if attempt["status"] == "success":
            return {
                "record_type": "response",
                "schema_version": RUN_SCHEMA_VERSION,
                "run_id": run_id,
                "round": round_number,
                "ordinal": ordinal,
                "question_id": question.id,
                "question": question.question,
                "dataset_category": question.category,
                "dataset_question_type": question.question_type,
                "status": "success",
                "selected_attempt": len(attempts),
                "attempts": attempts,
                "final_response": attempt["final_response"],
            }
        if not attempt.get("retryable"):
            break
        retry_after = attempt.get("retry_after_seconds")
        llm_limiter.defer(retry_after)
        embedding_client.limiter.defer(retry_after)
    return {
        "record_type": "response",
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "round": round_number,
        "ordinal": ordinal,
        "question_id": question.id,
        "question": question.question,
        "dataset_category": question.category,
        "dataset_question_type": question.question_type,
        "status": "system_error",
        "selected_attempt": None,
        "attempts": attempts,
        "final_response": None,
    }


def write_jsonl_record(output_file: Any, record: dict[str, Any]) -> None:
    output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    output_file.flush()
    os.fsync(output_file.fileno())


def run_metadata(
    *,
    run_id: str,
    args: argparse.Namespace,
    settings: Any,
    question_ids: list[str],
) -> dict[str, Any]:
    return {
        "record_type": "run_metadata",
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": utc_now(),
        "git_commit": git_head(),
        "questions_sha256": sha256_file(args.questions),
        "qrel_sha256": sha256_file(QREL_PATH),
        "qrel_manifest_sha256": sha256_file(QREL_MANIFEST_PATH),
        "rubric_sha256": sha256_file(RUBRIC_PATH),
        "prompt_sha256": sha256_file(PROMPT_PATH),
        "provider": settings.llm_provider,
        "llm_model": settings.gemini_model
        if settings.llm_provider == "gemini"
        else settings.llama_cpp_model,
        "embedding_model": settings.embedding_model,
        "runtime_packages": runtime_package_versions(),
        "sampling_parameters": "provider_defaults_unspecified",
        "retriever": {
            "mode": "hybrid",
            "category": None,
            "semantic_top_n": settings.retriever_semantic_top_n,
            "bm25_top_n": settings.retriever_bm25_top_n,
            "final_top_k": settings.retriever_final_top_k,
            "semantic_weight": settings.retriever_semantic_weight,
            "bm25_weight": settings.retriever_bm25_weight,
            "best_bets_enabled": settings.retriever_best_bets_enabled,
        },
        "seed": args.seed,
        "rounds": args.rounds,
        "question_order": question_ids,
        "question_count": len(question_ids),
        "llm_rpm_limit": args.llm_rpm_limit,
        "embedding_rpm_limit": args.embedding_rpm_limit,
        "safety_factor": SAFETY_FACTOR,
        "cache_bypassed": True,
        "canonical_run": args.limit is None
        and len(question_ids) == 50
        and args.rounds == 3,
        "retry_policy": {
            "evaluation_level_max_retries": 1,
            "evaluation_level_scope": "retryable_infrastructure_errors_only",
            "production_json_repair_preserved": True,
            "production_embedding_retry_policy": "VoyageEmbedder: two retries; voyage client: zero retries",
            "gemini_sdk_retry_policy": "locked SDK default",
        },
        "timezone": "Asia/Seoul",
    }


def build_provider(
    settings: Any,
    limiter: AsyncStartRateLimiter,
    *,
    calls: list[dict[str, Any]] | None = None,
) -> RecordingLLMProvider:
    from app.services.llm import (
        GeminiProvider,
        LlamaCppProvider,
        validate_provider_settings,
    )

    validate_provider_settings(
        settings.llm_provider,
        llama_cpp_base_url=settings.llama_cpp_base_url,
        llama_cpp_model=settings.llama_cpp_model,
        gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
    )
    if settings.llm_provider == "gemini":
        provider = GeminiProvider(
            api_key=settings.gemini_api_key, model=settings.gemini_model
        )
        assert_gemini_transport_retry_disabled(provider)
    else:
        provider = LlamaCppProvider(
            base_url=settings.llama_cpp_base_url, model=settings.llama_cpp_model
        )
    return RecordingLLMProvider(provider, limiter, calls)


def assert_gemini_transport_retry_disabled(provider: Any) -> None:
    api_client = getattr(getattr(provider, "client", None), "_api_client", None)
    http_options = getattr(api_client, "_http_options", None)
    if http_options is None or getattr(http_options, "retry_options", None) is not None:
        raise RuntimeError(
            "the locked google-genai transport retry policy is not observable as disabled"
        )


def build_retriever(settings: Any, embedding_client: RecordingVoyageClient):
    from app.services.chroma_client import get_chroma_collection
    from app.services.embedding_provider import VoyageEmbedder
    from app.services.retriever import HybridRetriever

    embedder = VoyageEmbedder(
        model_name=settings.embedding_model,
        input_type="query",
        api_key=settings.voyage_api_key,
        require_api_key=True,
        client_factory=lambda: embedding_client,
    )
    collection = get_chroma_collection()
    retriever = HybridRetriever(
        collection=collection,
        embedder=embedder,
        semantic_weight=settings.retriever_semantic_weight,
        bm25_weight=settings.retriever_bm25_weight,
        final_top_k=settings.retriever_final_top_k,
        bm25_cache_dir=settings.retriever_bm25_cache_dir,
        best_bets_enabled=settings.retriever_best_bets_enabled,
    )
    return retriever, collection


def build_embedding_client(
    settings: Any, limiter: SyncStartRateLimiter
) -> RecordingVoyageClient:
    if not settings.voyage_api_key.strip():
        raise ValueError("VOYAGE_API_KEY is required")
    import voyageai

    return RecordingVoyageClient(
        voyageai.Client(api_key=settings.voyage_api_key, max_retries=0), limiter
    )


async def execute(args: argparse.Namespace) -> Path | None:
    validate_args(args)
    configure_runtime_env(local_services=args.local_services)
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    from app.core.config import settings
    from app.core.db import AsyncSessionLocal, engine

    runtime_dsn = asyncpg_dsn(settings.database_url)
    await assert_qrel_invariants(runtime_dsn)
    questions = load_questions(args.questions, category=None, limit=args.limit)
    expected = load_qrel_expected_behaviors()
    missing = sorted({question.id for question in questions} - set(expected))
    if missing:
        raise ValueError(f"qrel expected behavior is missing: {', '.join(missing)}")

    shuffled = list(questions)
    random.Random(args.seed).shuffle(shuffled)
    question_ids = [question.id for question in shuffled]
    if args.dry_run:
        print(
            f"questions: {len(question_ids)}, rounds: {args.rounds}, seed: {args.seed}"
        )
        print("order: " + ",".join(question_ids))
        await engine.dispose()
        return None

    llm_limiter = AsyncStartRateLimiter(args.llm_rpm_limit)
    embedding_limiter = SyncStartRateLimiter(args.embedding_rpm_limit)
    embedding_client = build_embedding_client(settings, embedding_limiter)
    retriever, collection = build_retriever(settings, embedding_client)
    llm_calls: list[dict[str, Any]] = []
    preflight_provider = build_provider(settings, llm_limiter)
    with suppress(Exception):
        await preflight_provider.aclose()

    run_id = datetime.now(UTC).strftime("exp07-%Y%m%dT%H%M%SZ")
    run_dir = args.out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    run_dir.chmod(0o700)
    raw_path = run_dir / "raw.jsonl"
    summary_path = run_dir / "run.json"
    before_path = run_dir / "corpus-before.json"
    after_path = run_dir / "corpus-after.json"

    try:
        before = await corpus_fingerprint(
            dsn=runtime_dsn,
            collection=collection,
            bm25_cache_dir=Path(settings.retriever_bm25_cache_dir),
        )
    except BaseException:
        await engine.dispose()
        raise
    write_private_text(
        before_path,
        json.dumps(before, ensure_ascii=False, indent=2) + "\n",
    )

    metadata = run_metadata(
        run_id=run_id, args=args, settings=settings, question_ids=question_ids
    )
    started_date = datetime.now(KOREA_TZ).date()
    completed_records = 0
    system_error_count = 0
    consecutive_failures = 0
    status = "completed"
    abort_reason: str | None = None
    raw_descriptor = os.open(
        raw_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    raw_file = os.fdopen(raw_descriptor, "w", encoding="utf-8")
    caught: BaseException | None = None
    finalization_errors: list[str] = []
    corpus_unchanged: bool | None = None
    try:
        write_jsonl_record(raw_file, metadata)
        async with AsyncSessionLocal() as session:
            for round_number in range(1, args.rounds + 1):
                for ordinal, question in enumerate(shuffled, start=1):
                    record = await run_question(
                        run_id=run_id,
                        round_number=round_number,
                        ordinal=ordinal,
                        question=question,
                        retriever=retriever,
                        llm_limiter=llm_limiter,
                        llm_calls=llm_calls,
                        embedding_client=embedding_client,
                        session=session,
                        settings=settings,
                    )
                    write_jsonl_record(raw_file, record)
                    completed_records += 1
                    if record["status"] == "system_error":
                        system_error_count += 1
                        consecutive_failures += 1
                    else:
                        consecutive_failures = 0
                    print(
                        f"round {round_number}/{args.rounds} {ordinal}/{len(shuffled)} "
                        f"{question.id}: {record['status']}",
                        flush=True,
                    )
                    if consecutive_failures >= SYSTEMIC_FAILURE_THRESHOLD:
                        status = "aborted"
                        abort_reason = "three_consecutive_system_errors"
                        break
                    if datetime.now(KOREA_TZ).date() != started_date:
                        status = "aborted"
                        abort_reason = "date_rollover"
                        break
                if status == "aborted":
                    break
    except BaseException as exc:
        status = "aborted"
        abort_reason = abort_reason or "unhandled_interruption"
        caught = exc
    finally:
        raw_file.close()
        try:
            after = await corpus_fingerprint(
                dsn=runtime_dsn,
                collection=collection,
                bm25_cache_dir=Path(settings.retriever_bm25_cache_dir),
            )
            write_private_text(
                after_path,
                json.dumps(after, ensure_ascii=False, indent=2) + "\n",
            )
            corpus_unchanged = fingerprints_match(before, after)
        except Exception as exc:
            finalization_errors.append(f"corpus_after:{type(exc).__name__}")
        if corpus_unchanged is not True and status == "completed":
            status = "invalid"
            abort_reason = (
                "corpus_fingerprint_changed"
                if corpus_unchanged is False
                else "corpus_fingerprint_unavailable"
            )
        try:
            await engine.dispose()
        except Exception as exc:
            finalization_errors.append(f"engine_dispose:{type(exc).__name__}")
        if finalization_errors and status == "completed":
            status = "invalid"
            abort_reason = "finalization_error"
        summary = {
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "status": status,
            "abort_reason": abort_reason,
            "started_date": started_date.isoformat(),
            "completed_at": utc_now(),
            "completed_response_records": completed_records,
            "planned_response_records": len(shuffled) * args.rounds,
            "system_error_count": system_error_count,
            "llm_call_count": len(llm_calls),
            "llm_json_repair_count": sum(
                call["kind"] == "json_repair" for call in llm_calls
            ),
            "embedding_call_count": len(embedding_client.calls),
            "corpus_unchanged": corpus_unchanged,
            "finalization_errors": finalization_errors,
            "raw_file": raw_path.name,
            "raw_sha256": sha256_file(raw_path),
            "raw_size": raw_path.stat().st_size,
            "metadata": metadata,
        }
        write_private_text(
            summary_path,
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        )

    if caught is not None:
        raise caught.with_traceback(caught.__traceback__)
    if finalization_errors:
        raise RuntimeError(
            "EXP-07 finalization failed: " + ", ".join(finalization_errors)
        )

    print(f"run: {run_dir.relative_to(REPO_ROOT)}")
    print(f"status: {status}")
    return run_dir


def main() -> None:
    args = parse_args()
    asyncio.run(execute(args))


if __name__ == "__main__":
    main()
