"""NPU wiki 조회 도구. NPU_WIKI_ROOT 아래만 본다.

wiki는 KernelWiki처럼 마크다운 페이지에 frontmatter(id, title, tags, aliases, confidence)를 단 형식이다.
설정하지 않아도 import는 실패하지 않는다. 검사는 이 도구를 쓰는 에이전트를 만들 때 require_root()로 한다.
"""

import os
import re
from pathlib import Path

from langchain_core.tools import tool

from llm import ConfigError

NPU_WIKI_ROOT = os.getenv("NPU_WIKI_ROOT")
MAX_HITS = 10
MAX_CHARS = 4000
LIST_FIELDS = ("tags", "aliases")


def require_root() -> Path:
    if not NPU_WIKI_ROOT:
        raise ConfigError("필요한 설정이 없습니다: NPU_WIKI_ROOT. .env에 지정하라 (.env.example 참고).")
    root = Path(NPU_WIKI_ROOT).expanduser().resolve()
    if not root.is_dir():
        raise ConfigError(f"NPU_WIKI_ROOT가 디렉터리가 아닙니다: {root}")
    return root


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """앞머리 --- 블록에서 'key: value'와 'key:' 다음의 '- item' 목록만 읽는다. PyYAML 없이 쓰기 위해서다."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    meta, key = {}, None
    for line in text[4:end].splitlines():
        item = re.match(r"\s*-\s+(.*)", line)
        if item and key:
            meta.setdefault(key, []).append(item.group(1).strip().strip("'\""))
            continue
        pair = re.match(r"([A-Za-z_][\w-]*):\s*(.*)", line)
        if pair:
            key, value = pair.group(1), pair.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            elif value:
                meta[key] = value.strip("'\"")
    return meta, text[end + 4 :].lstrip("-").lstrip("\n")


def _pages(root: Path) -> list[dict]:
    pages = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        meta, body = _split_frontmatter(path.read_text(errors="ignore"))
        heading = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        lines = [line.strip() for line in body.splitlines()]
        summary = next((line for line in lines if line and not line.startswith(("#", "```", "|", "-"))), "")
        pages.append(
            {
                "id": meta.get("id") or str(rel),
                "title": meta.get("title") or (heading.group(1).strip() if heading else rel.stem),
                "labels": [str(v).lower() for field in LIST_FIELDS for v in meta.get(field, []) or []],
                "confidence": meta.get("confidence", "-"),
                "path": str(rel),
                "summary": summary[:150],
                "body": body.lower(),
            }
        )
    return pages


def _score(page: dict, tokens: list[str]) -> int:
    """KernelWiki query.py와 같은 가중치: id·제목 10, 태그·별칭 5, 본문은 최대 3."""
    score = 0
    for token in tokens:
        if token in page["id"].lower() or token in page["title"].lower():
            score += 10
        if any(token in label for label in page["labels"]):
            score += 5
        score += min(page["body"].count(token), 3)
    return score


@tool
def search_wiki(query: str) -> str:
    """NPU wiki에서 페이지를 찾는다. 공백으로 나눈 낱말마다 제목, 태그, 별칭, 본문을 맞춰 보고 상위 결과를 반환한다."""
    try:
        root = require_root()
    except ConfigError as exc:
        return str(exc)
    tokens = [token.lower() for token in query.split()]
    scored = [(_score(page, tokens), page) for page in _pages(root)]
    hits = sorted((item for item in scored if item[0] > 0), key=lambda item: (-item[0], item[1]["path"]))
    if not hits:
        return f"'{query}'와 맞는 페이지가 없습니다. 다른 용어나 별칭으로 다시 찾아보라."
    return "\n".join(
        f"{p['id']} | {p['title']} | {p['confidence']} | {p['path']} | {p['summary']}" for _, p in hits[:MAX_HITS]
    )


@tool
def read_wiki_page(page: str) -> str:
    """NPU wiki 페이지 전체를 읽는다. search_wiki가 알려준 id나 경로를 넣는다."""
    try:
        root = require_root()
    except ConfigError as exc:
        return str(exc)
    target = next((root / p["path"] for p in _pages(root) if p["id"] == page), (root / page).resolve())
    if not target.is_relative_to(root):
        return "wiki 밖의 경로입니다."
    if not target.is_file():
        return f"페이지가 없습니다: {page}. search_wiki로 id를 확인하라."
    text = target.read_text(errors="ignore")
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + f"\n\n(앞 {MAX_CHARS}자만 표시했습니다. 페이지가 더 깁니다.)"
    return text
