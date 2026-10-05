"""Tests for ai/ai_manager.py — focused on the fallback path, since real
provider calls need network/API keys and are out of scope for unit tests."""

from __future__ import annotations

from ai.ai_manager import AIManager
from config.settings import settings


def test_send_message_falls_back_gracefully_when_no_provider_reachable(memory_db):
    settings.ai.provider = "ollama"
    settings.ai.ollama_host = "http://localhost:1"  # guaranteed unreachable port
    manager = AIManager(memory_db=memory_db)

    reply = manager.send_message("Hello Asha")

    assert isinstance(reply, str)
    assert len(reply) > 0
    history = memory_db.get_recent_messages()
    assert history[0].role == "user"
    assert history[0].content == "Hello Asha"
    assert history[1].role == "assistant"


def test_set_provider_rejects_unknown_name(memory_db):
    manager = AIManager(memory_db=memory_db)
    try:
        manager.set_provider("not_a_real_provider")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_provider_status_returns_bool_per_provider(memory_db):
    manager = AIManager(memory_db=memory_db)
    status = manager.provider_status()
    assert set(status.keys()) == {"simple", "openai", "ollama"}
    assert all(isinstance(v, bool) for v in status.values())
