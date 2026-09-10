"""에이전트 공통 부분."""

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from llm import build_llm


def build(system_prompt: str, tools: list):
    return create_agent(
        model=build_llm(),
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
    )


def _current_turn(messages: list) -> list:
    """체크포인터를 쓰면 이전 턴까지 함께 돌아오므로 마지막 질문 이후만 남긴다."""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index:]
    return messages


def _clean(text: str) -> str:
    """추론형 모델이 생각 부분을 답변에 흘릴 때가 있다. 마지막 </think> 뒤만 남긴다."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def ask(agent, question: str, thread_id: str = "default") -> str:
    messages = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        {"configurable": {"thread_id": thread_id}},
    )["messages"]
    answer = _clean(str(messages[-1].content))
    if answer:
        return answer
    # 작은 모델은 도구를 다 쓰고도 마무리 문장 없이 끝낼 때가 있다. 한 일이라도 보여준다.
    steps = [
        f"- {m.name}: {str(m.content).strip()[:200]}"
        for m in _current_turn(messages)
        if isinstance(m, ToolMessage)
    ]
    if steps:
        return "모델이 마무리 답변을 내놓지 않았다. 실행한 도구:\n" + "\n".join(steps)
    return "모델이 빈 답을 냈다."
