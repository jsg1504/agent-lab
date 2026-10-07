"""GPU 커널 최적화 워크플로 (오케스트레이터 1 + 하위 에이전트 3).

오케스트레이터 에이전트 하나가 조사, 최적화본 작성, 측정을 하위 에이전트에게 맡기고
측정 결과를 보고 다음 라운드를 정한다. 순서를 코드가 아니라 에이전트가 정한다.

    orchestrator -+-> research -> researcher
        ^         +-> optimize -> optimizer
        |         +-> evaluate -> evaluator
        |         +-> official_score -> 공식 채점기 (벤치마크가 넘겨줄 때만)
        +---- 결과를 보고 다음 호출을 정한다
"""

from collections.abc import Callable

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.errors import GraphRecursionError

from agents import ask
from agents.base import build
from workflows.kernel_opt_orchestrator.subagents import build_subagent_tools

MAX_ROUNDS = 3
# 모델이 멈추지 않을 때의 안전장치. 도구 호출 한 번이 2스텝이다. 라운드마다 도구를 최대 3번(공식 채점 포함) 부른다.
RECURSION_LIMIT = 40
THREAD = "orchestrator"

SYSTEM_PROMPT = f"""너는 GPU 커널 최적화의 총괄이다. 직접 코드를 읽거나 고치거나 재지 않는다. 일은 도구로 하위 에이전트에게 맡긴다.

도구:
- research: researcher가 최적화 기법 후보를 조사한다.
- optimize: optimizer가 최적화본을 새 파일에 만든다.
- evaluate: evaluator가 컴파일, 정확도, 지연을 잰다.

순서대로 한다:
1. research로 후보를 받는다.
2. 후보 하나를 골라 optimize로 최적화본을 만든다. 파일 이름은 원본 이름 뒤에 _opt와 라운드 번호를 붙인다.
   예) slow.py의 1라운드는 slow_opt1.py, 2라운드는 slow_opt2.py
3. evaluate로 그 최적화본을 잰다.
4. 컴파일 실패, 정확도 불통과, 지연 퇴행이면 evaluate의 보고를 근거로 지시를 고쳐 다음 라운드를 돈다.
   더 빨라질 여지가 있어 보여도 다음 라운드를 돌 수 있다. 라운드마다 새 파일에 만든다.

지켜야 할 것:
- 라운드는 최대 {MAX_ROUNDS}번이다. 요청한 목표를 채웠으면 일찍 멈춘다.
- 하위 에이전트는 앞 라운드를 기억하지 못한다. 필요한 내용은 도구 인자에 모두 적는다.
- 수치는 evaluate가 돌려준 것만 인용한다. 재지 않은 것을 잰 것처럼 말하지 않는다.
- 입력 모양을 모르면 evaluate를 부르지 말고 사용자에게 무엇이 필요한지 말한다.

마지막에 이 꼴로 보고한다:
  채택 : 파일 이름 (없으면 없음)
  근거 : evaluate가 준 정확도와 지연
  라운드별 요약 : 무엇을 시도했고 어떻게 됐는지

한국어로 간결하게 답한다."""

