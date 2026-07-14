"""동결 검색 JSONL을 page/evidence qrel v4로 오프라인 재채점한다."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.run_questions import normalize_url  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"
RETRIEVAL_PATHS = (
    RESULTS_DIR / "retrieval-bm25-20260712-061017.jsonl",
    RESULTS_DIR / "retrieval-semantic-20260712-061027.jsonl",
    RESULTS_DIR / "retrieval-hybrid-20260712-061045.jsonl",
)
GOLD_PAGES_PATH = EVAL_DIR / "gold_pages_v4.csv"
GOLD_EVIDENCE_PATH = EVAL_DIR / "gold_evidence_v4.csv"
RUN_NAMES = ("bm25", "semantic", "hybrid")
SUMMARY_FIELDS = ("variant", "retriever_mode", "metric", "value", "N")
METRIC_QUESTION_SET_NAMES = {
    "PageHit_full@5": "page_support",
    "PageHit_any@5": "page_support",
    "nDCG_support@5": "page_support",
    "nDCG_deployable@5": "page_deployable",
    "EvidenceHit_full@5": "text_evidence",
    "EvidenceHit_any@5": "text_evidence",
}
PAGE_REQUIRED_FIELDS = (
    "question_id",
    "canonical_url",
    "provenance",
    "judged",
    "support_grade",
    "temporal_validity",
    "audience_scope",
    "notes",
)
CHUNK_FIELDS = (
    "question_id",
    "canonical_url",
    "chunk_id",
    "content_hash",
    "judged",
    "evidence_grade",
    "evidence_type",
    "notes",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as input_file:
        return [json.loads(line) for line in input_file if line.strip()]


def top_k_items(row: Mapping[str, Any], *, k: int = 5) -> list[dict[str, Any]]:
    return sorted(row.get("retrieved", []), key=lambda item: int(item["rank"]))[:k]


def parse_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def write_csv_atomic(
    path: Path,
    *,
    fieldnames: Sequence[str],
    rows: list[dict[str, str]],
) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def load_csv(path: Path, required_fields: Sequence[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = set(reader.fieldnames or [])
        missing = set(required_fields) - fieldnames
        if missing:
            raise ValueError(f"{path}: 필수 컬럼 누락: {', '.join(sorted(missing))}")
        return [dict(row) for row in reader]


def dcg(gains: Iterable[int | float]) -> float:
    return sum(float(gain) / math.log2(index + 2) for index, gain in enumerate(gains))


def normalized_dcg(retrieved_gains: Sequence[int], ideal_gains: Sequence[int]) -> float:
    ideal = dcg(ideal_gains)
    if ideal == 0:
        return 0.0
    return dcg(retrieved_gains) / ideal


def support_gain(page: Mapping[str, Any]) -> int:
    return {"full": 2, "partial": 1}.get(str(page.get("support_grade") or ""), 0)


def deployable_gain(page: Mapping[str, Any]) -> int:
    if page.get("temporal_validity") != "current" or page.get("audience_scope") != "match":
        return 0
    return support_gain(page)


def page_gains_at_k(
    retrieval_row: Mapping[str, Any],
    page_qrels: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    gain_fn: Callable[[Mapping[str, Any]], int] = support_gain,
    k: int = 5,
) -> list[int]:
    """같은 URL은 처음 등장한 청크에만 page gain을 준다."""

    question_id = str(retrieval_row["id"])
    seen_urls: set[str] = set()
    gains: list[int] = []
    for item in top_k_items(dict(retrieval_row), k=k):
        canonical_url = normalize_url(item["url"])
        if canonical_url in seen_urls:
            gains.append(0)
            continue
        seen_urls.add(canonical_url)
        page = page_qrels.get((question_id, canonical_url), {})
        gains.append(gain_fn(page))
    return gains


def ideal_page_gains(
    question_id: str,
    pages_by_question: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    gain_fn: Callable[[Mapping[str, Any]], int],
    k: int = 5,
) -> list[int]:
    return sorted(
        (gain_fn(page) for page in pages_by_question.get(question_id, [])),
        reverse=True,
    )[:k]


def assert_top5_judged(
    retrieval_rows: Sequence[Mapping[str, Any]],
    page_qrels: Mapping[tuple[str, str], Mapping[str, Any]],
    evidence_qrels: Mapping[tuple[str, str], Mapping[str, Any]],
    *,
    k: int = 5,
) -> None:
    failures: list[str] = []
    for row in retrieval_rows:
        question_id = str(row["id"])
        for item in top_k_items(dict(row), k=k):
            canonical_url = normalize_url(item["url"])
            page = page_qrels.get((question_id, canonical_url))
            if page is None or parse_bool(page.get("judged")) is not True:
                failures.append(f"page:{question_id}|{canonical_url}")
            chunk_id = str(item["chunk_id"])
            evidence = evidence_qrels.get((question_id, chunk_id))
            if evidence is None or parse_bool(evidence.get("judged")) is not True:
                failures.append(f"evidence:{question_id}|{chunk_id}")
    if failures:
        sample = ", ".join(sorted(set(failures))[:20])
        extra = len(set(failures)) - min(len(set(failures)), 20)
        suffix = f" 외 {extra}건" if extra else ""
        raise AssertionError(f"top-5에 unjudged qrel이 있습니다: {sample}{suffix}")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _metric(value: float, denominator: int) -> dict[str, int | float]:
    return {"value": round(value, 6), "N": denominator}


def metric_question_sets(
    page_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    included_question_ids: set[str],
) -> dict[str, set[str]]:
    pages_by_question: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in page_rows:
        pages_by_question[str(row["question_id"])].append(row)

    support_questions = {
        question_id
        for question_id in included_question_ids
        if any(support_gain(page) > 0 for page in pages_by_question.get(question_id, []))
    }
    deployable_questions = {
        question_id
        for question_id in included_question_ids
        if any(deployable_gain(page) > 0 for page in pages_by_question.get(question_id, []))
    }
    navigation_questions = {
        str(row["question_id"])
        for row in evidence_rows
        if row.get("evidence_type") == "page_navigation"
        and row.get("evidence_grade") in {"full", "partial"}
    }
    text_evidence_questions = {
        str(row["question_id"])
        for row in evidence_rows
        if row.get("evidence_type") == "text_chunk"
        and row.get("evidence_grade") in {"full", "partial"}
        and str(row["question_id"]) in included_question_ids
    } - navigation_questions
    return {
        "page_support": support_questions,
        "page_deployable": deployable_questions,
        "text_evidence": text_evidence_questions,
    }


def score_retrieval_rows(
    retrieval_rows: Sequence[Mapping[str, Any]],
    page_rows: Sequence[Mapping[str, Any]],
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    included_question_ids: set[str] | None = None,
    k: int = 5,
) -> dict[str, dict[str, int | float]]:
    page_qrels = {(str(row["question_id"]), normalize_url(str(row["canonical_url"]))): row for row in page_rows}
    evidence_qrels = {(str(row["question_id"]), str(row["chunk_id"])): row for row in evidence_rows}
    assert_top5_judged(retrieval_rows, page_qrels, evidence_qrels, k=k)

    pages_by_question: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in page_rows:
        pages_by_question[str(row["question_id"])].append(row)

    rows_by_question = {str(row["id"]): row for row in retrieval_rows}
    run_ids = set(rows_by_question)
    included = run_ids if included_question_ids is None else run_ids & included_question_ids

    question_sets = metric_question_sets(
        page_rows,
        evidence_rows,
        included_question_ids=included,
    )
    support_questions = question_sets["page_support"]
    deployable_questions = question_sets["page_deployable"]
    text_evidence_questions = question_sets["text_evidence"]

    full_hits: list[float] = []
    any_hits: list[float] = []
    support_ndcgs: list[float] = []
    for question_id in sorted(support_questions):
        row = rows_by_question[question_id]
        unique_pages: list[Mapping[str, Any]] = []
        seen_urls: set[str] = set()
        for item in top_k_items(dict(row), k=k):
            canonical_url = normalize_url(item["url"])
            if canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            unique_pages.append(page_qrels[(question_id, canonical_url)])
        full_hits.append(float(any(page.get("support_grade") == "full" for page in unique_pages)))
        any_hits.append(float(any(support_gain(page) > 0 for page in unique_pages)))
        support_ndcgs.append(
            normalized_dcg(
                page_gains_at_k(row, page_qrels, gain_fn=support_gain, k=k),
                ideal_page_gains(
                    question_id,
                    pages_by_question,
                    gain_fn=support_gain,
                    k=k,
                ),
            )
        )

    deployable_ndcgs = [
        normalized_dcg(
            page_gains_at_k(
                rows_by_question[question_id],
                page_qrels,
                gain_fn=deployable_gain,
                k=k,
            ),
            ideal_page_gains(
                question_id,
                pages_by_question,
                gain_fn=deployable_gain,
                k=k,
            ),
        )
        for question_id in sorted(deployable_questions)
    ]

    evidence_full_hits: list[float] = []
    evidence_any_hits: list[float] = []
    for question_id in sorted(text_evidence_questions):
        retrieved = {str(item["chunk_id"]) for item in top_k_items(dict(rows_by_question[question_id]), k=k)}
        grades = {
            str(evidence_qrels[(question_id, chunk_id)].get("evidence_grade") or "")
            for chunk_id in retrieved
            if evidence_qrels[(question_id, chunk_id)].get("evidence_type") == "text_chunk"
        }
        evidence_full_hits.append(float("full" in grades))
        evidence_any_hits.append(float(bool(grades & {"full", "partial"})))

    support_n = len(support_questions)
    deployable_n = len(deployable_questions)
    evidence_n = len(text_evidence_questions)
    return {
        f"PageHit_full@{k}": _metric(_mean(full_hits), support_n),
        f"PageHit_any@{k}": _metric(_mean(any_hits), support_n),
        f"nDCG_support@{k}": _metric(_mean(support_ndcgs), support_n),
        f"nDCG_deployable@{k}": _metric(_mean(deployable_ndcgs), deployable_n),
        f"EvidenceHit_full@{k}": _metric(_mean(evidence_full_hits), evidence_n),
        f"EvidenceHit_any@{k}": _metric(_mean(evidence_any_hits), evidence_n),
    }


def now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="동결 검색 결과를 qrel v4로 채점합니다.")
    parser.add_argument("--pages", type=Path, default=GOLD_PAGES_PATH)
    parser.add_argument("--evidence", type=Path, default=GOLD_EVIDENCE_PATH)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pages = load_csv(args.pages, PAGE_REQUIRED_FIELDS)
    evidence = load_csv(args.evidence, CHUNK_FIELDS)
    runs = {name: load_jsonl(path) for name, path in zip(RUN_NAMES, RETRIEVAL_PATHS, strict=True)}
    page_qrels = {(row["question_id"], normalize_url(row["canonical_url"])): row for row in pages}
    evidence_qrels = {(row["question_id"], row["chunk_id"]): row for row in evidence}
    for rows in runs.values():
        assert_top5_judged(rows, page_qrels, evidence_qrels)

    run_id_sets = [{str(row["id"]) for row in rows} for rows in runs.values()]
    if any(question_ids != run_id_sets[0] for question_ids in run_id_sets[1:]):
        raise AssertionError("세 동결 실행의 질문 ID 집합이 서로 다릅니다")
    all_ids = run_id_sets[0]
    if len(all_ids) != 50:
        raise AssertionError(f"동결 실행은 50문항이어야 합니다: {len(all_ids)}문항")
    if not {"Q011", "Q035"} <= all_ids:
        raise AssertionError("Q011/Q035 중복 문항이 동결 실행에 모두 있어야 합니다")
    variants = {
        "all_50": all_ids,
        "without_duplicate_49": all_ids - {"Q035"},
    }

    result_variants: dict[str, Any] = {}
    summary_rows: list[dict[str, str]] = []
    for variant, question_ids in variants.items():
        run_results: dict[str, Any] = {}
        for run_name, rows in runs.items():
            metrics = score_retrieval_rows(
                rows,
                pages,
                evidence,
                included_question_ids=question_ids,
            )
            run_results[run_name] = {"metrics": metrics}
            for metric_name, metric in metrics.items():
                summary_rows.append(
                    {
                        "variant": variant,
                        "retriever_mode": run_name,
                        "metric": metric_name,
                        "value": str(metric["value"]),
                        "N": str(metric["N"]),
                    }
                )
        result_variants[variant] = {
            "question_count": len(question_ids),
            "excluded_question_ids": [] if variant == "all_50" else ["Q035"],
            "runs": run_results,
        }

    stamp = now_stamp()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"scores-v4-{stamp}.json"
    csv_path = args.out_dir / f"scores-v4-{stamp}-summary.csv"
    payload = {
        "schema_version": "qrel-v4-scores-1",
        "created_at": datetime.now(UTC).isoformat(),
        "inputs": {
            "gold_pages": str(args.pages.relative_to(REPO_ROOT)),
            "gold_evidence": str(args.evidence.relative_to(REPO_ROOT)),
            "retrieval_runs": [str(path.relative_to(REPO_ROOT)) for path in RETRIEVAL_PATHS],
        },
        "variants": result_variants,
    }
    write_json_atomic(json_path, payload)
    write_csv_atomic(csv_path, fieldnames=SUMMARY_FIELDS, rows=summary_rows)
    print(f"저장: {json_path}")
    print(f"저장: {csv_path}")
    for variant, result in result_variants.items():
        print(f"[{variant}] 질문 {result['question_count']}개")
        for run_name, run in result["runs"].items():
            rendered = ", ".join(
                f"{name}={metric['value']} (N={metric['N']})" for name, metric in run["metrics"].items()
            )
            print(f"- {run_name}: {rendered}")


if __name__ == "__main__":
    main()
