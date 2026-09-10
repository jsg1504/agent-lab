"""시각 관련 도구."""

from datetime import datetime

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """현재 로컬 날짜와 시각을 ISO 8601 형식으로 반환한다."""
    return datetime.now().isoformat(timespec="seconds")
