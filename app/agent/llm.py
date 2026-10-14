"""LLM provider abstraction.

Gemini Flash is the primary, default provider. Ollama is an optional local/offline
fallback for development -- both providers plug into the exact same LangGraph
StateGraph and tool set; only the chat model construction differs.

Switch providers purely via the LLM_PROVIDER environment variable; no code
changes or separate agent implementations are required.
"""
from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings
from app.core.exceptions import LLMError

logger = logging.getLogger(__name__)


def get_chat_model(settings: Settings) -> BaseChatModel:
    provider = settings.llm_provider.lower().strip()

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMError(
                "LLM_PROVIDER is 'gemini' but GEMINI_API_KEY is not set. "
                "Set it in your .env file (see .env.example).",
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.1,
            max_retries=2,
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise LLMError(
                "LLM_PROVIDER is 'ollama' but the optional 'langchain-ollama' package "
                "is not installed. Run: pip install langchain-ollama",
            ) from exc

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
        )

    raise LLMError(f"Unsupported LLM_PROVIDER '{settings.llm_provider}'. Use 'gemini' or 'ollama'.")
