"""answerable vs insufficient 분리 가능성 분석 (EXP-03 재현 도구).

질문 50개 각각에 검색을 1회 돌려 최고 매치의 세 신호를 answerability 라벨과
교차하고, 신호별 최적 단일 문턱 정확도를 산출한다.

- best_sem: 의미 검색 top-1의 원 유사도(1/(1+distance)) — 정규화·융합 이전 절대값.
- best_rel: 병합 후 최고 relevance(가중합 정규화) — evidence 게이트가 실제로 보는 값.
- best_ovl: 최고 키워드 겹침 — 게이트 overlap fallback이 보는 값.

원본 스크립트(scratchpad/abstain_sep.py)는 세션 임시 디렉터리에 있어 유실됐고,
docs/paper/06-experiment-log.md EXP-03의 방법 서술로 2026-07-12에 복원했다.
EXP-03 수치는 2026-07-05 코퍼스 기준이므로 재실행 값은 다를 수 있다.

기본값은 순수 검색(--no-best-bets 상태)이다. best bets는 큐레이션 질문의
relevance를 1.0으로 고정해 분리 분석을 오염시키므로 EXP-03과 같이 끈다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_questions import (  # noqa: E402
    DEFAULT_QUESTIONS_PATH,
    DEFAULT_RESULTS_DIR,
    EvalQuestion,
    configure_runtime_env,
    load_questions,
    now_stamp,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross answerability labels with retrieval score signals (EXP-03).",
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=DEFAULT_QUESTIONS_PATH,
        help="CSV question dataset path.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory for the JSON analysis output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions (smoke test).",
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
        help="Use localhost service defaults for the repo-level docker compose data.",
    )
    parser.add_argument(
        "--best-bets",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Include the curated best-bets pin layer. EXP-03 measured pure "
            "retrieval signals, so this defaults to off."
        ),
    )
    return parser.parse_args()


def best_single_threshold(
    values: list[float], is_answerable: list[bool]
) -> dict[str, Any]:
    # 단일 문턱 규칙: value >= t 이면 answerable로 판정(답변), 미만이면 거절.
    # 후보 문턱은 관측값 전체와 "전부 거절" 상한 하나다. 동점이면 낮은 문턱을 취해
    # answerable 유지(과잉거절 회피)를 우선한다.
    candidates = sorted(set(values)) + [max(values) + 1e-9]
    best: dict[str, Any] | None = None
    total = len(values)
    for threshold in candidates:
        correct = sum(
            (value >= threshold) == label
            for value, label in zip(values, is_answerable, strict=True)
        )
        accuracy = correct / total
        if best is None or accuracy > best["accuracy"]:
            answerable_kept = sum(
                value >= threshold
                for value, label in zip(values, is_answerable, strict=True)
                if label
            )
            insufficient_rejected = sum(
                value < threshold
                for value, label in zip(values, is_answerable, strict=True)
                if not label
            )
            best = {
                "threshold": round(threshold, 6),
                "accuracy": round(accuracy, 4),
                "answerable_kept": answerable_kept,
                "insufficient_rejected": insufficient_rejected,
            }
    assert best is not None
    return best


def summarize_signal(
    name: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    values = [record[name] for record in records]
    labels = [record["answerability"] == "answerable" for record in records]
    answerable_values = [v for v, keep in zip(values, labels, strict=True) if keep]
    insufficient_values = [
        v for v, keep in zip(values, labels, strict=True) if not keep
    ]
    # --limit 스모크 실행에서는 한쪽 라벨이 비어 있을 수 있다.
    if not answerable_values or not insufficient_values:
        raise SystemExit(
            "both labels are required for separation analysis; "
            "run without --limit (or with a limit that covers insufficient rows)"
        )
    return {
        "signal": name,
        "answerable_median": round(statistics.median(answerable_values), 4),
        "insufficient_median": round(statistics.median(insufficient_values), 4),
        "answerable_min": round(min(answerable_values), 4),
        "insufficient_max": round(max(insufficient_values), 4),
        "answerable_count": len(answerable_values),
        "insufficient_count": len(insufficient_values),
        "best_threshold": best_single_threshold(values, labels),
    }


async def collect_signals(args: argparse.Namespace) -> list[dict[str, Any]]:
    # app.* imports must happen after configure_runtime_env().
    from app.core.config import settings
    from app.core.db import AsyncSessionLocal, engine
    from app.services.chroma_client import get_chroma_collection
    from app.services.embedding_provider import VoyageEmbedder
    from app.services.retriever import (
        HybridRetriever,
        _direct_keyword_overlap,
        normalize_query_keywords,
    )

    questions: list[EvalQuestion] = load_questions(
        args.questions, category=None, limit=args.limit
    )
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
        best_bets_enabled=args.best_bets,
    )

    records: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as session:
        semantic_top_n = args.semantic_top_n or settings.retriever_semantic_top_n
        bm25_top_n = args.bm25_top_n or settings.retriever_bm25_top_n
        for question in questions:
            response = await retriever.retrieve_with_status(
                session,
                question=question.question,
                category=None,
                semantic_top_n=semantic_top_n,
                bm25_top_n=bm25_top_n,
                include_pools=True,
            )
            semantic_pool = response.semantic_pool or []
            query_keywords = normalize_query_keywords(question.question)
            best_sem = max((result.score for result in semantic_pool), default=0.0)
            best_rel = max(
                (
                    result.relevance if result.relevance is not None else result.score
                    for result in response.results
                ),
                default=0.0,
            )
            best_ovl = max(
                (
                    _direct_keyword_overlap(result, query_keywords)
                    for result in response.results
                ),
                default=0,
            )
            records.append(
                {
                    "id": question.id,
                    "answerability": question.answerability,
                    "best_sem": round(best_sem, 6),
                    "best_rel": round(best_rel, 6),
                    "best_ovl": best_ovl,
                }
            )
    await engine.dispose()
    return records


def render_summary(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "| 신호 | answerable 중앙 | insufficient 중앙 | 최적 문턱 | 정확도 | 유지/거절 |",
        "|---|---|---|---|---|---|",
    ]
    for summary in summaries:
        best = summary["best_threshold"]
        lines.append(
            "| {signal} | {a_med} | {i_med} | {t} | {acc} | "
            "answerable {kept}/{a_n} 유지, insufficient {rej}/{i_n} 거절 |".format(
                signal=summary["signal"],
                a_med=summary["answerable_median"],
                i_med=summary["insufficient_median"],
                t=best["threshold"],
                acc=best["accuracy"],
                kept=best["answerable_kept"],
                a_n=summary["answerable_count"],
                rej=best["insufficient_rejected"],
                i_n=summary["insufficient_count"],
            )
        )
    return "\n".join(lines)


async def run() -> None:
    args = parse_args()
    configure_runtime_env(local_services=args.local_services)

    records = await collect_signals(args)
    summaries = [
        summarize_signal(name, records) for name in ("best_sem", "best_rel", "best_ovl")
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"abstain-separation-{now_stamp()}.json"
    out_path.write_text(
        json.dumps(
            {
                "best_bets": args.best_bets,
                "question_count": len(records),
                "signals": summaries,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(render_summary(summaries))
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(run())
