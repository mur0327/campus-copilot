"""Run retrieval evaluation questions against the current local data set.

This script uses the backend retriever directly, so it records top-k retrieval
candidates instead of only user-facing answer sources.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
DEFAULT_QUESTIONS_PATH = REPO_ROOT / "eval" / "questions.csv"
DEFAULT_GOLD_SOURCES_PATH = REPO_ROOT / "eval" / "gold_sources.csv"
DEFAULT_RESULTS_DIR = REPO_ROOT / "eval" / "results"


# CSV 한 줄을 그대로 표현하는 내부 타입이다.
# question_type은 채팅 JSON 계약 필드가 아니라, 평가 데이터셋에서만 사용하는 분류값이다.
@dataclass(frozen=True)
class EvalQuestion:
    id: str
    category: str
    question: str
    question_type: str
    gold_url: str
    gold_title: str
    answerability: str
    needs_procedure: str
    expected_keywords: str
    notes: str


# gold_sources.csv 한 줄을 표현하는 내부 타입이다.
# 질문 하나가 여러 공식 정답 문서를 가질 수 있으므로 questions.csv와 분리해서 읽는다.
@dataclass(frozen=True)
class GoldSource:
    question_id: str
    gold_url: str
    gold_title: str
    relevance: str
    source_scope: str
    page_kind: str
    notes: str


def parse_args() -> argparse.Namespace:
    # 기본값은 현재 저장소의 docker compose가 localhost에 열어 둔 서비스를 사용한다.
    # 컨테이너 내부에서 실행하거나 별도 환경변수를 직접 쓰려면 --no-local-services를 사용한다.
    parser = argparse.ArgumentParser(
        description="Run eval/questions.csv against the local Campus Copilot retrieval data.",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS_PATH,
        help="CSV question dataset path.",
    )
    parser.add_argument(
        "--gold-sources",
        type=Path,
        default=DEFAULT_GOLD_SOURCES_PATH,
        help="CSV gold source dataset path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for JSONL detail and CSV summary outputs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Run only rows with this dataset category label.",
    )
    parser.add_argument(
        "--retrieval-category",
        default=None,
        help="Optional backend document category filter. Defaults to no filter.",
    )
    parser.add_argument(
        "--semantic-top-n",
        type=int,
        default=None,
        help="Override semantic top-n. Defaults to backend settings.",
    )
    parser.add_argument(
        "--bm25-top-n",
        type=int,
        default=None,
        help="Override BM25 top-n. Defaults to backend settings.",
    )
    parser.add_argument(
        "--local-services",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Use localhost service defaults for the repo-level docker compose data "
            "(.data/postgres, .data/chromadb, .data/bm25)."
        ),
    )
    return parser.parse_args()


def configure_runtime_env(*, local_services: bool) -> None:
    """Set import-time backend settings before importing app modules."""

    # backend 설정 객체는 import 시점에 환경변수를 읽는다.
    # 따라서 app.* 모듈을 import하기 전에 로컬 docker compose 기준 값을 먼저 주입한다.
    if local_services:
        os.environ["ENVIRONMENT"] = "production"
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
        )
        os.environ["CHROMA_HOST"] = "localhost"
        os.environ["CHROMA_PORT"] = "8001"
        os.environ["RETRIEVER_BM25_CACHE_DIR"] = str(REPO_ROOT / ".data" / "bm25")

    # backend는 package root가 backend/라서 repo root에서 실행할 때 import path를 보강한다.
    sys.path.insert(0, str(BACKEND_ROOT))


def load_questions(
    path: Path, *, category: str | None, limit: int | None
) -> list[EvalQuestion]:
    # CSV 스키마가 어긋나면 평가 결과가 조용히 틀어지므로 필수 필드는 먼저 검증한다.
    with path.open(newline="", encoding="utf-8") as question_file:
        reader = csv.DictReader(question_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")

        expected_fields = set(EvalQuestion.__dataclass_fields__)
        missing_fields = expected_fields - set(reader.fieldnames)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"{path} is missing required fields: {missing}")

        rows = [
            EvalQuestion(**{field: row.get(field, "") for field in expected_fields})
            for row in reader
        ]

    # 부분 실행용 필터다. 20개 전체를 실행하기 전에 --limit 1 smoke 테스트에 사용한다.
    if category:
        rows = [row for row in rows if row.category == category]
    if limit is not None:
        rows = rows[:limit]
    return rows


def load_gold_sources(path: Path) -> dict[str, list[GoldSource]]:
    # 다중 정답 문서 라벨을 질문 ID별로 묶는다.
    # 파일이 없으면 초기 평가를 막지 않고 빈 라벨로 실행한다.
    if not path.exists():
        return {}

    with path.open(newline="", encoding="utf-8-sig") as gold_file:
        reader = csv.DictReader(gold_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no CSV header")

        expected_fields = set(GoldSource.__dataclass_fields__)
        missing_fields = expected_fields - set(reader.fieldnames)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"{path} is missing required fields: {missing}")

        grouped: dict[str, list[GoldSource]] = {}
        for row in reader:
            gold_source = GoldSource(
                **{field: row.get(field, "") for field in expected_fields}
            )
            grouped.setdefault(gold_source.question_id, []).append(gold_source)
        return grouped


def normalize_url(url: str | None) -> str:
    # URL 비교용 정규화다.
    # fragment와 끝 슬래시 차이는 정답 URL 매칭에서 의미가 작으므로 제거한다.
    if not url:
        return ""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def content_signature(text: str | None) -> str:
    # 학과 미러 문서는 호스트만 다르고 본문이 같으므로, 정답 매칭을 본문 기준으로 한다.
    # 공백을 정규화한 본문 해시를 시그니처로 쓴다.
    if not text:
        return ""
    return hashlib.sha256(" ".join(text.split()).lower().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GoldMatch:
    # 질문별 정답 매칭 기준이다.
    # urls: 정규화한 gold URL 집합(완전 일치 fallback).
    # signatures: gold 문서 chunk들의 본문 시그니처 집합(미러 무관 매칭).
    urls: frozenset[str]
    signatures: frozenset[str]


def first_gold_rank(items: list[dict[str, Any]], match: GoldMatch | None) -> int | None:
    # 정답 문서가 검색 후보에 처음 등장한 순위를 계산한다.
    # 본문 시그니처 일치를 우선하고, URL 완전 일치를 fallback으로 둔다.
    if match is None or (not match.urls and not match.signatures):
        return None

    for item in items:
        if item.get("content_sig") and item["content_sig"] in match.signatures:
            return int(item["rank"])
        if normalize_url(item["url"]) in match.urls:
            return int(item["rank"])
    return None


def gold_rank_in_pool(results: list[Any], match: GoldMatch | None) -> int | None:
    # 후보 풀(semantic/BM25 top-N)에서 gold가 처음 등장한 순위다. 미스 부검용:
    # "풀에 아예 못 들어옴"과 "풀에는 있는데 병합에서 밀림"을 구분할 수 있게 한다.
    if match is None or (not match.urls and not match.signatures):
        return None

    for index, result in enumerate(results, start=1):
        if content_signature(result.content) in match.signatures:
            return index
        if normalize_url(result.url) in match.urls:
            return index
    return None


def diagnose_miss(record: dict[str, Any], *, k: int = 5) -> str | None:
    # answerable 미스의 원인을 단계별로 분류한다(부검 자동화).
    # corpus_missing: gold 문서가 코퍼스에 없음(크롤 커버리지 문제).
    # pool_miss: semantic/BM25 후보 풀 어느 쪽에도 진입 실패(색인 신호 문제).
    # merge_loss: 풀에는 있었지만 병합/부스트 후 최종 top-k에서 탈락(랭킹 문제).
    # ranked_low: 최종 결과에는 있으나 k위 밖.
    rank = record["gold_rank"]
    if rank is not None and rank <= k:
        return None
    if not record["gold_in_corpus"]:
        return "corpus_missing"
    if record["gold_rank_semantic"] is None and record["gold_rank_bm25"] is None:
        return "pool_miss"
    if rank is None:
        return "merge_loss"
    return "ranked_low"


async def build_gold_matches(
    session: Any, gold_sources_by_question: dict[str, list[GoldSource]]
) -> dict[str, GoldMatch]:
    # gold 문서들의 chunk 본문 시그니처를 DB에서 모아 질문별 매칭 기준을 만든다.
    from sqlalchemy import select

    from app.models.document import Document, DocumentChunk

    def hit_urls(sources: list[GoldSource]) -> set[str]:
        return {
            g.gold_url
            for g in sources
            if g.relevance in {"primary", "secondary"} and g.gold_url
        }

    raw_urls = {
        url
        for sources in gold_sources_by_question.values()
        for url in hit_urls(sources)
    }
    url_to_signatures: dict[str, set[str]] = {}
    if raw_urls:
        statement = (
            select(Document.url, DocumentChunk.content)
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .where(Document.url.in_(raw_urls))
        )
        for url, content in (await session.execute(statement)).all():
            url_to_signatures.setdefault(normalize_url(url), set()).add(
                content_signature(content)
            )

    matches: dict[str, GoldMatch] = {}
    for qid, sources in gold_sources_by_question.items():
        urls = {normalize_url(url) for url in hit_urls(sources)}
        signatures: set[str] = set()
        for url in urls:
            signatures |= url_to_signatures.get(url, set())
        matches[qid] = GoldMatch(urls=frozenset(urls), signatures=frozenset(signatures))
    return matches


def compute_metrics(records: list[dict[str, Any]], *, k: int = 5) -> dict[str, Any]:
    # answerable(정답이 코퍼스에 존재) 문항만 분모로 삼는다. insufficient는 별도로 센다.
    answerable = [
        r for r in records if r["answerability"] != "insufficient" and r["has_gold"]
    ]
    n = len(answerable)
    insufficient = sum(1 for r in records if r["answerability"] == "insufficient")
    if n == 0:
        return {"n_answerable": 0, "n_insufficient": insufficient}

    def recalled(rank: int | None) -> bool:
        return rank is not None and rank <= k

    recall = sum(1 for r in answerable if recalled(r["gold_rank"])) / n
    mrr = sum((1.0 / r["gold_rank"]) if r["gold_rank"] else 0.0 for r in answerable) / n
    evidence_recall = (
        sum(1 for r in answerable if recalled(r["gold_rank_evidence"])) / n
    )
    return {
        "n_answerable": n,
        "n_insufficient": insufficient,
        f"recall@{k}": round(recall, 4),
        "mrr": round(mrr, 4),
        f"evidence_recall@{k}": round(evidence_recall, 4),
        "misses": sorted(r["id"] for r in answerable if not recalled(r["gold_rank"])),
        # 미스별 원인 분류. 어느 단계(커버리지/색인/랭킹)를 고쳐야 하는지 바로 보여준다.
        "miss_diagnosis": {
            r["id"]: diagnose_miss(r, k=k)
            for r in sorted(answerable, key=lambda item: item["id"])
            if not recalled(r["gold_rank"])
        },
    }


def now_stamp() -> str:
    # 결과 파일명 충돌을 피하기 위해 UTC timestamp를 붙인다.
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def result_item(result: Any, *, rank: int) -> dict[str, Any]:
    # RetrievalResult 전체 content는 길 수 있으므로 JSONL에는 식별자와 미리보기만 저장한다.
    # 검색 성능 계산에는 rank/url/document_id가 핵심이다.
    return {
        "rank": rank,
        "score": result.score,
        "chunk_id": str(result.chunk_id),
        "document_id": str(result.document_id),
        "title": result.title,
        "url": result.url,
        "menu_path": result.menu_path,
        "category": result.category,
        "source_scope": result.source_scope,
        "page_kind": result.page_kind,
        "chunk_type": result.chunk_type,
        "chunk_index": result.chunk_index,
        "crawled_at": result.crawled_at.isoformat() if result.crawled_at else None,
        "content_preview": " ".join(result.content.split())[:240],
        "content_sig": content_signature(result.content),
    }


def evidence_item(candidate: Any) -> dict[str, Any]:
    # evidence_candidates는 최종 답변 프롬프트에 포함될 수 있는 후보 항목이다.
    # retrieved top-k와 분리해서 저장해야 검색 성능과 출처 품질을 따로 볼 수 있다.
    display = candidate.display_result
    return {
        "source_number": candidate.source_number,
        "overlap": candidate.overlap,
        "score": display.score,
        "title": display.title,
        "url": display.url,
        "menu_path": display.menu_path,
        "category": display.category,
        "document_id": str(display.document_id),
        "chunk_id": str(display.chunk_id),
        "source_scope": display.source_scope,
        "page_kind": display.page_kind,
        "chunk_type": display.chunk_type,
        "chunk_index": display.chunk_index,
        "crawled_at": display.crawled_at.isoformat() if display.crawled_at else None,
        "content_preview": " ".join(display.content.split())[:240],
        "content_sig": content_signature(display.content),
    }


def pipe_join(values: Iterable[str | None]) -> str:
    # CSV 요약 파일에서 여러 URL/제목을 한 칸에 담기 위한 간단한 변환이다.
    # 제목처럼 비어 있을 수 있는 값도 위치가 중요하므로 빈 칸으로 보존한다.
    return "|".join(value or "" for value in values)


async def run() -> None:
    args = parse_args()
    configure_runtime_env(local_services=args.local_services)

    # app.* imports must happen after configure_runtime_env().
    # 아래 객체들은 운영 코드의 retriever와 같은 구현을 재사용한다.
    from app.core.config import settings
    from app.core.db import AsyncSessionLocal, engine
    from app.services.chroma_client import get_chroma_collection
    from app.services.embedding_provider import VoyageEmbedder
    from app.services.retriever import (
        HybridRetriever,
        classify_question_intent,
        filter_evidence_candidates,
    )

    questions = load_questions(args.questions, category=args.category, limit=args.limit)
    gold_sources_by_question = load_gold_sources(args.gold_sources)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    jsonl_path = args.out_dir / f"retrieval-{stamp}.jsonl"
    csv_path = args.out_dir / f"retrieval-{stamp}.csv"

    # LLM은 호출하지 않는다.
    # 이 스크립트의 목적은 현재 .data 기준 retrieval 후보를 수집하는 것이다.
    retriever = HybridRetriever(
        collection=get_chroma_collection(),
        embedder=VoyageEmbedder(
            model_name=settings.embedding_model,
            input_type="query",
            api_key=settings.voyage_api_key,
        ),
        semantic_weight=settings.retriever_semantic_weight,
        bm25_weight=settings.retriever_bm25_weight,
        final_top_k=settings.retriever_final_top_k,
        bm25_cache_dir=settings.retriever_bm25_cache_dir,
    )

    summary_rows: list[dict[str, Any]] = []
    metric_records: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as jsonl_file:
        # 같은 세션을 재사용해 20개 질문을 순차 실행한다.
        # 병렬화하면 외부 embedding API rate limit과 DB/Chroma 상태 추적이 복잡해져 초기 평가에는 불리하다.
        async with AsyncSessionLocal() as session:
            gold_matches = await build_gold_matches(session, gold_sources_by_question)
            semantic_top_n = args.semantic_top_n or settings.retriever_semantic_top_n
            bm25_top_n = args.bm25_top_n or settings.retriever_bm25_top_n
            for question in questions:
                response = await retriever.retrieve_with_status(
                    session,
                    question=question.question,
                    category=args.retrieval_category,
                    semantic_top_n=semantic_top_n,
                    bm25_top_n=bm25_top_n,
                )

                # 부검용 풀 진단: gold가 각 후보 풀에 들어왔는지 기록한다.
                # 병합 전 순위가 있어야 미스 원인을 색인/병합/랭킹 단계로 가를 수 있다.
                gold_match = gold_matches.get(question.id)
                try:
                    semantic_pool = await retriever.search_chroma(
                        session,
                        question.question,
                        args.retrieval_category,
                        semantic_top_n,
                    )
                except Exception:
                    # semantic 열화 시에도 평가는 계속한다(상태는 retrieval_status에 이미 기록).
                    semantic_pool = []
                bm25_pool = (
                    await retriever.ensure_bm25_index(session, args.retrieval_category)
                ).search(question.question, bm25_top_n)
                gold_rank_semantic = gold_rank_in_pool(semantic_pool, gold_match)
                gold_rank_bm25 = gold_rank_in_pool(bm25_pool, gold_match)

                # retrieved: retriever가 반환한 최종 top-k 후보 항목이다.
                # evidence_candidates: 답변 생성 프롬프트에 포함되도록 필터링/그룹핑한 후보 항목이다.
                evidence_candidates = filter_evidence_candidates(
                    question.question, response.results
                )
                retrieved = [
                    result_item(result, rank=index + 1)
                    for index, result in enumerate(response.results)
                ]
                evidence = [
                    evidence_item(candidate) for candidate in evidence_candidates
                ]
                gold_sources = gold_sources_by_question.get(question.id, [])
                top_gold_rank = first_gold_rank(retrieved, gold_match)
                evidence_with_rank = [
                    {"rank": index + 1, **item} for index, item in enumerate(evidence)
                ]
                evidence_gold_rank = first_gold_rank(evidence_with_rank, gold_match)
                metric_records.append(
                    {
                        "id": question.id,
                        "answerability": question.answerability,
                        "has_gold": bool(
                            gold_match and (gold_match.urls or gold_match.signatures)
                        ),
                        # 시그니처가 비면 gold 문서가 코퍼스에 없다(라벨만 존재).
                        "gold_in_corpus": bool(gold_match and gold_match.signatures),
                        "gold_rank": top_gold_rank,
                        "gold_rank_evidence": evidence_gold_rank,
                        "gold_rank_semantic": gold_rank_semantic,
                        "gold_rank_bm25": gold_rank_bm25,
                    }
                )
                payload = {
                    "id": question.id,
                    "category": question.category,
                    "question": question.question,
                    "dataset_question_type": question.question_type,
                    "classified_intent": classify_question_intent(question.question),
                    "gold_url": question.gold_url,
                    "gold_title": question.gold_title,
                    "gold_sources": [
                        gold_source.__dict__ for gold_source in gold_sources
                    ],
                    "gold_hit_top": top_gold_rank is not None,
                    "gold_hit_top_rank": top_gold_rank,
                    "gold_hit_evidence": evidence_gold_rank is not None,
                    "gold_hit_evidence_rank": evidence_gold_rank,
                    "gold_in_corpus": bool(gold_match and gold_match.signatures),
                    "gold_rank_semantic_pool": gold_rank_semantic,
                    "gold_rank_bm25_pool": gold_rank_bm25,
                    "expected_answerability": question.answerability,
                    "needs_procedure": question.needs_procedure,
                    "expected_keywords": question.expected_keywords,
                    "retrieval_status": response.status.model_dump(),
                    "retrieved": retrieved,
                    "evidence_candidates": evidence,
                }

                # JSONL은 사람이 나중에 한 줄씩 보거나, 스크립트로 재채점하기 좋다.
                jsonl_file.write(json.dumps(payload, ensure_ascii=False) + "\n")

                # CSV는 빠른 검토용이다. 긴 content는 제외하고 URL/제목 위주로 한 행에 요약한다.
                summary_rows.append(
                    {
                        "id": question.id,
                        "category": question.category,
                        "question": question.question,
                        "dataset_question_type": question.question_type,
                        "classified_intent": payload["classified_intent"],
                        "retrieval_mode": response.status.mode,
                        "degraded": response.status.degraded,
                        "semantic_available": response.status.semantic_available,
                        "bm25_available": response.status.bm25_available,
                        "semantic_error": response.status.semantic_error or "",
                        "bm25_error": response.status.bm25_error or "",
                        "retrieved_count": len(retrieved),
                        "evidence_count": len(evidence),
                        "gold_urls": pipe_join(gold.gold_url for gold in gold_sources),
                        "gold_relevance": pipe_join(
                            gold.relevance for gold in gold_sources
                        ),
                        "gold_source_scopes": pipe_join(
                            gold.source_scope for gold in gold_sources
                        ),
                        "gold_page_kinds": pipe_join(
                            gold.page_kind for gold in gold_sources
                        ),
                        "gold_hit_top": top_gold_rank is not None,
                        "gold_hit_top_rank": top_gold_rank or "",
                        "gold_hit_evidence": evidence_gold_rank is not None,
                        "gold_hit_evidence_rank": evidence_gold_rank or "",
                        "gold_in_corpus": bool(gold_match and gold_match.signatures),
                        "gold_rank_semantic_pool": gold_rank_semantic or "",
                        "gold_rank_bm25_pool": gold_rank_bm25 or "",
                        "top_urls": pipe_join(item["url"] for item in retrieved),
                        "evidence_urls": pipe_join(item["url"] for item in evidence),
                        "top_titles": pipe_join(item["title"] for item in retrieved),
                        "top_source_scopes": pipe_join(
                            item["source_scope"] for item in retrieved
                        ),
                        "top_page_kinds": pipe_join(
                            item["page_kind"] for item in retrieved
                        ),
                        "evidence_source_scopes": pipe_join(
                            item["source_scope"] for item in evidence
                        ),
                        "evidence_page_kinds": pipe_join(
                            item["page_kind"] for item in evidence
                        ),
                    }
                )

    if summary_rows:
        # 질문이 0개면 파일 헤더를 만들 근거가 없으므로 CSV 생성을 건너뛴다.
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)

    await engine.dispose()

    # answerable 문항 기준 집계 지표를 계산해 별도 파일과 콘솔에 남긴다.
    metrics = compute_metrics(metric_records)
    metrics_path = args.out_dir / f"retrieval-{stamp}-metrics.json"
    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, ensure_ascii=False, indent=2)

    # 출력 경로만 알린다. API key나 환경변수 값은 출력하지 않는다.
    print(f"questions: {len(questions)}")
    print(f"jsonl: {jsonl_path.relative_to(REPO_ROOT)}")
    print(f"csv: {csv_path.relative_to(REPO_ROOT)}")
    print(f"metrics: {metrics_path.relative_to(REPO_ROOT)}")
    for key, value in metrics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(run())
