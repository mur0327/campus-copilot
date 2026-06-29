"""Crawl pipeline orchestrator and CLI.

run_crawl()이 discovery→fetch→parse→save→index를 한 번에 돌던 것을, 다시 돌릴
phase만 골라 실행할 수 있게 묶는 얇은 오케스트레이터다. 실제 작업은 tasks.crawl의
discovery/execute_ingestion이 하고, 여기서는 어떤 구간을 돌릴지 결정한다.

phase 구간:
- discover: 네트워크 discovery로 대상 URL을 수집한다(느림).
- parse:    fetch→diff→parse→save. --from parse면 네트워크 없이 fetch 캐시로 재파싱한다.
- index:    임베딩 + BM25 재색인.

--from parse는 기존에 저장된 활성 문서를 대상으로(네트워크 discovery 없이) fetch 캐시를
cache_first로 읽어 재파싱한다. 파서 개선(parser_version 범프)을 코퍼스에 싸게 반영하는 길이다.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from enum import IntEnum

from core.db import create_pool
from tasks import crawl
from tasks.contracts import CrawlStats, CrawlTarget
from tasks.crawl import ProgressCallback
from tasks.storage import load_reparse_html_targets

logger = logging.getLogger(__name__)


class Phase(IntEnum):
    DISCOVER = 1
    PARSE = 2
    INDEX = 3


_PHASE_BY_NAME = {phase.name.lower(): phase for phase in Phase}


def parse_phase(name: str) -> Phase:
    try:
        return _PHASE_BY_NAME[name.lower()]
    except KeyError:
        choices = ", ".join(_PHASE_BY_NAME)
        raise ValueError(f"unknown phase {name!r}; choose from {choices}") from None


async def _resolve_targets(
    start: Phase,
    progress_callback: ProgressCallback | None = None,
) -> tuple[list[CrawlTarget], list[CrawlTarget], list[str]]:
    """start phase에 맞는 (html, pdf, 초기 실패) 대상을 구한다."""
    if start <= Phase.DISCOVER:
        html_discovery, pdf_targets = await asyncio.gather(
            crawl.discover_html_targets_with_failures(progress_callback=progress_callback),
            crawl.discover_pdf_targets(progress_callback=progress_callback),
        )
        html_targets, pdf_targets = crawl.apply_crawl_target_limit(
            html_discovery.targets,
            pdf_targets,
        )
        return html_targets, pdf_targets, list(html_discovery.failures)

    if start <= Phase.PARSE:
        # parse부터 시작하면 네트워크 discovery 없이 기존 HTML 문서를 캐시로 재파싱한다.
        # (충실히 복원 가능한 HTML만 — PDF/학과 페이지 제외, storage 주석 참고.)
        pool = await create_pool()
        try:
            async with pool.acquire() as connection:
                html_targets = await load_reparse_html_targets(connection)
        finally:
            await pool.close()
        return html_targets, [], []

    # index만 다시 돌릴 때는 대상이 필요 없다(이미 저장된 pending chunk를 색인).
    return [], [], []


async def run_pipeline(
    *,
    start: Phase = Phase.DISCOVER,
    end: Phase = Phase.INDEX,
    force: bool = False,
    dry_run: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> CrawlStats:
    if start > end:
        raise ValueError(f"start phase {start.name} must not come after end phase {end.name}")

    html_targets, pdf_targets, failures = await _resolve_targets(start, progress_callback)
    logger.info(
        "pipeline resolved targets: start=%s end=%s html=%s pdf=%s force=%s dry_run=%s",
        start.name.lower(),
        end.name.lower(),
        len(html_targets),
        len(pdf_targets),
        force,
        dry_run,
    )

    if dry_run:
        # 대상만 확인하고 어떤 변경도 하지 않는다.
        return CrawlStats(
            pages_crawled=len(html_targets) + len(pdf_targets),
            failures=failures,
        )

    process_documents = start <= Phase.PARSE <= end
    index_documents = start <= Phase.INDEX <= end

    # parse부터 시작하는 재처리는 네트워크 대신 캐시를 읽는다(cache_first).
    # 강제 재파싱은 하지 않는다 — parser_version이 content_hash에 들어가 v3 범프만으로
    # 이미 전부 재파싱되고, 이미 최신인 문서는 건너뛰는 게 맞다. 명시 --force만 강제한다.
    reparse_from_cache = process_documents and start >= Phase.PARSE
    fetch_cache_mode = "cache_first" if reparse_from_cache else None
    return await crawl.execute_ingestion(
        html_targets,
        pdf_targets,
        initial_failures=failures,
        process_documents=process_documents,
        index_documents=index_documents,
        force=force,
        fetch_cache_mode=fetch_cache_mode,
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tasks.pipeline",
        description="Run selected crawl phases (discover → parse → index).",
    )
    parser.add_argument(
        "--from",
        dest="start",
        default="discover",
        help="시작 phase (discover|parse|index). 기본 discover.",
    )
    parser.add_argument(
        "--to",
        dest="end",
        default="index",
        help="끝 phase (discover|parse|index). 기본 index.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="변경이 없어도 전부 재파싱(parser 개선 반영용).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="대상만 확인하고 아무 것도 바꾸지 않는다.",
    )
    return parser


async def _main(argv: list[str] | None = None) -> CrawlStats:
    args = _build_arg_parser().parse_args(argv)
    start = parse_phase(args.start)
    end = parse_phase(args.end)
    stats = await run_pipeline(start=start, end=end, force=args.force, dry_run=args.dry_run)
    logger.info(
        "pipeline finished: skipped=%s pages_crawled=%s pages_changed=%s failures=%s",
        stats.skipped,
        stats.pages_crawled,
        stats.pages_changed,
        len(stats.failures),
    )
    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
