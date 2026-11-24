"""AI 채팅 — 컨텍스트 주입 + (보너스) Function Calling.

흐름
 1) 데이터 요약 조회 (build_summary == GET /api/data/summary)
 2) 요약을 시스템 프롬프트에 삽입 (컨텍스트 주입)
 3) GPT 호출 — 필요하면 GPT가 도구(기간별 데이터, 통계, 대화 목록)를 호출
 4) 사용자 질문 + AI 답변을 conversations에 자동 저장
"""
from __future__ import annotations

import json
import logging
from datetime import date

from ..config import settings
from . import conversation_service as conv_svc
from . import data_service as data_svc

logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 3  # 무한 도구 호출 방지


# ------------------------------------------------------------------ 프롬프트
def fmt(v: float) -> str:
    return f"{v:,.0f}{settings.DATA_UNIT}"


def build_system_prompt(summary: dict) -> str:
    if not summary["count"]:
        data_block = "- 아직 저장된 데이터가 없습니다."
    else:
        m = summary["metrics"]
        monthly = "\n".join(
            f"  · {x['month']}: 합계 {fmt(x['total'])}, 일평균 {fmt(x['average'])} ({x['days']}일)"
            for x in summary["monthly"]
        )
        recent = "\n".join(f"  · {r['date']}: {fmt(r['value'])}{' / ' + r['memo'] if r['memo'] else ''}"
                           for r in summary["recent"])
        data_block = (
            f"- 데이터 종류: {settings.DATA_NAME}\n"
            f"- 데이터 기간: {summary['period']}\n"
            f"- 총 레코드: {summary['count']}개\n"
            f"- 주요 지표: 합계 {fmt(m['total'])}, 평균 {fmt(m['average'])}, "
            f"최대 {fmt(m['max'])}({m['max_date']}), 최소 {fmt(m['min'])}({m['min_date']})\n"
            f"- 최근 트렌드: {summary['trend']}\n"
            f"- 월별 요약:\n{monthly}\n"
            f"- 최근 7개 기록:\n{recent}"
        )

    return f"""당신은 사용자의 개인 데이터 분석 비서입니다. 오늘 날짜는 {date.today().isoformat()}입니다.

[사용자 데이터 요약]
{data_block}

[답변 규칙]
1. 위 데이터를 근거로 구체적인 숫자를 들어 맞춤형으로 답하세요.
2. 요약에 없는 세부 정보(특정 기간의 일별 값, 요일별 평균, 표준편차 등)가 필요하면 도구를 호출하세요.
3. 데이터에 없는 내용은 추측하지 말고 "데이터에 없다"고 말하세요.
4. '이번 달'은 데이터의 가장 최근 월을 기준으로 해석하세요.
5. 아직 진행 중인 달(일수가 적은 달)을 다른 달과 비교할 때는 합계가 아니라 일평균으로 비교하고, 진행 중인 달이라는 점을 밝히세요.
6. 한국어로, 3~5문장 이내로 친근하고 간결하게 답하세요. 금액은 '620만원'처럼 읽기 쉽게 표기하세요."""


# ------------------------------------------------------------------ 도구 (Function Calling)
_REASON = {"type": "string", "description": "이 도구를 호출하는 이유(한 문장, 한국어)"}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_data_by_period",
            "description": "특정 기간의 일별 원본 데이터를 조회한다. 특정 날짜·주·월의 상세 값이 필요할 때 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "시작일 YYYY-MM-DD"},
                    "end": {"type": "string", "description": "종료일 YYYY-MM-DD"},
                    "reason": _REASON,
                },
                "required": ["start", "end", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_statistics",
            "description": "중앙값, 표준편차, 요일별 평균, 최고 월, 전월 대비 증감률 등 확장 통계를 조회한다.",
            "parameters": {"type": "object", "properties": {"reason": _REASON}, "required": ["reason"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_past_conversations",
            "description": "사용자의 이전 대화 목록(제목, 미리보기)을 조회한다. '지난번에 뭐 물어봤지?' 같은 질문에 사용.",
            "parameters": {"type": "object", "properties": {"reason": _REASON}, "required": ["reason"]},
        },
    },
]


