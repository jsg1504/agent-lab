"""에이전트가 사용할 도구 모음. 새 도구는 모듈을 만들고 아래 목록에 추가한다."""

from tools.clock import get_current_time
from tools.docs import list_docs, read_doc, search_docs
from tools.files import list_files
from tools.web import fetch_page, web_search

TOOLS = [get_current_time, list_files]
RESEARCH_TOOLS = [
    web_search,
    fetch_page,
    list_docs,
    search_docs,
    read_doc,
    get_current_time,
]
