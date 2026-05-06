from datetime import UTC, datetime, timedelta

from app.services.freshness import calculate_source_freshness, calculate_top_level_freshness


def test_source_without_crawled_at_is_stale():
    assert calculate_source_freshness(None, stale_days=180) == "stale"


def test_recent_source_is_recent():
    assert calculate_source_freshness(datetime.now(UTC), stale_days=180) == "recent"


def test_old_source_is_stale():
    old = datetime.now(UTC) - timedelta(days=181)
    assert calculate_source_freshness(old, stale_days=180) == "stale"


def test_top_level_is_stale_if_any_source_is_stale():
    assert calculate_top_level_freshness(["recent", "stale"]) == "stale"
