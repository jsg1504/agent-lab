# optimizer-agent

OpenAI 호환 API에 연결하는 LangChain 에이전트. 엔드포인트만 바꾸면 로컬 Ollama, vLLM, LM Studio, llama.cpp, OpenAI 본체 어디에든 붙는다.

에이전트는 여덟이다. 일반 어시스턴트(`agent`), 조사 담당(`researcher`), 코딩 담당(`coder`), 그리고 딥러닝 성능을 다루는
계획 담당(`planner`), 최적화 담당(`optimizer`), 검토 담당(`reviewer`), 평가 담당(`evaluator`), 진단 담당(`debugger`).

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

명령은 여덟이다. 어느 것이든 **질문을 인자로 주면 한 번 답하고 끝나고, 인자 없이 실행하면 대화형으로 들어간다**(종료: Ctrl-D).

| 명령 | 에이전트 |
| --- | --- |
| `uv run agent` | 일반 어시스턴트 |
| `uv run researcher` | 조사 담당. 웹과 로컬 문서를 근거로 답하고 출처를 밝힌다 |
| `uv run coder` | 코딩 담당. `WORKSPACE_ROOT` 안에서 파일을 고치고 셸 명령을 실행한다 |
| `uv run optimizer` | 최적화 담당. 딥러닝 모델과 커널 코드를 고쳐 지연을 줄인다 |
| `uv run evaluator` | 평가 담당. 빌드되는지, 결과가 맞는지, 얼마나 빨라졌는지 잰다 |
| `uv run planner` | 계획 담당. 프로파일, 분석적 상한, 채택/반려 기록을 보고 후보 가설을 순위대로 낸다 |
| `uv run reviewer` | 검토 담당. 디바이스에서 재기 전에 후보 코드를 정적으로 검토한다 |
| `uv run debugger` | 진단 담당. 실패한 후보의 원인을 밝히고 optimizer에게 줄 지시를 쓴다 |

```bash
# 단발 질문
uv run agent "지금 몇 시야?"
uv run researcher "LangChain의 create_agent는 어떤 인자를 받아?"
WORKSPACE_ROOT=~/some/project uv run coder "test_calc.py가 실패한다. 원인을 찾아 고쳐줘."
```

```bash
# 대화형 (종료: Ctrl-D)
uv run agent
uv run researcher
WORKSPACE_ROOT=~/some/project uv run coder
WORKSPACE_ROOT=~/kernels uv run optimizer
WORKSPACE_ROOT=~/kernels uv run evaluator
WORKSPACE_ROOT=~/kernels uv run planner
WORKSPACE_ROOT=~/kernels uv run reviewer
WORKSPACE_ROOT=~/kernels uv run debugger
```

> `coder`와 `optimizer`는 파일을 덮어쓰고 셸 명령을 실행한다. 되돌릴 수 있는 곳(버전 관리 중인 디렉터리)에서 쓰는 편이 안전하다.
> 파일 도구는 `WORKSPACE_ROOT` 밖을 거부하지만, `run_command`는 셸이라 그 경계가 적용되지 않는다.

## 성능 최적화

`optimizer`와 `evaluator`는 짝으로 쓴다. optimizer는 고치기만 하고 측정 도구가 없으며,
evaluator는 재기만 하고 코드를 고치지 않는다. 사람이 사이에서 이어준다.

```bash
export WORKSPACE_ROOT=~/kernels

uv run optimizer "slow.py의 softmax_rows가 느리다. 최적화본을 fast.py에 같은 이름으로 만들어줘."
uv run evaluator "slow.py가 원본, fast.py가 최적화본이다. 입력은 torch.randn(512,1024,device='cuda')를 쓴다. 평가해줘."
```

evaluator의 보고 꼴:

```
컴파일 : OK
정확도 : max_abs_err=3.7e-09 (통과)
지연   : 31.0ms -> 0.03ms
```

다루는 범위는 PyTorch 파이썬 코드, Triton 커널, CUDA C++ 커널이다.
`.cu`는 `nvcc -c`로, `.py`는 임포트로 빌드를 확인한다. Triton 커널은 호출할 때 컴파일되므로
임포트만으로는 문법까지만 걸러진다.

> 측정은 `BENCH_PYTHON`이 가리키는 인터프리터에서 돈다. torch가 설치된 것이어야 한다.
> 이 프로젝트의 uv venv에는 torch가 없으므로 보통 따로 지정해야 한다.

### 계획, 검토, 진단

최적화 한 바퀴는 이렇게 돈다. 에이전트 사이는 지금은 사람이 이어준다.

```
planner ──가설──> optimizer ──후보──> reviewer ──통과──> evaluator ──성공──> 채택
   ^                  ^                  │수정요청            │실패
   │                  └──────────────────┘                    v
   └──────────── 반려 기록(교훈) <─────────────────────── debugger ──지시──> optimizer
```

| 에이전트 | 하는 일 | 도구 |
| --- | --- | --- |
| `planner` | 프로파일, 분석적 상한, 채택/반려 기록을 받아 가설을 순위대로 낸다. 기대 이득은 상한을 넘지 않는다 | 읽기 전용 |
| `reviewer` | 의미 보존, 수치 안정성, 빌드, 커널별 함정을 정적으로 보고 통과/수정요청/반려로 판정한다 | 읽기 전용 |
| `debugger` | 컴파일 실패, 정확도 불통과, 성능 퇴행의 원인을 구현 실수와 가설 오류로 가른다 | 읽기 전용 |

세 에이전트 모두 코드를 고치지도 재지도 않는다. `reviewer`는 디바이스를 쓰기 전 단계라 `compile_check`도 없다.

