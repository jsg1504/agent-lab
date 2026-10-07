"""에이전트 공통 부분."""

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

import tracing
from llm import build_llm

WRAP_UP_REQUEST = (
    "스텝 한도에 닿아 도구를 더 쓸 수 없다. 지금까지 도구로 확인한 내용만으로 처음 질문에 답하라. "
    "확인하지 못한 것은 확인하지 못했다고 적어라."
)
WRAP_UP_NOTE = "(스텝 한도에 닿아, 그때까지 확인한 내용으로 답했다.)"

# 스텝 한도를 둔 에이전트의 마무리용 모델과 시스템 프롬프트. 에이전트 이름으로 찾는다.
_WRAP_UP: dict[str, tuple] = {}


def build(
    system_prompt: str,
    tools: list,
    model: str | None = None,
    name: str | None = None,
    recursion_limit: int | None = None,
):
    """name은 추적 로그에서 에이전트를 가리키는 이름이다.

    recursion_limit을 주면 그 스텝에서 멈추고, ask()가 그때까지 모은 내용으로 마무리 답을 받는다(name 필요).
    """
    llm = build_llm(model)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=InMemorySaver(),
        name=name,
    )
    if recursion_limit is None:
        return agent
    # 도구 메시지가 든 대화를 그대로 보내야 하므로 도구는 붙이되 부르지는 못하게 한다.
    _WRAP_UP[name] = (llm.bind_tools(tools, tool_choice="none"), system_prompt)
    return agent.with_config(recursion_limit=recursion_limit)


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
    config = {"configurable": {"thread_id": thread_id}}
    with tracing.asking(agent.get_name(), thread_id, question) as trace:
        try:
            messages = agent.invoke({"messages": [{"role": "user", "content": question}]}, config)["messages"]
            trace.answer = _answer(messages)
        except GraphRecursionError:
            if agent.get_name() not in _WRAP_UP:
                raise
            trace.answer = _wrap_up(agent, config)
    return trace.answer


def _wrap_up(agent, config: dict) -> str:
    """스텝 한도에 걸린 대화를 버리지 않고, 도구 없이 한 번 더 물어 그때까지 모은 내용으로 답을 받는다."""
    llm, system_prompt = _WRAP_UP[agent.get_name()]
    history = list(agent.get_state(config).values.get("messages", []))
    # 한도는 모델이 도구를 부른 직후에 걸릴 수 있다. 결과가 없는 도구 호출이 남으면 서버가 거부하므로 닫아 준다.
    pending = history[-1].tool_calls if history and isinstance(history[-1], AIMessage) else []
    closing = [ToolMessage("스텝 한도에 닿아 실행하지 않았다.", tool_call_id=call["id"]) for call in pending]
    request = HumanMessage(WRAP_UP_REQUEST)
    reply = llm.invoke([SystemMessage(system_prompt), *history, *closing, request])
    text = _clean(str(reply.content)) or _answer(history)
    # 같은 대화를 이어 갈 때 이 답이 보이도록 기억에 남긴다.
    agent.update_state(config, {"messages": [*closing, request, AIMessage(text)]})
    return f"{WRAP_UP_NOTE}\n\n{text}"


def _answer(messages: list) -> str:
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
