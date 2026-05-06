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
    assert document.chunks[1].content == "구분: 총계 | 학점: 130"
    assert document.chunks[2].content == "결론 문장입니다."
    assert [chunk.meta["page"] for chunk in document.chunks] == [1, 1, 1]
    assert [chunk.meta["year"] for chunk in document.chunks] == [2024, 2024, 2024]
    assert [chunk.meta["source_filename"] for chunk in document.chunks] == [
        "2024.pdf",
        "2024.pdf",
        "2024.pdf",
    ]


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
    assert document.chunks[2].content == "구분: 총계 | 학점: 130"


@pytest.mark.asyncio
async def test_parse_pdf_normalizes_markdown_table_metadata_and_content():
    def fake_loader(pdf_path: str) -> list[Document]:
        return [
            Document(
                page_content=(
                    "|대학|학과|졸업학점|\n"
                    "|---|---|---|\n"
                    "|사회경영대학|사회복지학과|120|\n"
                    "|AI융합대학|컴퓨터공학과|120|"
                ),
                metadata={"page": 3},
            )
        ]

    target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
        menu_path="졸업학점 2025",
        source_type="pdf",
        year=2025,
    )

    document = await parse_pdf(
        target=target,
        pdf_bytes=b"%PDF-1.4 sample",
        file_loader=fake_loader,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    table_chunk = document.chunks[0]

    assert table_chunk.chunk_type == "table"
    assert table_chunk.content == (
        "대학: 사회경영대학 | 학과: 사회복지학과 | 졸업학점: 120\n"
        "대학: AI융합대학 | 학과: 컴퓨터공학과 | 졸업학점: 120"
    )
    assert table_chunk.meta == {
        "source_filename": "2025.pdf",
        "year": 2025,
        "page": 3,
        "headers": ["대학", "학과", "졸업학점"],
        "records": [
            {"대학": "사회경영대학", "학과": "사회복지학과", "졸업학점": "120"},
            {"대학": "AI융합대학", "학과": "컴퓨터공학과", "졸업학점": "120"},
        ],
    }


@pytest.mark.asyncio
async def test_parse_graduation_credit_pdf_expands_multi_level_headers_and_merged_cells():
    def fake_loader(pdf_path: str) -> list[Document]:
        header = (
            "|대학|학과(부)|교양영역||||전공영역|"
            "자유선택 (교직, 타학과 전공, 교양)|졸업 이수 학점|\n"
        )
        return [
            Document(
                page_content=(
                    header +
                    "|---|---|---|---|---|---|---|---|---|\n"
                    "|||핵심 교양|균형 교양|소양 교양|소계|전공선택|||\n"
                    "|사회 경영 대학|경영학부<br><br>경영학전공 무역학전공|12|9|9|30|60|30|120|\n"
                    "||관광경영학과|12|9|9|30|60|30|120|\n"
                    "||호텔컨벤션학과★|12|9|9|30|60|30|120|"
                ),
                metadata={"page": 1},
            )
        ]

    target = CrawlTarget(
        url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
        menu_path="졸업학점 2025",
        source_type="pdf",
        year=2025,
    )

    document = await parse_pdf(
        target=target,
        pdf_bytes=b"%PDF-1.4 sample",
        file_loader=fake_loader,
        crawled_at=datetime(2026, 4, 19, tzinfo=UTC),
    )

    table_chunk = document.chunks[0]

    assert table_chunk.meta["headers"] == [
        "대학",
        "학과(부)",
        "교양영역 핵심교양",
        "교양영역 균형교양",
        "교양영역 소양교양",
        "교양영역 소계",
        "전공영역 전공선택",
        "자유선택 (교직, 타학과 전공, 교양)",
        "졸업 이수 학점",
    ]
    assert table_chunk.meta["records"] == [
        {
            "대학": "사회 경영 대학",
            "학과(부)": "경영학부 / 경영학전공 / 무역학전공",
            "교양영역 핵심교양": "12",
            "교양영역 균형교양": "9",
            "교양영역 소양교양": "9",
            "교양영역 소계": "30",
            "전공영역 전공선택": "60",
            "자유선택 (교직, 타학과 전공, 교양)": "30",
            "졸업 이수 학점": "120",
        },
        {
            "대학": "사회 경영 대학",
            "학과(부)": "관광경영학과",
            "교양영역 핵심교양": "12",
            "교양영역 균형교양": "9",
            "교양영역 소양교양": "9",
            "교양영역 소계": "30",
            "전공영역 전공선택": "60",
            "자유선택 (교직, 타학과 전공, 교양)": "30",
            "졸업 이수 학점": "120",
        },
        {
            "대학": "사회 경영 대학",
            "학과(부)": "호텔컨벤션학과★",
            "교양영역 핵심교양": "12",
            "교양영역 균형교양": "9",
            "교양영역 소양교양": "9",
            "교양영역 소계": "30",
            "전공영역 전공선택": "60",
            "자유선택 (교직, 타학과 전공, 교양)": "30",
            "졸업 이수 학점": "120",
        },
    ]
    assert "학과(부): 호텔컨벤션학과★" in table_chunk.content
    assert "교양영역 핵심교양: 12" in table_chunk.content
