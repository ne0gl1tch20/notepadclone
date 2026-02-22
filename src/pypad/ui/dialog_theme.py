from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QDialog, QFileDialog, QWidget


def _normalize_hex(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) not in (4, 7):
        return fallback
    if not all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return fallback
    return text


def build_dialog_theme_qss(settings: dict[str, Any]) -> str:
    dark = bool(settings.get("dark_mode", False))
    accent = _normalize_hex(settings.get("accent_color", "#4a90e2"), "#4a90e2")
    window_bg = "#202124" if dark else "#f5f7fb"
    panel_bg = "#25272b" if dark else "#ffffff"
    text_fg = "#e8eaed" if dark else "#111111"
    muted = "#9aa0a6" if dark else "#5f6368"
    border = "#3c4043" if dark else "#c7ccd4"
    input_bg = "#1f2023" if dark else "#ffffff"
    button_bg = "#303134" if dark else "#eef2f8"
    return f"""
        QDialog {{
            background: {window_bg};
            color: {text_fg};
        }}
        QLabel, QCheckBox, QRadioButton, QGroupBox {{
            color: {text_fg};
        }}
        QGroupBox {{
            border: 1px solid {border};
            margin-top: 10px;
            padding-top: 6px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget, QTreeWidget {{
            background: {input_bg};
            color: {text_fg};
            border: 1px solid {border};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QComboBox QAbstractItemView {{
            background: {panel_bg};
            color: {text_fg};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QPushButton {{
            background: {button_bg};
            color: {text_fg};
            border: 1px solid {border};
            padding: 4px 10px;
        }}
        QPushButton:hover {{
            background: {accent};
            color: #ffffff;
            border: 1px solid {accent};
        }}
        QPushButton:disabled {{
            color: {muted};
        }}
    """


def apply_dialog_theme_from_window(window: QWidget | None, dialog: QDialog) -> None:
    settings = getattr(window, "settings", {}) if window is not None else {}
    if not isinstance(settings, dict):
        settings = {}
    dialog.setStyleSheet(build_dialog_theme_qss(settings))


class _DialogThemeEventFilter(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Show and isinstance(obj, QDialog):
            if obj.property("pypad_dialog_theme_skip"):
                return False
            # Find closest top-level window carrying PyPad settings.
            w: QWidget | None = obj.parentWidget()
            while w is not None and not hasattr(w, "settings"):
                w = w.parentWidget()
            try:
                apply_dialog_theme_from_window(w, obj)
            except Exception:
                return False
        return False


_dialog_theme_filter: _DialogThemeEventFilter | None = None


def ensure_dialog_theme_filter_installed() -> None:
    from PySide6.QtWidgets import QApplication

    global _dialog_theme_filter
    app = QApplication.instance()
    if app is None:
        return
    if _dialog_theme_filter is None:
        _dialog_theme_filter = _DialogThemeEventFilter(app)
        app.installEventFilter(_dialog_theme_filter)


def themed_file_dialog_get_save_file_name(
    parent: QWidget,
    title: str,
    directory: str = "",
    filter_text: str = "",
) -> tuple[str, str]:
    dlg = QFileDialog(parent, title, directory, filter_text)
    dlg.setAcceptMode(QFileDialog.AcceptSave)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    apply_dialog_theme_from_window(parent, dlg)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return "", ""
    files = dlg.selectedFiles()
    return (files[0] if files else "", dlg.selectedNameFilter() or "")


def themed_file_dialog_get_open_file_name(
    parent: QWidget,
    title: str,
    directory: str = "",
    filter_text: str = "",
) -> tuple[str, str]:
    dlg = QFileDialog(parent, title, directory, filter_text)
    dlg.setAcceptMode(QFileDialog.AcceptOpen)
    dlg.setFileMode(QFileDialog.FileMode.ExistingFile)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    apply_dialog_theme_from_window(parent, dlg)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return "", ""
    files = dlg.selectedFiles()
    return (files[0] if files else "", dlg.selectedNameFilter() or "")


def themed_file_dialog_get_existing_directory(parent: QWidget, title: str, directory: str = "") -> str:
    dlg = QFileDialog(parent, title, directory)
    dlg.setFileMode(QFileDialog.FileMode.Directory)
    dlg.setOption(QFileDialog.Option.ShowDirsOnly, True)
    dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    apply_dialog_theme_from_window(parent, dlg)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return ""
    files = dlg.selectedFiles()
    return files[0] if files else ""
