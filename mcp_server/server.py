"""[보너스] MCP 서버 — 같은 기능을 Claude Desktop 등 외부 MCP 클라이언트에서 '도구'로 호출.

배포된 백엔드 API를 그대로 감싸므로 Firebase/OpenAI 키가 이 서버에는 필요 없다.

설치 : pip install "mcp>=1.2"
실행 : API_BASE_URL=https://your-api.onrender.com python mcp_server/server.py
(Claude Desktop 설정 예시는 README 참고)
"""
import json
import os
import urllib.parse
import urllib.request

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
mcp = _Server("ai-data-assistant")


def _get(path: str, **params):
    q = {k: v for k, v in params.items() if v}
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(q)}" if q else "")
    with urllib.request.urlopen(url, timeout=90) as r:  # Render 콜드스타트 고려
        return json.loads(r.read().decode())


@mcp.tool()
def get_data_summary() -> dict:
    """저장된 시계열 데이터의 요약(기간, 개수, 합계/평균/최대/최소, 추세, 월별 요약)을 조회한다."""
    return _get("/api/data/summary")


@mcp.tool()
def get_data_by_period(start: str, end: str) -> list:
    """특정 기간(YYYY-MM-DD ~ YYYY-MM-DD)의 일별 원본 데이터를 조회한다."""
    return _get("/api/data", start=start, end=end)


@mcp.tool()
def get_statistics() -> dict:
    """중앙값, 표준편차, 요일별 평균, 최고 월, 전월 대비 증감률 등 확장 통계를 조회한다."""
    stats = _get("/api/data/statistics")
    stats["moving_avg_7"] = stats["moving_avg_7"][-14:]
    return stats


@mcp.tool()
def list_conversations() -> list:
    """웹 서비스에서 저장된 이전 대화 목록(제목, 미리보기, 메시지 수)을 조회한다."""
    return _get("/api/conversations")


if __name__ == "__main__":
    mcp.run("stdio")
