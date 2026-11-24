"""샘플 시계열 데이터 생성: 작은 온라인 쇼핑몰의 180일 일매출(원).
추세(완만한 상승) + 주말 효과 + 이벤트 + 노이즈."""
import csv, math, random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
END = date(2026, 11, 23)
DAYS = 180
events = {
    "2026-06-06": ("현충일 연휴 프로모션", 1.6), "2026-07-15": ("여름 시즌 세일", 1.7),
    "2026-08-15": ("광복절 특가", 1.5), "2026-09-26": ("추석 선물세트", 2.1),
    "2026-10-03": ("개천절 연휴 배송 지연", 0.55), "2026-11-11": ("빼빼로데이 기획전", 2.3),
    "2026-07-29": ("서버 점검", 0.4),
}
rows = []
for i in range(DAYS):
    d = END - timedelta(days=DAYS - 1 - i)
    base = 170000 + i * 520                      # 완만한 상승
    season = 1 + 0.08 * math.sin(i / 30 * math.pi)
    weekend = 1.25 if d.weekday() >= 5 else (0.9 if d.weekday() == 0 else 1.0)
    memo, mult = events.get(d.isoformat(), ("", 1.0))
    v = base * season * weekend * mult * random.uniform(0.85, 1.15)
    rows.append({"date": d.isoformat(), "value": int(round(v, -3)), "memo": memo})

out = Path(__file__).resolve().parent.parent / "data" / "sample_sales.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["date", "value", "memo"]); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} rows -> {out}")