측정 노이즈로 인한 실패는 재측정으로 보내고 `debugger`에 넘기지 않는다. `debugger`의 진단은 반려 기록에
교훈으로 쌓이므로, 노이즈나 구현 실수를 "이 방향은 안 된다"로 적으면 옳은 방향이 묻힌다.
그래서 `debugger`는 확신도를 함께 적고, 구현 실수이거나 원인이 불명이면 교훈을 남기지 않는다.

```bash
uv run planner "프로파일: slow.py의 softmax_rows가 90%. 상한: 최대 10x. 채택: 없음. 반려: #1 torch.compile(컴파일 시간 과다)"
uv run reviewer "slow.py가 원본, fast.py가 후보다. 가설: 행 루프를 벡터화. 검토해줘."
uv run debugger "slow.py가 원본, fast.py가 후보다. evaluator 보고 - 정확도: max_abs_err=nan (불통과). 진단해줘."
```

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
| `WORKSPACE_ROOT` | `.` | coder와 optimizer가 파일을 고치고 명령을 실행할 디렉터리. evaluator, planner, reviewer, debugger도 이 아래를 읽는다 |
| `BENCH_PYTHON` | `python3` | evaluator가 측정을 돌릴 파이썬. torch가 있어야 한다 |

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
  optimizer.py      최적화 담당
  evaluator.py      평가 담당
  planner.py        계획 담당
  reviewer.py       검토 담당
  debugger.py       진단 담당
tools/
  __init__.py       도구 목록 집계 (TOOLS, RESEARCH_TOOLS, CODING_TOOLS,
                    OPTIMIZE_TOOLS, EVALUATE_TOOLS, READ_TOOLS,
                    PLAN_TOOLS, REVIEW_TOOLS, DEBUG_TOOLS)
  clock.py          get_current_time
  files.py          list_files
  web.py            web_search, fetch_page
  docs.py           list_docs, search_docs, read_doc
  workspace.py      WORKSPACE_ROOT와 경로 봉쇄 (code/shell 공용)
  code.py           read_file, edit_file, write_file, list_dir, glob_files, grep_files
  shell.py          run_command
  bench.py          compile_check, benchmark, compare_outputs
```

## 도구 추가하기

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 알맞은 목록(`TOOLS`, `RESEARCH_TOOLS`, `CODING_TOOLS`)에 추가한다.

목록을 바꾸면 같은 작업의 성패가 달라지는 일이 있다. 도구가 잘못돼서가 아니라 모델 쪽 문제이며,
아래 '알려진 한계'에 적었다. 일단 자주 쓰는 도구를 앞에 두는 편이 무난하다.

## 에이전트 추가하기

1. `agents/`에 모듈을 만들고 `SYSTEM_PROMPT`와 `build(SYSTEM_PROMPT, 도구목록)`을 호출하는 팩토리를 쓴다.
2. `agents/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 `_run(팩토리, "이름")` 함수를 하나 만들고 `[project.scripts]`에 등록한다.

## 알려진 한계

### 빈 응답으로 멈추는 문제

기본 모델 `qwen3.5:9b`는 추론형 모델이다. Ollama는 응답을 `content`와 `reasoning` 두 필드로 나눠 주는데,
이 모델은 **`reasoning`에만 쓰고 `content`를 비워 보낼 때가 있다**. 빈 메시지인데도 출력 토큰이
90개 넘게 잡히는 것으로 확인했다. 그러면 에이전트 루프는 "할 말도 부를 도구도 없다"로 읽고 작업 도중에 멈춘다.
`langchain-openai`는 `reasoning` 필드를 버리므로 우리 쪽에는 아무 정보도 남지 않는다.

같은 이유로 추론 내용이 `content`로 새어 `</think>`가 섞여 나오기도 한다. `ask()`가 마지막 `</think>`
뒤만 남겨 걷어내고, `content`가 비면 대신 실행한 도구 목록을 보여준다. 둘 다 증상을 가릴 뿐 원인은 못 막는다.

실제로 겪은 모습은 이렇다. `optimizer`에게 기존 파일의 버그 수정을 시키고 도구 구성만 바꿔가며
각 3회씩 잰 결과다. 판정은 고친 파일을 실행해 `torch.softmax`와 일치하는지로 했다.

| 구성 | 성공 | 빈 응답 |
| --- | --- | --- |
| 4개 도구 | 3/3 | 0/3 |
| 5개 도구 (+`list_dir`) | 0/3 | 3/3 |
| 6개 도구 (+`grep_files`) | 3/3 | 0/3 |
| 7개 도구 (+`glob_files`) | 0/3 | 3/3 |

개수에 따라 단조롭지 않다. 프롬프트 길이는 영향이 없었고(짧은 프롬프트 + 7개 도구도 0/3),
빈 응답 뒤에 이어서 하라고 재촉해도 회복되지 않았다(0/3). `temperature=0`이라 각 구성은 결정적이지만
어느 구성이 성공하느냐는 사실상 임의다. 도구 목록을 손봐서 고칠 수 있는 문제가 아니다.

`/no_think`로 이 모델의 추론을 끌 수 없고, 요청 본문의 `think: false`도 Ollama가 무시한다.
확실한 해결책은 더 큰 모델이나 추론형이 아닌 모델을 쓰는 것이다. `OPENAI_MODEL`로 바꿀 수 있다.

### 영향 범위

`evaluator`는 이 문제와 무관하게 안정적이다. `reviewer`는 파일을 읽은 뒤 빈 응답으로 멈추는 것을 관측했다. `optimizer`도 새 최적화본을 만드는 일은 해내지만,
기존 파일을 이어서 고치는 요청에서 멈추는 것을 반복해서 관측했다.
