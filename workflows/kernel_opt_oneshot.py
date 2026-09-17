"""GPU 커널 최적화 워크플로 (단발). 대화 없이 한 번 실행하고 끝난다.

planner가 커널을 분석하고, researcher가 최적화 후보를 찾고, planner가 그중 2개를 고른다.
고른 후보마다 optimizer가 최적화본을 만들고 reviewer가 검토한다. 두 갈래는 병렬로 돈다.

    plan -> research -> select -+-> [optimize -> review] -+-> END
                                +-> [optimize -> review] -+
"""

import operator
import re
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agents import ask, build_optimizer, build_planner, build_researcher, build_reviewer
from tools.workspace import resolve

BRANCHES = 2
MAX_SOURCE_CHARS = 8000


class Result(TypedDict):
    hypothesis: str
    candidate: str
    optimizer: str
    reviewer: str


class State(TypedDict):
    kernel: str
    request: str
    analysis: str
    candidates: str
    ranking: str
    results: Annotated[list[Result], operator.add]


class BranchState(TypedDict):
    index: int
    kernel: str
    hypothesis: str
    candidate: str
    optimizer: str
    reviewer: str


class BranchOutput(TypedDict):
    # 두 갈래가 같은 스텝에 부모 상태에 쓰므로 누적되는 키만 내보낸다.
    results: Annotated[list[Result], operator.add]


def _candidate_path(kernel: str, index: int) -> str:
    path = Path(kernel)
    return str(path.with_name(f"{path.stem}_opt{index}{path.suffix}"))


def _top_items(text: str, count: int) -> list[str]:
    """planner 보고 꼴의 '1. [대상] ...' 항목을 앞에서부터 count개 잘라낸다.

    마크다운 꾸밈(#, **)은 허용하고, [대상]이 없는 번호 목록(다음 단계 제안 등)은 항목으로 치지 않는다.
    """
    pattern = r"^[#*_ \t]*\d+\.[*_ \t]*\[대상\]"
    starts = [m.start() for m in re.finditer(pattern, text, re.MULTILINE)]
    items = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    # 마지막 항목 뒤에 붙은 다른 절(## 다음 단계 등)은 떼어낸다.
    return [re.split(r"\n#", item, maxsplit=1)[0].strip() for item in items[:count]]


def build_kernel_opt_oneshot():
    planner = build_planner()
    researcher = build_researcher()
    optimizer = build_optimizer()
    reviewer = build_reviewer()

    def plan(state: State) -> dict:
        question = (
            f"{state['kernel']}의 커널을 read_file로 읽고 병목이 무엇인지 분석해줘. "
            "프로파일 결과는 없으니 코드에서 근거를 대라. 아직 가설 순위는 매기지 마라.\n"
            f"요청: {state['request']}"
        )
        return {"analysis": ask(planner, question, "plan")}

    def research(state: State) -> dict:
        target = resolve(state["kernel"])
        if target is None or not target.is_file():
            raise ValueError(f"커널 파일을 찾을 수 없습니다: {state['kernel']}")
        source = target.read_text(errors="ignore")[:MAX_SOURCE_CHARS]
        question = (
            "아래 GPU 커널을 빠르게 만들 최적화 기법 후보를 찾아줘. "
            "후보마다 기법, 이 커널에 적용하는 방법, 근거 출처를 적어라.\n\n"
            f"[분석]\n{state['analysis']}\n\n[코드: {state['kernel']}]\n{source}"
        )
        return {"candidates": ask(researcher, question, "research")}

    def select(state: State) -> dict:
        question = (
            "researcher가 찾은 최적화 후보다. 앞서 한 분석을 바탕으로 순위를 매겨라. "
            "채택/반려 기록은 없다.\n\n"
            f"[후보]\n{state['candidates']}"
        )
        return {"ranking": ask(planner, question, "plan")}

    def dispatch(state: State) -> list[Send]:
        picks = _top_items(state["ranking"], BRANCHES)
        if len(picks) < BRANCHES:
            raise ValueError(
                f"planner의 순위에서 후보를 {BRANCHES}개 고르지 못했습니다:\n{state['ranking']}"
            )
        return [
            Send(
                "branch",
                {
                    "index": i,
                    "kernel": state["kernel"],
                    "hypothesis": pick,
                    "candidate": _candidate_path(state["kernel"], i),
                },
            )
            for i, pick in enumerate(picks, 1)
        ]

    def optimize(state: BranchState) -> dict:
        question = (
            f"{state['kernel']}을 아래 가설대로 최적화해줘. "
            f"원본은 고치지 말고 최적화본을 {state['candidate']}에 같은 함수 이름으로 만들어라.\n\n"
            f"[가설]\n{state['hypothesis']}"
        )
        return {"optimizer": ask(optimizer, question, f"optimize-{state['index']}")}

    def review(state: BranchState) -> dict:
        question = (
            f"{state['kernel']}이 원본, {state['candidate']}이 후보다. 검토해줘.\n\n"
            f"[가설]\n{state['hypothesis']}\n\n[optimizer 보고]\n{state['optimizer']}"
        )
        answer = ask(reviewer, question, f"review-{state['index']}")
        result = {
            "hypothesis": state["hypothesis"],
            "candidate": state["candidate"],
            "optimizer": state["optimizer"],
            "reviewer": answer,
        }
        return {"results": [result]}

    branch = StateGraph(BranchState, output_schema=BranchOutput)
    branch.add_node("optimize", optimize)
    branch.add_node("review", review)
    branch.add_edge(START, "optimize")
    branch.add_edge("optimize", "review")
    branch.add_edge("review", END)

    graph = StateGraph(State)
    graph.add_node("plan", plan)
    graph.add_node("research", research)
    graph.add_node("select", select)
    graph.add_node("branch", branch.compile())
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "select")
    graph.add_conditional_edges("select", dispatch, ["branch"])
    graph.add_edge("branch", END)
    return graph.compile()


def run_kernel_opt_oneshot(kernel: str, request: str = "") -> str:
    state = build_kernel_opt_oneshot().invoke({"kernel": kernel, "request": request, "results": []})
    sections = [
        f"## 분석\n{state['analysis']}",
        f"## 후보\n{state['candidates']}",
        f"## 순위\n{state['ranking']}",
    ]
    for i, result in enumerate(sorted(state["results"], key=lambda r: r["candidate"]), 1):
        sections.append(
            f"## 갈래 {i}: {result['candidate']}\n"
            f"### 가설\n{result['hypothesis']}\n"
            f"### optimizer\n{result['optimizer']}\n"
            f"### reviewer\n{result['reviewer']}"
        )
    return "\n\n".join(sections)
