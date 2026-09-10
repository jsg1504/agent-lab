"""에이전트가 사용할 도구 모음. 새 도구는 모듈을 만들고 TOOLS에 추가한다."""

from tools.clock import get_current_time
from tools.files import list_files

TOOLS = [get_current_time, list_files]
