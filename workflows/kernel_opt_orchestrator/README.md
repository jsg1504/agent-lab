# GPU 커널 최적화: 오케스트레이터 1 + 하위 에이전트 3 (`kernel-opt-orchestrator`)

모듈: [`orchestrator.py`](orchestrator.py), [`subagents.py`](subagents.py)

**오케스트레이터 에이전트 1개**가 **하위 에이전트 3개**(`researcher`, `optimizer`, `evaluator`)를 도구로 불러 가며 커널을 최적화한다.
조사하고, 최적화본을 만들고, 재고, 결과가 나쁘면 다시 도는 순서를 코드가 아니라 오케스트레이터가 정한다.

```
                 ┌─ research ─> researcher   기법 후보 조사
orchestrator ────┼─ optimize ─> optimizer    최적화본 작성
     ^           └─ evaluate ─> evaluator    컴파일, 정확도, 지연 측정
     └── 답을 보고 다음에 누구를 부를지 정한다 (최대 3라운드)
```

벤치마크가 공식 채점 함수를 넘기면 도구가 하나 더 붙고 흐름이 바뀐다([루프 안 공식 채점](#루프-안-공식-채점)).

```
research > optimize > evaluate > official_score
              ^                        |
              └── 통과하지 못하면 고쳐서 다시 (최대 3라운드)
```

## 구성

| 역할 | 에이전트 | 가진 도구 | 정의된 곳 |
| --- | --- | --- | --- |
| 오케스트레이터 | (이 워크플로 전용) | `research`, `optimize`, `evaluate` | [`orchestrator.py`](orchestrator.py) |
| 하위: 조사 | `researcher` | `RESEARCH_TOOLS` | `agents/researcher.py` |
| 하위: 작성 | `optimizer` | `OPTIMIZE_TOOLS` | `agents/optimizer.py` |
| 하위: 측정 | `evaluator` | `EVALUATE_TOOLS` | `agents/evaluator.py` |

오케스트레이터의 도구 3개는 하위 에이전트를 감싼 것이다([`subagents.py`](subagents.py)). 도구를 부르면 그 하위 에이전트가 자기 도구로 일을 끝내고 답을 돌려준다.
오케스트레이터는 파일을 직접 읽거나 고치거나 재지 못한다.

## 설계

- 루프를 그래프로 짜지 않았다. 에이전트의 도구 호출 루프가 그대로 최적화 루프다.
- 고치는 쪽(`optimizer`)과 재는 쪽(`evaluator`)은 여기서도 나뉘어 있다. 오케스트레이터는 `evaluate`가 돌려준 수치만 인용하도록 지시받는다.
- 그래도 요약이 수치를 잘못 옮길 수 있으므로, 출력 뒤에 **위임 기록**을 붙인다. 하위 에이전트를 부른 인자와 답 원문이 그대로 들어간다. 수치는 여기서 확인한다.
- 하위 에이전트는 호출마다 새 대화로 부른다. 앞 라운드를 기억하지 못하므로 오케스트레이터가 필요한 내용을 인자에 적어 넘긴다. `optimizer`가 기존 파일을 이어서 고치다 멈추는 일이 있어([실험 기록](../../README.md#실험-기록)) 라운드마다 새 파일 `<이름>_opt<라운드>.<확장자>`에 만든다. 원본은 고치지 않는다.
- `researcher`의 도구는 `WORKSPACE_ROOT`를 읽지 못하므로 `research` 도구가 커널 소스를 읽어 질문에 넣어 준다.
- 하위 에이전트가 예외로 죽으면(도구 예외 등) 그 사실이 답으로 돌아가고 루프는 이어진다. `researcher`는 스텝 한도(40)에 닿으면 죽지 않고 그때까지 읽은 내용으로 답한다.
- 라운드는 최대 3번이라고 프롬프트에 적었고, 모델이 지키지 않을 때를 대비해 스텝 한도(40)를 코드로 걸었다. 한도에 걸리면 그때까지의 위임 기록을 내고 끝난다.
- 위임 기록에는 `official_score`의 호출과 결과도 그대로 들어간다.

## 루프 안 공식 채점

`run_kernel_opt_orchestrator(kernel, request, official_score=...)`에 채점 함수를 넘기면 오케스트레이터가 `official_score` 도구를 갖는다.
지금은 `uv run flashinferbench ... --workflow orchestrator`가 이렇게 부른다. `uv run kernel-opt-orchestrator`로 직접 돌릴 때는 붙지 않는다.

- `official_score(candidate)`는 하위 에이전트가 아니라 **채점 함수를 바로 부르는 도구**다. 모델을 거치지 않으므로 통과 여부와 수치가 옮겨 적히다 바뀌지 않는다.
  원본과 입력은 채점기가 알고 있어 후보 경로만 받는다.
- 프롬프트가 달라진다(`OFFICIAL_SYSTEM_PROMPT`). 성공은 `official_score`의 통과뿐이고, `evaluate`가 통과해도 공식 채점을 통과하지 못하면 실패로 보고 다음 라운드를 돈다.
  통과할 때까지 최대 3라운드를 돈다. 통과했고 원본보다 빠르면 멈춘다.
- `evaluate`는 남겨 두었다. 컴파일이 안 되는 후보는 여기서 걸러지고, 지연 수치는 다음 라운드의 지시에 쓰인다.
  다만 **정확도의 기준은 `official_score`다.** `evaluate`의 허용 오차(기본 1e-3)가 공식 채점(1e-2)보다 엄격해, bf16에서 마지막 비트만 다른 후보가 `evaluate`에서는 떨어지고 공식 채점은 통과할 수 있다. 그래서 컴파일만 되면 `evaluate`의 정확도 판정과 상관없이 공식 채점을 부르게 했다.
- 채점 함수를 넘기지 않으면 도구와 프롬프트가 전과 글자 하나 다르지 않다. 그쪽 실험 조건은 그대로다.
- 이렇게 얻은 결과는 **공식 채점기의 피드백을 보고 고친 결과**다. 채점을 끝난 뒤에만 하던 실행(KernelBench, 단발 워크플로, 이 기능 이전의 실험 기록)과 같은 조건이 아니므로 수치를 나란히 비교하지 않는다.

## 실행

준비:

1. `uv sync`로 설치하고, `.env`에 `OPENAI_BASE_URL`과 `OPENAI_MODEL`을 채운다.
2. `BENCH_PYTHON`에 torch가 있는 파이썬을 **절대 경로로** 지정한다. 측정이 이 인터프리터에서 돈다.
   `python3`처럼 이름만 적으면 `uv run` 아래에서는 torch가 없는 이 프로젝트의 venv 파이썬이 잡힌다.
3. 커널 파일을 작업 디렉터리에 둔다. `WORKSPACE_ROOT`로 지정하고, 지정하지 않으면 프로젝트 안의 `workspace/`가 만들어져 쓰인다. 최적화본도 이 디렉터리에 생긴다.

```bash
uv run kernel-opt-orchestrator <커널 파일> [요청]
```

| 인자 | 설명 |
| --- | --- |
| `<커널 파일>` | 작업 디렉터리 기준 경로. 예: `slow.py` |
| `[요청]` | 무엇을 빠르게 할지와 **측정에 쓸 입력**. 오케스트레이터는 커널을 직접 읽지 못하므로 입력 모양을 여기에 적어야 한다 |

예:

```bash
WORKSPACE_ROOT=~/kernels BENCH_PYTHON=~/miniconda3/bin/python3 \
  uv run kernel-opt-orchestrator slow.py "softmax_rows를 GPU에서 빠르게. 입력은 torch.randn(512,1024,device='cuda')"
```

두 변수는 `.env`에 적어 두면 명령에서 뺄 수 있다. 대화형이 아니다. 한 번 실행하면 끝까지 돌고 끝난다.

결과:

- 작업 디렉터리에 라운드마다 `slow_opt1.py`, `slow_opt2.py`, ...가 생긴다. 원본은 그대로다.
- 화면에는 **오케스트레이터 보고**(채택한 파일, 근거, 라운드별 요약)와 **위임 기록**(하위 에이전트를 부른 인자와 답 원문)이 차례로 나온다.

## 한계

- 언제 다음 라운드를 돌고 언제 멈출지를 모델이 정한다. 같은 요청이라도 고정 그래프보다 결과가 덜 일정하다.
- 모델이 빈 응답으로 멈추는 문제([알려진 한계](../../README.md#알려진-한계))는 오케스트레이터와 하위 에이전트 두 층 모두에서 일어날 수 있다.
