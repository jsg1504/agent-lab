# 가속기 최적화 루프 (사람이 이음)

코드가 없는 워크플로다. 에이전트를 하나씩 실행하고 결과를 사람이 다음 에이전트에 넘긴다.

딥러닝 모델과 커널 코드(PyTorch, Triton, CUDA C++)의 지연을 줄이는 루프다.

```
planner ──가설──> optimizer ──후보──> reviewer ──통과──> evaluator ──성공──> 채택
   ^                  ^                  │수정요청            │실패
   │                  └──────────────────┘                    v
   └──────────── 반려 기록(교훈) <─────────────────────── debugger ──지시──> optimizer
```

| 단계 | 에이전트 | 할 수 있는 일 |
| --- | --- | --- |
| 계획 | `planner` | 읽기. 기대 이득은 분석적 상한을 넘지 않는다 |
| 수정 | `optimizer` | 읽기, 고치기, 셸. 측정 도구는 없다 |
| 검토 | `reviewer` | 읽기. 디바이스를 쓰기 전 단계라 `compile_check`도 없다 |
| 측정 | `evaluator` | 읽기, 컴파일 확인, 정확도 비교, 지연 측정. 고치지 않는다 |
| 진단 | `debugger` | 읽기. 컴파일 실패, 정확도 불통과, 성능 퇴행의 원인을 구현 실수와 가설 오류로 가른다 |

역할을 이렇게 나눈 이유:
- 고치는 쪽이 측정 도구를 가지면 추측한 배수를 사실처럼 보고하기 쉽다. 그래서 `optimizer`는 고치기만, `evaluator`는 재기만 한다.
- 측정 노이즈로 인한 실패는 재측정으로 보내고 `debugger`에 넘기지 않는다. `debugger`의 진단은 반려 기록에
  교훈으로 쌓이므로, 노이즈나 구현 실수를 "이 방향은 안 된다"로 적으면 옳은 방향이 묻힌다.
  그래서 `debugger`는 확신도를 함께 적고, 구현 실수이거나 원인이 불명이면 교훈을 남기지 않는다.

```bash
export WORKSPACE_ROOT=~/kernels

uv run planner "프로파일: slow.py의 softmax_rows가 90%. 상한: 최대 10x. 채택: 없음. 반려: #1 torch.compile(컴파일 시간 과다)"
uv run optimizer "slow.py의 softmax_rows가 느리다. 최적화본을 fast.py에 같은 이름으로 만들어줘."
uv run reviewer "slow.py가 원본, fast.py가 후보다. 가설: 행 루프를 벡터화. 검토해줘."
uv run evaluator "slow.py가 원본, fast.py가 최적화본이다. 입력은 torch.randn(512,1024,device='cuda')를 쓴다. 평가해줘."
uv run debugger "slow.py가 원본, fast.py가 후보다. evaluator 보고 - 정확도: max_abs_err=nan (불통과). 진단해줘."
```

evaluator의 보고 꼴:

```
컴파일 : OK
정확도 : max_abs_err=3.7e-09 (통과)
지연   : 31.0ms -> 0.03ms
```

`.cu`는 `nvcc -c`로, `.py`는 임포트로 빌드를 확인한다. Triton 커널은 호출할 때 컴파일되므로
임포트만으로는 문법까지만 걸러진다.

> 측정은 `BENCH_PYTHON`이 가리키는 인터프리터에서 돈다. torch가 설치된 것이어야 한다.
> 이 프로젝트의 uv venv에는 torch가 없으므로 보통 따로 지정해야 한다.
