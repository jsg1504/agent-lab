"""하위 에이전트 3개(researcher, optimizer, evaluator)를 오케스트레이터가 부를 도구로 감싼다."""

from itertools import count

from langchain_core.tools import tool

from agents import ask, build_evaluator, build_optimizer, build_researcher
from tools.workspace import resolve

MAX_SOURCE_CHARS = 8000


def _delegate(agent, task: str, thread_id: str) -> str:
    """하위 에이전트가 도구 예외로 죽어도 오케스트레이터의 루프는 이어지게 실패를 문자열로 돌려준다."""
    try:
        return ask(agent, task, thread_id)
    except Exception as exc:
        return f"하위 에이전트가 실패했습니다: {type(exc).__name__}: {str(exc)[:500]}"


def build_subagent_tools() -> list:
    researcher = build_researcher()
    optimizer = build_optimizer()
    evaluator = build_evaluator()
    # 하위 에이전트는 호출마다 새 대화로 부른다. optimizer가 앞의 대화를 이어서 고치다 멈추는 일이 있어서다.
    calls = count(1)

    @tool
    def research(kernel: str, question: str) -> str:
        """researcher에게 조사를 맡긴다. 커널을 빠르게 만들 최적화 기법 후보와 근거 출처를 받는다.

        kernel은 커널 파일 경로다. 소스는 이 도구가 읽어서 함께 넘기므로 question에 코드를 붙이지 않는다.
        """
        target = resolve(kernel)
        if target is None or not target.is_file():
            return f"커널 파일을 찾을 수 없습니다: {kernel}. 작업 루트 기준 경로로 다시 불러라."
        source = target.read_text(errors="ignore")[:MAX_SOURCE_CHARS]
        task = (
            f"{question}\n"
            "후보마다 기법, 이 커널에 적용하는 방법, 근거 출처를 적어라.\n\n"
            f"[코드: {kernel}]\n{source}"
        )
        return _delegate(researcher, task, f"research-{next(calls)}")

    @tool
    def optimize(kernel: str, candidate: str, instruction: str) -> str:
        """optimizer에게 최적화본 작성을 맡긴다. 원본 kernel은 그대로 두고 candidate 파일에 새로 만든다.

        instruction에는 적용할 기법을 적는다. optimizer는 앞 라운드를 기억하지 못하므로
        앞 라운드의 측정 결과에서 배운 것도 여기에 적어야 한다.
        """
        task = (
            f"{kernel}을 아래 지시대로 최적화해줘. "
            f"원본은 고치지 말고 최적화본을 {candidate}에 같은 함수 이름으로 만들어라.\n\n"
            f"[지시]\n{instruction}"
        )
        return _delegate(optimizer, task, f"optimize-{next(calls)}")

    @tool
    def evaluate(kernel: str, candidate: str, inputs: str) -> str:
        """evaluator에게 측정을 맡긴다. 컴파일 여부, 원본과 결과가 같은지, 지연이 얼마나 줄었는지 받는다.

        inputs에는 함수에 넣을 입력을 만드는 식을 적는다. 예) torch.randn(512,1024,device='cuda')
        """
        task = f"{kernel}이 원본, {candidate}이 최적화본이다. 입력은 {inputs}를 쓴다. 평가해줘."
        return _delegate(evaluator, task, f"evaluate-{next(calls)}")

    return [research, optimize, evaluate]
