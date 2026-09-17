"""명령줄 인터페이스."""

import sys

from agents import (
    ask,
    build_agent,
    build_coder,
    build_debugger,
    build_evaluator,
    build_optimizer,
    build_planner,
    build_researcher,
    build_reviewer,
)
from llm import BASE_URL, MODEL
from workflows import run_kernel_opt_oneshot


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


def planner() -> None:
    _run(build_planner, "planner")


def reviewer() -> None:
    _run(build_reviewer, "reviewer")


def debugger() -> None:
    _run(build_debugger, "debugger")


def kernel_opt_oneshot() -> None:
    if len(sys.argv) < 2:
        sys.exit("사용법: kernel-opt-oneshot <커널 파일> [요청]")
    print(run_kernel_opt_oneshot(sys.argv[1], " ".join(sys.argv[2:])))


if __name__ == "__main__":
    main()
