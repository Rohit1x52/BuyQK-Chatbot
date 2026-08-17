# Purpose:
# Centralized LLM configuration for the BuyQK AI engine.
#
# Architecture:
#
#                 .env
#                   │
#                   ▼
#             GROQ_API_KEY
#                   │
#                   ▼
#              ChatGroq
#                   │
#                   ▼
#          Llama 3.3 70B
#                   │
#                   ▼
#             LangGraph
#                   │
#        ┌──────────┼──────────┐
#        ▼          ▼          ▼
#      Intent     Entity     Response
#
# IMPORTANT:
# - Do not create ChatGroq separately inside every node.
# - Keep model configuration centralized here.
# - API keys must never be hardcoded.
# - The model name should be configurable through .env.


from __future__ import annotations

import os

from dotenv import load_dotenv

from langchain_groq import ChatGroq


# =========================================================
# Load Environment Variables
# =========================================================

load_dotenv()


# =========================================================
# Configuration
# =========================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "qwen/qwen3.6-27b",
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


# =========================================================
# Validation
# =========================================================

if not GROQ_API_KEY:

    raise RuntimeError(
        "GROQ_API_KEY is not configured. "
        "Add GROQ_API_KEY to your .env file."
    )


# =========================================================
# Create LLM
# =========================================================

llm = ChatGroq(
    model=GROQ_MODEL,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
    api_key=GROQ_API_KEY,
)


# =========================================================
# Getter
# =========================================================

def get_llm() -> ChatGroq:
    """
    Return the centralized BuyQK LLM instance.

    Returns:
        Configured ChatGroq instance.
    """

    return llm


# =========================================================
# Configuration Information
# =========================================================

def get_llm_config() -> dict:
    """
    Return safe LLM configuration information.

    The API key is intentionally NOT returned.
    """

    return {
        "provider": "groq",
        "model": GROQ_MODEL,
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
    }