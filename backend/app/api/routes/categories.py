from fastapi import APIRouter

router = APIRouter(tags=["categories"])


@router.get("/categories")
async def list_categories() -> list[object]:
    return []


@router.get("/recent")
async def list_recent() -> list[object]:
    return []
