"""Tests for animations/animation_controller.py."""

from __future__ import annotations

from animations.animation_controller import AnimationController, AnimationState


def test_default_state_is_idle(qapp):
    controller = AnimationController(size=100)
    assert controller.state == AnimationState.IDLE
    controller.stop()


def test_set_state_changes_state_and_emits_signal(qapp):
    controller = AnimationController(size=100)
    seen = []
    controller.state_changed.connect(seen.append)

    controller.set_state(AnimationState.DANCE)

    assert controller.state == AnimationState.DANCE
    assert seen == [AnimationState.DANCE]
    controller.stop()


def test_placeholder_frame_is_generated_when_no_disk_art(qapp):
    controller = AnimationController(size=64)
    pixmap = controller.current_pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() == 64
    controller.stop()


def test_set_outfit_clears_disk_frame_cache(qapp):
    controller = AnimationController(outfit="casual", size=64)
    controller._frames_for(AnimationState.IDLE)  # populate cache
    assert AnimationState.IDLE in controller._disk_frames

    controller.set_outfit("festival")

    assert controller.outfit == "festival"
    assert controller._disk_frames == {}
    controller.stop()
