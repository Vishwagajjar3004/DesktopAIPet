"""
ui/pet_window.py
-----------------
The core floating desktop-companion window: frameless, transparent,
always-on-top, draggable with the mouse, hidden from the taskbar, and
carrying the right-click context menu described in the spec.

This is also the integration point where AI chat (Phase 2), voice
(Phase 2), desktop-awareness reactions (Phase 3), outfits/plugins/
settings (Phase 4) all get wired together behind the pet's public
`say()` / animation-state surface.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from ai.ai_manager import AIManager
from ai.ai_worker import AIWorker
from animations.animation_controller import AnimationController, AnimationState
from config.settings import settings
from config.settings_manager import SettingsManager
from database.memory_db import MemoryDB
from plugins.plugin_base import PetAPI
from plugins.plugin_manager import PluginManager
from system.reaction_engine import ReactionEngine
from system.screen_time_tracker import ScreenTimeTracker
from ui.chat_input import ChatInput
from ui.history_panel import HistoryPanel
from ui.settings_dialog import SettingsDialog
from ui.speech_bubble import SpeechBubble
from utils.logger import get_logger
from voice.stt_engine import STTEngine
from voice.tts_engine import TTSEngine
from voice.wake_word import WakeWordListener

logger = get_logger(__name__)

#: Outfits the user can cycle through via the context menu.
#: Real art per outfit goes under assets/characters/<outfit_key>/...
AVAILABLE_OUTFITS: list[tuple[str, str]] = [
    ("casual", "Casual"),
    ("formal", "Formal"),
    ("winter", "Winter"),
    ("festival", "Festival"),
    ("night_suit", "Night Suit"),
    ("school", "School"),
    ("traditional_indian", "Traditional Indian"),
]


class PetWindow(QWidget):
    """The draggable, frameless, always-on-top desktop pet."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool,  # keeps the window out of the taskbar / alt-tab list
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        # -- Memory / settings (loaded early so the saved window position
        #    is available before we place the window on screen) -----------
        self._memory_db = MemoryDB()
        self._settings_manager = SettingsManager(self._memory_db)
        self._settings_manager.load()

        self._size = settings.window.width
        self.resize(self._size, self._size)

        saved_position = self._settings_manager.load_window_position()
        start_x, start_y = saved_position or (settings.window.start_x, settings.window.start_y)
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            geo = primary_screen.availableGeometry()
            if (
                start_x < geo.left() - 50
                or start_x > geo.right() - 50
                or start_y < geo.top() - 50
                or start_y > geo.bottom() - 50
            ):
                logger.info(
                    "Saved position (%d, %d) is off-screen (bounds: %s); resetting to default.",
                    start_x,
                    start_y,
                    geo,
                )
                start_x, start_y = settings.window.start_x, settings.window.start_y
        self.move(start_x, start_y)
        if not QGuiApplication.platformName().startswith("wayland"):
            self.setWindowOpacity(settings.window.opacity)

        self._drag_offset: Optional[QPoint] = None
        self._click_through = settings.window.click_through

        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._save_position_now)

        # -- Animation --------------------------------------------------
        self.animation_controller = AnimationController(
            outfit=settings.outfit, size=self._size, parent=self
        )
        self.animation_controller.frame_changed.connect(lambda _pixmap: self.update())
        self.animation_controller.apply_speed_settings()

        # -- AI / voice ----------------------------------------------------
        self._ai_manager = AIManager(memory_db=self._memory_db)
        self._tts_engine = TTSEngine()
        self._stt_engine = STTEngine()
        self._wake_word_listener = WakeWordListener(self._stt_engine, on_wake=self._on_wake_word)
        self._active_ai_worker: Optional[AIWorker] = None

        # -- UI popups ----------------------------------------------------
        self._speech_bubble = SpeechBubble()
        self._chat_input = ChatInput(mic_available=self._stt_engine.available)
        self._chat_input.message_submitted.connect(self._handle_user_message)
        self._chat_input.mic_clicked.connect(self._handle_mic_clicked)

        # -- Desktop awareness / smart reactions ---------------------------
        self._reaction_engine = ReactionEngine(say_callback=self.say, memory_db=self._memory_db, parent=self)
        self._reaction_engine.start()

        self._screen_time_tracker = ScreenTimeTracker(
            memory_db=self._memory_db, on_milestone=self.say, parent=self
        )
        self._screen_time_tracker.start()

        # -- Plugins --------------------------------------------------------
        plugin_api = PetAPI(say=self.say, set_animation_state=self.animation_controller.set_state)
        self._plugin_manager = PluginManager(plugin_api)
        loaded = self._plugin_manager.discover_and_load()
        if loaded:
            logger.info("Plugins loaded: %s", ", ".join(loaded))

        if settings.voice.wake_word_enabled:
            self._wake_word_listener.start()

        self._build_context_menu()

        logger.info("PetWindow initialized at (%d, %d), size=%d", self.x(), self.y(), self._size)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pixmap = self.animation_controller.current_pixmap()
        if not pixmap.isNull():
            painter.drawPixmap(0, 0, pixmap)
        painter.end()

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------
    #
    # Frameless "Tool" always-on-top windows (which is what this is, so it
    # stays out of the taskbar) don't reliably receive continuous
    # mouseMoveEvent callbacks while a button is held on every platform --
    # some window managers never hand the window an implicit mouse grab
    # because it never truly gains input focus. The fix: hand dragging off
    # to the OS's own native window-move via QWindow.startSystemMove(),
    # exactly what happens when you drag a normal titled window. This is
    # the Qt-recommended approach for frameless-window dragging and works
    # even when manual delta-tracking silently fails to start.
    #
    # A manual fallback (the original delta-tracking approach) is kept for
    # the rare platform/Qt-version combo where startSystemMove() isn't
    # available (it returns False rather than raising).

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        window_handle = self.windowHandle()
        if window_handle is not None and window_handle.startSystemMove():
            event.accept()
            return
        # Fallback: manual delta-tracking drag.
        self._drag_offset = event.globalPosition().toPoint() - self.pos()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        event.accept()

    def moveEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Whenever the window actually moves -- for any reason, including
        a native startSystemMove() drag which bypasses mouseMoveEvent --
        (re)start a short debounce timer that persists the new position.
        This is what makes Feature 1 ("remembers its last position") work
        regardless of which drag path was used."""
        super().moveEvent(event)
        if hasattr(self, "_position_save_timer"):
            self._position_save_timer.start(400)

    def _save_position_now(self) -> None:
        x, y = self.x(), self.y()
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            geo = primary_screen.availableGeometry()
            if (
                x < geo.left() - self.width()
                or x > geo.right()
                or y < geo.top() - self.height()
                or y > geo.bottom()
            ):
                logger.warning("Refusing to save off-screen window position: (%d, %d)", x, y)
                return
        self._settings_manager.save_window_position(x, y)

    # ------------------------------------------------------------------
    # Speech bubble / chat helpers
    # ------------------------------------------------------------------

    def say(self, text: str, category: str = "General", mood: Optional[str] = None) -> None:
        """Show `text` in the speech bubble (anchored above the pet), speak
        it aloud via TTS if enabled, and log it to the message history
        (Features 3/5/11) so it shows up in the History Panel."""
        top_center_local = QPoint(self.width() // 2, 0)
        anchor_global = self.mapToGlobal(top_center_local)
        self._speech_bubble.say(text, anchor_global)
        self._tts_engine.speak(text)

        self._memory_db.add_message_log(
            message=text,
            category=category,
            screen_time=self._screen_time_tracker.today_seconds()
            if hasattr(self, "_screen_time_tracker")
            else None,
            mood=mood or self.animation_controller.state.value,
        )

    def _open_chat_input(self) -> None:
        top_center_local = QPoint(self.width() // 2, 0)
        anchor_global = self.mapToGlobal(top_center_local)
        self._chat_input.open_at(anchor_global)

    def _handle_user_message(self, text: str) -> None:
        logger.info("User said: %s", text)
        self.animation_controller.set_state(AnimationState.THINKING)

        if self._active_ai_worker is not None and self._active_ai_worker.isRunning():
            logger.debug("AI worker already running; ignoring overlapping request.")
            return

        worker = AIWorker(self._ai_manager, text, parent=self)
        worker.reply_ready.connect(self._handle_ai_reply)
        worker.failed.connect(lambda err: self._handle_ai_reply("Sorry, something went wrong on my end."))
        worker.finished.connect(worker.deleteLater)
        self._active_ai_worker = worker
        worker.start()

    def _handle_ai_reply(self, reply_text: str) -> None:
        self.animation_controller.set_state(AnimationState.TALK)
        self.say(reply_text, category="General")
        QApplication.instance().processEvents()
        # Return to idle shortly after "talking" finishes being shown.
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1500, lambda: self.animation_controller.set_state(AnimationState.IDLE))

    def _handle_mic_clicked(self) -> None:
        if not self._stt_engine.available:
            self.say("I can't hear you — no microphone detected.")
            return
        self.say("I'm listening...")
        self._stt_engine.listen_once_async(self._on_speech_transcribed)

    def _on_speech_transcribed(self, text: Optional[str]) -> None:
        if text:
            self._handle_user_message(text)
        else:
            self.say("Sorry, I didn't catch that.")

    def _on_wake_word(self) -> None:
        self.say("Yes?")
        self._stt_engine.listen_once_async(self._on_speech_transcribed)

    # ------------------------------------------------------------------
    # Click-through mode
    # ------------------------------------------------------------------

    def set_click_through(self, enabled: bool) -> None:
        """
        Toggle click-through mode: when enabled, mouse events pass through
        the window to whatever is beneath it on the desktop.
        """
        self._click_through = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        logger.info("Click-through mode: %s", "ON" if enabled else "OFF")
        self.say("Click-through ON — use the tray icon to bring me back!" if enabled else "I'm interactive again!")

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self) -> None:
        self._menu = QMenu(self)

        chat_action = self._menu.addAction("💬 Chat")
        chat_action.triggered.connect(self._on_chat)

        sleep_action = self._menu.addAction("😴 Sleep")
        sleep_action.triggered.connect(self._on_toggle_sleep)

        dance_action = self._menu.addAction("💃 Dance")
        dance_action.triggered.connect(self._on_dance)

        self._menu.addSeparator()

        outfit_menu = self._menu.addMenu("👗 Change Outfit")
        for key, label in AVAILABLE_OUTFITS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, k=key, l=label: self._on_change_outfit(k, l))
            outfit_menu.addAction(action)

        click_through_action = self._menu.addAction("🖱️ Click-through Mode")
        click_through_action.setCheckable(True)
        click_through_action.setChecked(self._click_through)
        click_through_action.triggered.connect(self.set_click_through)

        self._menu.addSeparator()

        datetime_action = self._menu.addAction("📅 Date && Time")
        datetime_action.triggered.connect(self._on_show_datetime)

        screen_time_action = self._menu.addAction("📊 Screen Time Today")
        screen_time_action.triggered.connect(self._on_show_screen_time)

        history_action = self._menu.addAction("🕘 History")
        history_action.triggered.connect(self._on_show_history)

        settings_action = self._menu.addAction("⚙️ Settings")
        settings_action.triggered.connect(self._on_settings)

        self._menu.addSeparator()

        self._mute_action = self._menu.addAction("🔇 Mute")
        self._mute_action.setCheckable(True)
        self._mute_action.setChecked(settings.muted)
        self._mute_action.triggered.connect(self._on_toggle_mute)

        restart_action = self._menu.addAction("🔄 Restart")
        restart_action.triggered.connect(self._on_restart)

        about_action = self._menu.addAction("ℹ️ About")
        about_action.triggered.connect(self._on_about)

        self._menu.addSeparator()

        exit_action = self._menu.addAction("✖ Exit")
        exit_action.triggered.connect(self._on_exit)

    def contextMenuEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._menu.exec(event.globalPos())

    # -- Menu action handlers -----------------------------------------

    def _on_chat(self) -> None:
        logger.info("Chat opened from context menu.")
        self._open_chat_input()

    def _on_toggle_sleep(self) -> None:
        if self.animation_controller.state == AnimationState.SLEEP:
            self.animation_controller.set_state(AnimationState.IDLE)
            self.say("I'm awake!")
        else:
            self.animation_controller.set_state(AnimationState.SLEEP)
            self.say("Zzz... wake me if you need me.")

    def _on_dance(self) -> None:
        self.animation_controller.set_state(AnimationState.DANCE)
        self.say("Let's dance! 💃")

    def _on_change_outfit(self, key: str, label: str) -> None:
        self.animation_controller.set_outfit(key)
        settings.outfit = key
        self.say(f"New outfit: {label}!")

    def _on_show_datetime(self) -> None:
        from datetime import datetime

        now = datetime.now()
        self.say(f"It's {now.strftime('%I:%M %p')} on {now.strftime('%A, %d %B %Y')} 🕐")

    def _on_show_screen_time(self) -> None:
        formatted = self._screen_time_tracker.today_formatted()
        self.say(f"You've been active for {formatted} today 📊", category="Screen Time")

    def _on_show_history(self) -> None:
        dialog = HistoryPanel(memory_db=self._memory_db, parent=self)
        dialog.exec()

    def _on_settings(self) -> None:
        dialog = SettingsDialog(
            ai_manager=self._ai_manager,
            tts_engine=self._tts_engine,
            settings_manager=self._settings_manager,
            on_apply=self._apply_live_settings,
            parent=self,
        )
        dialog.exec()

    def _apply_live_settings(self) -> None:
        """Re-apply settings that can take effect immediately after Save."""
        if not QGuiApplication.platformName().startswith("wayland"):
            self.setWindowOpacity(settings.window.opacity)
        self.animation_controller.apply_speed_settings()
        self._mute_action.setChecked(settings.muted)
        if settings.voice.wake_word_enabled:
            self._wake_word_listener.start()
        else:
            self._wake_word_listener.stop()
        self.say("Settings applied!")

    def _on_toggle_mute(self, checked: bool) -> None:
        settings.muted = checked
        logger.info("Muted set to %s", checked)
        self.say("Muted." if checked else "Sound's back on.")

    def _on_restart(self) -> None:
        logger.info("Restart requested from context menu.")
        self.say("Be right back...")
        QApplication.processEvents()
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def _on_about(self) -> None:
        from config.settings import APP_NAME, APP_VERSION

        self.say(f"{APP_NAME} v{APP_VERSION} — your desktop companion 💜")

    def save_state(self) -> None:
        """Persist window position and settings. Safe to call more than
        once (e.g. from both the context-menu Exit action and the
        application's aboutToQuit signal)."""
        x, y = self.x(), self.y()
        primary_screen = QApplication.primaryScreen()
        if primary_screen:
            geo = primary_screen.availableGeometry()
            if (
                geo.left() - self.width() <= x <= geo.right()
                and geo.top() - self.height() <= y <= geo.bottom()
            ):
                self._settings_manager.save_window_position(x, y)
        else:
            self._settings_manager.save_window_position(x, y)
        self._settings_manager.save()

    def _on_exit(self) -> None:
        logger.info("Exit requested from context menu.")
        self.animation_controller.stop()
        self._reaction_engine.stop()
        self._screen_time_tracker.stop()
        self._wake_word_listener.stop()
        self._plugin_manager.unload_all()
        self.save_state()
        QApplication.instance().quit()

    # ------------------------------------------------------------------
    # Minimize-to-tray behaviour
    # ------------------------------------------------------------------

    def toggle_visibility(self) -> None:
        """Show the pet if hidden, hide it if shown (used by the tray icon)."""
        if self.isVisible():
            self.hide()
            logger.info("PetWindow hidden to tray.")
        else:
            self.show()
            self.raise_()
            logger.info("PetWindow restored from tray.")
        