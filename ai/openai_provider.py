"""
ai/openai_provider.py
----------------------
OpenAI chat-completion backend. Uses the official `openai` Python SDK
if installed; raises a clear `AIProviderError` if the package or API
key is missing, rather than crashing the app.
"""

from __future__ import annotations

from ai.base_provider import AIProvider, AIProviderError, ChatTurn
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self._client = None  # lazy-initialized on first use

    def is_available(self) -> bool:
        return bool(settings.ai.openai_api_key)

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise AIProviderError(
                "The 'openai' package isn't installed. Run: pip install openai"
            ) from exc

        if not settings.ai.openai_api_key:
            raise AIProviderError(
                "No OpenAI API key configured. Set the OPENAI_API_KEY environment "
                "variable or add it in Settings."
            )

        self._client = OpenAI(api_key=settings.ai.openai_api_key)
        return self._client

    def chat(self, messages: list[ChatTurn], temperature: float = 0.8) -> str:
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=settings.ai.openai_model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:  # noqa: BLE001 - surface as a provider error
            logger.exception("OpenAI request failed")
            raise AIProviderError(f"OpenAI request failed: {exc}") from exc
