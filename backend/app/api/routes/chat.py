from fastapi import APIRouter

from app.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer=f"stub response for: {payload.question}",
    )
