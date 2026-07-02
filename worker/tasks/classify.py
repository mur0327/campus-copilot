from urllib.parse import urlparse

from core.types import PageKind, SourceScope


def infer_source_scope(
    *,
    url: str,
    site_url: str | None = None,
) -> SourceScope:
    parsed_url = urlparse(url)
    source_host = parsed_url.hostname or ""
    site_host = urlparse(site_url or url).hostname or source_host
    host = site_host or source_host

    if host == "enter.honam.ac.kr" or source_host == "enter.honam.ac.kr":
        return "admission"
    if host in {"www.honam.ac.kr", "honam.ac.kr"}:
        return "general_academic"
    if host.endswith(".honam.ac.kr"):
        return "department"
    return "unknown"


def infer_page_kind(
    *,
    url: str,
    menu_path: str | None = None,
) -> PageKind:
    text = f"{url} {menu_path or ''}".casefold()
    is_transport_guide = any(
        keyword in text
        for keyword in (
            "통학버스",
            "교통편",
            "schbusguideschedule",
        )
    )
    is_license_course = "자격증" in text
    is_transport_location = any(
        keyword in text
        for keyword in (
            "등교버스 위치조회",
            "schbuslocation",
        )
    )
    is_academic_year_reference = any(
        keyword in text
        for keyword in (
            "입학년도",
            "입학자",
        )
    )

    if (
        any(keyword in text for keyword in ("학사일정", "schedule", "calendar"))
        and not is_transport_guide
    ):
        return "schedule"
    if (
        any(keyword in text for keyword in ("증명", "제증명", "certificate"))
        and not is_license_course
    ):
        return "certificate"
    if (
        any(
            keyword in text
            for keyword in (
                "연락처",
                "전화번호",
                "오시는 길",
                "오시는길",
                "찾아오시는 길",
                "찾아오시는길",
                "캠퍼스맵",
                "campusmap",
                "campus_map",
                "contact",
                "directions",
                "location",
            )
        )
        and not is_transport_location
    ):
        return "contact"
    if (
        "입학" in text or "admission" in text or "enter.honam.ac.kr" in text
    ) and not is_academic_year_reference:
        return "admission"
    return "academic"
