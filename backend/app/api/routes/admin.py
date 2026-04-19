from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def status() -> dict[str, int | None]:
    return {"documents": 0, "last_crawled": None}


@router.post("/crawl")
async def trigger_crawl() -> dict[str, str]:
    return {"status": "triggered"}


@router.get("/conflicts")
async def list_conflicts() -> list[object]:
    return []


@router.get("/logs")
async def list_logs() -> list[object]:
    return []
