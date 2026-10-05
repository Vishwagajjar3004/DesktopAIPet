"""
ai/ai_manager.py
------------------
The single entry point the rest of the app talks to for AI chat.

Responsibilities:
    * Picks the active provider (OpenAI / Ollama) based on `settings.ai.provider`
      and lets the user switch at runtime.
    * Builds the outgoing message list: personality system prompt +
      recent conversation history (from `MemoryDB`) + the new user message.
    * Persists both sides of every exchange to `MemoryDB`.
    * Converts provider failures into a friendly, in-character fallback
      line instead of raising into the UI layer.
"""

from __future__ import annotations

from typing import Optional

from ai.base_provider import AIProvider, AIProviderError, ChatTurn
from ai.ollama_provider import OllamaProvider
from ai.openai_provider import OpenAIProvider
from ai.simple_provider import SimpleProvider
from config.settings import settings
from database.memory_db import MemoryDB
from utils.logger import get_logger

logger = get_logger(__name__)

_FALLBACK_REPLIES = [
    "Hmm, my brain glitched for a second 😅 Can you say that again?",
    "I couldn't quite think that through — try me again?",
    "Oops, connection hiccup! Ask me again in a moment.",
]


class AIManager:
    """Coordinates providers, personality, and memory for chat."""

    def __init__(self, memory_db: Optional[MemoryDB] = None) -> None:
        self._memory_db = memory_db or MemoryDB()
        self._providers: dict[str, AIProvider] = {
            "simple": SimpleProvider(),
            "openai": OpenAIProvider(),
            "ollama": OllamaProvider(),
        }

    # ------------------------------------------------------------------
    # Provider selection
    # ------------------------------------------------------------------

    @property
    def active_provider_name(self) -> str:
        return settings.ai.provider

    def set_provider(self, name: str) -> None:
        if name not in self._providers:
            raise ValueError(f"Unknown AI provider: {name}")
        settings.ai.provider = name
        logger.info("AI provider switched to %s", name)

    def _active_provider(self) -> AIProvider:
        return self._providers[settings.ai.provider]

    def provider_status(self) -> dict[str, bool]:
        """Availability of each registered provider (for the Settings UI)."""
        return {name: provider.is_available() for name, provider in self._providers.items()}

    # ------------------------------------------------------------------
    # Chatting
    # ------------------------------------------------------------------

    def send_message(self, user_text: str) -> str:
        """
        Send `user_text` to the active AI provider with personality +
        recent history as context, persist both sides, and return the
        assistant's reply text (never raises — falls back gracefully).
        """
        self._memory_db.add_message("user", user_text)

        history = self._memory_db.get_recent_messages(limit=settings.ai.max_history_messages)
        messages = [ChatTurn("system", self._build_system_prompt())]
        messages += [ChatTurn(m.role, m.content) for m in history]

        provider = self._active_provider()
        try:
            reply = provider.chat(messages, temperature=settings.ai.temperature)
        except AIProviderError as exc:
            logger.warning("AI provider '%s' failed: %s", provider.name, exc)
            reply = self._fallback_reply(str(exc))
        else:
            self._memory_db.increment_relationship_level(1)

        self._memory_db.add_message("assistant", reply)
        return reply

    def _build_system_prompt(self) -> str:
        prompt = settings.ai.personality_prompt
        user_name = self._memory_db.get_user_name()
        if user_name:
            prompt += f" The user's name is {user_name}; address them by name occasionally."
        level = self._memory_db.get_relationship_level()
        if level > 50:
            prompt += " You've known this user for a while now and can be extra warm and familiar."
        return prompt

    @staticmethod
    def _fallback_reply(reason: str) -> str:
        import random

        logger.debug("Falling back to canned reply. Reason: %s", reason)
        return random.choice(_FALLBACK_REPLIES)

    # ------------------------------------------------------------------
    # Memory passthrough helpers
    # ------------------------------------------------------------------

    def remember_user_name(self, name: str) -> None:
        self._memory_db.set_user_name(name)

    def clear_memory(self) -> None:
        self._memory_db.clear_conversation_history()
        logger.info("Conversation history cleared.")

    @property
    def memory_db(self) -> MemoryDB:
        return self._memory_db
