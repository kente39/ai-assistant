import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..schemas import DataCreate, DataItem, DataUpdate, Statistics, Summary
from ..services import data_service as svc

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("", response_model=DataItem, status_code=201, summary="새 데이터 추가")
def create(payload: DataCreate):
    return svc.create_data(payload)


@router.get("", response_model=list[DataItem], summary="데이터 목록 조회 (날짜 오름차순)")
def list_all(
    start: str | None = Query(None, description="시작일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str | None = Query(None, description="종료일 YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    return svc.list_data(start, end)


@router.get("/summary", response_model=Summary, summary="데이터 요약 (시스템 프롬프트 주입용)")
def summary():
    return svc.build_summary()


@router.get("/statistics", response_model=Statistics, summary="[보너스] 확장 통계")
def statistics():
    return svc.build_statistics()


@router.get("/export", summary="[보너스] 데이터 내보내기 (CSV/JSON)")
def export(format: str = Query("csv", pattern="^(csv|json)$")):
    rows = svc.list_data()
    if format == "json":
        return Response(
            json.dumps(rows, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="data.json"'},
        )
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "date", "value", "memo"])
    w.writeheader()
    w.writerows(rows)
    return Response(
        "﻿" + buf.getvalue(),  # BOM: 엑셀에서 한글 깨짐 방지
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="data.csv"'},
    )


class BulkIn(BaseModel):
    items: list[DataCreate] = Field(..., min_length=1, max_length=1000)


@router.post("/bulk", status_code=201, summary="여러 건 한 번에 추가 (초기 데이터 업로드용)")
def bulk(payload: BulkIn):
    created = [svc.create_data(i) for i in payload.items]
    return {"created": len(created)}


@router.put("/{doc_id}", response_model=DataItem, summary="데이터 수정")
def update(doc_id: str, payload: DataUpdate):
    doc = svc.update_data(doc_id, payload)
    if not doc:
        raise HTTPException(404, "해당 데이터를 찾을 수 없습니다.")
    return doc


@router.delete("/{doc_id}", status_code=204, summary="데이터 삭제")
def delete(doc_id: str):
    if not svc.delete_data(doc_id):
        raise HTTPException(404, "해당 데이터를 찾을 수 없습니다.")
