"""추적 로그. 에이전트가 받은 질문과 답, LLM에 보낸 요청과 받은 응답의 원문, 토큰 사용량을 JSONL로 남긴다.

    ask (에이전트가 질문을 받음) -> llm (LLM 호출, 여러 번) -> answer (답과 토큰 합계)

하위 에이전트가 다른 에이전트의 도구 안에서 불리면 바깥 ask가 parent와 caller로 잡힌다.
LLM 호출은 HTTP 층에서 기록한다. langchain-openai가 버리는 reasoning 필드와 서버가 보고한 usage가 그대로 남는다.
"""

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from pathlib import Path

import httpx
from openai import DefaultHttpxClient

DEFAULT_DIR = Path(__file__).resolve().parent / "traces"


@dataclass
class Ask:
    """진행 중인 ask 하나. 그 안에서 일어난 LLM 호출의 토큰을 모은다."""

    id: int
    agent: str
    started_at: str
    start: float
    answer: str | None = None
    llm_calls: int = 0
    usage: dict = field(default_factory=dict)


_current: ContextVar[Ask | None] = ContextVar("trace_ask", default=None)
_ids = count(1)
_lock = threading.Lock()
_file = None


def enabled() -> bool:
    # .env는 llm.py가 읽으므로 import 시점이 아니라 쓸 때 읽는다.
    return os.getenv("TRACE", "1").strip() != "0"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _open():
    """첫 이벤트에서 파일을 연다. 설정 오류로 끝나는 실행은 빈 파일을 남기지 않는다."""
    directory = Path(os.getenv("TRACE_DIR") or DEFAULT_DIR).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now():%Y%m%d_%H%M%S}_{Path(sys.argv[0]).stem or 'python'}"
    for n in count(1):
        path = directory / (f"{stem}.jsonl" if n == 1 else f"{stem}_{n}.jsonl")
        try:
            file = path.open("x", encoding="utf-8")
            break
        except FileExistsError:
            continue
    print(f"추적 로그: {path}", file=sys.stderr)
    run = {
        "ts": _now(),
        "type": "run",
        "argv": sys.argv,
        "model": os.getenv("OPENAI_MODEL"),
        "base_url": os.getenv("OPENAI_BASE_URL"),
    }
    file.write(json.dumps(run, ensure_ascii=False) + "\n")
    return file


def _write(type_: str, ts: str | None = None, **fields) -> None:
    if not enabled():
        return
    global _file
    line = json.dumps({"ts": ts or _now(), "type": type_, **fields}, ensure_ascii=False, default=str)
    # 병렬 갈래가 동시에 쓰므로 줄이 섞이지 않게 잠근다.
    with _lock:
        if _file is None:
            _file = _open()
        _file.write(line + "\n")
        _file.flush()


@contextmanager
def asking(agent: str, thread_id: str, question: str):
    """에이전트 하나가 질문을 받아 답할 때까지를 감싼다. 답은 돌려받은 Ask의 answer에 넣는다."""
    parent = _current.get()
    frame = Ask(next(_ids), agent, _now(), time.perf_counter())
    _write(
        "ask",
        ts=frame.started_at,
        id=frame.id,
        parent=parent.id if parent else None,
        caller=parent.agent if parent else None,
        agent=agent,
        thread_id=thread_id,
        question=question,
    )
    token = _current.set(frame)
    error = None
    try:
        yield frame
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _current.reset(token)
        result = {"error": error} if error else {"answer": frame.answer}
        _write(
            "answer",
            id=frame.id,
            agent=agent,
            started_at=frame.started_at,
            duration_s=round(time.perf_counter() - frame.start, 3),
            **result,
            llm_calls=frame.llm_calls,
            usage=frame.usage,
        )


def mark(label: str, **fields) -> None:
    """실행 중의 경계를 남긴다. 예) 벤치마크의 문제 시작."""
    _write("mark", label=label, **fields)


def _json(content: bytes):
    try:
        return json.loads(content)
    except ValueError:
        return content.decode(errors="replace")


def _on_request(request: httpx.Request) -> None:
    request.extensions["trace_started"] = (_now(), time.perf_counter())


def _on_response(response: httpx.Response) -> None:
    response.read()
    started_at, start = response.request.extensions.get("trace_started", (None, None))
    body = _json(response.content)
    usage = body.get("usage") if isinstance(body, dict) else None
    frame = _current.get()
    if frame is not None:
        frame.llm_calls += 1
        # 중첩된 *_details는 서버마다 달라서 맨 위의 숫자만 더한다.
        for key, value in (usage or {}).items():
            if isinstance(value, int | float):
                frame.usage[key] = frame.usage.get(key, 0) + value
    _write(
        "llm",
        started_at=started_at,
        duration_s=round(time.perf_counter() - start, 3) if start else None,
        ask=frame.id if frame else None,
        agent=frame.agent if frame else None,
        url=str(response.request.url),
        status=response.status_code,
        request=_json(response.request.content),
        response=body,
        usage=usage,
    )


def http_client() -> httpx.Client | None:
    """LLM 요청과 응답을 기록하는 HTTP 클라이언트. 꺼져 있으면 None(openai 기본 클라이언트를 쓴다)."""
    if not enabled():
        return None
    # 맨 httpx.Client는 타임아웃이 5초라 openai의 기본 설정을 물려받은 클라이언트를 쓴다.
    return DefaultHttpxClient(event_hooks={"request": [_on_request], "response": [_on_response]})
