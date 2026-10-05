"""Tests for the messages table added to database/memory_db.py."""

from __future__ import annotations

from database.memory_db import MESSAGE_CATEGORIES


def test_add_and_get_message_log(memory_db):
    memory_db.add_message_log("Drink some water", category="Water Reminder", screen_time=1800)
    memory_db.add_message_log("Great focus today!", category="Compliment", mood="happy")

    logs = memory_db.get_message_logs()
    assert len(logs) == 2
    # newest first
    assert logs[0].message == "Great focus today!"
    assert logs[1].screen_time == 1800


def test_unknown_category_falls_back_to_general(memory_db):
    memory_db.add_message_log("hello", category="NotARealCategory")
    logs = memory_db.get_message_logs()
    assert logs[0].category == "General"


def test_filter_by_category(memory_db):
    memory_db.add_message_log("a", category="Health")
    memory_db.add_message_log("b", category="Motivation")
    assert len(memory_db.get_message_logs(category="Health")) == 1
    assert len(memory_db.get_message_logs(category="All")) == 2


def test_search_filter(memory_db):
    memory_db.add_message_log("You've been very productive today.")
    memory_db.add_message_log("Drink some water.")
    results = memory_db.get_message_logs(search="water")
    assert len(results) == 1
    assert "water" in results[0].message.lower()


def test_clear_message_logs(memory_db):
    memory_db.add_message_log("gone soon")
    assert len(memory_db.get_message_logs()) == 1
    memory_db.clear_message_logs()
    assert len(memory_db.get_message_logs()) == 0


def test_all_spec_categories_present():
    expected = {
        "Health",
        "Break Reminder",
        "Screen Time",
        "Focus",
        "Compliment",
        "Motivation",
        "Productivity",
        "Water Reminder",
        "Exercise",
        "General",
    }
    assert expected.issubset(set(MESSAGE_CATEGORIES))
