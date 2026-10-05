"""
ai/ollama_provider.py
-----------------------
Local Ollama backend. Talks to a running `ollama serve` instance over
HTTP (default http://localhost:11434) — no API key required, fully
offline once the model is pulled (`ollama pull llama3.2`).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ai.base_provider import AIProvider, AIProviderError, ChatTurn
from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class OllamaProvider(AIProvider):
    name = "ollama"

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{settings.ai.ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=1.5):
                return True
        except (urllib.error.URLError, OSError):
            return False

    def chat(self, messages: list[ChatTurn], temperature: float = 0.8) -> str:
        payload = {
            "model": settings.ai.ollama_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            req = urllib.request.Request(
                f"{settings.ai.ollama_host}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["message"]["content"].strip()
        except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as exc:
            logger.exception("Ollama request failed")
            raise AIProviderError(
                f"Couldn't reach Ollama at {settings.ai.ollama_host}. "
                f"Is 'ollama serve' running and is '{settings.ai.ollama_model}' pulled? ({exc})"
            ) from exc
