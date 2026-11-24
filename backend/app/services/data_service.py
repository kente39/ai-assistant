"""데이터 CRUD + 시계열 분석(요약/통계)."""
from __future__ import annotations

import statistics as st
from collections import defaultdict
from datetime import date, datetime, timezone

from ..database import DATA_COLLECTION, get_repo
from ..schemas import DataCreate, DataUpdate

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
TREND_WINDOW = 30      # 최근 N개 vs 직전 N개 비교
TREND_THRESHOLD = 3.0  # ±3% 이내면 '유지'


def _repo():
    return get_repo(DATA_COLLECTION)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(doc: dict) -> dict:
    return {"id": doc["id"], "date": doc["date"], "value": float(doc["value"]), "memo": doc.get("memo", "")}


# ------------------------------------------------------------------ CRUD
def list_data(start: str | None = None, end: str | None = None) -> list[dict]:
    items = [_clean(d) for d in _repo().list(order_by="date")]
    if start:
        items = [i for i in items if i["date"] >= start]
    if end:
        items = [i for i in items if i["date"] <= end]
    return items


def create_data(payload: DataCreate) -> dict:
    data = {
        "date": payload.date.isoformat(),
        "value": payload.value,
        "memo": payload.memo,
        "created_at": _now(),
        "updated_at": _now(),
    }
    return _clean(_repo().create(data))


def update_data(doc_id: str, payload: DataUpdate) -> dict | None:
    patch = payload.model_dump(exclude_none=True)
    if "date" in patch:
        patch["date"] = patch["date"].isoformat()
    patch["updated_at"] = _now()
    doc = _repo().update(doc_id, patch)
    return _clean(doc) if doc else None


def delete_data(doc_id: str) -> bool:
    return _repo().delete(doc_id)


# ------------------------------------------------------------------ 분석
def _pct(new: float, old: float) -> float:
    return round((new - old) / old * 100, 1) if old else 0.0


def _label(change: float) -> str:
    return "상승" if change > TREND_THRESHOLD else "하락" if change < -TREND_THRESHOLD else "유지"


def _trend(items: list[dict]) -> str:
    """단기: 최근 N일 vs 직전 N일 / 장기: 월별 일평균의 평균 월간 증감률."""
    values = [i["value"] for i in items]
    if len(values) < 4:
        return "데이터 부족 (추세 판단 불가)"
    w = min(TREND_WINDOW, len(values) // 2)
    short = _pct(st.mean(values[-w:]), st.mean(values[-2 * w : -w]))
    text = f"단기 {_label(short)} (최근 {w}일 평균, 직전 {w}일 대비 {short:+.1f}%)"

    months = [m for m in _monthly(items) if m["days"] >= 15]  # 일부만 있는 달 제외
    if len(months) >= 3:
        growth = [_pct(b["average"], a["average"]) for a, b in zip(months, months[1:])]
        g = round(st.mean(growth), 1)
        text = f"장기 {_label(g)} (월평균 {g:+.1f}%) · " + text
    return text


def _monthly(items: list[dict]) -> list[dict]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for i in items:
        buckets[i["date"][:7]].append(i["value"])
    return [
        {"month": m, "total": int(round(sum(v))), "average": int(round(st.mean(v))), "days": len(v)}
        for m, v in sorted(buckets.items())
    ]


def build_summary(items: list[dict] | None = None) -> dict:
    """시스템 프롬프트에 주입할 요약. GET /api/data/summary 응답과 동일."""
    items = list_data() if items is None else items
    if not items:
        return {"period": "데이터 없음", "count": 0, "metrics": None, "trend": "데이터 없음", "monthly": [], "recent": []}

    values = [i["value"] for i in items]
    mx = max(items, key=lambda i: i["value"])
    mn = min(items, key=lambda i: i["value"])
    return {
        "period": f"{items[0]['date']} ~ {items[-1]['date']}",
        "count": len(items),
        "metrics": {
            "total": int(round(sum(values))),
            "average": int(round(st.mean(values))),
            "max": mx["value"],
            "max_date": mx["date"],
            "min": mn["value"],
            "min_date": mn["date"],
        },
        "trend": _trend(items),
        "monthly": _monthly(items),
        "recent": items[-7:],
    }


def build_statistics(items: list[dict] | None = None) -> dict:
    """보너스: 추가 지표 (중앙값, 표준편차, 7일 이동평균, 요일별 평균, 전월 대비)."""
    items = list_data() if items is None else items
    if not items:
        return {"median": 0, "std_dev": 0, "moving_avg_7": [], "weekday_avg": {}, "best_month": None, "mom_change_pct": None}

    values = [i["value"] for i in items]
    ma = []
    for idx in range(len(items)):
        window = values[max(0, idx - 6) : idx + 1]
        ma.append({"date": items[idx]["date"], "value": round(st.mean(window))})

    wd: dict[str, list[float]] = defaultdict(list)
    for i in items:
        wd[WEEKDAYS[date.fromisoformat(i["date"]).weekday()]].append(i["value"])

    monthly = _monthly(items)
    best = max(monthly, key=lambda m: m["average"])["month"] if monthly else None
    mom = _pct(monthly[-1]["average"], monthly[-2]["average"]) if len(monthly) >= 2 else None

    return {
        "median": round(st.median(values)),
        "std_dev": round(st.pstdev(values)),
        "moving_avg_7": ma,
        "weekday_avg": {k: round(st.mean(wd[k])) for k in WEEKDAYS if wd[k]},
        "best_month": best,
        "mom_change_pct": mom,
    }
