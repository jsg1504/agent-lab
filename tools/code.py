"""코드 읽기와 편집 도구. WORKSPACE_ROOT 아래에서만 동작한다."""

import fnmatch
import re

from langchain_core.tools import tool

from tools.workspace import ROOT, SKIP_DIRS, resolve, walk

MAX_CHARS = 8000
MAX_HITS = 50
OUT_OF_SCOPE = "작업 범위 밖의 경로입니다."


@tool
def list_dir(path: str = ".") -> str:
    """디렉터리의 파일과 하위 디렉터리 목록을 반환한다."""
    target = resolve(path)
    if target is None:
        return OUT_OF_SCOPE
    if not target.is_dir():
        return f"디렉터리가 아닙니다: {path}"
    entries = sorted(
        f"{p.name}/" if p.is_dir() else p.name
        for p in target.iterdir()
        if p.name not in SKIP_DIRS
    )
    return "\n".join(entries) or "(비어 있음)"


@tool
def read_file(path: str) -> str:
    """파일 내용을 읽는다."""
    target = resolve(path)
    if target is None:
        return OUT_OF_SCOPE
    if not target.is_file():
        return f"파일이 없습니다: {path}"
    text = target.read_text(errors="ignore")
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + f"\n... (앞 {MAX_CHARS}자만 표시)"
    return text or "(빈 파일)"


@tool
def write_file(path: str, content: str) -> str:
    """파일을 쓴다. 파일이 이미 있으면 내용을 통째로 덮어쓴다."""
    target = resolve(path)
    if target is None:
        return OUT_OF_SCOPE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"{path}에 {len(content)}자를 썼다."


@tool
def edit_file(path: str, old: str, new: str) -> str:
    """파일에서 old를 new로 바꾼다. old는 파일에 정확히 한 번만 나와야 한다."""
    target = resolve(path)
    if target is None:
        return OUT_OF_SCOPE
    if not target.is_file():
        return f"파일이 없습니다: {path}"
    text = target.read_text()
    count = text.count(old)
    if count == 0:
        return "바꿀 내용을 파일에서 찾지 못했습니다. read_file로 정확한 내용을 확인하라."
    if count > 1:
        return f"바꿀 내용이 {count}번 나옵니다. 앞뒤를 더 붙여 하나만 걸리게 하라."
    target.write_text(text.replace(old, new))
    return f"{path}를 수정했다."


@tool
def glob_files(pattern: str) -> str:
    """이름 패턴으로 파일을 찾는다. 예: *.py, tools/*.py"""
    hits = []
    for path in walk():
        relative = str(path.relative_to(ROOT))
        if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern):
            hits.append(relative)
    return "\n".join(hits[:MAX_HITS]) or f"'{pattern}'와 맞는 파일이 없습니다."


@tool
def grep_files(pattern: str) -> str:
    """파일 내용을 정규식으로 검색해 경로, 줄 번호, 해당 줄을 반환한다."""
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"정규식이 잘못됐습니다: {exc}"
    hits = []
    for path in walk():
        for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            if regex.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:200]}")
                if len(hits) >= MAX_HITS:
                    return "\n".join(hits) + f"\n(상위 {MAX_HITS}건만 표시)"
    return "\n".join(hits) or f"'{pattern}'와 맞는 내용이 없습니다."
