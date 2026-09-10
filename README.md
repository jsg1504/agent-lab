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
uv run agent "지금 몇 시야?"

# 대화형 (종료: Ctrl-D)
uv run agent
```

조사용 에이전트는 별도 명령이다. 웹과 로컬 문서를 근거로 답하고 출처를 밝힌다.

```bash
uv run researcher "LangChain의 create_agent는 어떤 인자를 받아?"
uv run researcher "이 프로젝트에서 LLM 연결 설정은 어디서 하지?"
```

## 설정

`.env` 파일 또는 환경 변수로 설정한다. 셋 다 선택 사항이다.

```bash
cp .env.example .env
```

이미 설정된 환경 변수가 `.env` 값보다 우선한다. `.env`는 커밋되지 않는다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | `http://localhost:11434/v1` | OpenAI 호환 엔드포인트 |
| `OPENAI_MODEL` | `qwen3.5:9b` | 모델 이름 |
| `OPENAI_API_KEY` | (없음) | 인증이 필요한 서버에서만 지정한다. 비워 두면 자리 표시자가 들어간다 |
| `DOCS_ROOT` | `.` | researcher가 조사할 로컬 디렉터리 |

연결 예시:

```bash
# 로컬 Ollama, 다른 모델
OPENAI_MODEL=qwen2.5:3b-instruct uv run agent "안녕"

# vLLM 등 인증 없는 서버
OPENAI_BASE_URL=http://192.168.0.10:8000/v1 OPENAI_MODEL=my-model \
  uv run agent "안녕"

# 키가 필요한 서버
OPENAI_BASE_URL=https://api.example.com/v1 OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini \
  uv run agent "안녕"
```

## 구조

```
cli.py              명령줄 인터페이스 (`agent`, `researcher` 진입점)
llm.py              OpenAI 호환 API 연결 (ChatOpenAI)
.env.example        환경 변수 틀
agents/
  __init__.py       에이전트 재노출
  base.py           build() / ask() 공통
  assistant.py      일반 어시스턴트
  researcher.py     조사 담당
tools/
  __init__.py       TOOLS / RESEARCH_TOOLS 집계
  clock.py          get_current_time
  files.py          list_files
  web.py            web_search, fetch_page
  docs.py           list_docs, search_docs, read_doc
```

## 도구 추가하기

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 `TOOLS` 또는 `RESEARCH_TOOLS`에 추가한다.

## 에이전트 추가하기

1. `agents/`에 모듈을 만들고 `SYSTEM_PROMPT`와 `build(SYSTEM_PROMPT, 도구목록)`을 호출하는 팩토리를 쓴다.
2. `agents/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 `_run(팩토리, "이름")` 함수를 하나 만들고 `[project.scripts]`에 등록한다.
