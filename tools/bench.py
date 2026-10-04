"""컴파일 확인, 정확도 비교, 지연 측정 도구. 측정은 별도 인터프리터에서 돌린다."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from langchain_core.tools import tool

from tools.workspace import ROOT, resolve

BENCH_PYTHON = os.getenv("BENCH_PYTHON", "python3")
TIMEOUT = 300
WARMUP = 10

_PRELUDE = """
import json, sys, os, time, traceback
sys.path.insert(0, os.getcwd())
try:
    import torch
    CUDA = torch.cuda.is_available()
except Exception:
    torch, CUDA = None, False
G = {}
"""


def _run(script: str, python: str = BENCH_PYTHON) -> dict:
    """준비된 파이썬 스크립트를 측정용 인터프리터로 실행하고 JSON 결과를 받는다."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(_PRELUDE + script)
        path = handle.name
    try:
        result = subprocess.run(
            [python, path],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except FileNotFoundError:
        return {"error": f"측정용 인터프리터를 찾지 못했습니다: {python}. .env의 설정을 확인하라."}
    except subprocess.TimeoutExpired:
        return {"error": f"{TIMEOUT}초 안에 끝나지 않아 중단했습니다."}
    finally:
        os.unlink(path)

    for line in reversed(result.stdout.splitlines()):
        if line.startswith("{"):
            return json.loads(line)
    return {"error": (result.stderr or result.stdout).strip()[:3000] or "출력이 없습니다."}


def _report(data: dict) -> str:
    if "error" in data:
        return f"실패:\n{data['error']}"
    return "\n".join(f"{key}: {value}" for key, value in data.items())


@tool
def benchmark(setup: str, statement: str, repeats: int = 50) -> str:
    """statement의 실행 시간을 잰다. setup은 한 번만 돌며 statement가 쓸 것을 준비한다.

    GPU에서는 CUDA 이벤트로 재고 워밍업을 거친다. 결과는 밀리초 단위다.
    예) setup="import torch; from m import f; x=torch.randn(4096,4096,device='cuda')"
        statement="f(x)"
    """
    script = f"""
try:
    exec({setup!r}, G)
    stmt = compile({statement!r}, "<statement>", "exec")
    for _ in range({WARMUP}):
        exec(stmt, G)
    if CUDA:
        torch.cuda.synchronize()
    times = []
    for _ in range({int(repeats)}):
        if CUDA:
            s, e = torch.cuda.Event(True), torch.cuda.Event(True)
            s.record(); exec(stmt, G); e.record()
            torch.cuda.synchronize()
            times.append(s.elapsed_time(e))
        else:
            t0 = time.perf_counter(); exec(stmt, G)
            times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    n = len(times)
    print(json.dumps({{
        "device": "cuda" if CUDA else "cpu",
        "repeats": n,
        "mean_ms": round(sum(times) / n, 4),
        "median_ms": round(times[n // 2], 4),
        "min_ms": round(times[0], 4),
        "max_ms": round(times[-1], 4),
    }}))
except Exception:
    print(json.dumps({{"error": traceback.format_exc()[-3000:]}}))
"""
    return _report(_run(script))


@tool
def compare_outputs(setup: str, reference: str, candidate: str, tolerance: float = 1e-3) -> str:
    """두 식의 결과가 같은지 비교한다. 최적화가 답을 바꾸지 않았는지 확인할 때 쓴다.

    예) setup="import torch; from old import f; from new import g; x=torch.randn(1024,1024,device='cuda')"
        reference="f(x)", candidate="g(x)"
    """
    script = f"""
try:
    exec({setup!r}, G)
    ref = eval({reference!r}, G)
    cand = eval({candidate!r}, G)
    if torch is not None and torch.is_tensor(ref):
        ref_f, cand_f = ref.float(), cand.float()
        if ref_f.shape != cand_f.shape:
            print(json.dumps({{"passed": False, "reason": f"모양이 다르다: {{tuple(ref_f.shape)}} vs {{tuple(cand_f.shape)}}"}}))
        else:
            diff = (ref_f - cand_f).abs()
            max_abs = diff.max().item()
            max_rel = (diff / ref_f.abs().clamp_min(1e-12)).max().item()
            print(json.dumps({{
                "passed": bool(max_abs <= {float(tolerance)}),
                "tolerance": {float(tolerance)},
                "max_abs_err": float(f"{{max_abs:.3e}}"),
                "max_rel_err": float(f"{{max_rel:.3e}}"),
                "shape": str(tuple(ref_f.shape)),
                "dtype": str(ref.dtype),
            }}))
    else:
        print(json.dumps({{"passed": bool(ref == cand), "note": "텐서가 아니라 == 로 비교했다"}}))
except Exception:
    print(json.dumps({{"error": traceback.format_exc()[-3000:]}}))
"""
    return _report(_run(script))


@tool
def compile_check(path: str) -> str:
    """파일이 빌드되는지 본다. .py는 임포트해 보고, .cu는 nvcc로 컴파일한다.

    Triton 커널은 호출할 때 컴파일되므로 임포트만으로는 문법까지만 확인된다.
    """
    target = resolve(path)
    if target is None:
        return "작업 범위 밖의 경로입니다."
    if not target.is_file():
        return f"파일이 없습니다: {path}"

    if target.suffix in {".cu", ".cuh"}:
        nvcc = shutil.which("nvcc") or "/usr/local/cuda/bin/nvcc"
        if not Path(nvcc).exists():
            return "nvcc를 찾지 못했습니다."
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [nvcc, "-arch=native", "-c", str(target), "-o", f"{tmp}/out.o"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        if result.returncode == 0:
            return "컴파일 성공 (nvcc -c)"
        return f"컴파일 실패:\n{result.stderr.strip()[:3000]}"

    module = str(target.relative_to(ROOT)).removesuffix(".py").replace("/", ".")
    script = f"""
try:
    __import__({module!r})
    print(json.dumps({{"ok": True, "note": "임포트 성공"}}))
except Exception:
    print(json.dumps({{"error": traceback.format_exc()[-3000:]}}))
"""
    return _report(_run(script))
