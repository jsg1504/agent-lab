"""KernelBench 어댑터. 문제를 workspace로 가져오고, 후보를 KernelBench 공식 채점기로 잰다.

KernelBench(ScalingIntelligence/KernelBench)는 agent-lab 의존성이 아니다. 측정용 인터프리터
(KERNELBENCH_PYTHON, 비우면 BENCH_PYTHON)에 설치하고 그 안에서 채점 스크립트를 돌린다.
"""

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from benchmarks.suite import Problem, Score, run_suite
from llm import ConfigError
from tools.bench import _PRELUDE, BENCH_PYTHON, _run
from tools.workspace import ROOT

load_dotenv()

KERNELBENCH_ROOT = os.getenv("KERNELBENCH_ROOT")
KERNELBENCH_PYTHON = os.getenv("KERNELBENCH_PYTHON") or BENCH_PYTHON

REQUEST = (
    "KernelBench 문제다. get_init_inputs()로 Model을 만들고 get_inputs()로 입력을 만든다. "
    "출력이 원본과 같아야 한다."
)

_SCRIPT = """
from contextlib import redirect_stdout
try:
    with redirect_stdout(sys.stderr):
        from kernelbench.eval import eval_kernel_against_ref
        import tempfile
        with tempfile.TemporaryDirectory() as build_dir:
            r = eval_kernel_against_ref(
                original_model_src={reference!r},
                custom_model_src={candidate!r},
                measure_performance=True,
                verbose=False,
                build_dir=build_dir,
                backend={backend!r},
                check_for_excessive_speedup=True,
            )
    if r is None:
        print(json.dumps({{"error": "KernelBench가 결과를 돌려주지 않았다(None)."}}))
    else:
        print(json.dumps({{
            "compiled": bool(r.compiled),
            "correct": bool(r.correctness),
            "runtime": r.runtime,
            "ref_runtime": r.ref_runtime,
            "metadata": str(r.metadata)[:1000],
        }}))
except ImportError:
    print(json.dumps({{"error": "측정용 인터프리터에 KernelBench가 없다: " + traceback.format_exc()[-1000:]}}))
except Exception:
    print(json.dumps({{"error": traceback.format_exc()[-3000:]}}))
"""


def _score(reference: Path, candidate: Path) -> Score:
    source = candidate.read_text(errors="ignore")
    # 기존 워크플로는 원본과 같은 이름으로 만들라고 시킨다. 프롬프트를 바꾸지 않고 KernelBench가 찾는 ModelNew에 맞춘다.
    if "ModelNew" not in source and "class Model" in source:
        source += "\n\nModelNew = Model\n"
    # Triton 커널은 소스 파일이 있어야 jit이 되므로 KernelBench가 임시 파일로 불러오는 triton 백엔드를 쓴다.
    backend = "triton" if "import triton" in source else "cuda"
    data = _run(
        _PRELUDE + _SCRIPT.format(reference=reference.read_text(errors="ignore"), candidate=source, backend=backend),
        KERNELBENCH_PYTHON,
    )
    if "error" in data:
        return Score(False, False, None, data["error"])
    speedup = None
    if data["correct"] and data["runtime"] and data["runtime"] > 0 and data["ref_runtime"] and data["ref_runtime"] > 0:
        speedup = data["ref_runtime"] / data["runtime"]
    return Score(data["compiled"], data["correct"], speedup, "" if data["correct"] else data["metadata"])


def _prepare(level: int, problem_ids: list[int]) -> list[Problem]:
    source_dir = Path(KERNELBENCH_ROOT).expanduser() / "KernelBench" / f"level{level}"
    target_dir = ROOT / "kernelbench"
    target_dir.mkdir(parents=True, exist_ok=True)
    problems, missing = [], []
    for problem_id in problem_ids:
        found = sorted(source_dir.glob(f"{problem_id}_*.py"))
        if not found:
            missing.append(problem_id)
            continue
        # 원래 파일 이름은 숫자로 시작해 import가 안 된다.
        name = f"l{level}_p{problem_id}"
        path = target_dir / f"{name}.py"
        shutil.copyfile(found[0], path)
        problems.append(Problem(name, path))
    if missing:
        raise ConfigError(f"{source_dir}에서 문제를 찾지 못했습니다: {', '.join(map(str, missing))}")
    return problems


def run_kernelbench(level: int, problem_ids: list[int], workflow: str = "orchestrator", request: str = "") -> str:
    if not KERNELBENCH_ROOT:
        raise ConfigError("필요한 설정이 없습니다: KERNELBENCH_ROOT. .env에 지정하라 (.env.example 참고).")
    problems = _prepare(level, problem_ids)
    return run_suite(f"kernelbench_l{level}", problems, _score, workflow, f"{REQUEST}\n{request}".strip())
