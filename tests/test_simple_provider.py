"""Tests for the offline, zero-setup SimpleProvider and AIManager default."""

from __future__ import annotations

from ai.ai_manager import AIManager
from ai.base_provider import ChatTurn
from ai.simple_provider import SimpleProvider
from config.settings import settings


def test_simple_provider_always_available():
    provider = SimpleProvider()
    assert provider.is_available() is True


def test_simple_provider_responds_to_greeting():
    provider = SimpleProvider()
    reply = provider.chat([ChatTurn("user", "hi there")])
    assert isinstance(reply, str)
    assert len(reply) > 0


def test_simple_provider_datetime_pattern():
    provider = SimpleProvider()
    reply = provider.chat([ChatTurn("user", "what time is it?")])
    assert any(ch.isdigit() for ch in reply)


def test_default_provider_is_simple_and_works_without_setup(memory_db):
    settings.ai.provider = "simple"
    manager = AIManager(memory_db=memory_db)
    reply = manager.send_message("hello")
    assert isinstance(reply, str) and len(reply) > 0
    # SimpleProvider never fails, so this should not be a canned fallback line.
    from ai.ai_manager import _FALLBACK_REPLIES

    assert reply not in _FALLBACK_REPLIES
