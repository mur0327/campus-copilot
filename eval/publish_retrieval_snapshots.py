"""Publish sanitized public copies of the frozen RQ1 retrieval snapshots.

The frozen originals under eval/results/ keep chunk text excerpts that can
contain personal names from crawled board posts, plus pre-v4 gold labels that
no longer represent the final qrel. The public copies keep only the fields
needed to re-score the retrieval metrics against the final qrel; content_sig
still allows verifying that indexed chunk content did not change.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
OUTPUT_DIR = EVAL_DIR / "retrieval-frozen-public"

SOURCES = {
    "bm25": RESULTS_DIR / "retrieval-bm25-20260712-061017.jsonl",
    "semantic": RESULTS_DIR / "retrieval-semantic-20260712-061027.jsonl",
    "hybrid": RESULTS_DIR / "retrieval-hybrid-20260712-061045.jsonl",
}

STATUS_FIELDS = ("mode", "degraded", "semantic_available", "bm25_available")
ITEM_FIELDS = (
    "rank",
    "source_number",
    "score",
    "chunk_id",
    "document_id",
    "title",
    "url",
    "menu_path",
    "source_scope",
    "page_kind",
    "chunk_type",
    "chunk_index",
    "content_sig",
)
FORBIDDEN_FIELDS = ("content_preview", "content", "text")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize_item(item: dict) -> dict:
    return {key: item[key] for key in ITEM_FIELDS if key in item}


def sanitize_record(record: dict) -> dict:
    status = record.get("retrieval_status", {})
    public = {
        "id": record["id"],
        "question": record["question"],
        "retrieval_status": {key: status.get(key) for key in STATUS_FIELDS},
        "retrieved": [sanitize_item(item) for item in record.get("retrieved", [])],
        "evidence_candidates": [
            sanitize_item(item) for item in record.get("evidence_candidates", [])
        ],
    }
    for item in (*public["retrieved"], *public["evidence_candidates"]):
        for field in FORBIDDEN_FIELDS:
            if field in item:
                raise ValueError(f"{record['id']}: forbidden field {field} survived")
    return public


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    manifest = {
        "schema": "retrieval-frozen-public.v1",
        "kept_item_fields": list(ITEM_FIELDS),
        "removed": "chunk text excerpts and pre-v4 gold/expectation labels",
        "files": {},
    }
    for mode, source in SOURCES.items():
        output = OUTPUT_DIR / f"retrieval-{mode}-20260712-public.jsonl"
        lines = []
        for line in source.read_text(encoding="utf-8").splitlines():
            record = sanitize_record(json.loads(line))
            lines.append(json.dumps(record, ensure_ascii=False))
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest["files"][mode] = {
            "source": source.name,
            "source_sha256": sha256_file(source),
            "public": output.name,
            "public_sha256": sha256_file(output),
            "records": len(lines),
        }
        print(f"{mode}: {len(lines)} records -> {output.name}")
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest -> {manifest_path.name}")


if __name__ == "__main__":
    main()
