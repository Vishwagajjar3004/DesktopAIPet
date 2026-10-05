"""Tests for voice/tts_engine.py — focused on the female-voice
auto-selection heuristic, which doesn't need a real audio backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from voice.tts_engine import TTSEngine


@dataclass
class FakeVoice:
    id: str
    name: str
    gender: Optional[str] = None


class FakeEngine:
    def __init__(self, voices):
        self._voices = voices
        self._properties = {}

    def getProperty(self, key):
        if key == "voices":
            return self._voices
        return self._properties.get(key)

    def setProperty(self, key, value):
        self._properties[key] = value


def _make_engine_with(voices) -> TTSEngine:
    engine = TTSEngine.__new__(TTSEngine)  # bypass __init__ / real pyttsx3
    engine._engine = FakeEngine(voices)
    return engine


def test_prefers_gender_metadata_when_present():
    voices = [
        FakeVoice(id="v1", name="David", gender="male"),
        FakeVoice(id="v2", name="Zira", gender="female"),
    ]
    engine = _make_engine_with(voices)
    engine._auto_select_female_voice()
    assert engine._engine.getProperty("voice") == "v2"


def test_falls_back_to_name_heuristic_without_gender_metadata():
    voices = [
        FakeVoice(id="v1", name="David"),
        FakeVoice(id="v2", name="Microsoft Zira Desktop"),
    ]
    engine = _make_engine_with(voices)
    engine._auto_select_female_voice()
    assert engine._engine.getProperty("voice") == "v2"


def test_no_match_leaves_engine_default_untouched():
    voices = [FakeVoice(id="v1", name="David"), FakeVoice(id="v2", name="Mark")]
    engine = _make_engine_with(voices)
    engine._auto_select_female_voice()
    assert engine._engine.getProperty("voice") is None
