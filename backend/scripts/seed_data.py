"""CSV 시계열 데이터를 업로드한다.

사용법 (backend 폴더에서):
  # 1) Firestore에 직접 (로컬 .env에 FIREBASE_SERVICE_ACCOUNT_JSON 필요)
  python -m scripts.seed_data --csv data/sample_sales.csv

  # 2) 배포된 API를 통해 (키를 로컬에 둘 필요 없음)
  python -m scripts.seed_data --csv data/sample_sales.csv --api https://your-api.onrender.com

  # 기존 data 컬렉션을 비우고 다시 넣기 (Firestore 직접 모드)
  python -m scripts.seed_data --csv data/sample_sales.csv --reset

CSV 형식: date,value,memo  (date=YYYY-MM-DD)
"""
import argparse
import csv
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        rows = [{"date": r["date"].strip(), "value": float(r["value"]), "memo": (r.get("memo") or "").strip()}
                for r in csv.DictReader(f)]
    if len(rows) < 100:
        print(f"⚠️  데이터가 {len(rows)}건입니다. 과제 요건은 100건 이상입니다.")
    return rows


def via_api(base: str, rows: list[dict]):
    url = base.rstrip("/") + "/api/data/bulk"
    req = urllib.request.Request(url, data=json.dumps({"items": rows}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        print("API 응답:", r.read().decode())


def via_firestore(rows: list[dict], reset: bool):
    from app.database import DATA_COLLECTION, get_repo

    repo = get_repo(DATA_COLLECTION)
    if reset:
        old = repo.list()
        for d in old:
            repo.delete(d["id"])
        print(f"기존 {len(old)}건 삭제")
    now = datetime.now(timezone.utc).isoformat()
    n = repo.bulk_create([{**r, "created_at": now, "updated_at": now} for r in rows])
    print(f"Firestore '{DATA_COLLECTION}' 컬렉션에 {n}건 업로드 완료")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/sample_sales.csv")
    p.add_argument("--api", help="배포된 백엔드 URL (지정 시 API로 업로드)")
    p.add_argument("--reset", action="store_true")
    a = p.parse_args()
    data = load_rows(a.csv)
    via_api(a.api, data) if a.api else via_firestore(data, a.reset)
