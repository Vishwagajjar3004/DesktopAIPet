"""
ai/base_provider.py
--------------------
Abstract interface every AI backend must implement, so `AIManager` and
the rest of the app never need to know whether they're talking to
OpenAI's API or a local Ollama model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatTurn:
    """One turn of conversation, in the generic role/content shape used
    by essentially every chat-completion API."""

    role: str      # "system" | "user" | "assistant"
    content: str


class AIProvider(ABC):
    """Common interface for chat-completion backends."""

    name: str = "base"

    @abstractmethod
    def chat(self, messages: list[ChatTurn], temperature: float = 0.8) -> str:
        """
        Send the full conversation (including the system/personality
        prompt as the first message) and return the assistant's reply
        as plain text.

        Implementations should raise `AIProviderError` on failure so
        `AIManager` can show a friendly fallback message instead of
        crashing the UI.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check for whether this provider is currently usable
        (e.g. API key present, or local server reachable)."""
        raise NotImplementedError


class AIProviderError(RuntimeError):
    """Raised when a provider fails to produce a response."""
