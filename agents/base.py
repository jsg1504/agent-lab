"""에이전트 공통 부분."""

from langchain.agents import create_agent

from llm import build_llm


def build(system_prompt: str, tools: list):
    return create_agent(model=build_llm(), tools=tools, system_prompt=system_prompt)


def ask(agent, question: str) -> str:
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    return result["messages"][-1].content
