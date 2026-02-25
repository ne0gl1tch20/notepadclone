from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsOpacityEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from .theme_tokens import build_dialog_theme_qss_from_tokens, build_tokens_from_settings, build_tutorial_dialog_qss


class InteractiveTutorialDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome Tutorial")
        self.resize(700, 420)
        self._steps = [
            ("Welcome", "Welcome to Pypad!\n\nThis quick walkthrough highlights the key features."),
            ("Tabs", "Use tabs for multiple notes.\nPin or favorite important files.\nRight-click a tab for advanced actions."),
            ("Search", "Press Ctrl+F to show Find panel.\nUse Replace and Replace in Files for project-wide edits."),
            ("Markdown + Code", "Toggle Markdown toolbar when needed.\nUse syntax mode and formatting tools from toolbar and menus."),
            ("Recovery + Security", "Autosave protects unsaved notes.\nEnable lock screen protection with Password/PIN in Settings."),
            ("Done", "You are all set.\nYou can reopen this from Help > First Time Tutorial anytime."),
        ]
        self._index = 0

        layout = QVBoxLayout(self)
        self.title_label = QLabel("", self)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.body_label = QLabel("", self)
        self.body_label.setObjectName("tutorialBodyCard")
        self.body_label.setWordWrap(True)
        self.body_label.setContentsMargins(12, 10, 12, 10)
        self.body_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.body_label, 1)

        self.opacity = QGraphicsOpacityEffect(self)
        self.body_label.setGraphicsEffect(self.opacity)
        self.anim = QPropertyAnimation(self.opacity, b"opacity", self)
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        nav = QDialogButtonBox(self)
        self.prev_btn = QPushButton("Previous", self)
        self.next_btn = QPushButton("Next", self)
        self.close_btn = QPushButton("Finish", self)
        nav.addButton(self.prev_btn, QDialogButtonBox.ButtonRole.ActionRole)
        nav.addButton(self.next_btn, QDialogButtonBox.ButtonRole.ActionRole)
        nav.addButton(self.close_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        layout.addWidget(nav)

        self.prev_btn.clicked.connect(self._prev_step)
        self.next_btn.clicked.connect(self._next_step)
        self.close_btn.clicked.connect(self.accept)

        self._apply_theme_from_parent()
        self._render(animate=False)

    @staticmethod
    def _normalize_hex(value: str, fallback: str) -> str:
        text = (value or "").strip()
        if not text:
            return fallback
        if not text.startswith("#"):
            text = f"#{text}"
        if len(text) not in (4, 7):
            return fallback
        if not all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
            return fallback
        return text

    def _apply_theme_from_parent(self) -> None:
        parent = self.parent()
        settings = getattr(parent, "settings", {}) if parent is not None else {}
        tokens = build_tokens_from_settings(settings if isinstance(settings, dict) else {})
        self.setStyleSheet(build_dialog_theme_qss_from_tokens(tokens) + "\n" + build_tutorial_dialog_qss(tokens))

    def _animate_swap(self, callback) -> None:
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)

        def after_fade_out() -> None:
            callback()
            self.anim.finished.disconnect(after_fade_out)
            self.anim.setStartValue(0.0)
            self.anim.setEndValue(1.0)
            self.anim.start()

        self.anim.finished.connect(after_fade_out)
        self.anim.start()

    def _render(self, *, animate: bool = True) -> None:
        def apply() -> None:
            title, body = self._steps[self._index]
            self.title_label.setText(title)
            self.body_label.setText(body)
            self.prev_btn.setEnabled(self._index > 0)
            self.next_btn.setEnabled(self._index < len(self._steps) - 1)

        if animate:
            self._animate_swap(apply)
        else:
            apply()
            self.opacity.setOpacity(1.0)

    def _next_step(self) -> None:
        if self._index >= len(self._steps) - 1:
            return
        self._index += 1
        self._render(animate=True)

    def _prev_step(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._render(animate=True)
