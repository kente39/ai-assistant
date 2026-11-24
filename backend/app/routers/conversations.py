from fastapi import APIRouter, HTTPException

from ..schemas import ConversationCreate, ConversationDetail, ConversationListItem
from ..services import conversation_service as svc

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, status_code=201, summary="대화 저장")
def create(payload: ConversationCreate):
    return svc.create_conversation(payload)


@router.get(
    "",
    response_model=list[ConversationListItem],
    summary="대화 목록 조회 (messages 미포함, 최근 수정순)",
    description="목록은 가볍게 유지하기 위해 messages를 포함하지 않습니다. 전체 메시지는 GET /api/conversations/{id}.",
)
def list_all():
    return svc.list_conversations()


@router.get("/{conv_id}", response_model=ConversationDetail, summary="특정 대화 전체 messages 조회")
def get_one(conv_id: str):
    conv = svc.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "해당 대화를 찾을 수 없습니다.")
    return conv


@router.delete("/{conv_id}", status_code=204, summary="대화 삭제")
def delete(conv_id: str):
    if not svc.delete_conversation(conv_id):
        raise HTTPException(404, "해당 대화를 찾을 수 없습니다.")
