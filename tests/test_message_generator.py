"""Tests for system/message_generator.py."""

from __future__ import annotations

from system import message_generator


def test_generate_returns_nonempty_string():
    text = message_generator.generate("Compliment")
    assert isinstance(text, str) and text


def test_generate_unknown_category_falls_back_to_general():
    # Should not raise, and should just produce a plain string (uses the
    # "General" pool under the hood for unrecognized categories).
    text = message_generator.generate("NotARealCategory")
    assert isinstance(text, str) and text


def test_generate_substitutes_format_args():
    text = message_generator.generate("Screen Time", duration="1h 30m")
    assert "1h 30m" in text


def test_generate_avoids_immediate_repeats():
    # Draw more times than the pool size for a small category and make sure
    # we don't see the exact same line twice in a row.
    seen = [message_generator.generate("Exercise") for _ in range(10)]
    consecutive_dupes = sum(1 for a, b in zip(seen, seen[1:]) if a == b)
    assert consecutive_dupes == 0
