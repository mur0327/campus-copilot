"""qrel v4의 페이지·근거 판정 pool을 만든다.

세 검색 모드의 동결 top-5와 기존 양성 seed를 합치되, 판정값은 넣지 않는다.
top-5 밖 seed 페이지는 로컬 DB의 청크를 추가해 근거 판정 대상으로 보존한다.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.run_questions import content_signature, normalize_url  # noqa: E402

EVAL_DIR = REPO_ROOT / "eval"
RESULTS_DIR = EVAL_DIR / "results"
RETRIEVAL_PATHS = (
    RESULTS_DIR / "retrieval-bm25-20260712-061017.jsonl",
    RESULTS_DIR / "retrieval-semantic-20260712-061027.jsonl",
    RESULTS_DIR / "retrieval-hybrid-20260712-061045.jsonl",
)
EXP06_PATH = RESULTS_DIR / "final-response-20260711-101912.jsonl"
EXP06_RETRIEVAL_PATH = RESULTS_DIR / "retrieval-20260705-094816.jsonl"
GOLD_V3_PATH = EVAL_DIR / "gold_sources_v3.csv"

PAGE_POOL_PATH = EVAL_DIR / "page_pool_v4.csv"
CHUNK_POOL_PATH = EVAL_DIR / "chunk_pool_v4.csv"
TARGET_SOURCES_PATH = EVAL_DIR / "target_sources_v4.csv"

DB_DSN = "postgresql://campus:campus@localhost:5432/campus_copilot"
TOP_K = 5
INSUFFICIENT_IDS = frozenset(
    "Q005 Q006 Q015 Q016 Q021 Q022 Q023 Q024 Q026 Q030 Q031 Q032 Q039 Q040 Q043 Q045 Q049 Q050".split()
)
EXPECTED_ALL_PAIRS = 414
EXPECTED_INSUFFICIENT_PAIRS = 156
EXPECTED_UNIQUE_URLS = 207

PAGE_FIELDS = (
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
TARGET_FIELDS = (
    "question_id",
    "target_url",
    "in_corpus_snapshot",
    "failure_reason",
    "notes",
)
PROVENANCE_ORDER = ("top5", "seed_v3", "exp06")


@dataclass
class PageCandidate:
    provenance: set[str] = field(default_factory=set)
    raw_urls: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Exp06Seed:
    question_id: str
    canonical_url: str
    content_hash: str


@dataclass
class PoolCandidates:
    pages: dict[tuple[str, str], PageCandidate]
    chunks: dict[tuple[str, str, str], str]
    top5_page_pairs: set[tuple[str, str]]
    top5_chunk_pairs: set[tuple[str, str]]
    exp06_seeds: list[Exp06Seed]
    exp06_chunk_pairs: set[tuple[str, str]]
    exp06_source_downgrades: int


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as input_file:
        return [json.loads(line) for line in input_file if line.strip()]


def top_k_items(row: dict[str, Any], *, k: int = TOP_K) -> list[dict[str, Any]]:
    """저장 순서가 아니라 명시된 순위를 기준으로 상위 k개를 고른다."""

    return sorted(row.get("retrieved", []), key=lambda item: int(item["rank"]))[:k]


def _add_page(
    pages: dict[tuple[str, str], PageCandidate],
    *,
    question_id: str,
    raw_url: str,
    provenance: str,
) -> tuple[str, str]:
    canonical_url = normalize_url(raw_url)
    if not canonical_url:
        raise ValueError(f"{question_id}: 빈 URL은 pool에 넣을 수 없습니다")
    key = (question_id, canonical_url)
    candidate = pages.setdefault(key, PageCandidate())
    candidate.provenance.add(provenance)
    candidate.raw_urls.add(raw_url)
    return key


def _add_chunk(
    chunks: dict[tuple[str, str, str], str],
    chunk_urls: dict[tuple[str, str], str],
    *,
    question_id: str,
    canonical_url: str,
    chunk_id: str,
    content_hash: str,
) -> None:
    if not chunk_id:
        return
    if not content_hash:
        raise ValueError(f"{question_id}/{chunk_id}: content_hash가 없습니다")

    qid_chunk = (question_id, chunk_id)
    previous_url = chunk_urls.setdefault(qid_chunk, canonical_url)
    if previous_url != canonical_url:
        raise ValueError(f"{question_id}/{chunk_id}: 서로 다른 URL에 연결됐습니다: {previous_url}, {canonical_url}")

    key = (question_id, canonical_url, chunk_id)
    previous_hash = chunks.setdefault(key, content_hash)
    if previous_hash != content_hash:
        raise ValueError(f"{question_id}/{chunk_id}: 동결 입력의 content hash가 서로 다릅니다")


def collect_pool_candidates(
    retrieval_paths: tuple[Path, ...] = RETRIEVAL_PATHS,
    *,
    gold_v3_path: Path = GOLD_V3_PATH,
    exp06_path: Path = EXP06_PATH,
    exp06_retrieval_path: Path = EXP06_RETRIEVAL_PATH,
) -> PoolCandidates:
    """파일 입력만으로 page pool과 알려진 chunk pool 후보를 모은다."""

    pages: dict[tuple[str, str], PageCandidate] = {}
    chunks: dict[tuple[str, str, str], str] = {}
    chunk_urls: dict[tuple[str, str], str] = {}
    top5_page_pairs: set[tuple[str, str]] = set()
    top5_chunk_pairs: set[tuple[str, str]] = set()
    exp06_seeds: list[Exp06Seed] = []
    exp06_chunk_pairs: set[tuple[str, str]] = set()
    exp06_source_downgrades = 0

    for retrieval_path in retrieval_paths:
        for row in load_jsonl(retrieval_path):
            question_id = row["id"]
            for item in top_k_items(row):
                page_key = _add_page(
                    pages,
                    question_id=question_id,
                    raw_url=item["url"],
                    provenance="top5",
                )
                canonical_url = page_key[1]
                top5_page_pairs.add(page_key)
                chunk_id = str(item.get("chunk_id") or "")
                _add_chunk(
                    chunks,
                    chunk_urls,
                    question_id=question_id,
                    canonical_url=canonical_url,
                    chunk_id=chunk_id,
                    content_hash=str(item.get("content_sig") or ""),
                )
                if chunk_id:
                    top5_chunk_pairs.add((question_id, chunk_id))

    with gold_v3_path.open(newline="", encoding="utf-8-sig") as gold_file:
        for row in csv.DictReader(gold_file):
            if row["support_grade"] not in {"full", "partial"}:
                continue
            _add_page(
                pages,
                question_id=row["question_id"],
                raw_url=row["gold_url"],
                provenance="seed_v3",
            )

    exp06_retrieval = {row["id"]: row for row in load_jsonl(exp06_retrieval_path)}
    for row in load_jsonl(exp06_path):
        if row.get("record_type") != "response":
            continue
        question_id = row["id"]
        source_row = exp06_retrieval.get(question_id)
        for item in row.get("evidence", []):
            page_key = _add_page(
                pages,
                question_id=question_id,
                raw_url=item["url"],
                provenance="exp06",
            )
            candidate = recover_exp06_candidate(question_id, item, source_row) if source_row is not None else None
            if candidate is None:
                exp06_source_downgrades += 1
                continue
            exp06_seeds.append(
                Exp06Seed(
                    question_id=question_id,
                    canonical_url=page_key[1],
                    content_hash=str(candidate["content_sig"]),
                )
            )

    return PoolCandidates(
        pages=pages,
        chunks=chunks,
        top5_page_pairs=top5_page_pairs,
        top5_chunk_pairs=top5_chunk_pairs,
        exp06_seeds=exp06_seeds,
        exp06_chunk_pairs=exp06_chunk_pairs,
        exp06_source_downgrades=exp06_source_downgrades,
    )


def recover_exp06_candidate(
    question_id: str,
    evidence_item: dict[str, Any],
    source_row: dict[str, Any],
) -> dict[str, Any] | None:
    """EXP-06의 축약 evidence를 원본 retrieval 청크로 되돌린다."""

    canonical_url = normalize_url(evidence_item.get("url"))
    source_number = evidence_item.get("source_number")
    matches = [
        candidate
        for candidate in source_row.get("evidence_candidates", [])
        if candidate.get("source_number") == source_number and normalize_url(candidate.get("url")) == canonical_url
    ]
    if len(matches) != 1:
        return None
    if evidence_item.get("sig_mismatch") is True:
        return None

    candidate = matches[0]
    chunk_id = str(candidate.get("chunk_id") or "")
    candidate_sig = str(candidate.get("content_sig") or "")
    if not chunk_id or not candidate_sig:
        return None

    retrieved_matches = [
        item for item in source_row.get("retrieved", []) if str(item.get("chunk_id") or "") == chunk_id
    ]
    if len(retrieved_matches) != 1:
        return None
    if str(retrieved_matches[0].get("content_sig") or "") != candidate_sig:
        return None
    return candidate


def validate_frozen_top5(candidates: PoolCandidates) -> None:
    all_pairs = len(candidates.top5_page_pairs)
    insufficient_pairs = sum(
        question_id in INSUFFICIENT_IDS for question_id, _canonical_url in candidates.top5_page_pairs
    )
    unique_urls = len({url for _question_id, url in candidates.top5_page_pairs})
    observed = (insufficient_pairs, all_pairs, unique_urls)
    expected = (
        EXPECTED_INSUFFICIENT_PAIRS,
        EXPECTED_ALL_PAIRS,
        EXPECTED_UNIQUE_URLS,
    )
    if observed != expected:
        raise ValueError(
            "동결 top-5 검증 수치가 다릅니다: "
            f"insufficient={insufficient_pairs}, 전체={all_pairs}, 고유 URL={unique_urls} "
            f"(기대값 {expected})"
        )


async def recover_exp06_chunks(
    candidates: PoolCandidates,
    *,
    dsn: str = DB_DSN,
) -> tuple[int, int]:
    """7/5 signature를 현재 DB의 같은 URL 청크에 대조해 식별자를 복구한다."""

    if not candidates.exp06_seeds:
        return 0, candidates.exp06_source_downgrades

    connection = await asyncpg.connect(dsn)
    try:
        documents = await connection.fetch("SELECT id, url FROM documents")
        document_ids_by_url: dict[str, list[uuid.UUID]] = {}
        for record in documents:
            document_ids_by_url.setdefault(normalize_url(record["url"]), []).append(record["id"])
        wanted_urls = {seed.canonical_url for seed in candidates.exp06_seeds}
        document_ids = [
            document_id for canonical_url in wanted_urls for document_id in document_ids_by_url.get(canonical_url, [])
        ]
        records = []
        if document_ids:
            records = await connection.fetch(
                """
                SELECT c.id, c.content, d.url
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = ANY($1::uuid[]) AND c.content != ''
                """,
                document_ids,
            )
    finally:
        await connection.close()

    records_by_signature: dict[tuple[str, str], list[asyncpg.Record]] = {}
    for record in records:
        key = (normalize_url(record["url"]), content_signature(record["content"]))
        records_by_signature.setdefault(key, []).append(record)

    chunk_urls = {(question_id, chunk_id): canonical_url for question_id, canonical_url, chunk_id in candidates.chunks}
    downgraded = candidates.exp06_source_downgrades
    recovered_seed_count = 0
    for seed in candidates.exp06_seeds:
        matches = records_by_signature.get((seed.canonical_url, seed.content_hash), [])
        if len(matches) != 1:
            downgraded += 1
            continue
        chunk_id = str(matches[0]["id"])
        _add_chunk(
            candidates.chunks,
            chunk_urls,
            question_id=seed.question_id,
            canonical_url=seed.canonical_url,
            chunk_id=chunk_id,
            content_hash=seed.content_hash,
        )
        candidates.exp06_chunk_pairs.add((seed.question_id, chunk_id))
        recovered_seed_count += 1
    return recovered_seed_count, downgraded


async def add_database_seed_chunks(
    candidates: PoolCandidates,
    *,
    dsn: str = DB_DSN,
) -> int:
    """검색 결과에 청크가 없는 seed 페이지를 DB 청크로 보완한다."""

    pages_with_chunks = {(question_id, canonical_url) for question_id, canonical_url, _chunk_id in candidates.chunks}
    missing_page_keys = sorted(
        key for key, page in candidates.pages.items() if "top5" not in page.provenance and key not in pages_with_chunks
    )
    if not missing_page_keys:
        return 0

    connection = await asyncpg.connect(dsn)
    try:
        # URL 표기 차이를 안전하게 흡수하려고 문서 식별자와 URL만 먼저 읽는다.
        documents = await connection.fetch("SELECT id, url FROM documents")
        document_ids_by_url: dict[str, list[uuid.UUID]] = {}
        for record in documents:
            document_ids_by_url.setdefault(normalize_url(record["url"]), []).append(record["id"])

        wanted_urls = {canonical_url for _question_id, canonical_url in missing_page_keys}
        document_ids = [
            document_id for canonical_url in wanted_urls for document_id in document_ids_by_url.get(canonical_url, [])
        ]
        chunk_records = []
        if document_ids:
            chunk_records = await connection.fetch(
                """
                SELECT d.url, c.id, c.content
                FROM document_chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE c.document_id = ANY($1::uuid[]) AND c.content != ''
                ORDER BY d.url, c.chunk_index, c.id
                """,
                document_ids,
            )
    finally:
        await connection.close()

    records_by_url: dict[str, list[asyncpg.Record]] = {}
    for record in chunk_records:
        records_by_url.setdefault(normalize_url(record["url"]), []).append(record)

    missing_without_chunks: list[str] = []
    added = 0
    chunk_urls = {(question_id, chunk_id): canonical_url for question_id, canonical_url, chunk_id in candidates.chunks}
    for question_id, canonical_url in missing_page_keys:
        records = records_by_url.get(canonical_url, [])
        if not records:
            missing_without_chunks.append(f"{question_id}|{canonical_url}")
            continue
        for record in records:
            before = len(candidates.chunks)
            _add_chunk(
                candidates.chunks,
                chunk_urls,
                question_id=question_id,
                canonical_url=canonical_url,
                chunk_id=str(record["id"]),
                content_hash=content_signature(record["content"]),
            )
            added += len(candidates.chunks) - before

    if missing_without_chunks:
        details = "\n".join(f"- {row_id}" for row_id in missing_without_chunks)
        raise ValueError(f"seed 페이지의 DB 청크를 찾지 못했습니다:\n{details}")
    return added


async def validate_exp06_chunks(
    candidates: PoolCandidates,
    *,
    dsn: str = DB_DSN,
) -> None:
    """복구한 EXP-06 청크의 URL과 content_sig를 DB 본문에 대조한다."""

    if not candidates.exp06_chunk_pairs:
        return
    chunk_ids = [uuid.UUID(chunk_id) for _question_id, chunk_id in candidates.exp06_chunk_pairs]
    connection = await asyncpg.connect(dsn)
    try:
        records = await connection.fetch(
            """
            SELECT c.id, c.content, d.url
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.id = ANY($1::uuid[])
            """,
            chunk_ids,
        )
    finally:
        await connection.close()
    actual = {
        str(record["id"]): (
            normalize_url(record["url"]),
            content_signature(record["content"]),
        )
        for record in records
    }

    failures: list[str] = []
    for question_id, chunk_id in sorted(candidates.exp06_chunk_pairs):
        pool_matches = [
            (canonical_url, content_hash)
            for (
                qid,
                canonical_url,
                candidate_chunk_id,
            ), content_hash in candidates.chunks.items()
            if qid == question_id and candidate_chunk_id == chunk_id
        ]
        if len(pool_matches) != 1 or chunk_id not in actual:
            failures.append(f"{question_id}|{chunk_id}: DB 대조 대상 누락")
            continue
        if pool_matches[0] != actual[chunk_id]:
            failures.append(f"{question_id}|{chunk_id}: URL 또는 content_sig 불일치")
    if failures:
        raise ValueError("EXP-06 복구 청크 DB 대조 실패:\n" + "\n".join(f"- {failure}" for failure in failures))


def page_rows(candidates: PoolCandidates) -> list[dict[str, str]]:
    rows = []
    for (question_id, canonical_url), candidate in sorted(candidates.pages.items()):
        provenance = "|".join(value for value in PROVENANCE_ORDER if value in candidate.provenance)
        rows.append(
            {
                "question_id": question_id,
                "canonical_url": canonical_url,
                "provenance": provenance,
                "judged": "false",
                "support_grade": "",
                "temporal_validity": "",
                "audience_scope": "",
                "notes": "",
            }
        )
    return rows


def chunk_rows(candidates: PoolCandidates) -> list[dict[str, str]]:
    return [
        {
            "question_id": question_id,
            "canonical_url": canonical_url,
            "chunk_id": chunk_id,
            "content_hash": content_hash,
            "judged": "false",
            "evidence_grade": "",
            "evidence_type": "",
            "notes": "",
        }
        for (question_id, canonical_url, chunk_id), content_hash in sorted(candidates.chunks.items())
    ]


def write_csv_atomic(
    path: Path,
    *,
    fieldnames: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="qrel v4 판정 pool을 생성합니다.")
    parser.add_argument("--db-dsn", default=DB_DSN, help="청크 전문을 읽을 PostgreSQL DSN")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    candidates = collect_pool_candidates()
    validate_frozen_top5(candidates)
    recovered_exp06, downgraded_exp06 = await recover_exp06_chunks(candidates, dsn=args.db_dsn)
    db_chunk_count = await add_database_seed_chunks(candidates, dsn=args.db_dsn)
    await validate_exp06_chunks(candidates, dsn=args.db_dsn)

    write_csv_atomic(PAGE_POOL_PATH, fieldnames=PAGE_FIELDS, rows=page_rows(candidates))
    write_csv_atomic(CHUNK_POOL_PATH, fieldnames=CHUNK_FIELDS, rows=chunk_rows(candidates))
    write_csv_atomic(TARGET_SOURCES_PATH, fieldnames=TARGET_FIELDS, rows=[])

    insufficient_pairs = sum(
        question_id in INSUFFICIENT_IDS for question_id, _canonical_url in candidates.top5_page_pairs
    )
    unique_urls = len({url for _question_id, url in candidates.top5_page_pairs})
    print(f"insufficient top-5 합집합: {insufficient_pairs}쌍")
    print(f"50문항 top-5 합집합: {len(candidates.top5_page_pairs)}쌍")
    print(f"top-5 고유 URL: {unique_urls}개")
    print(
        f"page pool: {len(candidates.pages)}행, chunk pool: {len(candidates.chunks)}행 "
        f"(DB seed 청크 {db_chunk_count}행 추가)"
    )
    print(f"EXP-06 content_sig 대조: 청크 복구 {recovered_exp06}행, URL seed 강등 {downgraded_exp06}행")
    print(f"저장: {PAGE_POOL_PATH}, {CHUNK_POOL_PATH}, {TARGET_SOURCES_PATH}")


if __name__ == "__main__":
    asyncio.run(run())
