# optimizer-agent

OpenAI 호환 API에 연결하는 LangChain 에이전트. 엔드포인트만 바꾸면 로컬 Ollama, vLLM, LM Studio, llama.cpp, OpenAI 본체 어디에든 붙는다.

## 요구 사항

- Python 3.13, [uv](https://docs.astral.sh/uv/)
- OpenAI 호환 엔드포인트 하나. 기본값은 로컬 [Ollama](https://ollama.com)(`http://localhost:11434/v1`)를 가리킨다.

## 설치

```bash
uv sync
```

기본값 그대로 Ollama를 쓴다면 모델을 미리 받아둔다:

```bash
ollama pull qwen3.5:9b
```

## 실행

```bash
# 단발 질문
uv run python agent.py "지금 몇 시야?"

# 대화형 (종료: Ctrl-D)
uv run python agent.py
```

## 설정

환경 변수로 재정의한다. 셋 다 선택 사항이다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | `http://localhost:11434/v1` | OpenAI 호환 엔드포인트 |
| `OPENAI_MODEL` | `qwen3.5:9b` | 모델 이름 |
| `OPENAI_API_KEY` | (없음) | 인증이 필요한 서버에서만 지정한다. 비워 두면 자리 표시자가 들어간다 |

연결 예시:

```bash
# 로컬 Ollama, 다른 모델
OPENAI_MODEL=qwen2.5:3b-instruct uv run python agent.py "안녕"

# vLLM 등 인증 없는 서버
OPENAI_BASE_URL=http://192.168.0.10:8000/v1 OPENAI_MODEL=my-model \
  uv run python agent.py "안녕"

# 키가 필요한 서버
OPENAI_BASE_URL=https://api.example.com/v1 OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini \
  uv run python agent.py "안녕"
```

## 구조

```
agent.py            에이전트 조립 + CLI
llm.py              OpenAI 호환 API 연결 (ChatOpenAI)
tools/
  __init__.py       TOOLS 집계
  clock.py          get_current_time
  files.py          list_files
```

## 도구 추가하기

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 `TOOLS`에 추가한다.

`agent.py`는 수정할 필요가 없다.