def run_tool(name: str, args: dict):
    if name == "get_data_by_period":
        rows = data_svc.list_data(args.get("start"), args.get("end"))
        return {"count": len(rows), "rows": [{"date": r["date"], "value": r["value"], "memo": r["memo"]} for r in rows[:62]]}
    if name == "get_statistics":
        s = data_svc.build_statistics()
        s["moving_avg_7"] = s["moving_avg_7"][-14:]  # 토큰 절약
        return s
    if name == "list_past_conversations":
        return conv_svc.list_conversations()[:10]
    return {"error": f"알 수 없는 도구: {name}"}


# ------------------------------------------------------------------ 데모 모드 (API 키 없음)
def _demo_reply(message: str, summary: dict) -> str:
    if not summary["count"]:
        return "[데모 모드] 아직 데이터가 없어요. 데이터 관리 탭에서 먼저 데이터를 추가해 주세요."
    m, last = summary["metrics"], summary["monthly"][-1]
    tag = "[데모 모드 · OPENAI_API_KEY 미설정] "
    if any(k in message for k in ("최고", "좋았", "많이", "최대")):
        return tag + f"가장 높았던 날은 {m['max_date']}로 {fmt(m['max'])}였어요. 전체 평균({fmt(m['average'])})의 약 {m['max'] / m['average']:.1f}배예요."
    if any(k in message for k in ("최저", "나빴", "적었", "최소")):
        return tag + f"가장 낮았던 날은 {m['min_date']}로 {fmt(m['min'])}였어요."
    if any(k in message for k in ("추세", "흐름", "트렌드")):
        return tag + f"추세는 '{summary['trend']}'입니다."
    return (
        f"[데모 모드 · OPENAI_API_KEY 미설정] {summary['period']} 동안 {summary['count']}개의 기록이 있어요. "
        f"가장 최근 월({last['month']}) 합계는 {fmt(last['total'])}, 전체 일평균은 {fmt(m['average'])}이에요. "
        f"최고 기록은 {m['max_date']}의 {fmt(m['max'])}이고, 추세는 '{summary['trend']}'입니다."
    )


# ------------------------------------------------------------------ 메인
class ChatError(Exception):
    pass


def chat(message: str, conversation_id: str | None, use_tools: bool = True) -> dict:
    summary = data_svc.build_summary()  # 1) 요약 조회
    system_prompt = build_system_prompt(summary)  # 2) 컨텍스트 주입
    tool_logs: list[dict] = []

    history: list[dict] = []
    if conversation_id:
        conv = conv_svc.get_conversation(conversation_id)
        if conv:
            history = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]][-settings.CHAT_HISTORY_LIMIT:]

    demo = not settings.OPENAI_API_KEY
    if demo:
        reply = _demo_reply(message, summary)
    else:
        reply = _call_openai(system_prompt, history, message, use_tools, tool_logs)  # 3) GPT 호출

    conv_id = conv_svc.append_messages(  # 4) 자동 저장
        conversation_id,
        [{"role": "user", "content": message}, {"role": "assistant", "content": reply}],
    )
    return {"reply": reply, "conversation_id": conv_id, "summary_used": summary, "tool_calls": tool_logs, "demo_mode": demo}


def _call_openai(system_prompt, history, message, use_tools, tool_logs) -> str:
    from openai import APIError, OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_BASE_URL or None, timeout=40)
    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]

    try:
        for _ in range(MAX_TOOL_ROUNDS + 1):
            kwargs = dict(model=settings.OPENAI_MODEL, messages=messages,
                          max_completion_tokens=settings.OPENAI_MAX_TOKENS)
            if use_tools:
                kwargs["tools"] = TOOLS
            resp = client.chat.completions.create(**kwargs)
            msg = resp.choices[0].message

            if not msg.tool_calls:
                return (msg.content or "").strip() or "답변을 생성하지 못했어요. 다시 질문해 주세요."

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [{"id": tc.id, "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                               for tc in msg.tool_calls],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = run_tool(tc.function.name, args)
                tool_logs.append({"name": tc.function.name,
                                  "arguments": {k: v for k, v in args.items() if k != "reason"},
                                  "reason": args.get("reason", "")})
                logger.info("tool call: %s %s", tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(result, ensure_ascii=False)})
            kwargs.pop("tools", None)
        return "도구 호출이 너무 많아 답변을 마무리하지 못했어요. 질문을 조금 더 구체적으로 해 주세요."
    except APIError as e:
        logger.exception("OpenAI API error")
        raise ChatError(f"AI 응답 생성 중 오류가 발생했습니다: {getattr(e, 'message', str(e))}") from e
