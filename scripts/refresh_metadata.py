"""Refresh source_scope/page_kind metadata and derived search indexes."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = REPO_ROOT / "worker"
DEFAULT_BM25_CACHE_DIR = REPO_ROOT / ".data" / "bm25"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh document search metadata without refetching source pages.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned document metadata changes without writing DB, Chroma, or BM25.",
    )
    parser.add_argument(
        "--include-inactive",
        action="store_true",
        help="Include inactive documents when recalculating DB metadata.",
    )
    parser.add_argument(
        "--skip-chroma",
        action="store_true",
        help="Skip Chroma metadata updates.",
    )
    parser.add_argument(
        "--skip-bm25",
        action="store_true",
        help="Skip BM25 cache rewrite.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Chroma metadata update batch size.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Retries for a failed Chroma metadata update batch.",
    )
    parser.add_argument(
        "--bm25-cache-dir",
        type=Path,
        default=DEFAULT_BM25_CACHE_DIR,
        help="BM25 cache output directory.",
    )
    parser.add_argument(
        "--local-services",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use localhost service defaults for the repo-level docker compose data.",
    )
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than 0")
    if args.max_retries < 0:
        parser.error("--max-retries must be greater than or equal to 0")
    return args


def configure_runtime_env(*, local_services: bool, bm25_cache_dir: Path) -> None:
    # worker 설정 객체는 import 시점에 환경변수를 읽는다.
    # 따라서 worker 모듈을 import하기 전에 로컬 실행 기준 값을 먼저 주입한다.
    if local_services:
        os.environ["DATABASE_URL"] = "postgresql://campus:campus@localhost:5432/campus_copilot"
        os.environ["CHROMA_HOST"] = "localhost"
        os.environ["CHROMA_PORT"] = "8001"

    os.environ["BM25_CACHE_DIR"] = str(bm25_cache_dir)
    sys.path.insert(0, str(WORKER_ROOT))


def print_summary(summary) -> None:
    print(f"dry_run: {summary.dry_run}")
    print(f"documents_seen: {summary.documents_seen}")
    print(f"documents_changed: {summary.documents_changed}")
    print(f"documents_unchanged: {summary.documents_unchanged}")
    print(f"chroma_skipped: {summary.chroma_skipped}")
    print(f"chroma_chunks_seen: {summary.chroma.chunks_seen}")
    print(f"chroma_chunks_updated: {summary.chroma.chunks_updated}")
    print(f"chroma_chunks_missing: {summary.chroma.chunks_missing}")
    print(f"chroma_batches_seen: {summary.chroma.batches_seen}")
    print(f"chroma_batches_failed: {summary.chroma.batches_failed}")
    if summary.chroma.missing_ids:
        print("chroma_missing_ids:")
        for chroma_id in summary.chroma.missing_ids[:50]:
            print(f"- {chroma_id}")
        if len(summary.chroma.missing_ids) > 50:
            print(f"- ... {len(summary.chroma.missing_ids) - 50} more")
    if summary.chroma.errors:
        print("chroma_errors:")
        for error in summary.chroma.errors:
            print(f"- {error}")
    print(f"bm25_skipped: {summary.bm25_skipped}")
    print(f"bm25_chunks_seen: {summary.bm25.chunks_seen if summary.bm25 else 0}")
    print(f"bm25_indexes_written: {summary.bm25.indexes_written if summary.bm25 else 0}")
    print(f"failed: {summary.failed}")


async def run() -> int:
    args = parse_args()
    configure_runtime_env(
        local_services=args.local_services,
        bm25_cache_dir=args.bm25_cache_dir,
    )

    # worker imports must happen after configure_runtime_env().
    from core.db import create_pool
    from tasks.metadata import refresh_search_metadata

    pool = await create_pool()
    try:
        async with pool.acquire() as connection:
            summary = await refresh_search_metadata(
                connection,
                include_inactive=args.include_inactive,
                dry_run=args.dry_run,
                skip_chroma=args.skip_chroma,
                skip_bm25=args.skip_bm25,
                batch_size=args.batch_size,
                max_retries=args.max_retries,
                bm25_cache_dir=args.bm25_cache_dir,
            )
    finally:
        await pool.close()

    print_summary(summary)
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