# 공식 채점기를 루프 안에서 부를 수 있을 때의 프롬프트. 통과 여부를 evaluate가 아니라 official_score가 정한다.
OFFICIAL_SYSTEM_PROMPT = f"""너는 GPU 커널 최적화의 총괄이다. 직접 코드를 읽거나 고치거나 재지 않는다. 일은 도구로 맡긴다.

도구:
- research: researcher가 최적화 기법 후보를 조사한다.
- optimize: optimizer가 최적화본을 새 파일에 만든다.
- evaluate: evaluator가 컴파일, 정확도, 지연을 잰다.
- official_score: 공식 채점기가 최적화본을 채점한다. 통과 여부는 이것이 정한다.

순서대로 한다:
1. research로 후보를 받는다.
2. 후보 하나를 골라 optimize로 최적화본을 만든다. 파일 이름은 원본 이름 뒤에 _opt와 라운드 번호를 붙인다.
   예) slow.py의 1라운드는 slow_opt1.py, 2라운드는 slow_opt2.py
3. evaluate로 그 최적화본을 잰다.
4. 컴파일이 됐으면 official_score로 그 최적화본을 채점한다. evaluate가 정확도 불통과라고 해도 채점한다.
   허용 오차가 서로 달라 evaluate에서 떨어진 것이 공식 채점은 통과할 수 있다. 컴파일이 안 되면 채점하지 않고 5로 간다.
5. evaluate와 official_score의 보고를 근거로 지시를 고쳐 2부터 다음 라운드를 돈다. 라운드마다 새 파일에 만든다.
   통과하지 못했으면 통과하도록 고치고, 통과했으면 지금까지 통과한 것 중 가장 빠른 것보다 더 빠르게 만든다.

지켜야 할 것:
- 성공은 official_score의 통과뿐이다. evaluate가 통과해도 official_score를 통과하지 못하면 실패다.
  정확도의 기준도 official_score다. evaluate의 정확도 판정만으로 후보를 버리지 않는다.
- 라운드는 {MAX_ROUNDS}번을 모두 돈다. official_score를 통과했어도 멈추지 않고 남은 라운드에서 더 빠른 것을 노린다.
  {MAX_ROUNDS}번을 채우면 통과한 것이 없어도 멈춘다.
- 하위 에이전트는 앞 라운드를 기억하지 못한다. 필요한 내용은 도구 인자에 모두 적는다.
  official_score가 알려준 실패 내용이나, 지금까지 가장 빨랐던 최적화본의 기법과 속도향상도 다음 optimize의 지시에 적는다.
- 수치는 evaluate와 official_score가 돌려준 것만 인용한다. 재지 않은 것을 잰 것처럼 말하지 않는다.
- 입력 모양을 모르면 evaluate를 부르지 말고 사용자에게 무엇이 필요한지 말한다.

마지막에 이 꼴로 보고한다:
  채택 : official_score를 통과한 것 중 속도향상이 가장 큰 파일 이름 (통과한 것이 없으면 없음)
  근거 : official_score가 준 통과 여부와 속도향상
  라운드별 요약 : 무엇을 시도했고 evaluate와 official_score에서 어떻게 됐는지

한국어로 간결하게 답한다."""


def build_kernel_opt_orchestrator(official_score: Callable[[str], str] | None = None):
    """official_score는 후보 경로를 받아 공식 채점 결과를 문자열로 돌려주는 함수다. 벤치마크가 넘긴다."""
    prompt = OFFICIAL_SYSTEM_PROMPT if official_score else SYSTEM_PROMPT
    agent = build(prompt, build_subagent_tools(official_score), name="orchestrator")
    return agent.with_config(recursion_limit=RECURSION_LIMIT)


def _delegations(messages: list) -> list[str]:
    """오케스트레이터가 하위 에이전트를 부른 기록을 인자와 답 원문 그대로 뽑는다."""
    calls = {
        call["id"]: call
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    }
    sections = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        args = calls.get(message.tool_call_id, {}).get("args", {})
        lines = "\n".join(f"- {key}: {value}" for key, value in args.items())
        sections.append(
            f"### {len(sections) + 1}. {message.name}\n{lines}\n\n{str(message.content).strip()}"
        )
    return sections


def run_kernel_opt_orchestrator(
    kernel: str, request: str = "", official_score: Callable[[str], str] | None = None
) -> str:
    agent = build_kernel_opt_orchestrator(official_score)
    try:
        answer = ask(agent, f"{kernel}의 커널을 최적화해줘.\n요청: {request}", THREAD)
    except GraphRecursionError:
        answer = f"스텝 한도({RECURSION_LIMIT})에 걸려 중단했다. 아래 위임 기록이 그때까지 한 일이다."
    # 오케스트레이터의 요약이 수치를 잘못 옮길 수 있으므로 하위 에이전트의 답 원문을 함께 낸다.
    messages = agent.get_state({"configurable": {"thread_id": THREAD}}).values.get("messages", [])
    return "\n\n".join([f"## 오케스트레이터 보고\n{answer}", "## 위임 기록", *_delegations(messages)])
