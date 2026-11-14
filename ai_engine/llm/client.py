from __future__ import annotations

import os

from dotenv import load_dotenv

from langchain_groq import ChatGroq


load_dotenv()

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

LLM_TEMPERATURE = float(
    os.getenv(
        "LLM_TEMPERATURE",
        "0",
    )
)

LLM_MAX_TOKENS = int(
    os.getenv(
        "LLM_MAX_TOKENS",
        "1024",
    )
)

if not GROQ_API_KEY:

    raise RuntimeError(
        "GROQ_API_KEY is not configured. "
        "Add GROQ_API_KEY to your .env file."
    )

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
    api_key=GROQ_API_KEY,
)


def get_llm() -> ChatGroq:
    return llm

def get_llm_config() -> dict:
    
    return {
        "provider": "groq",
        "model": GROQ_MODEL,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }