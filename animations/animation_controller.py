"""
animations/animation_controller.py
-----------------------------------
Drives Asha's frame-by-frame animation.

Design notes
~~~~~~~~~~~~
The full character art (the "cute Indian girl anime pet" described in the
spec) is a set of hand-drawn/exported sprite sheets that must be supplied
by an artist/designer and dropped into::

    assets/characters/<outfit_name>/<animation_state>/frame_0001.png
    assets/characters/<outfit_name>/<animation_state>/frame_0002.png
    ...

``AnimationController`` will automatically pick these up once they exist
(see :meth:`AnimationController._load_frames_from_disk`).

Until real art is provided, the controller falls back to a small
procedurally drawn placeholder character (a soft rounded blob with eyes)
so that the app is fully runnable end-to-end in Phase 1 -- dragging,
idle "breathing", and blinking all work today, and dropping real PNG
sequences into the folders above is a zero-code-change upgrade.
"""

from __future__ import annotations

import math
from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap

from config.settings import CHARACTERS_DIR, settings
from utils.logger import get_logger

logger = get_logger(__name__)


class AnimationState(str, Enum):
    """All animation states the character can be in.

    Only IDLE and BLINK are driven by real logic in Phase 1. The rest are
    declared now so the rest of the codebase (state machine, AI reactions,
    context menu actions in later phases) can reference a stable, complete
    vocabulary without renaming things later.
    """

    IDLE = "idle"
    BLINK = "blink"
    WALK = "walk"
    RUN = "run"
    JUMP = "jump"
    SLEEP = "sleep"
    TALK = "talk"
    HAPPY = "happy"
    SAD = "sad"
    THINKING = "thinking"
    SURPRISED = "surprised"
    LAUGH = "laugh"
    ANGRY = "angry"
    WAVE = "wave"
    DANCE = "dance"
    SIT = "sit"
    FOLLOW_CURSOR = "follow_cursor"
    STRETCH = "stretch"
    CELEBRATE = "celebrate"


