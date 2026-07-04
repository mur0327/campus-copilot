"""문서 확장: 어휘 갭 보완용 검색 키워드를 보조 LLM으로 생성한다.

정답 문서가 쓰는 어휘와 사용자 질의 어휘가 어긋나 키워드 매칭이 안 되는 recall 갭
(방학↔계절학기 등)을 메운다. 문서를 읽고 "본문에 없지만 이 문서가 답하는" 검색어를
소량 생성해 documents.search_keywords에 저장한다. BM25 색인 입력에만 얹어 dense는 안 건드린다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 생성 대상: 활성 + 아직 키워드 없음(NULL) 문서만(일회성). 문서 단위로 본문을 이어붙인다.
KEYWORD_TARGET_SQL = """
SELECT
    d.id AS document_id,
    d.title,
    d.menu_path,
    string_agg(c.content, E'\n' ORDER BY c.chunk_index) AS content
FROM documents d
JOIN document_chunks c ON c.document_id = d.id
WHERE d.is_active = TRUE
  AND d.search_keywords IS NULL
  AND c.content <> ''
GROUP BY d.id, d.title, d.menu_path
"""

KEYWORD_UPDATE_SQL = "UPDATE documents SET search_keywords = $2 WHERE id = $1"

MAX_KEYWORDS = 8
MAX_CONTENT_CHARS = 4000  # 긴 문서는 앞부분만(키워드 추출엔 충분, 토큰 절약)
KEYWORD_CHUNK_SIZE = 50  # LLM 호출 묶음 단위(묶음마다 DB에 기록해 진행을 보존)
# 지나치게 일반적이라 검색 변별력이 없는 말은 버린다.
GENERIC_KEYWORDS = frozenset(
    {"안내", "정보", "문서", "페이지", "내용", "관련", "대학", "대학교", "호남대학교", "호남대"}
)
_TERM_RE = re.compile(r"[0-9A-Za-z가-힣]+")

PROMPT_TEMPLATE = """너는 대학 학사 문서의 검색 키워드를 뽑는 도구다.
아래 문서를 학생이 검색창에서 찾을 때 칠 법한 핵심어 중에서,
**문서 본문에 글자 그대로 나오지 않는 단어만** 골라라.

규칙:
- 본문 내용이 명확히 뒷받침하는 것만. 추측하거나 지어내지 마라.
- 이미 본문에 있는 단어는 넣지 마라.
- 짧은 명사/명사구만. 문장·조사·어미 금지.
- 최대 {max_keywords}개. 넣을 게 없으면 빈 배열 [].
- 출력은 JSON 배열만. 예: ["여름방학", "겨울방학"]

제목: {title}
메뉴: {menu_path}
본문:
{content}
"""

# 보조 LLM 호출 함수: 프롬프트를 받아 원문 응답 문자열을 돌려준다.
GenerateFn = Callable[[str], Awaitable[str]]


@dataclass(slots=True)
class KeywordBuildSummary:
    documents_seen: int = 0
    documents_updated: int = 0
    documents_empty: int = 0
    errors: list[str] = field(default_factory=list)


def build_keyword_prompt(title: str | None, menu_path: str | None, content: str | None) -> str:
    return PROMPT_TEMPLATE.format(
        max_keywords=MAX_KEYWORDS,
        title=title or "",
        menu_path=menu_path or "",
        content=(content or "")[:MAX_CONTENT_CHARS],
    )


def parse_keyword_response(raw: str | None) -> list[str]:
    """LLM 응답에서 JSON 배열을 뽑아 문자열 리스트로 만든다. 실패 시 빈 리스트."""
    if not raw:
        return []
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item).strip() for item in data if str(item).strip()]


def _terms(text: str | None) -> set[str]:
    return {token.lower() for token in _TERM_RE.findall(text or "")}


def filter_keywords(keywords: list[str], content: str | None) -> list[str]:
    """이미 본문에 있는 단어·일반어·중복을 제거하고 상한을 건다(순수 주입만 남긴다)."""
    present = _terms(content)
    seen: set[str] = set()
    result: list[str] = []
    for keyword in keywords:
        normalized = keyword.strip()
        if not normalized or normalized in GENERIC_KEYWORDS:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        # 키워드의 모든 토큰이 이미 본문에 있으면 주입할 필요가 없다(중복).
        tokens = _terms(normalized)
        if tokens and tokens <= present:
            continue
        seen.add(lowered)
        result.append(normalized)
        if len(result) >= MAX_KEYWORDS:
            break
    return result


def format_keywords(keywords: list[str]) -> str:
    return " ".join(keywords)


def create_aux_generate(provider: str, model: str, api_key: str) -> GenerateFn | None:
    """보조 LLM 호출 함수를 만든다. 키가 없거나 미지원 프로바이더면 None(생성 스킵)."""
    if provider == "gemini":
        if not api_key.strip():
            return None
        from google import genai

        client = genai.Client(api_key=api_key)

        async def generate(prompt: str) -> str:
            response = await client.aio.models.generate_content(model=model, contents=prompt)
            return response.text or ""

        return generate

    logger.warning("aux llm provider not supported for keyword generation: %s", provider)
    return None


async def generate_document_keywords(
    generate: GenerateFn,
    title: str | None,
    menu_path: str | None,
    content: str | None,
) -> str:
    """단일 문서의 키워드 문자열을 생성한다(빈 문자열 가능=넣을 게 없음)."""
    raw = await generate(build_keyword_prompt(title, menu_path, content))
    return format_keywords(filter_keywords(parse_keyword_response(raw), content))


async def generate_missing_keywords(
    connection,
    *,
    generate: GenerateFn | None,
    concurrency: int = 8,
) -> KeywordBuildSummary:
    """활성+키워드 없음 문서에 검색 키워드를 채운다. generate가 None이면 우아하게 스킵한다."""
    summary = KeywordBuildSummary()
    if generate is None:
        logger.info("keyword generation skipped: aux llm not configured")
        return summary

    rows = await connection.fetch(KEYWORD_TARGET_SQL)
    summary.documents_seen = len(rows)
    if not rows:
        return summary

    semaphore = asyncio.Semaphore(concurrency)

    async def build(row) -> tuple[object, str | None, str | None]:
        # LLM 호출만 동시에 한다(DB 쓰기는 단일 커넥션이라 뒤에서 순차 처리).
        async with semaphore:
            try:
                keywords = await generate_document_keywords(
                    generate, row["title"], row["menu_path"], row["content"]
                )
            except Exception as exc:  # noqa: BLE001 - 개별 문서 실패는 전체를 막지 않는다
                return row["document_id"], None, type(exc).__name__
            return row["document_id"], keywords, None

    for start in range(0, len(rows), KEYWORD_CHUNK_SIZE):
        chunk = rows[start : start + KEYWORD_CHUNK_SIZE]
        results = await asyncio.gather(*(build(row) for row in chunk))
        for document_id, keywords, error in results:
            if error is not None:
                # 실패한 문서는 NULL로 남겨 다음 실행에서 재시도한다.
                summary.errors.append(f"{document_id}: {error}")
                continue
            await connection.execute(KEYWORD_UPDATE_SQL, document_id, keywords)
            if keywords:
                summary.documents_updated += 1
            else:
                summary.documents_empty += 1

    logger.info(
        "keyword generation completed: seen=%s updated=%s empty=%s errors=%s",
        summary.documents_seen,
        summary.documents_updated,
        summary.documents_empty,
        len(summary.errors),
    )
    return summary
