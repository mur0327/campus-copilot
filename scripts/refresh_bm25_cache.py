"""Refresh BM25 cache files from the current local database."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = REPO_ROOT / "worker"
DEFAULT_CACHE_DIR = REPO_ROOT / ".data" / "bm25"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh BM25 cache files from current document_chunks data.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="BM25 cache output directory.",
    )
    parser.add_argument(
        "--local-services",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use localhost PostgreSQL defaults for the repo-level docker compose data.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing bm25-*.pkl files before writing new cache files.",
    )
    return parser.parse_args()


def configure_runtime_env(*, local_services: bool, cache_dir: Path) -> None:
    # worker 설정 객체는 import 시점에 환경변수를 읽는다.
    # 따라서 worker 모듈을 import하기 전에 로컬 실행 기준 값을 먼저 주입한다.
    if local_services:
        os.environ["DATABASE_URL"] = "postgresql://campus:campus@localhost:5432/campus_copilot"

    os.environ["BM25_CACHE_DIR"] = str(cache_dir)

    # worker는 package root가 worker/라서 repo root에서 실행할 때 import path를 보강한다.
    sys.path.insert(0, str(WORKER_ROOT))


async def run() -> None:
    args = parse_args()
    configure_runtime_env(local_services=args.local_services, cache_dir=args.cache_dir)

    # worker imports must happen after configure_runtime_env().
    # 기존 worker BM25 작성 함수를 그대로 사용해 cache format drift를 피한다.
    from core.db import create_pool
    from tasks.bm25 import write_bm25_indexes

    # Docker worker가 만든 기존 캐시 파일은 host에서 덮어쓸 권한이 없을 수 있다.
    # BM25 캐시는 재생성 가능한 산출물이므로 기본 동작은 기존 pickle 파일을 제거한 뒤 다시 쓰는 것이다.
    if not args.keep_existing:
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        for cache_file in args.cache_dir.glob("bm25-*.pkl"):
            cache_file.unlink()

    pool = await create_pool()
    try:
        async with pool.acquire() as connection:
            summary = await write_bm25_indexes(connection, args.cache_dir)
    finally:
        await pool.close()

    print(f"cache_dir: {args.cache_dir}")
    print(f"chunks_seen: {summary.chunks_seen}")
    print(f"indexes_written: {summary.indexes_written}")


if __name__ == "__main__":
    asyncio.run(run())
