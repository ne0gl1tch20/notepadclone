from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QProgressDialog, QWidget
from pypad.ui.theme.theme_tokens import build_dialog_theme_qss_from_tokens, build_tokens_from_settings


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
    tokens = build_tokens_from_settings(settings if isinstance(settings, dict) else {})
    return build_dialog_theme_qss_from_tokens(tokens)


def apply_dialog_theme_from_window(window: QWidget | None, dialog: QDialog) -> None:
    settings = getattr(window, "settings", {}) if window is not None else {}
    if not isinstance(settings, dict):
        settings = {}
    dialog.setStyleSheet(build_dialog_theme_qss(settings))


def create_themed_message_box(window: QWidget | None, *, title: str, icon: QMessageBox.Icon, text: str) -> QMessageBox:
    box = QMessageBox(window)
    box.setWindowTitle(title)
    box.setIcon(icon)
    box.setText(text)
    apply_dialog_theme_from_window(window, box)
    return box


def themed_message_box_exec(
    window: QWidget | None,
    *,
    title: str,
    icon: QMessageBox.Icon,
    text: str,
    informative: str = "",
    detailed: str = "",
    buttons: QMessageBox.StandardButton | QMessageBox.StandardButtons = QMessageBox.StandardButton.Ok,
) -> int:
    box = create_themed_message_box(window, title=title, icon=icon, text=text)
    if informative:
        box.setInformativeText(informative)
    if detailed:
        box.setDetailedText(detailed)
    box.setStandardButtons(buttons)
    return box.exec()


def create_themed_progress_dialog(window: QWidget | None, *, title: str) -> QProgressDialog:
    dlg = QProgressDialog(window)
    dlg.setWindowTitle(title)
    apply_dialog_theme_from_window(window, dlg)
    return dlg


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

