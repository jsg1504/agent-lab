# agent-lab

도구, 에이전트, 워크플로를 조합해 LLM 에이전트 설계를 실험하는 저장소.

부품을 작게 정의해 두고, 어떤 도구를 어떤 에이전트에 주고 에이전트를 어떻게 이으면 일이 되는지를 재 본다.
LangChain `create_agent` 위에 만들었고 OpenAI 호환 API라면 어디에든 붙는다. 엔드포인트와 모델은 정해 두지 않았고 설정으로 고른다.

## 개념

| 층 | 무엇인가 | 위치 |
| --- | --- | --- |
| 도구 | `@tool` 함수. 가장 작은 부품 | `tools/` |
| 에이전트 | 시스템 프롬프트 + 도구 목록 | `agents/` |
| 워크플로 | 에이전트를 잇는 방식. LangGraph 그래프 | `workflows/` |
| 벤치마크 | 워크플로를 공개 문제 집합에 돌리고 공식 채점기로 채점한다 | `benchmarks/` |
| 실험 기록 | 어떤 조합이 어떤 결과를 냈는지 | 아래 [실험 기록](#실험-기록) |

에이전트의 도구 목록과 프롬프트가 곧 실험 변수다. 같은 모델이라도 조합에 따라 결과가 달라진다.

## 빠른 시작

- Python 3.13, [uv](https://docs.astral.sh/uv/)
- OpenAI 호환 엔드포인트 하나(로컬 서버든 호스팅 API든 상관없다). 연결 예시는 [설정](#설정) 참고

```bash
uv sync
cp .env.example .env      # OPENAI_BASE_URL과 OPENAI_MODEL을 채운다
uv run agent "지금 몇 시야?"
```

`OPENAI_BASE_URL`과 `OPENAI_MODEL`은 기본값이 없다. 비어 있으면 어느 값이 없는지 알려주고 끝난다.

에이전트 명령은 **질문을 인자로 주면 한 번 답하고 끝나고, 인자 없이 실행하면 대화형으로 들어간다**(종료: Ctrl-D).
워크플로 명령은 한 번 실행하고 끝난다.

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
| `uv run researcher` | 조사 담당. 웹과 로컬 문서를 근거로 답하고 출처를 밝힌다. 도구 호출이 20번쯤(40스텝)에 닿으면 더 찾지 않고 그때까지 확인한 내용으로 답한다 | `RESEARCH_TOOLS` |
| `uv run npu-researcher` | NPU 조사 담당. `NPU_WIKI_ROOT`의 NPU wiki만 근거로 답하고 페이지 id를 밝힌다. 웹은 보지 않는다 | `NPU_RESEARCH_TOOLS` |
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
| `NPU_RESEARCH_TOOLS` | `search_wiki`, `read_wiki_page` |
| `CODING_TOOLS` | `read_file`, `edit_file`, `run_command`, `list_dir`, `write_file`, `grep_files`, `glob_files` |
| `OPTIMIZE_TOOLS` | `CODING_TOOLS`와 같다 |
| `EVALUATE_TOOLS` | `read_file`, `compile_check`, `benchmark`, `compare_outputs`, `list_dir`, `glob_files` |
| `READ_TOOLS` | `read_file`, `grep_files`, `list_dir`, `glob_files` |
| `PLAN_TOOLS`, `REVIEW_TOOLS`, `DEBUG_TOOLS` | `READ_TOOLS`와 같다 |

### 도구

| 모듈 | 도구 | 비고 |
| --- | --- | --- |
| `clock.py` | `get_current_time` | |
| `files.py` | `list_files` | `WORKSPACE_ROOT` 제한 없이 아무 디렉터리나 본다 |
| `web.py` | `web_search`, `fetch_page` | 외부 네트워크 필요. 검색 API 키는 필요 없다. `fetch_page`는 4000자씩 돌려주고 `offset`으로 이어 읽는다 |
| `docs.py` | `list_docs`, `search_docs`, `read_doc` | `DOCS_ROOT` 아래만 본다. `read_doc`은 4000자씩 돌려주고 `offset`으로 이어 읽는다 |
| `npu_wiki.py` | `search_wiki`, `read_wiki_page` | `NPU_WIKI_ROOT` 아래만 본다 |
| `code.py` | `read_file`, `edit_file`, `write_file`, `list_dir`, `glob_files`, `grep_files` | `WORKSPACE_ROOT` 밖을 거부한다 |
| `shell.py` | `run_command` | `WORKSPACE_ROOT`에서 실행하지만 **샌드박스가 아니다** |
| `bench.py` | `compile_check`, `benchmark`, `compare_outputs` | `BENCH_PYTHON`에서 돈다 |

NPU wiki는 마크다운 페이지를 모아 둔 디렉터리다. 페이지 앞머리의 frontmatter에서 `id`, `title`, `tags`, `aliases`, `confidence`를 읽고, `search_wiki`는 제목·id, 태그·별칭, 본문 순으로 가중치를 두어 찾는다. frontmatter가 없으면 경로가 id, 첫 `#` 제목이 title이 된다. `read_wiki_page`는 앞 4000자만 돌려주므로 결론을 페이지 앞쪽에 둔다.

```markdown
---
id: hw-dma-engine
title: DMA 엔진
tags: [dma, memory]
aliases:
  - TMA
  - 데이터 이동 엔진
confidence: verified
---

DMA 엔진은 DRAM과 온칩 SRAM 사이 블록 전송을 맡는다. ...
```

> `coder`와 `optimizer`는 파일을 덮어쓰고 셸 명령을 실행한다. 되돌릴 수 있는 곳(버전 관리 중인 디렉터리)에서 쓰는 편이 안전하다.

## 워크플로

워크플로마다 `workflows/<이름>/` 디렉터리를 두고, 설명 문서는 그 안의 `README.md`다. LangGraph 그래프로 잇는 것은 코드가 함께 있고,
사람이 잇는 것은 문서만 있다.

| 워크플로 | 실행 | 문서 |
| --- | --- | --- |
| GPU 커널 최적화 (단발) | `uv run kernel-opt-oneshot <커널> [요청]` | [`workflows/kernel_opt_oneshot/`](workflows/kernel_opt_oneshot/README.md) |
| GPU 커널 최적화 (오케스트레이터 + 하위 에이전트) | `uv run kernel-opt-orchestrator <커널> [요청]` | [`workflows/kernel_opt_orchestrator/`](workflows/kernel_opt_orchestrator/README.md) |
| 가속기 최적화 루프 | 사람이 에이전트를 차례로 실행 | [`workflows/accel_opt_manual/`](workflows/accel_opt_manual/README.md) |

## 벤치마크

워크플로를 벤치마크 문제 여러 개에 돌리고, 끝난 뒤 공식 채점기로 후보(`<문제>_opt*`)를 모두 채점해 집계한다.
기본은 채점을 하네스만 하고 **에이전트는 공식 채점기를 모르는** 것이다. 에이전트의 도구와 프롬프트가 그대로라 워크플로끼리, 모델끼리 같은 잣대로 비교할 수 있다.

예외로 **FlashInfer-Bench를 오케스트레이터 워크플로로 돌릴 때는 채점이 루프 안에도 들어간다.** 오케스트레이터가 라운드마다 `official_score` 도구로 같은 채점을 부르고,
그 결과를 보고 고쳐서 다시 돈다([워크플로 문서](workflows/kernel_opt_orchestrator/README.md#루프-안-공식-채점)).
보고서의 "루프 안 공식 채점" 줄에 어느 쪽이었는지 남는다. 두 방식의 결과는 조건이 달라 나란히 비교하지 않는다.

벤치마크가 도는 동안에는 `DOCS_ROOT`가 이 프로젝트나 `WORKSPACE_ROOT`와 겹치면(기본값이 그렇다) researcher의 로컬 문서 조사를 빈 디렉터리로 돌린다.
채점 어댑터, 이전 보고서, 다른 실행의 후보를 읽지 못하게 하기 위해서다. 참고 자료를 주려면 두 곳과 겹치지 않는 디렉터리를 `DOCS_ROOT`로 지정한다.
어느 쪽이었는지는 보고서의 "로컬 문서" 줄에 남는다.

| 벤치마크 | 실행 |
| --- | --- |
| [KernelBench](https://github.com/ScalingIntelligence/KernelBench) | `uv run kernelbench <레벨> <문제 번호...> [--workflow orchestrator\|oneshot] [--request "..."]` |
| [FlashInfer-Bench](https://github.com/flashinfer-ai/flashinfer-bench) | `uv run flashinferbench <definition 또는 op_type...> [--workflow orchestrator\|oneshot] [--request "..."] [--max-workloads N]` |

### KernelBench

KernelBench는 이 프로젝트의 의존성이 아니다. torch가 있는 측정용 파이썬에 따로 설치한다.

```bash
git clone https://github.com/ScalingIntelligence/KernelBench.git ~/KernelBench
git -C ~/KernelBench checkout 423217d9fda91e0c2d67e4a43bf62f96f6d104f1
<측정용 python> -m pip install -e ~/KernelBench
```

`.env`에 `KERNELBENCH_ROOT=~/KernelBench`를 넣고, 측정용 파이썬이 `BENCH_PYTHON`과 다르면 `KERNELBENCH_PYTHON`도 지정한다.

```bash
uv run kernelbench 1 1-3                      # 레벨 1의 1~3번, 오케스트레이터 워크플로
uv run kernelbench 1 19 23 --workflow oneshot # 단발 워크플로
```

- 문제는 `WORKSPACE_ROOT/kernelbench/l<레벨>_p<번호>.py`로 복사된다. 같은 이름의 이전 후보는 실행 전에 지운다.
- 후보는 원본과 같이 `Model` 클래스로 만들어도 된다. `ModelNew`가 없으면 `Model`을 `ModelNew`로 보고 채점한다.
  `import triton`이 있는 후보는 KernelBench의 triton 백엔드로 채점한다.
- 지표: 정확 비율, `fast_0`(정확한 비율), `fast_1`(정확하고 원본보다 빠른 비율), 정확한 문제의 속도향상 기하평균.
  문제마다 정확한 후보 중 가장 빠른 것을 쓴다. 원본을 그대로 낸 후보도 측정 잡음으로 1.0x를 조금 넘을 수 있다.

### FlashInfer-Bench

FlashInfer-Bench도 이 프로젝트의 의존성이 아니다. torch가 있는 측정용 파이썬에 따로 설치한다.

```bash
git clone https://github.com/flashinfer-ai/flashinfer-bench.git ~/flashinfer-bench
git -C ~/flashinfer-bench checkout 23ac808d1e617dca7e551e412294bcd840e3d5d9
<측정용 python> -m pip install -e ~/flashinfer-bench
```

`.env`의 `FLASHINFER_TRACE_ROOT`에 데이터셋 디렉터리(`definitions/`와 `workloads/`가 있는 곳)를 넣는다.
측정용 파이썬이 `BENCH_PYTHON`과 다르면 `FLASHINFER_BENCH_PYTHON`도 지정한다.

- 저장소 안의 `~/flashinfer-bench/flashinfer_trace`를 그대로 쓸 수 있다. 입력이 모두 난수인 `gemm`, `rmsnorm`은 이것만으로 돈다.
- `gqa_paged`, `gqa_ragged`, `mla_paged`, `moe`처럼 실제 입력 텐서를 쓰는 workload는
  [flashinfer-trace 데이터셋](https://huggingface.co/datasets/flashinfer-ai/flashinfer-trace)(약 26GB)을 받아 그 경로를 지정해야 한다.

```bash
uv run flashinferbench rmsnorm_h4096                       # definition 하나, 오케스트레이터 워크플로
uv run flashinferbench rmsnorm --workflow oneshot          # op_type 이름을 주면 그 아래 definition 전부
uv run flashinferbench gemm_n4096_k4096 --max-workloads 0  # 그 definition의 workload를 전부 채점
```

- 문제 하나가 definition 하나다. definition의 PyTorch 기준 구현이 `WORKSPACE_ROOT/fibench/<definition>.py`로 만들어지고,
  파일 머리에 축과 입력·출력의 모양, dtype이 주석으로 붙는다. 같은 이름의 이전 후보는 실행 전에 지운다.
- 후보는 원본처럼 `run` 함수가 출력을 반환하는 파이썬 파일이어야 한다. `import triton`이 있는 후보는 triton 솔루션으로 채점한다.
  C++/CUDA 솔루션은 채점하지 않는다.
- definition마다 workload를 `--max-workloads`개(기본 8, `0`이면 전부) 고르게 골라 잰다.
  후보가 **고른 workload를 모두 통과해야** 정확한 것으로 치고, 속도향상은 workload별 속도향상(기준 구현 대비)의 기하평균이다.
- 지표는 KernelBench와 같고 definition 단위다. FlashInfer-Bench 논문의 `fast_p`는 workload 단위라 값이 다르다.
- `--workflow orchestrator`(기본)에서는 오케스트레이터가 루프 안에서 같은 채점(`--max-workloads`도 같음)을 부르며 3라운드를 모두 돈다. 통과한 뒤에도 남은 라운드에서 더 빠른 후보를 노린다.
  끝난 뒤의 채점은 그대로 다시 하고, 보고서의 수치는 그쪽이 기준이다. `--workflow oneshot`에는 루프가 없어 해당하지 않는다.
- 결과는 화면에 요약과 후보별 채점 표로 나오고, 워크플로 보고 원문까지 담은 보고서가 `WORKSPACE_ROOT/benchmarks/`에 남는다.
- 이 커밋의 레벨 1 문제는 입력이 수 GiB인 것이 많다. GPU 메모리가 작으면 OOM으로 실패로 채점된다.
  하드웨어와 채점 설정이 다르므로 수치는 공식 리더보드와 바로 비교할 수 없다.

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

### 오케스트레이터 워크플로 첫 실행 (`glm-5.3-flash`)

- **조건**: `glm-5.3-flash` @ `https://ollama.com/v1`, `kernel-opt-orchestrator`. 오케스트레이터 도구는 `research`, `optimize`, `evaluate`,
  하위 에이전트(`researcher`, `optimizer`, `evaluator`)의 도구와 프롬프트는 그대로
- **과제와 판정**: 행 루프와 `.item()`으로 짠 `softmax_rows`를 "GPU에서 빠르게. 입력은 torch.randn(512,1024,device='cuda')".
  세 하위 에이전트를 모두 거쳐 끝나고, 보고의 수치가 위임 기록의 evaluator 원문과 일치하면 성공
- **결과**: 측정 환경을 갖춘 실행 1회, 성공 1/1. 1라운드에서 멈췄다. research → optimize → evaluate 한 번씩,
  `max_abs_err=7.451e-09`, 48.07ms → 0.033ms. 약 1분 30초
- **해석**: 구조가 끝까지 돈다는 것만 말할 수 있다. 1회라 안정성은 말할 수 없고, 과제가 쉬워 2라운드 이상(실패 뒤 지시를 고쳐 다시 도는 경로)은
  확인하지 못했다. 그 전 실행에서 `web_search`가 예외를 내 researcher가 실패했을 때는 오케스트레이터가 조사 없이 진행했고,
  측정용 인터프리터에 torch가 없었을 때는 수치를 지어내지 않고 "채택 없음"으로 보고했다.

## 확장하기

### 도구 추가

1. `tools/`에 모듈을 만들고 `@tool` 함수를 작성한다.
2. `tools/__init__.py`에서 import 한 뒤 알맞은 도구 목록에 추가한다.

목록을 바꾸면 같은 작업의 성패가 달라지는 일이 있다([실험 기록](#실험-기록) 참고). 바꿨다면 결과를 기록해 둔다.

### 에이전트 추가

1. `agents/`에 모듈을 만들고 `SYSTEM_PROMPT`와 `build(SYSTEM_PROMPT, 도구목록, name="이름")`을 호출하는 팩토리를 쓴다.
   `name`은 추적 로그에서 이 에이전트를 가리키는 이름이다.
2. `agents/__init__.py`에서 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 `_run(팩토리, "이름")` 함수를 하나 만들고 `[project.scripts]`에 등록한다.
4. 이 README의 [카탈로그](#카탈로그) 표에 추가한다.

모델은 기본으로 `OPENAI_MODEL`을 쓴다. 에이전트마다 다른 모델을 쓰려면 `build(SYSTEM_PROMPT, 도구목록, model="모델 이름")`처럼
`model`을 넘긴다. 엔드포인트(`OPENAI_BASE_URL`)는 모두 같은 것을 쓰므로 그 서버가 제공하는 모델이어야 한다.

### 워크플로 추가

1. `workflows/<이름>/` 디렉터리를 만들고, 그 안에 그래프를 조립하는 `build_<이름>()`과 실행해 결과를 문자열로 돌려주는 `run_<이름>()`을 쓴다.
   노드 안에서는 `agents`의 팩토리로 에이전트를 만들고 `ask()`로 부른다. 모듈을 어떻게 나눌지는 워크플로마다 정한다.
2. `workflows/<이름>/__init__.py`에서 두 함수를 재노출하고, `workflows/__init__.py`에서 다시 재노출한다.
3. 명령으로 쓰려면 `cli.py`에 함수를 만들고 `[project.scripts]`에 등록한다.
4. `workflows/<이름>/README.md`에 흐름도, 노드별 에이전트와 하는 일, 설계 이유, 실행 예시를 적고, 이 README의 [워크플로](#워크플로) 표에 한 줄 추가한다.

사람이 잇는 워크플로는 코드 없이 `workflows/<이름>/README.md`만 둔다.

### 벤치마크 추가

1. `benchmarks/<이름>.py`에 어댑터를 쓴다. 문제를 `WORKSPACE_ROOT` 아래로 준비해 `Problem` 목록을 만들고,
   원본과 후보 경로를 받아 `Score(compiled, correct, speedup, detail)`를 돌려주는 채점 함수를 쓴 뒤 `run_suite()`를 부른다.
   workload가 여러 개인 벤치마크라면 이를 하나의 `Score`로 줄이는 방법도 어댑터가 정한다.
2. 측정용 파이썬은 `<이름>_PYTHON`처럼 벤치마크마다 두고, 비어 있으면 `BENCH_PYTHON`을 쓴다. 채점 스크립트는 `tools/bench.py`의 `_run(script, python, timeout)`으로 돌린다.
3. `benchmarks/__init__.py`에서 재노출하고, `cli.py`에 명령을 만들어 `[project.scripts]`에 등록한다.
4. 이 README의 [벤치마크](#벤치마크) 표와 설정 표에 추가한다.

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

## 추적 로그

모든 명령은 실행마다 `traces/<날짜_시각>_<명령>.jsonl` 파일 하나에 다음을 남긴다(경로는 시작할 때 stderr에 나온다).

- 에이전트가 받은 질문과 낸 답. 하위 에이전트라면 누가 불렀는지(`caller`, `parent`)
- 에이전트가 LLM에 보낸 요청 원문(시스템 프롬프트, 대화, 도구 스키마, 파라미터)과 받은 응답 원문(`reasoning` 포함)
- LLM 호출마다, 그리고 질문 하나를 답하는 동안의 토큰 사용량(서버가 보고한 `usage`)
- 모든 줄의 발생 시각(`ts`, 시간대 포함 밀리초). 구간이 있는 줄은 시작 시각(`started_at`)과 걸린 시간(`duration_s`)도

한 줄이 이벤트 하나다.

| `type` | 언제 | 주요 필드 |
| --- | --- | --- |
| `run` | 파일 첫 줄 | `argv`, `model`, `base_url` |
| `ask` | 에이전트가 질문을 받음 | `id`, `agent`, `caller`, `parent`, `thread_id`, `question` |
| `llm` | LLM 호출 하나가 끝남 | `ask`, `agent`, `started_at`, `duration_s`, `status`, `request`, `response`, `usage` |
| `answer` | 에이전트가 답함 | `id`, `agent`, `started_at`, `duration_s`, `answer` 또는 `error`, `llm_calls`, `usage` |
| `mark` | 벤치마크가 문제를 시작함 | `label`(`problem`), `name`, `workflow` |

`answer.usage`는 그 에이전트가 직접 한 LLM 호출의 합계다. 오케스트레이터의 합계에 하위 에이전트 몫은 들어 있지 않다.
요청 원문에는 매번 대화 전체가 실리므로 긴 실행은 파일이 커진다. 끄려면 `TRACE=0`, 위치를 바꾸려면 `TRACE_DIR`를 지정한다.

`jq`로 보는 예:

```bash
f=$(ls -t traces/*.jsonl | head -1)

# 누가 누구에게 무엇을 시켰나
jq -r 'select(.type=="ask") | "\(.ts) #\(.id) \(.caller // "-") -> \(.agent): \(.question[:80])"' $f

# 에이전트별 토큰 합계
jq -s 'map(select(.type=="answer")) | group_by(.agent)
       | map({agent: .[0].agent, calls: (map(.llm_calls) | add), tokens: (map(.usage.total_tokens // 0) | add)})' $f

# content가 비고 reasoning만 온 응답 (빈 응답 문제 추적)
jq -c 'select(.type=="llm") | .response.choices[0].message
       | select((.content // "") == "" and (.tool_calls | not)) | {reasoning}' $f
```

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
| `DOCS_ROOT` | `.` | researcher가 조사할 로컬 디렉터리. 벤치마크에서는 프로젝트나 `WORKSPACE_ROOT`와 겹치면 쓰지 않는다([벤치마크](#벤치마크)) |
| `NPU_WIKI_ROOT` | (없음) | npu-researcher가 조사할 NPU wiki 디렉터리. `uv run npu-researcher`에만 필요하다 |
| `WORKSPACE_ROOT` | 프로젝트의 `workspace/` | 지정하지 않으면 이 디렉터리를 만들어 쓴다(git에는 올리지 않는다). coder와 optimizer가 파일을 고치고 명령을 실행할 디렉터리. evaluator, planner, reviewer, debugger도 이 아래를 읽는다 |
| `BENCH_PYTHON` | `python3` | evaluator가 측정을 돌릴 파이썬. torch가 있어야 한다 |
| `KERNELBENCH_ROOT` | (없음) | KernelBench 저장소 경로. `uv run kernelbench`에만 필요하다 |
| `KERNELBENCH_PYTHON` | `BENCH_PYTHON` | KernelBench 채점을 돌릴 파이썬. KernelBench와 torch가 있어야 한다 |
| `FLASHINFER_TRACE_ROOT` | (없음) | FlashInfer-Bench 데이터셋 디렉터리. `uv run flashinferbench`에만 필요하다 |
| `FLASHINFER_BENCH_PYTHON` | `BENCH_PYTHON` | FlashInfer-Bench 채점을 돌릴 파이썬. flashinfer-bench와 torch가 있어야 한다 |
| `TRACE` | `1` | `0`이면 [추적 로그](#추적-로그)를 남기지 않는다 |
| `TRACE_DIR` | 프로젝트의 `traces/` | 추적 로그를 남길 디렉터리(git에는 올리지 않는다) |

연결 예시:

```bash
# 인증 없는 서버 (vLLM, llama.cpp, LM Studio, Ollama 등). 주소와 포트는 서버 설정을 따른다
OPENAI_BASE_URL=http://localhost:8000/v1 OPENAI_MODEL=my-model uv run agent "안녕"

# 키가 필요한 서버
OPENAI_BASE_URL=https://api.example.com/v1 OPENAI_API_KEY=sk-... OPENAI_MODEL=gpt-4o-mini \
  uv run agent "안녕"
```

## 구조

```
cli.py              명령줄 진입점 (에이전트와 워크플로마다 하나)
llm.py              OpenAI 호환 API 연결 (ChatOpenAI), 필수 설정 확인
tracing.py          추적 로그 (질문과 답, LLM 요청/응답 원문, 토큰)
.env.example        환경 변수 틀
agents/
  __init__.py       에이전트 재노출
  base.py           build() / ask() 공통, 대화 기억
  assistant.py      일반 어시스턴트
  researcher.py     조사 담당
  npu_researcher.py NPU 조사 담당 (NPU wiki만 근거)
  coder.py          코딩 담당
  planner.py        계획 담당
  optimizer.py      최적화 담당
  reviewer.py       검토 담당
  evaluator.py      평가 담당
  debugger.py       진단 담당
workflows/
  __init__.py       워크플로 재노출
  kernel_opt_oneshot/    GPU 커널 최적화 (단발)
    __init__.py         재노출
    graph.py            그래프
    README.md           설명
  kernel_opt_orchestrator/  GPU 커널 최적화 (오케스트레이터 1 + 하위 에이전트 3)
    __init__.py         재노출
    orchestrator.py     오케스트레이터 에이전트와 실행
    subagents.py        하위 에이전트를 감싼 도구
    README.md           설명
  accel_opt_manual/     가속기 최적화 루프 (사람이 이음)
    README.md           설명
benchmarks/
  __init__.py       벤치마크 재노출
  suite.py          공통: 문제마다 워크플로 실행, 채점 결과 집계, 보고서
  kernelbench.py    KernelBench 어댑터 (문제 준비, 공식 채점)
  flashinfer_bench.py  FlashInfer-Bench 어댑터 (definition 준비, workload별 공식 채점)
tools/
  __init__.py       도구 목록 정의
  workspace.py      WORKSPACE_ROOT와 경로 봉쇄 (code/shell/bench 공용)
  paging.py         긴 본문을 offset으로 나눠 읽는 공통 부분 (docs/web 공용)
  clock.py, files.py, web.py, docs.py, npu_wiki.py, code.py, shell.py, bench.py
```

## 알려진 한계

### 빈 응답으로 멈추는 문제

추론형 모델은 서버에 따라 응답이 `content`와 `reasoning` 두 필드로 나뉘어 온다. 이때 모델이
**`reasoning`에만 쓰고 `content`를 비워 보내면** 에이전트 루프는 "할 말도 부를 도구도 없다"로 읽고 작업 도중에 멈춘다.
`langchain-openai`는 `reasoning` 필드를 버리므로 에이전트에게는 아무 정보도 남지 않는다.

- **알아보는 법**: 답이 비어 `ask()`가 실행한 도구 목록만 보여주면 이 문제를 의심한다.
  [추적 로그](#추적-로그)는 응답 원문을 남기므로, 거기 있는 "content가 비고 reasoning만 온 응답" 질의로 확인한다.
- **해결**: `OPENAI_MODEL`로 다른 모델(더 큰 모델이나 추론형이 아닌 모델)을 쓴다. 도구 목록이나 프롬프트를 손봐서는 고쳐지지 않았다.
- **증상만 가리는 처리**: 추론 내용이 `content`로 새어 `</think>`가 섞여 나오면 `ask()`가 마지막 `</think>` 뒤만 남긴다.

### 같은 도구 호출을 되풀이하는 문제

모델이 같은 도구를 같은 인자로 끝없이 다시 부르는 일이 있다. 대화가 계속 길어져 결국 엔드포인트의 컨텍스트 한도에서 오류로 끝난다.

- **확인된 원인 하나**: `read_doc`과 `fetch_page`가 본문을 앞 4000자에서 말없이 잘랐고 뒤를 읽을 방법이 없었다.
  모델은 뒷부분을 얻으려고 같은 문서를 수백 번 다시 불렀다(URL 끝에 `&x=1`, `&x=2`…를 붙여 가며 다시 받기도 했다).
  지금은 잘린 곳과 전체 길이를 알려 주고 `offset`으로 이어 읽게 한다.

- **알아보는 법**: [추적 로그](#추적-로그)에서 한 `ask`의 LLM 호출 수가 비정상적으로 많고 도구 호출이 같은 것만 이어진다.
- **막아 둔 곳**: researcher는 40스텝(도구 호출 20번쯤)에 닿으면 멈추고, 도구 없이 한 번 더 물어 그때까지 확인한 내용으로 답을 받는다.
  그런 답은 `(스텝 한도에 닿아, 그때까지 확인한 내용으로 답했다.)`로 시작한다. 한도를 100스텝으로 올려 봤지만 모델은 자료를 끝까지 읽기만 하고 답을 쓰지 않았다.
- **해결**: 추적 로그에서 되풀이된 호출의 결과가 매번 같은지 먼저 본다. 같다면 도구가 모델이 원하는 것을 주지 못하는 것이다. 도구 쪽 원인이 없으면 `OPENAI_MODEL`로 다른 모델을 쓴다.

모든 모델에서 생기는 문제는 아니다. 관측한 조건과 횟수는 [실험 기록](#도구-구성에-따른-빈-응답-qwen359b)에 있다.
