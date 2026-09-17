# GPU 커널 최적화 단발 (`kernel-opt-oneshot`)

모듈: [`kernel_opt_oneshot.py`](kernel_opt_oneshot.py)

커널 파일 하나를 받아 최적화 후보 2개를 병렬로 만들고 검토까지 한다. 대화형이 아니다. 한 번 실행하면 끝까지 돌고 끝난다.

```
plan ─> research ─> select ─┬─> [optimize ─> review] ─┬─> 끝
                            └─> [optimize ─> review] ─┘
```

## 노드

| 노드 | 에이전트 | 하는 일 |
| --- | --- | --- |
| `plan` | `planner` | 커널을 읽고 병목을 분석한다 |
| `research` | `researcher` | 분석과 커널 소스를 받아 최적화 기법 후보를 찾는다 |
| `select` | `planner` | 후보에 순위를 매긴다. 위의 2개를 각 갈래로 보낸다 |
| `optimize` | `optimizer` | 가설대로 최적화본을 `<이름>_opt<번호>.<확장자>`에 만든다 |
| `review` | `reviewer` | 원본과 최적화본을 정적으로 검토한다 |

## 설계

- 대괄호 안은 갈래마다 따로 도는 하위 그래프다. `Send`로 두 갈래를 병렬로 띄우고, 결과는 `results`에 모은다.
- 갈래마다 파일 이름이 달라 두 optimizer가 서로의 결과를 덮어쓰지 않는다.
- researcher의 도구는 `WORKSPACE_ROOT`를 읽지 못하므로 커널 소스를 질문에 넣어 준다.
- planner는 `plan`과 `select`에서 같은 대화를 이어 쓴다. 순위를 매길 때 앞의 분석을 기억한다.
- planner의 순위에서 `1. [대상] ...` 꼴의 항목을 앞에서 2개 잘라 갈래로 보낸다. `**`, `#` 같은 마크다운 꾸밈은 무시하고, `[대상]`이 없는 번호 목록(다음 단계 제안 등)은 치지 않는다. 2개를 찾지 못하면 순위 원문과 함께 멈춘다.
- 측정(`evaluator`)은 이 워크플로에 없다. 검토에서 끝난다.

## 실행

```bash
WORKSPACE_ROOT=~/kernels uv run kernel-opt-oneshot slow.py "softmax_rows를 GPU에서 빠르게"
```

출력은 분석, 후보, 순위, 그리고 갈래별 가설, optimizer 보고, reviewer 판정 순이다.