class AnimationController(QObject):
    """
    Owns the current animation state and produces the QPixmap that should
    be drawn for the current frame.

    Signals:
        frame_changed: emitted with the new QPixmap whenever the visible
            frame changes, so the window can repaint itself.
        state_changed: emitted with the new AnimationState whenever the
            active animation changes (e.g. IDLE -> BLINK -> IDLE).
    """

    frame_changed = Signal(QPixmap)
    state_changed = Signal(AnimationState)

    def __init__(
        self,
        outfit: str = "casual",
        size: int = 200,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._outfit = outfit
        self._size = size
        self._state = AnimationState.IDLE
        self._frame_index = 0
        self._tick = 0  # global tick counter, used for the idle "breathing" wave

        # Cache of loaded sprite frames per state, populated lazily.
        self._disk_frames: dict[AnimationState, list[QPixmap]] = {}

        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._advance_frame)
        self._frame_timer.start(settings.animation.idle_frame_interval_ms)

        # Blink scheduling: a one-shot timer that fires at a random-ish
        # interval, briefly switches to BLINK, then returns to the
        # previous state.
        self._blink_timer = QTimer(self)
        self._blink_timer.setSingleShot(True)
        self._blink_timer.timeout.connect(self._trigger_blink)
        self._schedule_next_blink()

        logger.info("AnimationController initialized (outfit=%s, size=%d)", outfit, size)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> AnimationState:
        return self._state

    @property
    def outfit(self) -> str:
        return self._outfit

    def set_outfit(self, outfit: str) -> None:
        """
        Switch the active outfit and drop the disk-frame cache so the new
        outfit's sprite folders (assets/characters/<outfit>/...) are
        re-checked on next draw. Falls back to the placeholder character
        automatically if no art exists yet for the new outfit.
        """
        if outfit == self._outfit:
            return
        logger.info("Outfit changed: %s -> %s", self._outfit, outfit)
        self._outfit = outfit
        self._disk_frames.clear()

    def set_state(self, state: AnimationState) -> None:
        """Switch the active animation state."""
        if state == self._state:
            return
        logger.debug("Animation state: %s -> %s", self._state.value, state.value)
        self._state = state
        self._frame_index = 0
        self.state_changed.emit(state)

    def current_pixmap(self) -> QPixmap:
        """Return the pixmap that should currently be displayed."""
        frames = self._frames_for(self._state)
        if not frames:
            return QPixmap()
        return frames[self._frame_index % len(frames)]

    # ------------------------------------------------------------------
    # Frame sourcing (disk sprite sheets, else procedural placeholder)
    # ------------------------------------------------------------------

    def _frames_for(self, state: AnimationState) -> list[QPixmap]:
        if state not in self._disk_frames:
            self._disk_frames[state] = self._load_frames_from_disk(state)

        disk_frames = self._disk_frames[state]
        if disk_frames:
            return disk_frames

        # No real art yet -> synthesize a placeholder frame on the fly.
        return [self._placeholder_frame(state)]

    def _load_frames_from_disk(self, state: AnimationState) -> list[QPixmap]:
        """Look for PNG frames under assets/characters/<outfit>/<state>/."""
        folder: Path = CHARACTERS_DIR / self._outfit / state.value
        if not folder.is_dir():
            return []

        frame_paths = sorted(folder.glob("*.png"))
        frames = [QPixmap(str(p)) for p in frame_paths if not QPixmap(str(p)).isNull()]
        if frames:
            logger.info("Loaded %d disk frame(s) for state=%s from %s", len(frames), state.value, folder)
        return frames

    def _placeholder_frame(self, state: AnimationState) -> QPixmap:
        """
        Draw a cute, full-body chibi placeholder character so the app is
        fully functional before real sprite art is supplied.

        Chibi proportions (big head, short body) are used deliberately:
        a desktop companion is viewed small and square, so a tall,
        realistically-proportioned figure would either get cropped or
        shrink to an unreadable sliver. Chibi mascots are the standard
        look for this kind of always-on-top desktop pet for exactly
        that reason.

        The placeholder gently "breathes" (scales) while idle and closes
        its eyes for a couple of frames during a blink/sleep.
        """
        size = self._size
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)

        breathe = 1.0 + 0.015 * math.sin(self._tick / 10.0)
        cx = size / 2
        top_y = size * 0.06

        skin = QColor("#F6D9BC")
        hair = QColor("#5B3A29")
        hair_dark = QColor("#4A2E20")
        top_white = QColor("#FFFFFF")
        top_shadow = QColor("#E7E4EE")
        denim = QColor("#5C7EA8")
        denim_dark = QColor("#4A6890")
        shoe_white = QColor("#FFFFFF")
        outline = QColor(0, 0, 0, 40)

        # Proportions (chibi: head is roughly 40% of total height).
        head_r = size * 0.19 * breathe
        head_cy = top_y + head_r * 1.05
        neck_y = head_cy + head_r * 0.85
        shoulder_w = head_r * 1.55
        torso_h = size * 0.20
        hip_y = neck_y + torso_h
        leg_h = size * 0.30
        foot_y = hip_y + leg_h

        painter.setPen(Qt.NoPen)

        # -- Original "dance" motion: a rhythmic side-to-side body sway
        # plus alternating raised arms (not modeled on any existing
        # character — just a fun original bounce for the DANCE state). --
        dance_phase = math.sin(self._tick / 4.0)
        if state == AnimationState.DANCE:
            sway_degrees = 10 * math.sin(self._tick / 5.0)
            painter.translate(cx, hip_y)
            painter.rotate(sway_degrees)
            painter.translate(-cx, -hip_y)

        # -- Legs (drawn first, behind shorts/top) -----------------------
        leg_w = head_r * 0.42
        leg_spread = 1.0 + (0.35 * abs(dance_phase) if state == AnimationState.DANCE else 0.0)
        for side in (-1, 1):
            leg_x = cx + side * head_r * 0.42 * leg_spread
            painter.setBrush(skin)
            painter.drawRoundedRect(
                QRectF(leg_x - leg_w / 2, hip_y + torso_h * 0.1, leg_w, foot_y - hip_y - torso_h * 0.1),
                leg_w / 2, leg_w / 2,
            )
            # Shoe
            painter.setBrush(shoe_white)
            painter.drawEllipse(QPointF(leg_x, foot_y), leg_w * 0.62, leg_w * 0.4)
            painter.setBrush(QColor("#D8D8E0"))
            painter.drawEllipse(QPointF(leg_x, foot_y + leg_w * 0.12), leg_w * 0.55, leg_w * 0.18)

        # -- Arms (behind torso at the shoulder, hands resting near hips) --
        arm_w = head_r * 0.34
        for side in (-1, 1):
            shoulder_x = cx + side * shoulder_w * 0.85
            if state == AnimationState.DANCE:
                # Opposite arms raise on alternating beats for a playful,
                # energetic wiggle.
                raise_amount = max(0.0, dance_phase if side == 1 else -dance_phase)
                hand_x = cx + side * shoulder_w * (1.0 + raise_amount * 0.25)
                hand_y = (hip_y - torso_h * 0.05) - raise_amount * torso_h * 1.5
            else:
                hand_x = cx + side * shoulder_w * 1.05
                hand_y = hip_y - torso_h * 0.05
            painter.setBrush(skin)
            # Approximate the arm as a thick stroked path via a rounded rect chain.
            painter.drawEllipse(QPointF(shoulder_x, neck_y + torso_h * 0.05), arm_w * 0.55, arm_w * 0.55)
            painter.drawEllipse(QPointF(hand_x, hand_y), arm_w * 0.5, arm_w * 0.5)
            mid_x = (shoulder_x + hand_x) / 2 + side * arm_w * 0.9
            mid_y = (neck_y + torso_h * 0.05 + hand_y) / 2
            painter.drawEllipse(QPointF(mid_x, mid_y), arm_w * 0.5, arm_w * 0.5)

        # -- Shorts (denim) -------------------------------------------------
        shorts_h = torso_h * 0.55
        shorts_rect = QRectF(cx - shoulder_w * 0.62, hip_y - shorts_h * 0.3, shoulder_w * 1.24, shorts_h)
        painter.setBrush(denim)
        painter.drawRoundedRect(shorts_rect, shorts_h * 0.35, shorts_h * 0.35)
        painter.setBrush(denim_dark)
        painter.drawRoundedRect(
            QRectF(shorts_rect.left(), shorts_rect.bottom() - shorts_h * 0.25, shorts_rect.width(), shorts_h * 0.25),
            shorts_h * 0.2, shorts_h * 0.2,
        )

        # -- Off-shoulder white top -----------------------------------------
        top_path = QPainterPath()
        top_path.moveTo(cx - shoulder_w * 0.95, neck_y + torso_h * 0.18)
        top_path.quadTo(cx - shoulder_w * 1.05, neck_y - torso_h * 0.05, cx - shoulder_w * 0.55, neck_y - torso_h * 0.12)
        top_path.quadTo(cx, neck_y - torso_h * 0.22, cx + shoulder_w * 0.55, neck_y - torso_h * 0.12)
        top_path.quadTo(cx + shoulder_w * 1.05, neck_y - torso_h * 0.05, cx + shoulder_w * 0.95, neck_y + torso_h * 0.18)
        top_path.quadTo(cx + shoulder_w * 0.75, hip_y - torso_h * 0.1, cx + shoulder_w * 0.66, hip_y)
        top_path.lineTo(cx - shoulder_w * 0.66, hip_y)
        top_path.quadTo(cx - shoulder_w * 0.75, hip_y - torso_h * 0.1, cx - shoulder_w * 0.95, neck_y + torso_h * 0.18)
        top_path.closeSubpath()
        painter.setBrush(top_white)
        painter.drawPath(top_path)
        # Soft shading fold near the hem
        painter.setBrush(top_shadow)
        painter.drawRoundedRect(
            QRectF(cx - shoulder_w * 0.6, hip_y - torso_h * 0.14, shoulder_w * 1.2, torso_h * 0.14),
            torso_h * 0.07, torso_h * 0.07,
        )

        # -- Hair back-layer (behind head, flows past the shoulders) --------
        back_hair = QPainterPath()
        back_hair.moveTo(cx - head_r * 1.0, head_cy - head_r * 0.2)
        back_hair.cubicTo(
            cx - head_r * 1.7, head_cy + head_r * 0.9,
            cx - head_r * 1.3, neck_y + torso_h * 0.75,
            cx - head_r * 0.55, neck_y + torso_h * 0.55,
        )
        back_hair.lineTo(cx - head_r * 0.2, head_cy + head_r * 0.3)
        back_hair.cubicTo(
            cx - head_r * 0.1, head_cy - head_r * 0.6,
            cx - head_r * 0.5, head_cy - head_r * 1.0,
            cx - head_r * 1.0, head_cy - head_r * 0.2,
        )
        back_hair.closeSubpath()
        painter.setBrush(hair)
        painter.drawPath(back_hair)

        mirrored_back_hair = QPainterPath()
        mirrored_back_hair.moveTo(cx + head_r * 1.0, head_cy - head_r * 0.2)
        mirrored_back_hair.cubicTo(
            cx + head_r * 1.7, head_cy + head_r * 0.9,
            cx + head_r * 1.3, neck_y + torso_h * 0.75,
            cx + head_r * 0.55, neck_y + torso_h * 0.55,
        )
        mirrored_back_hair.lineTo(cx + head_r * 0.2, head_cy + head_r * 0.3)
        mirrored_back_hair.cubicTo(
            cx + head_r * 0.1, head_cy - head_r * 0.6,
            cx + head_r * 0.5, head_cy - head_r * 1.0,
            cx + head_r * 1.0, head_cy - head_r * 0.2,
        )
        mirrored_back_hair.closeSubpath()
        painter.drawPath(mirrored_back_hair)

        # -- Head / face ------------------------------------------------------
        painter.setBrush(skin)
        painter.drawEllipse(QPointF(cx, head_cy), head_r, head_r * 0.98)

        # Eyes: closed line if blinking/sleeping, open otherwise.
        eye_offset_x = head_r * 0.40
        eye_y = head_cy + head_r * 0.05
        eye_w, eye_h = head_r * 0.20, head_r * 0.26

        if state in (AnimationState.BLINK, AnimationState.SLEEP):
            pen = painter.pen()
            pen.setColor(QColor("#2B2118"))
            pen.setWidthF(2.6)
            painter.setPen(pen)
            for side in (-1, 1):
                painter.drawLine(
                    QPointF(cx + side * eye_offset_x - eye_w / 2, eye_y),
                    QPointF(cx + side * eye_offset_x + eye_w / 2, eye_y),
                )
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(QColor("#2B2118"))
            for side in (-1, 1):
                painter.drawEllipse(QPointF(cx + side * eye_offset_x, eye_y), eye_w / 2, eye_h / 2)
            # Little eye highlights for a lively, cute look.
            painter.setBrush(QColor("#FFFFFF"))
            for side in (-1, 1):
                painter.drawEllipse(
                    QPointF(cx + side * eye_offset_x - eye_w * 0.15, eye_y - eye_h * 0.15),
                    eye_w * 0.18, eye_h * 0.18,
                )

        # Blush
        painter.setBrush(QColor(255, 170, 160, 90))
        for side in (-1, 1):
            painter.drawEllipse(
                QPointF(cx + side * head_r * 0.62, head_cy + head_r * 0.32), head_r * 0.16, head_r * 0.1
            )

        # Smile
        smile_pen = painter.pen()
        smile_pen.setColor(QColor("#B5654A"))
        smile_pen.setWidthF(2.2)
        painter.setPen(smile_pen)
        painter.setBrush(Qt.NoBrush)
        smile_rect = QRectF(cx - head_r * 0.32, head_cy + head_r * 0.12, head_r * 0.64, head_r * 0.42)
        painter.drawArc(smile_rect, 200 * 16, 140 * 16)
        painter.setPen(Qt.NoPen)

        # -- Hair front-layer (bangs, drawn over the forehead) -----------------
        bangs = QPainterPath()
        bangs.moveTo(cx - head_r * 1.02, head_cy - head_r * 0.15)
        bangs.cubicTo(
            cx - head_r * 0.9, head_cy - head_r * 1.15,
            cx - head_r * 0.2, head_cy - head_r * 1.3,
            cx, head_cy - head_r * 1.02,
        )
        bangs.cubicTo(
            cx + head_r * 0.2, head_cy - head_r * 1.3,
            cx + head_r * 0.9, head_cy - head_r * 1.15,
            cx + head_r * 1.02, head_cy - head_r * 0.15,
        )
        bangs.cubicTo(
            cx + head_r * 0.7, head_cy - head_r * 0.55,
            cx + head_r * 0.25, head_cy - head_r * 0.35,
            cx, head_cy - head_r * 0.42,
        )
        bangs.cubicTo(
            cx - head_r * 0.25, head_cy - head_r * 0.35,
            cx - head_r * 0.7, head_cy - head_r * 0.55,
            cx - head_r * 1.02, head_cy - head_r * 0.15,
        )
        bangs.closeSubpath()
        painter.setBrush(hair_dark)
        painter.drawPath(bangs)

        if state == AnimationState.SLEEP:
            z_font = painter.font()
            z_font.setPointSizeF(size * 0.07)
            z_font.setBold(True)
            painter.setFont(z_font)
            z_pen = painter.pen()
            z_pen.setColor(QColor("#8A7CA8"))
            painter.setPen(z_pen)
            drift = 4 * math.sin(self._tick / 15.0)
            painter.drawText(
                QPointF(cx + head_r * 1.1, head_cy - head_r * 1.0 + drift),
                "Zzz",
            )

        painter.end()
        return pixmap

    # ------------------------------------------------------------------
    # Timer-driven internals
    # ------------------------------------------------------------------

    def _advance_frame(self) -> None:
        self._tick += 1
        self._frame_index += 1
        self.frame_changed.emit(self.current_pixmap())

    def _schedule_next_blink(self) -> None:
        import random

        interval = random.randint(
            settings.animation.blink_min_interval_ms,
            settings.animation.blink_max_interval_ms,
        )
        self._blink_timer.start(interval)

    def _trigger_blink(self) -> None:
        previous_state = self._state
        if previous_state in (AnimationState.SLEEP,):
            # Don't blink while asleep; just reschedule.
            self._schedule_next_blink()
            return

        self.set_state(AnimationState.BLINK)
        QTimer.singleShot(150, lambda: self.set_state(previous_state))
        self._schedule_next_blink()

    def stop(self) -> None:
        """Stop all internal timers (call on application shutdown)."""
        self._frame_timer.stop()
        self._blink_timer.stop()
        logger.info("AnimationController stopped.")

    def apply_speed_settings(self) -> None:
        """
        Re-read `settings.animation.animation_speed_multiplier` and adjust
        the frame timer interval accordingly. Call after the Settings
        dialog changes the multiplier.
        """
        base_interval = settings.animation.idle_frame_interval_ms
        multiplier = max(0.1, settings.animation.animation_speed_multiplier)
        new_interval = max(10, int(base_interval / multiplier))
        self._frame_timer.setInterval(new_interval)
        logger.debug("Animation speed applied: interval=%dms (multiplier=%.2f)", new_interval, multiplier)
