"""벤치마크 공통 부분. 워크플로를 문제마다 돌리고, 끝난 뒤 코드가 직접 채점해 집계한다.

채점 함수는 벤치마크마다 다르고(어댑터가 넘긴다), 집계와 보고서는 여기서 같이 쓴다.
에이전트는 공식 채점기를 모른다. 도구 목록과 프롬프트를 그대로 두어야 워크플로끼리 비교할 수 있어서다.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import tracing
from tools.workspace import ROOT
from workflows import run_kernel_opt_oneshot, run_kernel_opt_orchestrator

WORKFLOWS = {
    "orchestrator": run_kernel_opt_orchestrator,
    "oneshot": run_kernel_opt_oneshot,
}


@dataclass
class Problem:
    """workspace에 준비된 원본. 워크플로는 이 파일 옆에 <name>_opt*를 만든다."""

    name: str
    path: Path


@dataclass
class Score:
    """벤치마크마다 다른 채점 결과를 이 꼴로 맞춘다. speedup은 정확할 때만 있다."""

    compiled: bool
    correct: bool
    speedup: float | None
    detail: str = ""


def _candidates(problem: Problem) -> list[Path]:
    return sorted(problem.path.parent.glob(f"{problem.name}_opt*{problem.path.suffix}"))


def _row(name: str, candidate: str, score: Score) -> str:
    speedup = f"{score.speedup:.3f}x" if score.speedup is not None else "-"
    # traceback은 마지막 줄이 원인이다.
    reason = score.detail.strip().splitlines()[-1][:200] if score.detail.strip() else ""
    return f"| {name} | {candidate} | {score.compiled} | {score.correct} | {speedup} | {reason} |"


def run_suite(
    title: str,
    problems: list[Problem],
    score: Callable[[Path, Path], Score],
    workflow: str = "orchestrator",
    request: str = "",
) -> str:
    run = WORKFLOWS[workflow]
    best: dict[str, Score | None] = {}
    rows, reports = [], []
    for problem in problems:
        # 앞 실행이 남긴 후보가 이번 채점에 섞이지 않게 지운다.
        for old in _candidates(problem):
            old.unlink()
        tracing.mark("problem", name=problem.name, workflow=workflow)
        try:
            report = run(str(problem.path.relative_to(ROOT)), request)
        except Exception as exc:
            report = f"워크플로가 실패했습니다: {type(exc).__name__}: {str(exc)[:500]}"
        reports.append(f"## {problem.name}\n\n{report}")

        scores = [(path, score(problem.path, path)) for path in _candidates(problem)]
        rows += [_row(problem.name, path.name, s) for path, s in scores]
        if not scores:
            rows.append(f"| {problem.name} | (후보 없음) | - | - | - | |")
        correct = [s for _, s in scores if s.correct and s.speedup is not None]
        best[problem.name] = max(correct, key=lambda s: s.speedup) if correct else None

    total = len(problems)
    speedups = [s.speedup for s in best.values() if s is not None]
    geomean = math.exp(sum(math.log(x) for x in speedups) / len(speedups)) if speedups else None
    summary = "\n".join([
        f"# {title} ({workflow})",
        "",
        f"- 문제 수: {total}",
        f"- 정확: {len(speedups)}/{total}",
        f"- fast_0 (정확): {len(speedups) / total:.2f}" if total else "- fast_0: -",
        f"- fast_1 (정확하고 더 빠름): {sum(x > 1 for x in speedups) / total:.2f}" if total else "- fast_1: -",
        f"- 정확한 문제의 속도향상 기하평균: {geomean:.3f}x" if geomean else "- 정확한 문제의 속도향상 기하평균: -",
    ])
    table = "\n".join([
        "| 문제 | 후보 | 컴파일 | 정확 | 속도향상 | 비고 |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
    ])

    out = ROOT / "benchmarks" / f"{title}_{datetime.now():%Y%m%d_%H%M%S}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join([summary, "## 후보별 채점", table, "# 워크플로 보고", *reports]) + "\n")
    return f"{summary}\n\n{table}\n\n보고서: {out}"
