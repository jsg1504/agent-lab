"""벤치마크 모음. 새 벤치마크는 어댑터 모듈을 만들고 여기서 재노출한다."""

from benchmarks.kernelbench import run_kernelbench

__all__ = ["run_kernelbench"]
