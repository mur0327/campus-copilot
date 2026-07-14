"""동일한 동결 검색 결과에서 qrel v4 감사 전후 판정 민감도를 비교한다."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.build_v4_qrel import build_rows, load_json, load_question_order  # noqa: E402
from eval.check_v4_invariants import load_csv  # noqa: E402
from eval.make_v4_pool import (  # noqa: E402
    CHUNK_FIELDS,
    CHUNK_POOL_PATH,
    PAGE_FIELDS,
    PAGE_POOL_PATH,
)
from eval.score_v4 import (  # noqa: E402
    METRIC_QUESTION_SET_NAMES,
    RETRIEVAL_PATHS,
    RUN_NAMES,
    load_jsonl,
    metric_question_sets,
    now_stamp,
    score_retrieval_rows,
    write_csv_atomic,
    write_json_atomic,
)

EVAL_DIR = REPO_ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"
PRIMARY_PATH = EVAL_DIR / "qrel-v4-primary-initial.json"
ADJUDICATED_PATH = EVAL_DIR / "qrel-v4-adjudicated.json"
VARIANT_EXCLUSIONS = {
    "all_50": frozenset(),
    "without_duplicate_49": frozenset({"Q035"}),
}
SUMMARY_FIELDS = (
    "variant",
    "metric",
    "question_set",
    "retriever_mode",
    "before_value",
    "after_value",
    "delta",
    "before_N",
    "after_N",
    "question_set_changed",
    "before_ranking",
    "after_ranking",
    "ranking_changed",
)
JUDGMENT_FIELDS = {
    "pages": ("judged", "support_grade", "temporal_validity", "audience_scope"),
    "evidence": ("judged", "evidence_grade", "evidence_type"),
    "questions": (
        "judged",
        "expected_behavior",
        "primary_reason",
        "secondary_reasons",
        "composition_override",
        "composition_sources",
    ),
}


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ranking_groups(
    run_metrics: dict[str, dict[str, dict[str, int | float]]],
    metric: str,
) -> list[list[str]]:
    order = {name: index for index, name in enumerate(RUN_NAMES)}
    pairs = sorted(
        (
            (float(run_metrics[run_name][metric]["value"]), run_name)
            for run_name in RUN_NAMES
        ),
        key=lambda item: (-item[0], order[item[1]]),
    )
    groups: list[list[str]] = []
    previous_value: float | None = None
    for value, run_name in pairs:
        if previous_value is None or value != previous_value:
            groups.append([])
            previous_value = value
        groups[-1].append(run_name)
    return groups


def render_ranking(groups: list[list[str]]) -> str:
    return " > ".join("=".join(group) for group in groups)


def judgment_changes(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for section, fields in JUDGMENT_FIELDS.items():
        before_rows = {str(row["row_id"]): row for row in before[section]}
        after_rows = {str(row["row_id"]): row for row in after[section]}
        if set(before_rows) != set(after_rows):
            raise ValueError(f"{section}의 감사 전후 row_id 집합이 다릅니다")
        for row_id in sorted(before_rows):
            field_changes = {
                field: {
                    "before": before_rows[row_id].get(field),
                    "after": after_rows[row_id].get(field),
                }
                for field in fields
                if before_rows[row_id].get(field) != after_rows[row_id].get(field)
            }
            if field_changes:
                changes.append(
                    {
                        "section": section,
                        "row_id": row_id,
                        "question_id": str(before_rows[row_id]["question_id"]),
                        "fields": field_changes,
                    }
                )
    return changes


def _load_qrel_rows(
    path: Path,
    *,
    page_pool: list[dict[str, str]],
    chunk_pool: list[dict[str, str]],
    question_ids: list[str],
) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    payload = load_json(path)
    pages, evidence, _ = build_rows(
        page_pool,
        chunk_pool,
        question_ids,
        payload,
    )
    return payload, pages, evidence


def _validate_run_ids(runs: dict[str, list[dict[str, Any]]]) -> set[str]:
    run_id_sets = [{str(row["id"]) for row in rows} for rows in runs.values()]
    if any(question_ids != run_id_sets[0] for question_ids in run_id_sets[1:]):
        raise AssertionError("세 동결 실행의 질문 ID 집합이 서로 다릅니다")
    all_ids = run_id_sets[0]
    if len(all_ids) != 50 or not {"Q011", "Q035"} <= all_ids:
        raise AssertionError("동결 실행은 Q011/Q035를 포함한 50문항이어야 합니다")
    return all_ids


def build_audit_comparison(
    *,
    before_path: Path = PRIMARY_PATH,
    after_path: Path = ADJUDICATED_PATH,
) -> dict[str, Any]:
    page_pool = load_csv(PAGE_POOL_PATH, PAGE_FIELDS)
    chunk_pool = load_csv(CHUNK_POOL_PATH, CHUNK_FIELDS)
    question_ids = load_question_order()
    before_payload, before_pages, before_evidence = _load_qrel_rows(
        before_path,
        page_pool=page_pool,
        chunk_pool=chunk_pool,
        question_ids=question_ids,
    )
    after_payload, after_pages, after_evidence = _load_qrel_rows(
        after_path,
        page_pool=page_pool,
        chunk_pool=chunk_pool,
        question_ids=question_ids,
    )
    runs = {
        name: load_jsonl(path)
        for name, path in zip(RUN_NAMES, RETRIEVAL_PATHS, strict=True)
    }
    all_ids = _validate_run_ids(runs)
    variants: dict[str, Any] = {}
    max_delta: dict[str, Any] | None = None
    any_question_set_changed = False
    any_ranking_changed = False

    for variant, excluded_ids in VARIANT_EXCLUSIONS.items():
        included_ids = all_ids - set(excluded_ids)
        before_sets = metric_question_sets(
            before_pages,
            before_evidence,
            included_question_ids=included_ids,
        )
        after_sets = metric_question_sets(
            after_pages,
            after_evidence,
            included_question_ids=included_ids,
        )
        before_metrics = {
            run_name: score_retrieval_rows(
                rows,
                before_pages,
                before_evidence,
                included_question_ids=included_ids,
            )
            for run_name, rows in runs.items()
        }
        after_metrics = {
            run_name: score_retrieval_rows(
                rows,
                after_pages,
                after_evidence,
                included_question_ids=included_ids,
            )
            for run_name, rows in runs.items()
        }
        question_set_comparison = {
            name: {
                "before": sorted(before_sets[name]),
                "after": sorted(after_sets[name]),
                "added": sorted(after_sets[name] - before_sets[name]),
                "removed": sorted(before_sets[name] - after_sets[name]),
                "changed": before_sets[name] != after_sets[name],
            }
            for name in before_sets
        }
        metric_comparison: dict[str, Any] = {}
        variant_max_delta: dict[str, Any] | None = None
        for metric, question_set_name in METRIC_QUESTION_SET_NAMES.items():
            before_ranking = ranking_groups(before_metrics, metric)
            after_ranking = ranking_groups(after_metrics, metric)
            ranking_changed = before_ranking != after_ranking
            question_set_changed = question_set_comparison[question_set_name]["changed"]
            runs_comparison: dict[str, Any] = {}
            for run_name in RUN_NAMES:
                before_metric = before_metrics[run_name][metric]
                after_metric = after_metrics[run_name][metric]
                delta = round(
                    float(after_metric["value"]) - float(before_metric["value"]),
                    6,
                )
                runs_comparison[run_name] = {
                    "before_value": before_metric["value"],
                    "after_value": after_metric["value"],
                    "delta": delta,
                    "before_N": before_metric["N"],
                    "after_N": after_metric["N"],
                }
                candidate = {
                    "variant": variant,
                    "metric": metric,
                    "retriever_mode": run_name,
                    "delta": delta,
                }
                if max_delta is None or abs(delta) > abs(float(max_delta["delta"])):
                    max_delta = candidate
                if variant_max_delta is None or abs(delta) > abs(
                    float(variant_max_delta["delta"])
                ):
                    variant_max_delta = candidate
            metric_comparison[metric] = {
                "question_set": question_set_name,
                "question_set_changed": question_set_changed,
                "before_ranking": before_ranking,
                "after_ranking": after_ranking,
                "ranking_changed": ranking_changed,
                "runs": runs_comparison,
            }
            any_question_set_changed = any_question_set_changed or question_set_changed
            any_ranking_changed = any_ranking_changed or ranking_changed
        variants[variant] = {
            "question_count": len(included_ids),
            "excluded_question_ids": sorted(excluded_ids),
            "max_absolute_delta": variant_max_delta,
            "question_sets": question_set_comparison,
            "metrics": metric_comparison,
        }

    changes = judgment_changes(before_payload, after_payload)
    changed_by_section = {
        section: sorted(
            {change["question_id"] for change in changes if change["section"] == section}
        )
        for section in JUDGMENT_FIELDS
    }
    return {
        "schema_version": "qrel-v4-audit-comparison-1",
        "purpose": "판정 민감도 확인이며 검색 시스템의 성능 개선을 뜻하지 않는다.",
        "inputs": {
            "before_judgments": {
                "path": display_path(before_path),
                "sha256": sha256_file(before_path),
            },
            "after_judgments": {
                "path": display_path(after_path),
                "sha256": sha256_file(after_path),
            },
            "retrieval_runs": [
                {"path": display_path(path), "sha256": sha256_file(path)}
                for path in RETRIEVAL_PATHS
            ],
        },
        "judgment_changes": changes,
        "changed_question_ids": sorted({change["question_id"] for change in changes}),
        "changed_question_ids_by_section": changed_by_section,
        "retrieval_qrel_changed_question_ids": sorted(
            set(changed_by_section["pages"]) | set(changed_by_section["evidence"])
        ),
        "question_label_changed_question_ids": changed_by_section["questions"],
        "variants": variants,
        "summary": {
            "any_metric_question_set_changed": any_question_set_changed,
            "any_mode_ranking_changed": any_ranking_changed,
            "max_absolute_delta": max_delta,
        },
    }


def summary_rows(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for variant, variant_result in payload["variants"].items():
        for metric, metric_result in variant_result["metrics"].items():
            before_ranking = render_ranking(metric_result["before_ranking"])
            after_ranking = render_ranking(metric_result["after_ranking"])
            for run_name, run_result in metric_result["runs"].items():
                rows.append(
                    {
                        "variant": variant,
                        "metric": metric,
                        "question_set": metric_result["question_set"],
                        "retriever_mode": run_name,
                        "before_value": str(run_result["before_value"]),
                        "after_value": str(run_result["after_value"]),
                        "delta": str(run_result["delta"]),
                        "before_N": str(run_result["before_N"]),
                        "after_N": str(run_result["after_N"]),
                        "question_set_changed": str(metric_result["question_set_changed"]).lower(),
                        "before_ranking": before_ranking,
                        "after_ranking": after_ranking,
                        "ranking_changed": str(metric_result["ranking_changed"]).lower(),
                    }
                )
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 감사 전후 판정 민감도를 비교합니다.")
    parser.add_argument("--before", type=Path, default=PRIMARY_PATH)
    parser.add_argument("--after", type=Path, default=ADJUDICATED_PATH)
    parser.add_argument("--out-dir", type=Path, default=RESULTS_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_audit_comparison(
        before_path=args.before,
        after_path=args.after,
    )
    payload["created_at"] = datetime.now(UTC).isoformat()
    stamp = now_stamp()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"qrel-v4-audit-comparison-{stamp}.json"
    csv_path = args.out_dir / f"qrel-v4-audit-comparison-{stamp}.csv"
    write_json_atomic(json_path, payload)
    write_csv_atomic(
        csv_path,
        fieldnames=SUMMARY_FIELDS,
        rows=summary_rows(payload),
    )
    print(f"저장: {json_path}")
    print(f"저장: {csv_path}")
    print(
        "요약: "
        f"분모 문항 집합 변화={payload['summary']['any_metric_question_set_changed']}, "
        f"모드 순위 변화={payload['summary']['any_mode_ranking_changed']}, "
        f"최대 절대 변화={abs(payload['summary']['max_absolute_delta']['delta']):.6f}"
    )


if __name__ == "__main__":
    main()
