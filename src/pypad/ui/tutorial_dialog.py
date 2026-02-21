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
        self.body_label.setWordWrap(True)
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
        dark_mode = bool(settings.get("dark_mode", False))
        accent = self._normalize_hex(str(settings.get("accent_color", "#4a90e2")), "#4a90e2")
        theme = str(settings.get("theme", "Default") or "Default")
        use_custom = bool(settings.get("use_custom_colors", False))

        palette_map = {
            "Default": {"window_bg": "#ffffff", "text_color": "#000000", "chrome_bg": "#f0f0f0"},
            "Soft Light": {"window_bg": "#f5f5f7", "text_color": "#222222", "chrome_bg": "#e1e1e6"},
            "High Contrast": {"window_bg": "#000000", "text_color": "#ffffff", "chrome_bg": "#000000"},
            "Solarized Light": {"window_bg": "#fdf6e3", "text_color": "#586e75", "chrome_bg": "#eee8d5"},
            "Ocean Blue": {"window_bg": "#eaf4ff", "text_color": "#10324a", "chrome_bg": "#d6e9fb"},
        }

        if dark_mode:
            bg = "#202124"
            text = "#e8eaed"
            chrome_bg = "#303134"
            border = "#3c4043"
            hover_bg = "#3a3f45"
        else:
            palette = palette_map.get(theme, palette_map["Default"])
            bg = palette["window_bg"]
            text = palette["text_color"]
            chrome_bg = palette["chrome_bg"]
            border = "#c0c0c0"
            hover_bg = "#e9eef7"

        if use_custom:
            custom_editor_bg = self._normalize_hex(str(settings.get("custom_editor_bg", "")), "")
            custom_editor_fg = self._normalize_hex(str(settings.get("custom_editor_fg", "")), "")
            custom_chrome_bg = self._normalize_hex(str(settings.get("custom_chrome_bg", "")), "")
            if custom_editor_bg:
                bg = custom_editor_bg
            if custom_editor_fg:
                text = custom_editor_fg
            if custom_chrome_bg:
                chrome_bg = custom_chrome_bg

        self.setStyleSheet(
            f"""
            QDialog {{
                background: {bg};
                color: {text};
            }}
            QLabel {{
                color: {text};
                background: transparent;
            }}
            QPushButton {{
                background: {chrome_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                border: 1px solid {accent};
            }}
            QPushButton:pressed {{
                background: {accent};
                color: #ffffff;
                border: 1px solid {accent};
            }}
            QPushButton:disabled {{
                opacity: 0.55;
            }}
            """
        )

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
