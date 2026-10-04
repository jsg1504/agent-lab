"""OpenAI 호환 API 연결. base_url만 바꾸면 어떤 서버에든 붙는다."""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()  # .env가 있으면 읽는다. 이미 설정된 환경 변수가 우선한다.

# 엔드포인트와 모델은 기본값 없이 .env나 환경 변수로 반드시 지정한다.
BASE_URL = os.getenv("OPENAI_BASE_URL")
MODEL = os.getenv("OPENAI_MODEL")
# 인증하지 않는 서버(ollama, llama.cpp 등)도 클라이언트가 키 값을 요구하므로 자리 표시자를 넣는다.
API_KEY = os.getenv("OPENAI_API_KEY") or "no-key"


class ConfigError(Exception):
    """실행에 필요한 설정 값이 없다."""


def build_llm(model: str | None = None) -> ChatOpenAI:
    """model을 주면 OPENAI_MODEL 대신 그 모델을 쓴다. 에이전트마다 모델을 달리할 때 쓴다."""
    model = model or MODEL
    missing = [name for name, value in (("OPENAI_BASE_URL", BASE_URL), ("OPENAI_MODEL", model)) if not value]
    if missing:
        raise ConfigError(
            f"필요한 설정이 없습니다: {', '.join(missing)}. .env에 지정하라 (.env.example 참고)."
        )
    return ChatOpenAI(
        model=model,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=0,
    )
