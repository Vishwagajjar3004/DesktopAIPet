"""
system/message_generator.py
------------------------------
Generates the pet's contextual one-liners (Feature 7: "AI generated
messages"). This is a lightweight, fully-offline template generator --
no network/API key required -- that picks a random phrasing per
category and avoids repeating the same line twice in a row (and avoids
repeating anything from the last N lines shown for that category).

If a real LLM provider is configured (`ai.ai_manager.AIManager`), the
pet's free-form chat replies already go through that instead; this
module only covers the proactive, non-chat "smart" messages (screen
time, breaks, hydration, focus, etc.) described in the spec.
"""

from __future__ import annotations

import random
from collections import deque
from typing import Deque, Dict, List

# Category -> pool of varied phrasings. Kept intentionally larger than
# strictly necessary so "never repeats often" holds up over a full day.
_TEMPLATES: Dict[str, List[str]] = {
    "Screen Time": [
        "You've been using your screen for {duration}.",
        "That's {duration} of screen time today.",
        "Screen time check: {duration} and counting.",
        "You've been active for {duration} today \u2014 nice focus! \U0001f440",
    ],
    "Break Reminder": [
        "You've worked for {duration}. Take a short walk?",
        "Take a 5 minute break \u2014 you've earned it.",
        "How about stepping away from the screen for a bit?",
        "A quick break now will help you focus later.",
    ],
    "Health": [
        "Stretch your neck \u2014 you've been sitting a while.",
        "Remember to blink! Screens are tough on the eyes.",
        "Sit up straight for a second, check your posture.",
        "You look tired. Maybe rest your eyes for a minute.",
    ],
    "Water Reminder": [
        "Hydration check! \U0001f4a7",
        "Drink some water \u2014 your brain will thank you.",
        "When did you last have some water?",
        "Quick reminder: grab a glass of water.",
    ],
    "Exercise": [
        "Stretch those shoulders \u2014 you've earned it.",
        "A quick stretch break could feel great right now.",
        "Stand up and shake it out for a moment.",
    ],
    "Focus": [
        "Your focus is impressive today.",
        "You're locked in \u2014 keep going.",
        "Nice deep-work streak going on there.",
    ],
    "Compliment": [
        "Great focus today!",
        "Nice progress! Keep it up.",
        "You're doing amazing today.",
        "Impressive consistency today.",
    ],
    "Motivation": [
        "Keep going! You're making progress.",
        "Awesome consistency \u2014 don't stop now.",
        "One step at a time \u2014 you've got this.",
        "You've been very productive today.",
    ],
    "Productivity": [
        "I think a short walk would help your focus.",
        "Your productivity today has been solid.",
        "Small steady progress adds up \u2014 nice work.",
    ],
    "General": [
        "Just checking in on you.",
        "I'm here if you need anything.",
    ],
}

# Remember the last few lines shown per category so we don't repeat too soon.
_recent_by_category: Dict[str, Deque[str]] = {}
_HISTORY_SIZE = 3


def generate(category: str, **format_args: object) -> str:
    """Return a template for `category`, avoiding recent repeats.

    Guarantees the exact same line is never chosen twice in a row (when the
    pool has more than one option), and additionally tries to avoid the last
    few lines shown for that category for better variety over a full day.

    Any `format_args` (e.g. `duration="1h 30m"`) are substituted into the
    chosen template via `str.format`.
    """
    pool = _TEMPLATES.get(category, _TEMPLATES["General"])
    recent = _recent_by_category.setdefault(category, deque(maxlen=_HISTORY_SIZE))

    # Hard constraint: never repeat the immediately-previous line.
    last = recent[-1] if recent else None
    not_last = [t for t in pool if t != last] or pool

    # Soft constraint: prefer lines not shown in the last few picks.
    candidates = [t for t in not_last if t not in recent] or not_last

    choice = random.choice(candidates)
    recent.append(choice)

    try:
        return choice.format(**format_args)
    except (KeyError, IndexError):
        return choice
