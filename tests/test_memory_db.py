"""Tests for database/memory_db.py."""

from __future__ import annotations


def test_preferences_roundtrip(memory_db):
    assert memory_db.get_preference("theme") is None
    memory_db.set_preference("theme", "dark")
    assert memory_db.get_preference("theme") == "dark"
    memory_db.set_preference("theme", "light")
    assert memory_db.get_preference("theme") == "light"


def test_conversation_history_order(memory_db):
    memory_db.add_message("user", "hello")
    memory_db.add_message("assistant", "hi there")
    memory_db.add_message("user", "how are you")

    messages = memory_db.get_recent_messages(limit=10)
    assert [m.content for m in messages] == ["hello", "hi there", "how are you"]
    assert [m.role for m in messages] == ["user", "assistant", "user"]


def test_conversation_history_limit(memory_db):
    for i in range(5):
        memory_db.add_message("user", f"message {i}")
    messages = memory_db.get_recent_messages(limit=2)
    assert len(messages) == 2
    assert messages[-1].content == "message 4"


def test_favorite_apps_counts(memory_db):
    memory_db.record_app_seen("Visual Studio Code")
    memory_db.record_app_seen("Visual Studio Code")
    memory_db.record_app_seen("Chrome")
    top = memory_db.top_favorite_apps(limit=5)
    assert top[0] == ("Visual Studio Code", 2)


def test_reminders(memory_db):
    reminder_id = memory_db.add_reminder("Buy milk")
    pending = memory_db.pending_reminders()
    assert len(pending) == 1
    memory_db.mark_reminder_done(reminder_id)
    assert memory_db.pending_reminders() == []


def test_user_profile_and_relationship_level(memory_db):
    assert memory_db.get_user_name() is None
    memory_db.set_user_name("Vishwa")
    assert memory_db.get_user_name() == "Vishwa"

    assert memory_db.get_relationship_level() == 0
    new_level = memory_db.increment_relationship_level(3)
    assert new_level == 3
    assert memory_db.get_relationship_level() == 3
