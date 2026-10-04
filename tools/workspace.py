"""코딩 도구가 다루는 작업 루트. 모든 경로는 이 아래로 제한된다."""

import os
from pathlib import Path

# 지정하지 않으면 프로젝트 안의 workspace/를 만들어 쓴다. 에이전트가 프로젝트 소스를 건드리지 않게 한다.
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "workspace"

ROOT = Path(os.getenv("WORKSPACE_ROOT") or DEFAULT_ROOT).expanduser().resolve()
if ROOT == DEFAULT_ROOT:
    ROOT.mkdir(exist_ok=True)
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}


def resolve(path: str) -> Path | None:
    """작업 루트 기준 경로로 바꾼다. 루트를 벗어나면 None을 준다."""
    target = (ROOT / path).resolve()
    return target if target.is_relative_to(ROOT) else None


def walk() -> list[Path]:
    return sorted(
        p
        for p in ROOT.rglob("*")
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(ROOT).parts))
    )
