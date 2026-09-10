"""일반 어시스턴트."""

from agents.base import build
from tools import TOOLS

SYSTEM_PROMPT = "너는 도움이 되는 어시스턴트다. 필요하면 주어진 도구를 사용하고, 한국어로 간결하게 답한다."


def build_agent():
    return build(SYSTEM_PROMPT, TOOLS)
