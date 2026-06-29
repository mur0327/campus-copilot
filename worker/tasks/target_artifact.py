"""Filesystem artifact for the validated crawl target list.

discovery가 만든 검증된 CrawlTarget 목록을 JSON 한 파일로 저장한다. 이걸 저장해 두면
`--from parse` 재파싱이 네트워크 discovery를 다시 돌리지 않고도, year/site_name/site_url
같은 discovery 시점 메타까지 충실히 복원해 전체 코퍼스를 재처리할 수 있다.

원자적 쓰기는 fetch 캐시와 동일한 헬퍼를 재사용한다(동시 discover/parse가 잘린 파일을
보지 않도록 temp+rename).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from tasks.contracts import CrawlTarget
from tasks.fetch_cache import atomic_write_bytes


def write_targets(path: Path, targets: list[CrawlTarget]) -> None:
    payload = json.dumps([asdict(target) for target in targets], ensure_ascii=False)
    atomic_write_bytes(path, payload.encode("utf-8"))


def read_targets(path: Path) -> list[CrawlTarget]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        return [CrawlTarget(**item) for item in raw]
    except TypeError as exc:
        # 필드가 바뀐 옛 artifact 등 스키마 불일치를 친절히 알린다.
        raise ValueError(
            f"target artifact at {path} does not match the current CrawlTarget schema; "
            f"regenerate it with a full discover (python -m tasks.pipeline --from discover)"
        ) from exc
