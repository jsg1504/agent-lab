"""에이전트가 사용할 도구 모음. 새 도구는 모듈을 만들고 아래 목록에 추가한다."""

from dotenv import load_dotenv

# 도구 모듈이 import 시점에 환경 변수를 읽으므로 그 전에 .env를 올린다.
load_dotenv()

from tools.bench import benchmark, compare_outputs, compile_check
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

# 자주 쓰는 것을 앞에 둔다. 목록을 바꾸면 결과가 달라지는 일이 있으나
# 원인은 도구 자체가 아니라 모델 쪽에 있다. README의 '알려진 한계' 참고.
CODING_TOOLS = [
    read_file,
    edit_file,
    run_command,
    list_dir,
    write_file,
    grep_files,
    glob_files,
]

# optimizer는 코드를 고치기만 한다. 측정 도구는 evaluator만 가진다.
OPTIMIZE_TOOLS = CODING_TOOLS

EVALUATE_TOOLS = [
    read_file,
    compile_check,
    benchmark,
    compare_outputs,
    list_dir,
    glob_files,
]

# planner, reviewer, debugger는 읽기만 한다. 고치는 일은 optimizer, 재는 일은 evaluator 몫이다.
# reviewer는 디바이스를 쓰기 전 단계라 compile_check도 두지 않는다.
READ_TOOLS = [
    read_file,
    grep_files,
    list_dir,
    glob_files,
]

PLAN_TOOLS = READ_TOOLS

REVIEW_TOOLS = READ_TOOLS

DEBUG_TOOLS = READ_TOOLS
