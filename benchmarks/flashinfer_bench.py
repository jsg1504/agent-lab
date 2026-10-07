"""FlashInfer-Bench 어댑터. definition을 workspace로 가져오고, 후보를 FlashInfer-Bench 공식 채점기로 잰다.

FlashInfer-Bench(flashinfer-ai/flashinfer-bench)는 agent-lab 의존성이 아니다. 측정용 인터프리터
(FLASHINFER_BENCH_PYTHON, 비우면 BENCH_PYTHON)에 설치하고 그 안에서 채점 스크립트를 돌린다.
문제 하나가 definition 하나이고, 그 definition의 workload 여러 개를 재서 Score 하나로 줄인다.
"""

import json
import math
import os
from functools import partial
from pathlib import Path

from dotenv import load_dotenv

from benchmarks.suite import Problem, Score, run_suite
from llm import ConfigError
from tools.bench import BENCH_PYTHON, TIMEOUT, _run
from tools.workspace import ROOT

load_dotenv()

FLASHINFER_TRACE_ROOT = os.getenv("FLASHINFER_TRACE_ROOT")
FLASHINFER_BENCH_PYTHON = os.getenv("FLASHINFER_BENCH_PYTHON") or BENCH_PYTHON
MAX_WORKLOADS = 8
# workload 하나를 재는 데 넉넉히 잡은 시간(초). 채점 전체의 제한 시간을 workload 수에 맞춘다.
SECONDS_PER_WORKLOAD = 60

REQUEST = (
    "FlashInfer-Bench 문제다. 진입점은 run이고 입력의 모양과 dtype은 파일 머리의 주석대로다. "
    "출력은 반환하며 모양, dtype, 값이 원본과 같아야 한다."
)

# 채점기가 워커를 spawn으로 띄우며 이 스크립트를 다시 임포트하므로 본문은 __main__ 아래에 둔다.
# 워커도 stdout에 쓰므로 파일 기술자째로 stderr에 돌려 두었다가, 끝에 되돌려 JSON 한 줄만 낸다.
_SCRIPT = """
if __name__ == "__main__":
    stdout_fd = os.dup(1)
    os.dup2(2, 1)
    benchmark = None
    try:
        from flashinfer_bench.bench import Benchmark, BenchmarkConfig
        from flashinfer_bench.data import (
            BuildSpec, Definition, Solution, SourceFile, Trace, TraceSet, load_json_file, load_jsonl_file,
        )
        definition = load_json_file(Definition, {definition!r})
        workloads = load_jsonl_file(Trace, {workloads!r})
        limit = {limit!r}
        if limit and len(workloads) > limit:
            workloads = [workloads[i * len(workloads) // limit] for i in range(limit)]
        solution = Solution(
            name={name!r},
            definition=definition.name,
            author="agent-lab",
            spec=BuildSpec(
                language={language!r},
                target_hardware=["cuda"],
                entry_point="main.py::run",
                destination_passing_style=False,
            ),
            sources=[SourceFile(path="main.py", content={candidate!r})],
        )
        trace_set = TraceSet(
            root={root!r},
            definitions={{definition.name: definition}},
            solutions={{definition.name: [solution]}},
            workloads={{definition.name: workloads}},
        )
        benchmark = Benchmark(trace_set, BenchmarkConfig())
        traces = benchmark.run_all(dump_traces=False).traces.get(definition.name, [])
        result = {{
            "total": len(workloads),
            "results": [
                {{
                    "status": t.evaluation.status.value,
                    "speedup": t.evaluation.performance.speedup_factor if t.evaluation.performance else None,
                    "log": (t.evaluation.log or "")[-1000:],
                }}
                for t in traces
            ],
        }}
    except ImportError:
        result = {{"error": "측정용 인터프리터에 FlashInfer-Bench가 없다: " + traceback.format_exc()[-1000:]}}
    except Exception:
        result = {{"error": traceback.format_exc()[-3000:]}}
    finally:
        if benchmark is not None:
            benchmark.close()
    sys.stdout.flush()
    os.dup2(stdout_fd, 1)
    print(json.dumps(result))
"""


def _root() -> Path:
    return Path(FLASHINFER_TRACE_ROOT).expanduser()


def _files(name: str) -> tuple[Path | None, Path | None]:
    """definition JSON과 그 workload JSONL을 찾는다. 둘은 op_type 디렉터리 아래에 같은 이름으로 있다."""
    definition = next(iter(sorted((_root() / "definitions").rglob(f"{name}.json"))), None)
    workloads = next(iter(sorted((_root() / "workloads").rglob(f"{name}.jsonl"))), None)
    return definition, workloads


