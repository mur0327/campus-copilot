"""Filesystem cache for fetched page sources.

크롤 페이즈 분리의 첫 단계다. fetch 단계가 받은 원본 HTML/PDF를 URL 해시로
파일에 저장해 두면, parse/index를 다시 돌릴 때 네트워크 재요청 없이 재사용할 수 있다.
설정에 의존하지 않는 순수 함수로 두어 단위 테스트가 쉽도록 한다.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

HTML_SUFFIX = ".html"
BYTES_SUFFIX = ".bin"


def cache_key(url: str) -> str:
    # URL을 그대로 파일명에 쓰면 길이/특수문자 문제가 있으므로 해시로 주소화한다.
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _path(cache_dir: Path, url: str, suffix: str) -> Path:
    return cache_dir / f"{cache_key(url)}{suffix}"


def _atomic_write(path: Path, data: bytes) -> None:
    # 같은 디렉터리에 임시 파일로 쓴 뒤 rename해서, 동시 reader가 잘린 파일을 보지 않게 한다.
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(data)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def read_html(cache_dir: Path, url: str) -> str | None:
    path = _path(cache_dir, url, HTML_SUFFIX)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        # 동시 write 중이거나 깨진 파일이면 cache miss로 처리해 네트워크 폴백을 유도한다.
        return None


def write_html(cache_dir: Path, url: str, html: str) -> None:
    _atomic_write(_path(cache_dir, url, HTML_SUFFIX), html.encode("utf-8"))


def read_bytes(cache_dir: Path, url: str) -> bytes | None:
    path = _path(cache_dir, url, BYTES_SUFFIX)
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def write_bytes(cache_dir: Path, url: str, data: bytes) -> None:
    _atomic_write(_path(cache_dir, url, BYTES_SUFFIX), data)
