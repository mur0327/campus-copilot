from __future__ import annotations

import json
import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://campus:campus@localhost:5432/campus_copilot"
)

import pytest  # noqa: E402

from tasks import target_artifact  # noqa: E402
from tasks.contracts import CrawlTarget  # noqa: E402


def test_write_then_read_roundtrips_all_fields(tmp_path):
    targets = [
        CrawlTarget(
            url="https://www.honam.ac.kr/General_Rest",
            menu_path="학사",
            source_type="html",
            source_scope="general_academic",
            page_kind="academic",
            title_hint="휴학 안내",
            site_name="호남대학교",
            site_url="https://www.honam.ac.kr",
        ),
        CrawlTarget(
            url="https://www.honam.ac.kr/GraduateGrades/pdfdownload/2025",
            menu_path="졸업",
            source_type="pdf",
            source_scope="general_academic",
            page_kind="academic",
            year=2025,
            site_name="호남대학교",
            site_url="https://www.honam.ac.kr",
        ),
    ]
    path = tmp_path / "targets.json"
    target_artifact.write_targets(path, targets)

    restored = target_artifact.read_targets(path)
    # discovery 시점 메타(year/site_name/site_url)까지 그대로 살아 돌아와야 한다.
    assert restored == targets
    assert restored[1].year == 2025


def test_write_is_atomic_without_temp_residue(tmp_path):
    path = tmp_path / "targets.json"
    target_artifact.write_targets(path, [])
    assert target_artifact.read_targets(path) == []
    # 원자적 쓰기는 .tmp 잔여 파일을 남기지 않는다.
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_raises_friendly_error_on_schema_mismatch(tmp_path):
    path = tmp_path / "targets.json"
    # CrawlTarget에 없는 키가 든 옛/손상 artifact.
    path.write_text(json.dumps([{"url": "https://x", "bogus_field": 1}]), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the current CrawlTarget schema"):
        target_artifact.read_targets(path)
