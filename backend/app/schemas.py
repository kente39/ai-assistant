"""Pydantic 스키마 — 요청 데이터 검증의 단일 지점.

잘못된 날짜 형식, 음수 값, 너무 긴 메모·메시지는 라우터에 도달하기 전에 422로 거절된다.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ------------------------------------------------------------------ data
class DataCreate(BaseModel):
    date: dt.date = Field(..., description="YYYY-MM-DD", examples=["2025-01-15"])
    value: float = Field(..., ge=0, le=1_000_000_000, description="측정값 (예: 일매출, 원)", examples=[5300000])
    memo: str = Field("", max_length=200, examples=["주말 프로모션"])

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: str) -> str:
        return v.strip()

    @field_validator("date")
    @classmethod
    def not_future(cls, v: dt.date) -> dt.date:
        if v > dt.date.today() + dt.timedelta(days=1):
            raise ValueError("미래 날짜는 입력할 수 없습니다.")
        return v


class DataUpdate(BaseModel):
    date: dt.date | None = None
    value: float | None = Field(None, ge=0, le=1_000_000_000)
    memo: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.date is None and self.value is None and self.memo is None:
            raise ValueError("수정할 필드(date, value, memo)를 하나 이상 보내야 합니다.")
        return self


class DataItem(BaseModel):
    id: str
    date: str
    value: float
    memo: str = ""


class Metrics(BaseModel):
    total: float
    average: float
    max: float
    max_date: str
    min: float
    min_date: str


class MonthlyStat(BaseModel):
    month: str
    total: float
    average: float
    days: int


class Summary(BaseModel):
    period: str
    count: int
    metrics: Metrics | None
    trend: str
    monthly: list[MonthlyStat] = []
    recent: list[DataItem] = []


class Statistics(BaseModel):
    """보너스: 확장 통계"""
    median: float
    std_dev: float
    moving_avg_7: list[dict]
    weekday_avg: dict[str, float]
    best_month: str | None
    mom_change_pct: float | None = Field(None, description="최근 월 vs 직전 월 증감률(%)")


# ------------------------------------------------------------------ conversations
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)
    created_at: str | None = None


class ConversationCreate(BaseModel):
    title: str = Field("새 대화", min_length=1, max_length=100)
    messages: list[Message] = Field(default_factory=list, max_length=200)


class ConversationListItem(BaseModel):
    """목록 응답에는 messages를 포함하지 않는다 (가볍게). 전체는 GET /{id}."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
    preview: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: list[Message]


# ------------------------------------------------------------------ chat
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["이번 달 실적이 어때?"])
    conversation_id: str | None = Field(None, description="이어서 대화할 경우 기존 대화 ID")
    use_tools: bool = Field(True, description="Function Calling(도구 호출) 사용 여부")

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지가 비어 있습니다.")
        return v


class ToolCallLog(BaseModel):
    name: str
    arguments: dict
    reason: str = ""


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    summary_used: Summary
    tool_calls: list[ToolCallLog] = []
    demo_mode: bool = False
