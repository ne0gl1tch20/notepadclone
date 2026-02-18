from __future__ import annotations
import getpass
import base64
import hashlib
import json
import os
import random
import sys
import time
import webbrowser
from typing import TYPE_CHECKING, Any
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPdfWriter,
    QPixmap,
    QTextCursor,
    QTextCharFormat,
    QTextDocument,
) 
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QStyleFactory,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter

from ..debug_logs_dialog import DebugLogsDialog
from ..detachable_tab_bar import DetachableTabBar
from ..editor_tab import EditorTab
from ..ai_controller import AIController
from ..asset_paths import resolve_asset_path
from ..autosave import AutoSaveRecoveryDialog, AutoSaveStore
from ..reminders import ReminderStore, RemindersDialog
from ..security_controller import SecurityController
from ..syntax_highlighter import CodeSyntaxHighlighter
from ..updater_controller import UpdaterController
from ..version_history import VersionHistoryDialog
from ..workspace_controller import WorkspaceController



class FileOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    # ---------- File operations ----------
    def maybe_save(self) -> bool:
        tab = self.active_tab()
        if tab is None:
            return True
        return self.maybe_save_tab(tab)

    def file_new(self) -> None:
        self.add_new_tab(make_current=True)
        self.update_window_title()
        self.log_event("Info", "Created new file tab")

    def file_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open",
            "",
            "All Supported (*.md *.markdown *.mdown *.txt *.encnote);;Markdown Documents (*.md *.markdown *.mdown);;Text Documents (*.txt);;Encrypted Notes (*.encnote);;All Files (*.*)",
        )
        if not path:
            return
        self.log_event("Info", f'Open requested: "{path}"')
        if not self._open_file_path(path):
            return
        self.log_event("Info", f'Open succeeded: "{path}"')

    def _prompt_password(self, title: str, label: str) -> str | None:
        return self.security_controller.prompt_password(title, label)

    def _load_text_from_path(self, path: str, encoding: str = "utf-8") -> tuple[str, bool, str | None]:
        return self.security_controller.load_text_from_path(path, encoding=encoding)

    def _open_file_path(self, path: str) -> bool:
        encoding = self._encoding_for_path(path)
        try:
            text, encrypted, password = self._load_text_from_path(path, encoding=encoding)
        except Exception as e:  # noqa: BLE001
            self.log_event("Error", f'Open failed: "{path}" - {e}')
            QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
            return False

        active = self.active_tab()
        if active and not active.current_file and not active.text_edit.is_modified() and not active.text_edit.get_text().strip():
            tab = active
            tab.text_edit.set_text(text)
        else:
            tab = self.add_new_tab(text=text, file_path=path, make_current=True)

        tab.current_file = path
        tab.encoding = encoding if not encrypted else "utf-8"
        eol_map = self.settings.get("file_eol_modes", {})
        if isinstance(eol_map, dict) and path in eol_map:
            tab.eol_mode = str(eol_map.get(path) or self._detect_eol_mode(text))
        else:
            tab.eol_mode = self._detect_eol_mode(text)
        try:
            threshold_kb = int(self.settings.get("large_file_threshold_kb", 2048))
            size_kb = int(Path(path).stat().st_size / 1024)
            tab.large_file = size_kb >= threshold_kb
        except Exception:
            tab.large_file = False
        tab.zoom_steps = 0
        tab.encryption_enabled = encrypted
        tab.encryption_password = password
        tab.markdown_mode_enabled = self._is_markdown_path(path) and not tab.large_file
        tab.markdown_preview.setVisible(tab.markdown_mode_enabled)
        if tab.markdown_mode_enabled:
            tab.markdown_preview.setMarkdown(tab.text_edit.get_text())
        if hasattr(self, "_notify_large_file_mode"):
            self._notify_large_file_mode(tab)
        self._apply_syntax_highlighting(tab)
        self._seed_version_history(tab, label="Opened")
        tab.pinned = path in set(self.settings.get("pinned_files", []))
        self._apply_file_metadata_to_tab(tab)
        if tab.pinned:
            self._sort_tabs_by_pinned()
        tab.text_edit.set_modified(False)
        self._refresh_tab_title(tab)
        self.update_window_title()
        self._add_recent_file(path)
        if hasattr(self, "_watch_file"):
            self._watch_file(path)
        return True

    def file_save(self) -> bool:
        tab = self.active_tab()
        if tab is None:
            return False
        return self.file_save_tab(tab)

    def file_save_tab(self, tab: EditorTab) -> bool:
        if tab.current_file is None:
            return self.file_save_as_tab(tab)
        if tab.read_only:
            ret = QMessageBox.question(
                self,
                "Read-Only File",
                "This file is read-only. Disable read-only and save?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return False
            if not self._set_file_read_only(tab.current_file, False):
                QMessageBox.warning(self, "Read-Only", "Could not update read-only attribute.")
                return False
            tab.read_only = False
            tab.text_edit.set_read_only(False)
        payload = self.security_controller.build_payload_for_save(tab)
        if payload is None:
            return False
        if not tab.encryption_enabled:
            payload = self._normalize_eol(payload, tab.eol_mode or "LF")
        try:
            encoding = tab.encoding or self._encoding_for_path(tab.current_file)
            if tab.encryption_enabled:
                encoding = "utf-8"
            with open(tab.current_file, "w", encoding=encoding, errors="replace") as f:
                f.write(payload)
        except Exception as e:  # noqa: BLE001
            self.log_event("Error", f'Save failed: "{tab.current_file}" - {e}')
            QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")
            return False
        tab.text_edit.set_modified(False)
        self._refresh_tab_title(tab)
        self.update_window_title()
        tab.version_history.add_snapshot(tab.text_edit.get_text(), label="Saved")
        tab.last_snapshot_time = time.monotonic()
        if tab.current_file:
            self._persist_encoding_for_path(tab.current_file, tab.encoding or "utf-8")
            self._persist_eol_for_path(tab.current_file, tab.eol_mode or "LF")
        self._persist_file_metadata_for_tab(tab)
        self._add_recent_file(tab.current_file)
        self._clear_tab_autosave(tab)
        self.log_event("Info", f'Save succeeded: "{tab.current_file}"')
        return True

    def file_save_as(self) -> bool:
        tab = self.active_tab()
        if tab is None:
            return False
        return self.file_save_as_tab(tab)

    def file_save_as_tab(self, tab: EditorTab) -> bool:
        was_unsaved = tab.current_file is None
        previous_favorite = tab.favorite
        previous_tags = list(tab.tags)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save As",
            tab.current_file or "",
            "Markdown Documents (*.md *.markdown *.mdown);;Text Documents (*.txt);;Encrypted Notes (*.encnote);;All Files (*.*)",
        )
        if not path:
            return False
        self.log_event("Info", f'Save As selected: "{path}"')

        tab.current_file = path
        tab.encoding = tab.encoding or self._encoding_for_path(path)
        if Path(path).suffix.lower() == ".encnote":
            tab.encryption_enabled = True
        tab.markdown_mode_enabled = self._is_markdown_path(path)
        tab.markdown_preview.setVisible(tab.markdown_mode_enabled)
        if tab.markdown_mode_enabled:
            tab.markdown_preview.setMarkdown(tab.text_edit.get_text())
        self._apply_syntax_highlighting(tab)
        if path in set(self.settings.get("pinned_files", [])):
            tab.pinned = True
        self._apply_file_metadata_to_tab(tab)
        if was_unsaved and previous_favorite:
            tab.favorite = True
        if was_unsaved and previous_tags:
            tab.tags = previous_tags
        self._refresh_tab_title(tab)
        if tab is self.active_tab():
            self.md_toggle_preview_action.blockSignals(True)
            self.md_toggle_preview_action.setChecked(tab.markdown_mode_enabled)
            self.md_toggle_preview_action.blockSignals(False)
        return self.file_save_tab(tab)

    def file_print(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Document")
        if dialog.exec() != QDialog.Accepted:
            return
        doc = QTextDocument()
        text = tab.text_edit.get_text()
        if tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file):
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)
        try:
            doc.print_(printer)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Print Failed", f"Could not print document:\n{e}")
            return
        self.show_status_message("Print job sent to printer", 3000)

    def file_print_preview(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintPreviewDialog(printer, self)
        dialog.setWindowTitle("Print Preview")

        def render_preview(preview_printer: QPrinter) -> None:
            doc = QTextDocument()
            text = tab.text_edit.get_text()
            if tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file):
                doc.setMarkdown(text)
            else:
                doc.setPlainText(text)
            try:
                doc.print_(preview_printer)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Print Preview Failed", f"Could not render preview:\n{e}")

        dialog.paintRequested.connect(render_preview)
        dialog.exec()

    def _encoding_for_path(self, path: str) -> str:
        enc_map = self.settings.get("file_encodings", {})
        if isinstance(enc_map, dict):
            return str(enc_map.get(path, "utf-8") or "utf-8")
        return "utf-8"

    def _persist_encoding_for_path(self, path: str, encoding: str) -> None:
        enc_map = self.settings.get("file_encodings", {})
        if not isinstance(enc_map, dict):
            enc_map = {}
        enc_map[path] = encoding
        self.settings["file_encodings"] = enc_map

    def _persist_eol_for_path(self, path: str, mode: str) -> None:
        eol_map = self.settings.get("file_eol_modes", {})
        if not isinstance(eol_map, dict):
            eol_map = {}
        eol_map[path] = mode
        self.settings["file_eol_modes"] = eol_map

    @staticmethod
    def _detect_eol_mode(text: str) -> str:
        if "\r\n" in text:
            return "CRLF"
        if "\n" in text:
            return "LF"
        return "LF"

    @staticmethod
    def _normalize_eol(text: str, mode: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if mode == "CRLF":
            return normalized.replace("\n", "\r\n")
        return normalized

    def set_tab_encoding(self, encoding: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.encoding = encoding
        if tab.current_file:
            self._persist_encoding_for_path(tab.current_file, encoding)
        self.show_status_message(f"Encoding set to {encoding}", 3000)

    def set_tab_eol_mode(self, mode: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.eol_mode = mode
        if not tab.read_only:
            text = tab.text_edit.get_text()
            tab.text_edit.set_text(self._normalize_eol(text, mode))
            tab.text_edit.set_modified(True)
        if tab.current_file:
            self._persist_eol_for_path(tab.current_file, mode)
        self.update_status_bar()
        self.show_status_message(f"EOL mode set to {mode}", 3000)

