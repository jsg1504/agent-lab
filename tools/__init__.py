"""에이전트가 사용할 도구 모음. 새 도구는 모듈을 만들고 아래 목록에 추가한다."""

from tools.clock import get_current_time
from tools.code import (
    edit_file,
    glob_files,
    grep_files,
    list_dir,
    read_file,
    write_file,
)
from tools.docs import list_docs, read_doc, search_docs
from tools.files import list_files
from tools.shell import run_command
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

# 순서가 작은 모델의 도구 선택에 영향을 준다. 가장 자주 쓰는 것을 앞에 둔다.
CODING_TOOLS = [
    read_file,
    edit_file,
    run_command,
    list_dir,
    write_file,
    grep_files,
    glob_files,
]
