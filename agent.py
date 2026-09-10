"""Ollama(OpenAI 호환 API) 기반 LangChain 에이전트."""

import sys

from langchain.agents import create_agent

from llm import BASE_URL, MODEL, build_llm
from tools import TOOLS

agent = create_agent(
    model=build_llm(),
    tools=TOOLS,
    system_prompt="너는 도움이 되는 어시스턴트다. 필요하면 주어진 도구를 사용하고, 한국어로 간결하게 답한다.",
)


def ask(question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content


def main() -> None:
    if len(sys.argv) > 1:
        print(ask(" ".join(sys.argv[1:])))
        return
    print(f"model={MODEL} @ {BASE_URL}  (종료: Ctrl-D)")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            break
        if question:
            print(ask(question))


if __name__ == "__main__":
    main()
