"""파일 시스템 관련 도구."""

from pathlib import Path

from langchain_core.tools import tool


@tool
def list_files(path: str = ".") -> str:
    """주어진 디렉터리의 파일과 하위 디렉터리 목록을 반환한다."""
    target = Path(path).expanduser()
    if not target.is_dir():
        return f"디렉터리가 아닙니다: {target}"
    return "\n".join(sorted(p.name for p in target.iterdir())) or "(비어 있음)"
