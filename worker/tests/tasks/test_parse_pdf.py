from datetime import UTC, datetime

import pytest
from langchain_core.documents import Document

from tasks.contracts import CrawlTarget
from tasks.parse import parse_pdf


@pytest.mark.asyncio
async def test_parse_pdf_preserves_chunk_order_within_page():
    def fake_loader(pdf_path: str) -> list[Document]:
        return [
            Document(
                page_content=(
                    "서론 문장입니다.\n\n"
                    "|구분|학점|\n|---|---|\n|총계|130|\n\n"
                    "결론 문장입니다."
                ),
                metadata={"page": 1},
            )
        ]

    target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2024",
        menu_path="졸업학점 2024",
        source_type="pdf",
        year=2024,
    )

    document = await parse_pdf(
        target=target,
        pdf_bytes=b"%PDF-1.4 sample",
        file_loader=fake_loader,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    assert document.source_type == "pdf"
    assert document.content_hash
    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "table", "text"]
    assert document.chunks[0].content == "서론 문장입니다."
    assert document.chunks[1].content == "|구분|학점|\n|---|---|\n|총계|130|"
    assert document.chunks[2].content == "결론 문장입니다."
    assert [chunk.meta["page"] for chunk in document.chunks] == [1, 1, 1]


@pytest.mark.asyncio
async def test_parse_pdf_preserves_page_metadata_across_pages():
    def fake_loader(pdf_path: str) -> list[Document]:
        return [
            Document(
                page_content="1페이지 첫 문장입니다.",
                metadata={"page": 1},
            ),
            Document(
                page_content=(
                    "2페이지 시작입니다.\n\n"
                    "|구분|학점|\n|---|---|\n|총계|130|"
                ),
                metadata={"page": 2},
            ),
        ]

    target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2024",
        menu_path="졸업학점 2024",
        source_type="pdf",
        year=2024,
    )

    document = await parse_pdf(
        target=target,
        pdf_bytes=b"%PDF-1.4 sample",
        file_loader=fake_loader,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    assert [chunk.chunk_type for chunk in document.chunks] == ["text", "text", "table"]
    assert [chunk.meta["page"] for chunk in document.chunks] == [1, 2, 2]
    assert document.chunks[0].content == "1페이지 첫 문장입니다."
    assert document.chunks[1].content == "2페이지 시작입니다."
    assert document.chunks[2].content == "|구분|학점|\n|---|---|\n|총계|130|"
