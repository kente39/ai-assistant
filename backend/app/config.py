"""환경 변수 로딩. 키/비밀값은 절대 코드에 하드코딩하지 않는다."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "").strip()
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # 비용 보호: 응답 토큰 상한
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "500"))

    # 서비스 계정 JSON 문자열(또는 base64) / 혹은 키 파일 경로
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    # "firestore"(기본) | "memory"(로컬 테스트 전용)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "firestore").lower()

    # 쉼표로 구분된 CORS 허용 도메인
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000"
        ).split(",")
        if o.strip()
    ]

    # 데이터 의미 (프롬프트에 사용) — 내 데이터에 맞게 바꾼다
    DATA_NAME: str = os.getenv("DATA_NAME", "일별 매출")
    DATA_UNIT: str = os.getenv("DATA_UNIT", "원")

    # 대화 시 GPT에 함께 보내는 이전 메시지 최대 개수(토큰 절약)
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))


settings = Settings()
