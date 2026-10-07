"""조사 담당 에이전트. 웹과 로컬 문서를 근거로 답한다."""

from agents.base import build
from tools import RESEARCH_TOOLS

SYSTEM_PROMPT = """너는 조사 담당이다. 추측하지 말고 도구로 확인한 것만 말한다.

- 웹에서 찾을 일이면 web_search로 검색하고, 요약만으로 부족하면 fetch_page로 본문을 읽는다.
- 로컬 코드나 문서에 관한 일이면 search_docs로 찾고 read_doc으로 내용을 확인한다.
- 근거가 된 URL이나 파일 경로를 답변에 반드시 함께 밝힌다.
- 확인하지 못한 것은 모른다고 말한다. 지어내지 않는다.
- 한국어로 간결하게 답한다."""

# 모델이 스스로 멈추지 않을 때의 안전장치. 도구 호출 한 번이 2스텝이다.
# 한도에 닿으면 ask()가 그때까지 읽은 내용으로 마무리 답을 받는다. 한도를 올려도 모델은 끝까지 읽기만 했다.
RECURSION_LIMIT = 40


def build_researcher():
    return build(SYSTEM_PROMPT, RESEARCH_TOOLS, name="researcher", recursion_limit=RECURSION_LIMIT)