def _score(reference: Path, candidate: Path, max_workloads: int = MAX_WORKLOADS) -> Score:
    definition, workloads = _files(reference.stem)
    source = candidate.read_text(errors="ignore")
    if not source.strip():
        return Score(False, False, None, "후보 파일이 비어 있다.")
    total = sum(1 for line in workloads.read_text().splitlines() if line.strip())
    count = min(total, max_workloads) if max_workloads else total
    script = _SCRIPT.format(
        definition=str(definition),
        workloads=str(workloads),
        limit=max_workloads,
        name=candidate.stem,
        # Triton 커널은 FlashInfer-Bench의 triton 빌더로 불러온다.
        language="triton" if "import triton" in source else "python",
        candidate=source,
        root=str(_root()),
    )
    data = _run(script, FLASHINFER_BENCH_PYTHON, max(TIMEOUT, 2 * SECONDS_PER_WORKLOAD + SECONDS_PER_WORKLOAD * count))
    if "error" in data:
        return Score(False, False, None, data["error"])

    results = data["results"]
    compiled = bool(results) and all(r["status"] != "COMPILE_ERROR" for r in results)
    passed = [r for r in results if r["status"] == "PASSED" and r["speedup"]]
    summary = f"{len(passed)}/{data['total']} workload 통과"
    # 모든 workload를 통과해야 정확한 것으로 친다. 일부만 빠른 후보를 채택하지 않기 위해서다.
    if len(passed) == data["total"]:
        speedup = math.exp(sum(math.log(r["speedup"]) for r in passed) / len(passed))
        return Score(compiled, True, speedup, summary)
    failed = next((r for r in results if r["status"] != "PASSED"), None)
    reason = f"{failed['log']}\n{failed['status']}, " if failed else "채점기가 결과를 내지 않은 workload가 있다, "
    # 보고서는 detail의 마지막 줄을 비고로 쓴다.
    return Score(compiled, False, None, reason + summary)


def _header(definition: dict) -> str:
    """원본 위에 붙일 주석. 에이전트가 입력을 만들 수 있게 축과 텐서 모양을 적는다."""

    def tensors(specs: dict) -> list[str]:
        return [f"#   {name}: shape={spec.get('shape')}, dtype={spec.get('dtype')}" for name, spec in specs.items()]

    axes = [
        f"#   {name}: {axis['value']} (고정)" if axis.get("type") == "const" else f"#   {name}: 실행마다 달라짐"
        for name, axis in definition["axes"].items()
    ]
    lines = [
        f"# FlashInfer-Bench definition: {definition['name']} (op_type: {definition['op_type']})",
        *[f"# {line}" for line in definition.get("description", "").splitlines()],
        "# 축:",
        *axes,
        "# 입력 (run의 인자 순서, shape가 None이면 스칼라):",
        *tensors(definition["inputs"]),
        "# 출력 (run이 반환):",
        *tensors(definition["outputs"]),
        *[f"# 제약: {constraint}" for constraint in definition.get("constraints") or []],
    ]
    return "\n".join(lines) + "\n\n"


def _prepare(names: list[str]) -> list[Problem]:
    target_dir = ROOT / "flashinfer_bench"
    target_dir.mkdir(parents=True, exist_ok=True)
    expanded = []
    for name in names:
        # op_type 이름을 주면 그 아래 definition 전부로 펼친다.
        group = _root() / "definitions" / name
        expanded += sorted(p.stem for p in group.glob("*.json")) if group.is_dir() else [name]

    problems, missing = [], []
    for name in dict.fromkeys(expanded):
        definition, workloads = _files(name)
        if definition is None or workloads is None:
            missing.append(name)
            continue
        data = json.loads(definition.read_text())
        path = target_dir / f"{name}.py"
        path.write_text(_header(data) + data["reference"].rstrip() + "\n")
        problems.append(Problem(name, path))
    if missing:
        raise ConfigError(
            f"{_root()}에서 definition이나 workload를 찾지 못했습니다: {', '.join(missing)}"
        )
    return problems


def run_flashinfer_bench(
    names: list[str],
    workflow: str = "orchestrator",
    request: str = "",
    max_workloads: int = MAX_WORKLOADS,
) -> str:
    if not FLASHINFER_TRACE_ROOT:
        raise ConfigError("필요한 설정이 없습니다: FLASHINFER_TRACE_ROOT. .env에 지정하라 (.env.example 참고).")
    problems = _prepare(names)
    score = partial(_score, max_workloads=max_workloads)
    return run_suite("flashinfer_bench", problems, score, workflow, f"{REQUEST}\n{request}".strip())
