"""명령줄 인터페이스."""

import sys

from agents import (
    ask,
    build_agent,
    build_coder,
    build_evaluator,
    build_optimizer,
    build_researcher,
)
from llm import BASE_URL, MODEL


def _run(build, label: str) -> None:
    agent = build()
    if len(sys.argv) > 1:
        print(ask(agent, " ".join(sys.argv[1:])))
        return
    print(f"{label} | model={MODEL} @ {BASE_URL}  (종료: Ctrl-D)")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            break
        if question:
            print(ask(agent, question))


def main() -> None:
    _run(build_agent, "assistant")


def researcher() -> None:
    _run(build_researcher, "researcher")


def coder() -> None:
    _run(build_coder, "coder")


def optimizer() -> None:
    _run(build_optimizer, "optimizer")


def evaluator() -> None:
    _run(build_evaluator, "evaluator")


if __name__ == "__main__":
    main()
