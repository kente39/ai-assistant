"""나만의 AI 데이터 비서 — FastAPI 진입점.

실행: uvicorn main:app --reload
문서: http://localhost:8000/docs
"""
import csv
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import DATA_COLLECTION, get_repo
from app.routers import chat, conversations, data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("main")



def seed_memory_store():
    """메모리 모드일 때만 샘플 데이터를 자동으로 채운다 (로컬 데모 편의)."""
    if settings.STORAGE_BACKEND != "memory":
        return
    repo = get_repo(DATA_COLLECTION)
    if repo.list():
        return
    path = Path(__file__).parent / "data" / "sample_sales.csv"
    with path.open(encoding="utf-8") as f:
        rows = [{"date": r["date"], "value": float(r["value"]), "memo": r.get("memo", "")} for r in csv.DictReader(f)]
    repo.bulk_create(rows)
    logger.info("메모리 저장소에 샘플 데이터 %d건 로드", len(rows))


@asynccontextmanager
async def lifespan(_app):
    logger.info("storage=%s, model=%s, origins=%s", settings.STORAGE_BACKEND, settings.OPENAI_MODEL, settings.ALLOWED_ORIGINS)
    seed_memory_store()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="나만의 AI 데이터 비서 API",
    description="시계열 데이터 CRUD · 요약 · 컨텍스트 주입 AI 채팅 · 대화 기록",
    version="1.0.0",
)

# CORS: 배포된 프론트(Vercel) 도메인만 허용. ALLOWED_ORIGINS 환경 변수로 관리.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*.vercel.app" in settings.ALLOWED_ORIGINS else None,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})


@app.get("/", tags=["health"])
def root():
    return {"service": "AI 데이터 비서", "docs": "/docs", "storage": settings.STORAGE_BACKEND}


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok"}

