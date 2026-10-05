"""
ai/simple_provider.py
------------------------
A fully offline, zero-setup chat backend: no API key, no local server,
no internet required. This is the DEFAULT provider so Asha's Chat
feature works the moment you run `python main.py`, with OpenAI/Ollama
available as optional upgrades for smarter replies (see Settings ->
Voice & AI).

It works with simple keyword/pattern matching plus a personality
"flavor" layer, not a real language model — so replies are limited and
repeat over time. That's the explicit trade-off for requiring zero
setup and zero external dependency.
"""

from __future__ import annotations

import random
import re

from ai.base_provider import AIProvider, ChatTurn
from utils.logger import get_logger

logger = get_logger(__name__)

_PATTERNS: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\b(hi|hello|hey|namaste|kem cho)\b", re.I), [
        "Hi there! 💜", "Hey! How's it going?", "Hello hello! What's up?",
    ]),
    (re.compile(r"\bhow are you\b", re.I), [
        "I'm doing great, thanks for asking! How about you?",
        "Living my best pixel life! You?",
    ]),
    (re.compile(r"\b(bye|goodbye|see you|jau chu)\b", re.I), [
        "Bye! Come back soon 💜", "See you later!",
    ]),
    (re.compile(r"\bthank", re.I), [
        "You're welcome! 😊", "Anytime!",
    ]),
    (re.compile(r"\b(tired|exhausted|thak|thaki)\b", re.I), [
        "Maybe it's time for a short break? ☕", "Take it easy on yourself.",
    ]),
    (re.compile(r"\b(sad|upset|udas)\b", re.I), [
        "I'm sorry you're feeling that way. I'm here if you want to talk.",
    ]),
    (re.compile(r"\b(happy|khush|great|awesome)\b", re.I), [
        "That's wonderful to hear! 🎉", "Yay! Love that energy.",
    ]),
    (re.compile(r"\b(name|naam)\b", re.I), [
        "I'm Asha, your desktop companion! 💜",
    ]),
    (re.compile(r"\bwhat.*(time|date)\b|\btime.*is.*it\b", re.I), [
        "__DATETIME__",  # handled specially in generate_reply()
    ]),
    (re.compile(r"\bjoke\b", re.I), [
        "Why did the developer go broke? Because they used up all their cache! 😄",
        "I'd tell you a UDP joke, but you might not get it.",
    ]),
]

_FALLBACKS = [
    "Tell me more!",
    "Hmm, interesting — go on?",
    "I'm listening 💜",
    "Got it! Anything else on your mind?",
    "I hear you.",
]


class SimpleProvider(AIProvider):
    """Offline, zero-dependency keyword-based responder."""

    name = "simple"

    def is_available(self) -> bool:
        return True  # always available — no external dependency at all

    def chat(self, messages: list[ChatTurn], temperature: float = 0.8) -> str:
        # The last message is always the newest user turn.
        user_messages = [m for m in messages if m.role == "user"]
        if not user_messages:
            return random.choice(_FALLBACKS)

        latest = user_messages[-1].content
        for pattern, replies in _PATTERNS:
            if pattern.search(latest):
                reply = random.choice(replies)
                if reply == "__DATETIME__":
                    return self._current_datetime_reply()
                return reply

        return random.choice(_FALLBACKS)

    @staticmethod
    def _current_datetime_reply() -> str:
        from datetime import datetime

        now = datetime.now()
        return f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %d %B %Y')} 🕐"
