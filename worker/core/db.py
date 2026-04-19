from urllib.parse import urlsplit, urlunsplit

import asyncpg

from core.config import settings


def normalize_asyncpg_dsn(database_url: str) -> str:
    parts = urlsplit(database_url)
    scheme = parts.scheme.split("+", 1)[0]
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


async def create_pool(database_url: str | None = None) -> asyncpg.Pool:
    dsn = normalize_asyncpg_dsn(database_url or settings.database_url)
    return await asyncpg.create_pool(dsn=dsn)
