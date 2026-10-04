"""웹 조사 도구."""

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from langchain_core.tools import tool

MAX_RESULTS = 5
MAX_CHARS = 4000
TIMEOUT = 15


@tool
def web_search(query: str) -> str:
    """웹을 검색해 상위 결과의 제목, URL, 요약을 반환한다."""
    try:
        results = DDGS().text(query, max_results=MAX_RESULTS)
    except DDGSException as exc:
        return f"검색하지 못했습니다: {exc} 검색어를 바꿔 다시 검색하라."
    if not results:
        return "검색 결과가 없습니다."
    return "\n\n".join(f"{r['title']}\n{r['href']}\n{r['body']}" for r in results)


@tool
def fetch_page(url: str) -> str:
    """URL의 본문 텍스트를 가져온다. 검색 결과를 자세히 확인할 때 쓴다."""
    try:
        response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return f"가져오지 못했습니다: {exc}"
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text[:MAX_CHARS] or "본문이 비어 있습니다."
