"""에이전트 정의."""

from langchain.agents import create_agent

from llm import build_llm
from tools import TOOLS

SYSTEM_PROMPT = "너는 도움이 되는 어시스턴트다. 필요하면 주어진 도구를 사용하고, 한국어로 간결하게 답한다."


def build_agent():
    return create_agent(
        model=build_llm(),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
    )


def ask(agent, question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content
