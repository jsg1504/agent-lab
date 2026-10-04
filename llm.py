"""OpenAI 호환 API 연결. base_url만 바꾸면 어떤 서버에든 붙는다."""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()  # .env가 있으면 읽는다. 이미 설정된 환경 변수가 우선한다.

# 아래는 기본값일 뿐이다. 다른 서버를 쓰려면 환경 변수로 재정의한다.
BASE_URL = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("OPENAI_MODEL", "qwen3.5:9b")
# 인증하지 않는 서버(ollama, llama.cpp 등)도 클라이언트가 키 값을 요구하므로 자리 표시자를 넣는다.
API_KEY = os.getenv("OPENAI_API_KEY") or "no-key"


def build_llm(model: str | None = None) -> ChatOpenAI:
    """model을 주면 OPENAI_MODEL 대신 그 모델을 쓴다. 에이전트마다 모델을 달리할 때 쓴다."""
    return ChatOpenAI(
        model=model or MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=0,
    )
