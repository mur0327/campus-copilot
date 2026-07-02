import json
import pickle
import re
from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from rank_bm25 import BM25Okapi

TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")

BM25_WATERMARK_SQL = "SELECT max(created_at) FROM document_chunks"

BM25_ACTIVE_CHUNKS_SQL = """
SELECT
    c.id AS chunk_id,
    c.document_id,
    c.content,
    c.chunk_type,
    c.chunk_index,
    c.meta,
    d.url,
    d.title,
    d.menu_path,
    d.category,
    d.source_scope,
    d.page_kind,
    d.crawled_at
FROM document_chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.is_active = TRUE
  AND c.content <> ''
ORDER BY d.crawled_at DESC NULLS LAST, c.created_at ASC
"""


@dataclass(slots=True)
class BM25BuildSummary:
    chunks_seen: int = 0
    indexes_written: int = 0


def tokenize_korean_light(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def search_index_text(title: str | None, menu_path: str | None, content: str) -> str:
    """검색 색인 입력 텍스트를 만든다(BM25 토큰화와 임베딩 입력 공통 규칙).

    청크 본문만으로는 "무엇에 대한 답인지"가 벡터/토큰에 실리지 않는다. 문서 제목과
    메뉴 경로를 앞에 붙여 주제 맥락을 준다. 표시용 content는 바꾸지 않는다.
    (backend retriever의 BM25Index 폴백 경로와 같은 규칙을 유지할 것.)
    """
    context = "\n".join(part for part in (title, menu_path) if part)
    return f"{context}\n{content}" if context else content


def build_bm25_cache_path(cache_dir: str | Path, category: str | None) -> Path:
    category_key = category if category is not None else "_all"
    digest = sha256(category_key.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"bm25-{digest}.pkl"


async def write_bm25_indexes(connection, cache_dir: str | Path) -> BM25BuildSummary:
    watermark = await connection.fetchval(BM25_WATERMARK_SQL)
    rows = await connection.fetch(BM25_ACTIVE_CHUNKS_SQL)
    summary = BM25BuildSummary(chunks_seen=len(rows))
    grouped_rows: dict[str | None, list[object]] = defaultdict(list)
    grouped_rows[None].extend(rows)
    for row in rows:
        category = row["category"]
        if category is not None:
            grouped_rows[category].append(row)

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    for category, category_rows in grouped_rows.items():
        _write_bm25_index(cache_dir, category, watermark, category_rows)
        summary.indexes_written += 1
    return summary


def _write_bm25_index(
    cache_dir: str | Path,
    category: str | None,
    watermark,
    rows: list[object],
) -> None:
    records = [_row_to_record(row) for row in rows]
    corpus = [
        tokenize_korean_light(
            search_index_text(record["title"], record["menu_path"], record["content"])
        )
        for record in records
    ]
    index = BM25Okapi(corpus) if any(corpus) else None
    cache_path = build_bm25_cache_path(cache_dir, category)
    with cache_path.open("wb") as cache_file:
        pickle.dump(
            {
                "version": 1,
                "watermark": watermark,
                "category": category,
                "records": records,
                "corpus": corpus,
                "index": index,
            },
            cache_file,
        )


def _row_to_record(row) -> dict:
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "content": row["content"],
        "chunk_type": row["chunk_type"],
        "chunk_index": _row_value(row, "chunk_index", 0),
        "score": 0,
        "title": row["title"],
        "url": row["url"],
        "menu_path": row["menu_path"],
        "category": row["category"],
        "source_scope": _row_value(row, "source_scope", "unknown"),
        "page_kind": _row_value(row, "page_kind", "unknown"),
        "crawled_at": row["crawled_at"],
        "meta": _normalize_jsonb_meta(row["meta"]),
    }


def _row_value(row, key: str, default):
    try:
        return row[key]
    except KeyError:
        return default


def _normalize_jsonb_meta(value):
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None
    return None
