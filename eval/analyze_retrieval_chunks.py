"""Expand retrieval JSONL results into a chunk-level CSV report."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = REPO_ROOT / "eval" / "results"
DEFAULT_PREVIEW_CHARS = 500


@dataclass(frozen=True)
class AnalyzeArgs:
    input_path: Path
    output_path: Path
    question_ids: set[str]
    preview_chars: int
    include_content: bool


def parse_args() -> AnalyzeArgs:
    parser = argparse.ArgumentParser(
        description="Write a chunk-level CSV from eval retrieval JSONL output.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Input retrieval-*.jsonl path. Defaults to the newest eval/results file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output CSV path. Defaults to retrieval-chunks-<timestamp>.csv.",
    )
    parser.add_argument(
        "--question-id",
        action="append",
        default=[],
        help="Question ID to include. Can be repeated. Defaults to all questions.",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=DEFAULT_PREVIEW_CHARS,
        help="Maximum content preview length.",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Include full content when the input JSONL contains it.",
    )
    parsed = parser.parse_args()
    if parsed.preview_chars <= 0:
        parser.error("--preview-chars must be greater than 0")

    input_path = parsed.input or newest_retrieval_jsonl(DEFAULT_RESULTS_DIR)
    output_path = parsed.output or default_output_path(input_path)
    return AnalyzeArgs(
        input_path=input_path,
        output_path=output_path,
        question_ids=set(parsed.question_id),
        preview_chars=parsed.preview_chars,
        include_content=parsed.include_content,
    )


def newest_retrieval_jsonl(results_dir: Path) -> Path:
    candidates = sorted(
        path
        for path in results_dir.glob("retrieval-*.jsonl")
        if not path.name.startswith("retrieval-chunks-")
    )
    if not candidates:
        raise FileNotFoundError(f"no retrieval-*.jsonl files found in {results_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def default_output_path(input_path: Path) -> Path:
    suffix = input_path.stem.removeprefix("retrieval-")
    return input_path.with_name(f"retrieval-chunks-{suffix}.csv")


def load_rows(path: Path, *, question_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as jsonl_file:
        for line_number, line in enumerate(jsonl_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSONL") from exc
            if question_ids and row.get("id") not in question_ids:
                continue
            rows.append(row)
    return rows


def content_text(item: dict[str, Any]) -> str:
    value = item.get("content")
    if isinstance(value, str):
        return value
    preview = item.get("content_preview")
    return preview if isinstance(preview, str) else ""


def content_preview(item: dict[str, Any], *, preview_chars: int) -> str:
    return " ".join(content_text(item).split())[:preview_chars]


def base_output_row(
    question: dict[str, Any],
    *,
    row_type: str,
    item: dict[str, Any],
    preview_chars: int,
    include_content: bool,
) -> dict[str, Any]:
    text = content_text(item)
    output = {
        "question_id": question.get("id", ""),
        "category": question.get("category", ""),
        "question": question.get("question", ""),
        "dataset_question_type": question.get("dataset_question_type", ""),
        "classified_intent": question.get("classified_intent", ""),
        "row_type": row_type,
        "rank": item.get("rank", ""),
        "source_number": item.get("source_number", ""),
        "overlap": item.get("overlap", ""),
        "score": item.get("score", ""),
        "url": item.get("url", ""),
        "title": item.get("title", ""),
        "menu_path": item.get("menu_path", ""),
        "category_metadata": item.get("category", ""),
        "source_scope": item.get("source_scope", ""),
        "page_kind": item.get("page_kind", ""),
        "chunk_id": item.get("chunk_id", ""),
        "document_id": item.get("document_id", ""),
        "chunk_index": item.get("chunk_index", ""),
        "chunk_type": item.get("chunk_type", ""),
        "crawled_at": item.get("crawled_at", ""),
        "content_length": len(text),
        "content_preview": content_preview(item, preview_chars=preview_chars),
        "content_available": "content" in item,
    }
    if include_content:
        output["content"] = item.get("content", "")
    return output


def flatten_rows(
    questions: list[dict[str, Any]],
    *,
    preview_chars: int,
    include_content: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    output_rows: list[dict[str, Any]] = []
    evidence_empty_question_ids: list[str] = []
    for question in questions:
        for item in question.get("retrieved", []):
            output_rows.append(
                base_output_row(
                    question,
                    row_type="retrieved",
                    item=item,
                    preview_chars=preview_chars,
                    include_content=include_content,
                )
            )
        evidence_candidates = question.get("evidence_candidates", [])
        if not evidence_candidates:
            evidence_empty_question_ids.append(question.get("id", ""))
        for item in evidence_candidates:
            output_rows.append(
                base_output_row(
                    question,
                    row_type="evidence",
                    item=item,
                    preview_chars=preview_chars,
                    include_content=include_content,
                )
            )
    return output_rows, evidence_empty_question_ids


def fieldnames(*, include_content: bool) -> list[str]:
    names = [
        "question_id",
        "category",
        "question",
        "dataset_question_type",
        "classified_intent",
        "row_type",
        "rank",
        "source_number",
        "overlap",
        "score",
        "url",
        "title",
        "menu_path",
        "category_metadata",
        "source_scope",
        "page_kind",
        "chunk_id",
        "document_id",
        "chunk_index",
        "chunk_type",
        "crawled_at",
        "content_length",
        "content_preview",
        "content_available",
    ]
    if include_content:
        names.append("content")
    return names


def write_csv(path: Path, rows: list[dict[str, Any]], *, include_content: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames(include_content=include_content))
        writer.writeheader()
        writer.writerows(rows)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    args = parse_args()
    questions = load_rows(args.input_path, question_ids=args.question_ids)
    rows, evidence_empty_question_ids = flatten_rows(
        questions,
        preview_chars=args.preview_chars,
        include_content=args.include_content,
    )
    write_csv(args.output_path, rows, include_content=args.include_content)

    retrieved_rows = sum(1 for row in rows if row["row_type"] == "retrieved")
    evidence_rows = sum(1 for row in rows if row["row_type"] == "evidence")
    print(f"input: {display_path(args.input_path)}")
    print(f"output: {display_path(args.output_path)}")
    print(f"questions: {len(questions)}")
    print(f"retrieved_rows: {retrieved_rows}")
    print(f"evidence_rows: {evidence_rows}")
    print(
        "evidence_empty_questions: "
        + (",".join(evidence_empty_question_ids) if evidence_empty_question_ids else "")
    )


if __name__ == "__main__":
    main()
