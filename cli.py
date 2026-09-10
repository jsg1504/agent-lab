"""명령줄 인터페이스."""

import sys

from agent import ask, build_agent
from llm import BASE_URL, MODEL


def main() -> None:
    agent = build_agent()
    if len(sys.argv) > 1:
        print(ask(agent, " ".join(sys.argv[1:])))
        return
    print(f"model={MODEL} @ {BASE_URL}  (종료: Ctrl-D)")
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            break
        if question:
            print(ask(agent, question))


if __name__ == "__main__":
    main()
