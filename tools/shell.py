"""셸 실행 도구. 작업 루트에서 명령을 돌린다."""

import subprocess

from langchain_core.tools import tool

from tools.workspace import ROOT

TIMEOUT = 60
MAX_CHARS = 4000


@tool
def run_command(command: str) -> str:
    """작업 루트에서 셸 명령을 실행하고 종료 코드와 출력을 반환한다."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
            # 출력이 UTF-8이 아닐 수 있다(바이너리, 글자 중간에서 잘린 tail -c). 깨진 바이트만 바꿔 읽는다.
            errors="replace",
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"{TIMEOUT}초 안에 끝나지 않아 중단했습니다."
    output = (result.stdout + result.stderr).strip()[:MAX_CHARS]
    if not output:
        return f"exit={result.returncode} (출력 없음)"
    return f"exit={result.returncode}\n{output}"
