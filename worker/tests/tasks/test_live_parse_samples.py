"""Live parsing samples for representative Phase 2 pages.

Run manually with:
RUN_LIVE_PARSE=1 rtk uv run python -m pytest tests/tasks/test_live_parse_samples.py -s -v
"""

import os
import shutil
from textwrap import shorten

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot",
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARSE") != "1",
    reason="live parsing samples are opt-in; set RUN_LIVE_PARSE=1",
)


def _preview(content: str, width: int = 280) -> str:
    return shorten(" ".join(content.split()), width=width, placeholder=" ...")


def _print_document_summary(label: str, document) -> None:
    chunk_counts: dict[str, int] = {}
    for chunk in document.chunks:
        chunk_counts[chunk.chunk_type] = chunk_counts.get(chunk.chunk_type, 0) + 1

    print(f"\n--- parsed document: {label} ---", flush=True)
    print(f"url: {document.url}", flush=True)
    print(f"menu_path: {document.menu_path}", flush=True)
    print(f"source_type: {document.source_type}", flush=True)
    print(f"content_hash: {document.content_hash}", flush=True)
    print(f"chunks: total={len(document.chunks)} by_type={chunk_counts}", flush=True)

    for chunk in document.chunks[:5]:
        print(
            f"chunk #{chunk.chunk_index:03d} type={chunk.chunk_type} meta={chunk.meta}",
            flush=True,
        )
        print(_preview(chunk.content), flush=True)

    derived_chunks = [
        chunk for chunk in document.chunks if chunk.meta.get("kind") == "semester_roadmap"
    ]
    for chunk in derived_chunks[:3]:
        print(
            f"derived chunk #{chunk.chunk_index:03d} type={chunk.chunk_type} meta={chunk.meta}",
            flush=True,
        )
        print(chunk.content, flush=True)


async def _expand_html_target(target, html: str, *, use_children: bool):
    from tasks.crawl import extract_article_box_targets

    children = extract_article_box_targets(parent=target, html=html)
    if not children:
        print(f"\n--- url expansion: {target.menu_path} ---", flush=True)
        print(f"no articleBox child links; parsing parent: {target.url}", flush=True)
        return [target]

    print(f"\n--- url expansion: {target.menu_path} ---", flush=True)
    print(f"parent excluded: {target.url}", flush=True)
    for index, child in enumerate(children, start=1):
        print(f"{index:02d}. {child.menu_path} | {child.url}", flush=True)

    if use_children:
        return children

    print(f"parsing parent sample only: {target.url}", flush=True)
    return [target]


@pytest.mark.asyncio
async def test_live_parse_representative_html_and_pdf_samples() -> None:
    from tasks.contracts import CrawlTarget
    from tasks.crawl import fetch_html, fetch_pdf_bytes
    from tasks.parse import parse_html, parse_pdf

    html_samples = [
        (
            CrawlTarget(
                url="https://www.honam.ac.kr/AcademicCalendar",
                menu_path="학사일정",
                source_type="html",
                source_scope="general_academic",
                page_kind="academic",
                site_name="호남대학교",
                site_url="https://www.honam.ac.kr",
            ),
            True,
        ),
        (
            CrawlTarget(
                url="https://www.honam.ac.kr/ClassLessonApply",
                menu_path="수강신청",
                source_type="html",
                source_scope="general_academic",
                page_kind="academic",
                site_name="호남대학교",
                site_url="https://www.honam.ac.kr",
            ),
            False,
        ),
        (
            CrawlTarget(
                url="https://com.honam.ac.kr/SubjectRoadmap2026",
                menu_path="컴퓨터공학과 > 교과목로드맵 2026",
                source_type="html",
                source_scope="general_academic",
                page_kind="academic",
                site_name="컴퓨터공학과",
                site_url="https://com.honam.ac.kr",
            ),
            False,
        ),
    ]

    print("\n=== live parse samples ===", flush=True)
    expanded_targets = []
    html_by_url: dict[str, str] = {}
    for target, use_children in html_samples:
        print(f"\nfetch html: {target.url}", flush=True)
        html = fetch_html(target.url)
        html_by_url[target.url] = html
        expanded_targets.extend(await _expand_html_target(target, html, use_children=use_children))

    parsed_html_count = 0
    for target in expanded_targets:
        html = html_by_url.get(target.url)
        if html is None:
            print(f"\nfetch expanded html: {target.url}", flush=True)
            html = fetch_html(target.url)

        document = await parse_html(target=target, html=html)
        _print_document_summary(target.menu_path, document)
        parsed_html_count += 1

    pdf_target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
        menu_path="졸업학점 2025",
        source_type="pdf",
        source_scope="general_academic",
        page_kind="academic",
        title_hint="졸업학점 2025",
        year=2025,
        site_name="호남대학교",
        site_url="https://www.honam.ac.kr",
    )
    print(f"\nfetch pdf: {pdf_target.url}", flush=True)
    pdf_bytes = fetch_pdf_bytes(pdf_target.url)
    if shutil.which("java") is None:
        print(f"pdf bytes downloaded: {len(pdf_bytes)}", flush=True)
        pytest.xfail("PDF parser dependency is missing: java")

    pdf_document = await parse_pdf(target=pdf_target, pdf_bytes=pdf_bytes)
    _print_document_summary(pdf_target.menu_path, pdf_document)

    assert parsed_html_count >= 3
    assert pdf_document.chunks
