"""
ui/settings_dialog.py
------------------------
The full Settings panel: theme, voice selection, AI provider/model,
opacity, animation speed, volume, language, and startup-with-OS —
everything listed under "Settings" in the spec.

Changes are applied live where possible (opacity, animation speed,
volume/mute) and persisted via `SettingsManager` on "Save".
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ai.ai_manager import AIManager
from config.settings import settings
from config.settings_manager import SettingsManager
from system import startup_manager
from utils.logger import get_logger
from voice.tts_engine import TTSEngine

logger = get_logger(__name__)

_LANGUAGES = [("en", "English"), ("gu", "ગુજરાતી (Gujarati)"), ("hi", "हिन्दी (Hindi)")]
_THEMES = [("dark", "Dark"), ("light", "Light")]


class SettingsDialog(QDialog):
    """Tabbed settings window: General / Voice & AI / Startup."""

    def __init__(
        self,
        ai_manager: AIManager,
        tts_engine: TTSEngine,
        settings_manager: SettingsManager,
        on_apply: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Asha — Settings")
        self.setMinimumWidth(360)
        self._ai_manager = ai_manager
        self._tts_engine = tts_engine
        self._settings_manager = settings_manager
        self._on_apply = on_apply

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_voice_ai_tab(), "Voice & AI")
        tabs.addTab(self._build_startup_tab(), "Startup")

        button_row = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._on_save)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch(1)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._theme_combo = QComboBox()
        for key, label in _THEMES:
            self._theme_combo.addItem(label, userData=key)
        self._theme_combo.setCurrentIndex(
            [k for k, _ in _THEMES].index(settings.theme) if settings.theme in dict(_THEMES) else 0
        )
        form.addRow("Theme:", self._theme_combo)

        self._language_combo = QComboBox()
        for key, label in _LANGUAGES:
            self._language_combo.addItem(label, userData=key)
        idx = [k for k, _ in _LANGUAGES].index(settings.language) if settings.language in dict(_LANGUAGES) else 0
        self._language_combo.setCurrentIndex(idx)
        form.addRow("Language:", self._language_combo)

        self._opacity_slider = self._make_slider(0, 100, int(settings.window.opacity * 100))
        form.addRow("Opacity:", self._opacity_slider)

        self._animation_speed_slider = self._make_slider(
            25, 200, int(settings.animation.animation_speed_multiplier * 100)
        )
        form.addRow("Animation speed:", self._animation_speed_slider)

        self._volume_slider = self._make_slider(0, 100, int(settings.volume * 100))
        form.addRow("Volume:", self._volume_slider)

        self._mute_checkbox = QCheckBox("Mute")
        self._mute_checkbox.setChecked(settings.muted)
        form.addRow("", self._mute_checkbox)

        return widget

    def _build_voice_ai_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self._ai_provider_combo = QComboBox()
        self._ai_provider_combo.addItem("Simple (offline, no setup)", userData="simple")
        self._ai_provider_combo.addItem("Ollama (local server)", userData="ollama")
        self._ai_provider_combo.addItem("OpenAI (API key)", userData="openai")
        provider_keys = ["simple", "ollama", "openai"]
        self._ai_provider_combo.setCurrentIndex(
            provider_keys.index(settings.ai.provider) if settings.ai.provider in provider_keys else 0
        )
        form.addRow("AI provider:", self._ai_provider_combo)

        status = self._ai_manager.provider_status()
        status_text = ", ".join(f"{name}: {'✅' if ok else '❌'}" for name, ok in status.items())
        form.addRow("Status:", QLabel(status_text))

        self._voice_combo = QComboBox()
        voices = self._tts_engine.list_voices()
        if voices:
            for voice_id, voice_name in voices:
                self._voice_combo.addItem(voice_name, userData=voice_id)
        else:
            self._voice_combo.addItem("Default (TTS unavailable)", userData="")
            self._voice_combo.setEnabled(False)
        form.addRow("TTS voice:", self._voice_combo)

        self._stt_checkbox = QCheckBox("Enable speech-to-text")
        self._stt_checkbox.setChecked(settings.voice.stt_enabled)
        form.addRow("", self._stt_checkbox)

        self._wake_word_checkbox = QCheckBox(f'Enable wake word ("{settings.voice.wake_word}")')
        self._wake_word_checkbox.setChecked(settings.voice.wake_word_enabled)
        form.addRow("", self._wake_word_checkbox)

        return widget

    def _build_startup_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._startup_checkbox = QCheckBox("Start Asha automatically when I log in")
        self._startup_checkbox.setChecked(startup_manager.is_startup_enabled())
        layout.addWidget(self._startup_checkbox)
        layout.addStretch(1)

        return widget

    @staticmethod
    def _make_slider(minimum: int, maximum: int, value: int) -> QSlider:
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)
        return slider

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        settings.theme = self._theme_combo.currentData()
        settings.language = self._language_combo.currentData()
        settings.window.opacity = self._opacity_slider.value() / 100.0
        settings.animation.animation_speed_multiplier = self._animation_speed_slider.value() / 100.0
        settings.volume = self._volume_slider.value() / 100.0
        settings.muted = self._mute_checkbox.isChecked()

        settings.ai.provider = self._ai_provider_combo.currentData()
        settings.voice.tts_voice_id = self._voice_combo.currentData() or ""
        settings.voice.stt_enabled = self._stt_checkbox.isChecked()
        settings.voice.wake_word_enabled = self._wake_word_checkbox.isChecked()

        wants_startup = self._startup_checkbox.isChecked()
        if wants_startup != startup_manager.is_startup_enabled():
            ok = startup_manager.enable_startup() if wants_startup else startup_manager.disable_startup()
            settings.start_with_os = ok and wants_startup

        self._settings_manager.save()
        logger.info("Settings saved from dialog.")

        if self._on_apply:
            self._on_apply()

        self.accept()
