from datetime import UTC, datetime, timedelta


def calculate_source_freshness(crawled_at: datetime | None, stale_days: int) -> str:
    if crawled_at is None:
        return "stale"
    now = datetime.now(UTC)
    if crawled_at.tzinfo is None:
        crawled_at = crawled_at.replace(tzinfo=UTC)
    return "stale" if now - crawled_at > timedelta(days=stale_days) else "recent"


def calculate_top_level_freshness(values: list[str]) -> str:
    if not values:
        return "stale"
    return "stale" if any(value != "recent" for value in values) else "recent"
