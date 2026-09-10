"""로컬 문서 조사 도구. DOCS_ROOT 아래만 본다."""

import os
from pathlib import Path

from langchain_core.tools import tool

DOCS_ROOT = Path(os.getenv("DOCS_ROOT", ".")).expanduser().resolve()
SUFFIXES = {".md", ".txt", ".rst", ".py", ".toml", ".yaml", ".yml"}
MAX_HITS = 20
MAX_CHARS = 4000


def _walk() -> list[Path]:
    return sorted(
        p
        for p in DOCS_ROOT.rglob("*")
        if p.is_file()
        and p.suffix in SUFFIXES
        and not any(part.startswith(".") for part in p.relative_to(DOCS_ROOT).parts)
    )


@tool
def list_docs() -> str:
    """조사할 수 있는 로컬 문서와 코드 파일의 목록을 반환한다."""
    paths = _walk()
    if not paths:
        return f"{DOCS_ROOT} 아래에 읽을 수 있는 파일이 없습니다."
    return "\n".join(str(p.relative_to(DOCS_ROOT)) for p in paths)


@tool
def search_docs(query: str) -> str:
    """로컬 문서에서 문자열을 검색해 파일 경로와 일치한 줄을 반환한다."""
    needle = query.lower()
    hits = []
    for path in _walk():
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{path.relative_to(DOCS_ROOT)}:{number}: {line.strip()[:200]}")
                if len(hits) >= MAX_HITS:
                    return "\n".join(hits) + f"\n(상위 {MAX_HITS}건만 표시)"
    return "\n".join(hits) or (
        f"'{query}'와 일치하는 내용이 없습니다. "
        "list_docs로 파일 목록을 본 뒤 read_doc으로 직접 확인해 보라."
    )


@tool
def read_doc(path: str) -> str:
    """로컬 문서 파일의 내용을 읽는다. search_docs가 알려준 경로를 넣는다."""
    target = (DOCS_ROOT / path).resolve()
    # 웹에서 가져온 내용이 경로를 지시할 수 있으므로 조사 범위를 벗어나지 못하게 한다.
    if not target.is_relative_to(DOCS_ROOT):
        return "조사 범위 밖의 경로입니다."
    if not target.is_file():
        return f"파일이 없습니다: {path}"
    return target.read_text(errors="ignore")[:MAX_CHARS]
