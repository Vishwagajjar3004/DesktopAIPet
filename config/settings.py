"""
config/settings.py
-------------------
Central configuration for the Desktop AI Pet (Asha) application.

This module defines:
    * Filesystem paths (assets, database, logs, plugins).
    * Default runtime settings (window size, opacity, animation speed,
      AI provider, voice options).
    * Dataclasses that later phases load/save from SQLite or JSON.

Keeping all "magic values" in one place makes the rest of the codebase
free of hard-coded paths/numbers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Base paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

ASSETS_DIR: Path = PROJECT_ROOT / "assets"
ANIMATIONS_DIR: Path = ASSETS_DIR / "animations"
AUDIO_DIR: Path = ASSETS_DIR / "audio"
ICONS_DIR: Path = ASSETS_DIR / "icons"
CHARACTERS_DIR: Path = ASSETS_DIR / "characters"

DATABASE_DIR: Path = PROJECT_ROOT / "database"
DATABASE_FILE: Path = DATABASE_DIR / "asha_memory.db"

LOGS_DIR: Path = PROJECT_ROOT / "logs"
LOG_FILE: Path = LOGS_DIR / "asha.log"

PLUGINS_DIR: Path = PROJECT_ROOT / "plugins"

APP_NAME: str = "Asha"
APP_VERSION: str = "0.5.0"
ORG_NAME: str = "DesktopAIPet"


# ---------------------------------------------------------------------------
# Window / animation / speech bubble settings
# ---------------------------------------------------------------------------

@dataclass
class WindowSettings:
    width: int = 220
    height: int = 220
    start_x: int = 100
    start_y: int = 100
    always_on_top: bool = True
    click_through: bool = False
    show_in_taskbar: bool = False
    opacity: float = 1.0


@dataclass
class AnimationSettings:
    fps: int = 12
    idle_frame_interval_ms: int = 1000 // 12
    blink_min_interval_ms: int = 3000
    blink_max_interval_ms: int = 7000
    animation_speed_multiplier: float = 1.0


@dataclass
class SpeechBubbleSettings:
    max_width: int = 260
    typing_speed_ms: int = 25
    auto_hide_ms: int = 6000


# ---------------------------------------------------------------------------
# AI provider settings (Phase 2)
# ---------------------------------------------------------------------------

@dataclass
class AISettings:
    """Which AI backend to talk to, and how."""

    #: "simple" (offline, zero-setup, default), "openai", or "ollama"
    provider: str = "simple"

    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    openai_model: str = "gpt-4o-mini"

    # Ollama (local)
    ollama_host: str = field(default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = "llama3.2"

    # Shared
    max_history_messages: int = 20  # how many past turns to send as context
    temperature: float = 0.8
    personality_prompt: str = (
        "You are Asha, a cute, playful, slightly sarcastic but caring desktop AI pet. "
        "You are intelligent, curious, and friendly. You speak in short, warm, expressive "
        "sentences (1-3 sentences max, since you live in a small speech bubble). "
        "You react naturally to what the user tells you and remember context from the "
        "conversation. Never break character or mention that you are a language model."
    )


# ---------------------------------------------------------------------------
# Voice settings (Phase 2)
# ---------------------------------------------------------------------------

@dataclass
class VoiceSettings:
    tts_enabled: bool = True
    stt_enabled: bool = True
    wake_word_enabled: bool = False
    wake_word: str = "hey asha"
    tts_rate: int = 175          # words per minute (pyttsx3)
    tts_volume: float = 0.9      # 0.0 - 1.0
    tts_voice_id: str = ""       # empty = engine default; set via Settings dialog
    stt_language: str = "en-US"


# ---------------------------------------------------------------------------
# Desktop awareness / smart reactions settings (Phase 3)
# ---------------------------------------------------------------------------

@dataclass
class AwarenessSettings:
    enabled: bool = True
    poll_interval_ms: int = 5000
    idle_threshold_seconds: int = 300         # 5 minutes -> "coffee break?"
    low_battery_threshold_percent: int = 20
    typing_streak_seconds: int = 90           # continuous typing -> "on fire" comment
    away_threshold_seconds: int = 3600        # 1 hour away -> "welcome back"
    reaction_cooldown_seconds: int = 60       # don't repeat reactions too often


# ---------------------------------------------------------------------------
# Aggregate settings object
# ---------------------------------------------------------------------------

@dataclass
class Settings:
    window: WindowSettings = field(default_factory=WindowSettings)
    animation: AnimationSettings = field(default_factory=AnimationSettings)
    speech_bubble: SpeechBubbleSettings = field(default_factory=SpeechBubbleSettings)
    ai: AISettings = field(default_factory=AISettings)
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    awareness: AwarenessSettings = field(default_factory=AwarenessSettings)

    theme: str = "dark"
    language: str = "en"
    volume: float = 0.8
    muted: bool = False
    outfit: str = "casual"
    start_with_os: bool = False


def ensure_directories() -> None:
    """Create all directories the application depends on if missing."""
    for directory in (
        ASSETS_DIR,
        ANIMATIONS_DIR,
        AUDIO_DIR,
        ICONS_DIR,
        CHARACTERS_DIR,
        DATABASE_DIR,
        LOGS_DIR,
        PLUGINS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


# A single shared settings instance used across the app.
# SettingsManager (config/settings_manager.py) loads/persists this from
# the SQLite database on top of these defaults.
settings = Settings()
