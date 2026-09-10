"""에이전트 공통 부분."""

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage

from llm import build_llm


def build(system_prompt: str, tools: list):
    return create_agent(model=build_llm(), tools=tools, system_prompt=system_prompt)


def ask(agent, question: str) -> str:
    messages = agent.invoke({"messages": [{"role": "user", "content": question}]})["messages"]
    answer = str(messages[-1].content).strip()
    if answer:
        return answer
    # 작은 모델은 도구를 다 쓰고도 마무리 문장 없이 끝낼 때가 있다. 한 일이라도 보여준다.
    steps = [
        f"- {m.name}: {str(m.content).strip()[:200]}"
        for m in messages
        if isinstance(m, ToolMessage)
    ]
    if steps:
        return "모델이 마무리 답변을 내놓지 않았다. 실행한 도구:\n" + "\n".join(steps)
    return "모델이 빈 답을 냈다."
