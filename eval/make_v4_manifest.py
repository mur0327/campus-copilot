"""qrel v4 입력·판정·발행 계보의 SHA-256 manifest를 만든다."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = REPO_ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"
OUT_PATH = EVAL_DIR / "qrel-v4-manifest.sha256"

MANIFEST_PATHS = (
    EVAL_DIR / "qrel-v4-criteria.md",
    EVAL_DIR / "questions.csv",
    RESULTS_DIR / "retrieval-bm25-20260712-061017.jsonl",
    RESULTS_DIR / "retrieval-semantic-20260712-061027.jsonl",
    RESULTS_DIR / "retrieval-hybrid-20260712-061045.jsonl",
    RESULTS_DIR / "final-response-20260711-101912.jsonl",
    RESULTS_DIR / "retrieval-20260705-094816.jsonl",
    EVAL_DIR / "page_pool_v4.csv",
    EVAL_DIR / "chunk_pool_v4.csv",
    EVAL_DIR / "gold_pages_v4.csv",
    EVAL_DIR / "gold_evidence_v4.csv",
    EVAL_DIR / "question_judgments_v4.csv",
    EVAL_DIR / "target_sources_v4.csv",
    EVAL_DIR / "qrel-v4-primary-initial.json",
    EVAL_DIR / "qrel-v4-secondary-audit.json",
    EVAL_DIR / "qrel-v4-secondary-audit-repilot.json",
    EVAL_DIR / "qrel-v4-secondary-audit-remaining.json",
    EVAL_DIR / "qrel-v4-secondary-audit-truncation-reaudit.json",
    EVAL_DIR / "qrel-v4-question-review.json",
    EVAL_DIR / "qrel-v4-adjudicated.json",
    EVAL_DIR / "qrel-v4-pilot-adjudication-2026-07-14.md",
    EVAL_DIR / "qrel-v4-adjudication-2026-07-14.md",
    EVAL_DIR / "select_v4_audit.py",
    EVAL_DIR / "make_v4_sheet.py",
    EVAL_DIR / "make_v4_question_review.py",
    EVAL_DIR / "adjudicate_v4_qrel.py",
    EVAL_DIR / "build_v4_qrel.py",
    EVAL_DIR / "check_v4_invariants.py",
    EVAL_DIR / "score_v4.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for block in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_lines(paths: tuple[Path, ...] = MANIFEST_PATHS) -> list[str]:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        rendered = "\n".join(f"- {path.relative_to(REPO_ROOT)}" for path in missing)
        raise FileNotFoundError(f"manifest 대상 파일이 없습니다:\n{rendered}")
    return [f"{sha256_file(path)}  {path.relative_to(REPO_ROOT).as_posix()}" for path in paths]


def write_manifest(path: Path, lines: list[str]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 SHA-256 manifest를 생성합니다.")
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lines = manifest_lines()
    write_manifest(args.out, lines)
    print(f"저장: {args.out} ({len(lines)}개 파일)")


if __name__ == "__main__":
    main()
