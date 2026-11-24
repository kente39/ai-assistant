from fastapi import APIRouter, HTTPException

from ..schemas import ChatRequest, ChatResponse
from ..services import chat_service as svc

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI 대화 (데이터 요약 컨텍스트 주입 + 자동 저장)",
    description="1) 데이터 요약 조회 → 2) 시스템 프롬프트에 삽입 → 3) GPT 호출(필요 시 도구 호출) → 4) conversations에 자동 저장",
)
def chat(req: ChatRequest):
    try:
        return svc.chat(req.message, req.conversation_id, req.use_tools)
    except svc.ChatError as e:
        raise HTTPException(502, str(e))
