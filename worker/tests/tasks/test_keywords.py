import pytest

from tasks.keywords import (
    MAX_KEYWORDS,
    build_keyword_prompt,
    filter_keywords,
    format_keywords,
    generate_document_keywords,
    generate_missing_keywords,
    parse_keyword_response,
)


def test_parse_keyword_response_extracts_json_array():
    assert parse_keyword_response('["여름방학", "겨울방학"]') == ["여름방학", "겨울방학"]


def test_parse_keyword_response_handles_code_fence_and_prose():
    raw = "다음과 같습니다:\n```json\n[\"방학\", \"개강\"]\n```"
    assert parse_keyword_response(raw) == ["방학", "개강"]


def test_parse_keyword_response_returns_empty_on_garbage_or_non_array():
    assert parse_keyword_response("죄송합니다 모르겠어요") == []
    assert parse_keyword_response('{"a": 1}') == []
    assert parse_keyword_response("") == []


def test_filter_keywords_drops_terms_already_in_content():
    # "계절학기"는 본문에 이미 있으니 주입 불필요, "방학"만 남아야 한다.
    content = "동계 계절학기 12-29 운영, 3월 개강일"
    assert filter_keywords(["방학", "계절학기"], content) == ["방학"]


def test_filter_keywords_drops_generic_and_duplicates_and_caps():
    keywords = ["안내", "방학", "방학", *[f"단어{i}" for i in range(20)]]
    result = filter_keywords(keywords, content="본문")
    assert "안내" not in result
    assert result.count("방학") == 1
    assert len(result) <= MAX_KEYWORDS


def test_build_keyword_prompt_truncates_long_content_and_includes_title():
    prompt = build_keyword_prompt("학사일정", "학사 > 일정", "가" * 10000)
    assert "학사일정" in prompt
    assert len(prompt) < 6000


@pytest.mark.asyncio
async def test_generate_document_keywords_filters_llm_output():
    async def fake_generate(_prompt: str) -> str:
        return '["방학", "계절학기"]'

    # 본문에 "계절학기"가 있으니 걸러지고 "방학"만 남아 문자열로 합쳐진다.
    result = await generate_document_keywords(
        fake_generate, "학사일정", None, "동계 계절학기 운영"
    )
    assert result == "방학"


@pytest.mark.asyncio
async def test_generate_missing_keywords_skips_when_generate_is_none():
    class DummyConnection:
        async def fetch(self, *_args):  # pragma: no cover - 호출되면 안 된다
            raise AssertionError("should not query when aux llm is unconfigured")

    summary = await generate_missing_keywords(DummyConnection(), generate=None)
    assert summary.documents_seen == 0
    assert summary.documents_updated == 0


def test_format_keywords_joins_with_space():
    assert format_keywords(["여름방학", "겨울방학"]) == "여름방학 겨울방학"
