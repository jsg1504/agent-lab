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


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=MODEL,
        base_url=BASE_URL,
        api_key=API_KEY,
        temperature=0,
    )
