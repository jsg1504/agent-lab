# optimizer-agent

OpenAI 호환 API에 연결하는 LangChain 에이전트. 엔드포인트만 바꾸면 로컬 Ollama, vLLM, LM Studio, llama.cpp, OpenAI 본체 어디에든 붙는다.

에이전트는 셋이다. 일반 어시스턴트(`agent`), 웹과 로컬 문서를 근거로 답하는 조사 담당(`researcher`), 파일을 고치고 명령을 실행하는 코딩 담당(`coder`).

## 요구 사항

- Python 3.13, [uv](https://docs.astral.sh/uv/)
- OpenAI 호환 엔드포인트 하나. 기본값은 로컬 [Ollama](https://ollama.com)(`http://localhost:11434/v1`)를 가리킨다.
- `researcher`의 웹 검색을 쓰려면 외부 네트워크 접속이 필요하다. 검색 API 키는 필요 없다.

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

코딩 담당은 `WORKSPACE_ROOT` 안에서 파일을 읽고 고치고 셸 명령을 실행한다.

```bash
WORKSPACE_ROOT=~/some/project uv run coder "test_calc.py가 실패한다. 원인을 찾아 고쳐줘."
```

> `coder`는 파일을 덮어쓰고 셸 명령을 실행한다. 되돌릴 수 있는 곳(버전 관리 중인 디렉터리)에서 쓰는 편이 안전하다.
> 파일 도구는 `WORKSPACE_ROOT` 밖을 거부하지만, `run_command`는 셸이라 그 경계가 적용되지 않는다.

## 대화 기억

대화형 모드는 앞의 대화를 기억한다. 세 에이전트 모두 해당한다.

```
> test_calc.py가 실패한다. 고쳐줘.
calc.py의 add 함수를 a - b에서 a + b로 고쳤습니다. ...

> 방금 어느 파일의 무엇을 고쳤지?
calc.py의 add 함수를 return a - b에서 return a + b로 고쳤습니다.
```

`create_agent`의 `checkpointer`에 `InMemorySaver`를 물려 구현했다. 기억은 **프로세스 안에서만** 산다.
명령을 끝내면 사라지므로 단발 질문끼리는 이어지지 않는다.

여러 대화를 나눠 담으려면 `ask(agent, question, thread_id)`에 서로 다른 `thread_id`를 준다.
실행 사이에도 기억을 남기려면 `langgraph-checkpoint-sqlite`를 설치하고 `agents/base.py`의 `InMemorySaver`를
`SqliteSaver`로 바꾸면 된다.

## 설정

`.env` 파일 또는 환경 변수로 설정한다. 모두 선택 사항이다.

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
| `WORKSPACE_ROOT` | `.` | coder가 파일을 고치고 명령을 실행할 디렉터리 |

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
  base.py           build() / ask() 공통, 대화 기억
  assistant.py      일반 어시스턴트
  researcher.py     조사 담당
  coder.py          코딩 담당
tools/
  __init__.py       TOOLS / RESEARCH_TOOLS / CODING_TOOLS 집계
  clock.py          get_current_time
  files.py          list_files
  web.py            web_search, fetch_page
  docs.py           list_docs, search_docs, read_doc
  workspace.py      WORKSPACE_ROOT와 경로 봉쇄 (code/shell 공용)
  code.py           read_file, edit_file, write_file, list_dir, glob_files, grep_files
  shell.py          run_command
```

## 도구 추가하기

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 알맞은 목록(`TOOLS`, `RESEARCH_TOOLS`, `CODING_TOOLS`)에 추가한다.

목록의 **순서**가 결과에 영향을 준다. 작은 모델은 도구가 많아지면 뒤쪽 도구를 잘 고르지 못하므로, 자주 쓰는 도구를 앞에 둔다.

## 에이전트 추가하기

1. `agents/`에 모듈을 만들고 `SYSTEM_PROMPT`와 `build(SYSTEM_PROMPT, 도구목록)`을 호출하는 팩토리를 쓴다.
2. `agents/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 `_run(팩토리, "이름")` 함수를 하나 만들고 `[project.scripts]`에 등록한다.

## 알려진 한계

기본 모델인 `qwen3.5:9b`는 도구가 일곱 개인 `coder`에서 작업은 끝내면서도 마무리 문장을 내놓지 않을 때가 있다.
그럴 때는 `ask()`가 대신 실행한 도구 목록을 보여준다. 더 큰 모델을 쓰면 줄어든다.

같은 모델이 여러 턴 대화에서 생각 부분을 답변에 흘려 `</think>`가 섞여 나오는 일도 있다.
`ask()`가 마지막 `</think>` 뒤만 남겨 걷어낸다.
