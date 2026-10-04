# agent-lab

도구, 에이전트, 워크플로를 조합해 LLM 에이전트 설계를 실험하는 저장소.

부품을 작게 정의해 두고, 어떤 도구를 어떤 에이전트에 주고 에이전트를 어떻게 이으면 일이 되는지를 재 본다.
LangChain `create_agent` 위에 만들었고 OpenAI 호환 API라면 어디에든 붙는다(로컬 Ollama, vLLM, LM Studio, llama.cpp, OpenAI 본체).

## 개념

| 층 | 무엇인가 | 위치 |
| --- | --- | --- |
| 도구 | `@tool` 함수. 가장 작은 부품 | `tools/` |
| 에이전트 | 시스템 프롬프트 + 도구 목록 | `agents/` |
| 워크플로 | 에이전트를 잇는 방식. LangGraph 그래프 | `workflows/` |
| 실험 기록 | 어떤 조합이 어떤 결과를 냈는지 | 아래 [실험 기록](#실험-기록) |

에이전트의 도구 목록과 프롬프트가 곧 실험 변수다. 같은 모델이라도 조합에 따라 결과가 달라진다.

## 빠른 시작

- Python 3.13, [uv](https://docs.astral.sh/uv/)
- OpenAI 호환 엔드포인트 하나. 예: 로컬 [Ollama](https://ollama.com)(`http://localhost:11434/v1`)

```bash
uv sync
cp .env.example .env      # OPENAI_BASE_URL과 OPENAI_MODEL을 채운다
uv run agent "지금 몇 시야?"
```

`OPENAI_BASE_URL`과 `OPENAI_MODEL`은 기본값이 없다. 비어 있으면 어느 값이 없는지 알려주고 끝난다.

모든 명령은 **질문을 인자로 주면 한 번 답하고 끝나고, 인자 없이 실행하면 대화형으로 들어간다**(종료: Ctrl-D).

```bash
uv run researcher "LangChain의 create_agent는 어떤 인자를 받아?"
WORKSPACE_ROOT=~/some/project uv run coder "test_calc.py가 실패한다. 원인을 찾아 고쳐줘."
WORKSPACE_ROOT=~/kernels uv run optimizer    # 대화형
```

## 카탈로그

### 에이전트

| 명령 | 역할 | 도구 목록 |
| --- | --- | --- |
| `uv run agent` | 일반 어시스턴트 | `TOOLS` |
| `uv run researcher` | 조사 담당. 웹과 로컬 문서를 근거로 답하고 출처를 밝힌다 | `RESEARCH_TOOLS` |
| `uv run coder` | 코딩 담당. `WORKSPACE_ROOT` 안에서 파일을 고치고 셸 명령을 실행한다 | `CODING_TOOLS` |
| `uv run planner` | 계획 담당. 프로파일, 분석적 상한, 채택/반려 기록을 보고 후보 가설을 순위대로 낸다 | `PLAN_TOOLS` |
| `uv run optimizer` | 최적화 담당. 딥러닝 모델과 커널 코드를 고쳐 지연을 줄인다 | `OPTIMIZE_TOOLS` |
| `uv run reviewer` | 검토 담당. 디바이스에서 재기 전에 후보 코드를 정적으로 검토한다 | `REVIEW_TOOLS` |
| `uv run evaluator` | 평가 담당. 빌드되는지, 결과가 맞는지, 얼마나 빨라졌는지 잰다 | `EVALUATE_TOOLS` |
| `uv run debugger` | 진단 담당. 실패한 후보의 원인을 밝히고 optimizer에게 줄 지시를 쓴다 | `DEBUG_TOOLS` |

### 도구 목록

`tools/__init__.py`에서 정의한다.

| 목록 | 도구 |
| --- | --- |
| `TOOLS` | `get_current_time`, `list_files` |
| `RESEARCH_TOOLS` | `web_search`, `fetch_page`, `list_docs`, `search_docs`, `read_doc`, `get_current_time` |
| `CODING_TOOLS` | `read_file`, `edit_file`, `run_command`, `list_dir`, `write_file`, `grep_files`, `glob_files` |
| `OPTIMIZE_TOOLS` | `CODING_TOOLS`와 같다 |
| `EVALUATE_TOOLS` | `read_file`, `compile_check`, `benchmark`, `compare_outputs`, `list_dir`, `glob_files` |
| `READ_TOOLS` | `read_file`, `grep_files`, `list_dir`, `glob_files` |
| `PLAN_TOOLS`, `REVIEW_TOOLS`, `DEBUG_TOOLS` | `READ_TOOLS`와 같다 |

### 도구

| 모듈 | 도구 | 비고 |
| --- | --- | --- |
| `clock.py` | `get_current_time` | |
| `files.py` | `list_files` | |
| `web.py` | `web_search`, `fetch_page` | 외부 네트워크 필요. 검색 API 키는 필요 없다 |
| `docs.py` | `list_docs`, `search_docs`, `read_doc` | `DOCS_ROOT` 아래만 본다 |
| `code.py` | `read_file`, `edit_file`, `write_file`, `list_dir`, `glob_files`, `grep_files` | `WORKSPACE_ROOT` 밖을 거부한다 |
| `shell.py` | `run_command` | `WORKSPACE_ROOT`에서 실행하지만 **샌드박스가 아니다** |
| `bench.py` | `compile_check`, `benchmark`, `compare_outputs` | `BENCH_PYTHON`에서 돈다 |

> `coder`와 `optimizer`는 파일을 덮어쓰고 셸 명령을 실행한다. 되돌릴 수 있는 곳(버전 관리 중인 디렉터리)에서 쓰는 편이 안전하다.

## 워크플로

워크플로마다 `workflows/`에 설명 문서(`.md`)를 둔다. LangGraph 그래프로 잇는 것은 같은 이름의 모듈(`.py`)이 함께 있고,
사람이 잇는 것은 문서만 있다.

| 워크플로 | 실행 | 문서 |
| --- | --- | --- |
| GPU 커널 최적화 (단발) | `uv run kernel-opt-oneshot <커널> [요청]` | [`workflows/kernel_opt_oneshot.md`](workflows/kernel_opt_oneshot.md) |
| 가속기 최적화 루프 | 사람이 에이전트를 차례로 실행 | [`workflows/accel_opt_manual.md`](workflows/accel_opt_manual.md) |

## 실험 기록

조합을 바꿔 본 결과는 여기에 남긴다. 다음 실험과 비교할 수 있도록 아래 항목을 함께 적는다.

- **조건**: 모델, 엔드포인트, 에이전트, 도구 구성, 프롬프트 변경 여부
- **과제와 판정**: 무엇을 시켰고 성공을 무엇으로 판정했는지
- **결과**: 반복 횟수와 성공/실패 수
- **해석**: 결과에서 말할 수 있는 것과 말할 수 없는 것

### 도구 구성에 따른 빈 응답 (`qwen3.5:9b`)

- **조건**: `qwen3.5:9b` @ Ollama, `optimizer`, 도구 구성만 바꿈
- **과제와 판정**: 기존 파일의 버그 수정. 고친 파일을 실행해 `torch.softmax`와 일치하면 성공
- **결과**: 구성마다 3회

| 구성 | 성공 | 빈 응답 |
| --- | --- | --- |
| 4개 도구 | 3/3 | 0/3 |
| 5개 도구 (+`list_dir`) | 0/3 | 3/3 |
| 6개 도구 (+`grep_files`) | 3/3 | 0/3 |
| 7개 도구 (+`glob_files`) | 0/3 | 3/3 |

- **해석**: 도구 개수에 따라 단조롭지 않다. 프롬프트 길이는 영향이 없었고(짧은 프롬프트 + 7개 도구도 0/3),
  빈 응답 뒤에 이어서 하라고 재촉해도 회복되지 않았다(0/3). `temperature=0`이라 각 구성은 결정적이지만
  어느 구성이 성공하느냐는 사실상 임의다. 도구 목록을 손봐서 고칠 수 있는 문제가 아니다.
  원인은 아래 [알려진 한계](#알려진-한계)에 적었다.

기타 관측:
- `evaluator`는 이 문제와 무관하게 안정적이다.
- `optimizer`는 새 최적화본을 만드는 일은 해내지만, 기존 파일을 이어서 고치는 요청에서 멈추는 것을 반복해서 관측했다.
- `reviewer`는 파일을 읽은 뒤 빈 응답으로 멈추는 것을 관측했다.

## 확장하기

### 도구 추가

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 알맞은 도구 목록에 추가한다.

목록을 바꾸면 같은 작업의 성패가 달라지는 일이 있다([실험 기록](#실험-기록) 참고). 바꿨다면 결과를 기록해 둔다.

### 에이전트 추가

1. `agents/`에 모듈을 만들고 `SYSTEM_PROMPT`와 `build(SYSTEM_PROMPT, 도구목록)`을 호출하는 팩토리를 쓴다.
2. `agents/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 `_run(팩토리, "이름")` 함수를 하나 만들고 `[project.scripts]`에 등록한다.
4. 이 README의 [카탈로그](#카탈로그) 표에 추가한다.

### 워크플로 추가

1. `workflows/`에 모듈을 만들고 그래프를 조립하는 `build_<이름>()`과 실행해 결과를 문자열로 돌려주는 `run_<이름>()`을 쓴다.
   노드 안에서는 `agents`의 팩토리로 에이전트를 만들고 `ask()`로 부른다.
2. `workflows/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 함수를 만들고 `[project.scripts]`에 등록한다.
4. `workflows/<이름>.md`에 흐름도, 노드별 에이전트와 하는 일, 설계 이유, 실행 예시를 적고, 이 README의 [워크플로](#워크플로) 표에 한 줄 추가한다.

사람이 잇는 워크플로는 코드 없이 4번의 문서만 둔다.

## 대화 기억

대화형 모드는 앞의 대화를 기억한다. 모든 에이전트에 해당한다.

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

`.env` 파일 또는 환경 변수로 설정한다. `OPENAI_BASE_URL`과 `OPENAI_MODEL`은 필수이고 나머지는 선택 사항이다.

```bash
cp .env.example .env
```

이미 설정된 환경 변수가 `.env` 값보다 우선한다. `.env`는 커밋되지 않는다.

| 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | (필수) | OpenAI 호환 엔드포인트 |
| `OPENAI_MODEL` | (필수) | 모델 이름 |
| `OPENAI_API_KEY` | (없음) | 인증이 필요한 서버에서만 지정한다. 비워 두면 자리 표시자가 들어간다 |
| `DOCS_ROOT` | `.` | researcher가 조사할 로컬 디렉터리 |
| `WORKSPACE_ROOT` | `.` | coder와 optimizer가 파일을 고치고 명령을 실행할 디렉터리. evaluator, planner, reviewer, debugger도 이 아래를 읽는다 |
| `BENCH_PYTHON` | `python3` | evaluator가 측정을 돌릴 파이썬. torch가 있어야 한다 |

연결 예시:

```bash
# 로컬 Ollama
OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_MODEL=qwen2.5:3b-instruct uv run agent "안녕"

# vLLM 등 인증 없는 서버
OPENAI_BASE_URL=http://192.168.0.10:8000/v1 OPENAI_MODEL=my-model \
  uv run agent "안녕"

# 키가 필요한 서버
OPENAI_BASE_URL=https://api.example.com/v1 OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini \
  uv run agent "안녕"
```

## 구조

```
cli.py              명령줄 진입점 (에이전트마다 하나)
llm.py              OpenAI 호환 API 연결 (ChatOpenAI)
.env.example        환경 변수 틀
agents/
  __init__.py       에이전트 재노출
  base.py           build() / ask() 공통, 대화 기억
  assistant.py      일반 어시스턴트
  researcher.py     조사 담당
  coder.py          코딩 담당
  planner.py        계획 담당
  optimizer.py      최적화 담당
  reviewer.py       검토 담당
  evaluator.py      평가 담당
  debugger.py       진단 담당
workflows/
  __init__.py       워크플로 재노출
  kernel_opt_oneshot.py  GPU 커널 최적화 (단발)
  kernel_opt_oneshot.md  그 설명
  accel_opt_manual.md    가속기 최적화 루프 설명 (사람이 이음)
tools/
  __init__.py       도구 목록 정의
  workspace.py      WORKSPACE_ROOT와 경로 봉쇄 (code/shell/bench 공용)
  clock.py, files.py, web.py, docs.py, code.py, shell.py, bench.py
```

## 알려진 한계

### 빈 응답으로 멈추는 문제

지금까지 실험에 쓴 `qwen3.5:9b`는 추론형 모델이다. Ollama는 응답을 `content`와 `reasoning` 두 필드로 나눠 주는데,
이 모델은 **`reasoning`에만 쓰고 `content`를 비워 보낼 때가 있다**. 빈 메시지인데도 출력 토큰이
90개 넘게 잡히는 것으로 확인했다. 그러면 에이전트 루프는 "할 말도 부를 도구도 없다"로 읽고 작업 도중에 멈춘다.
`langchain-openai`는 `reasoning` 필드를 버리므로 우리 쪽에는 아무 정보도 남지 않는다.

같은 이유로 추론 내용이 `content`로 새어 `</think>`가 섞여 나오기도 한다. `ask()`가 마지막 `</think>`
뒤만 남겨 걷어내고, `content`가 비면 대신 실행한 도구 목록을 보여준다. 둘 다 증상을 가릴 뿐 원인은 못 막는다.

어느 도구 구성에서 이 문제가 나타나는지는 사실상 임의다([실험 기록](#도구-구성에-따른-빈-응답-qwen359b) 참고).

`/no_think`로 이 모델의 추론을 끌 수 없고, 요청 본문의 `think: false`도 Ollama가 무시한다.
확실한 해결책은 더 큰 모델이나 추론형이 아닌 모델을 쓰는 것이다. `OPENAI_MODEL`로 바꿀 수 있다.
