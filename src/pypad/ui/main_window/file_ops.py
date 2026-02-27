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

from pypad.ui.debug.debug_logs_dialog import DebugLogsDialog
from pypad.ui.editor.detachable_tab_bar import DetachableTabBar
from pypad.ui.editor.editor_tab import EditorTab
from pypad.ui.ai.ai_controller import AIController
from pypad.ui.theme.asset_paths import resolve_asset_path
from pypad.ui.system.autosave import AutoSaveRecoveryDialog, AutoSaveStore
from pypad.ui.system.reminders import ReminderStore, RemindersDialog
from pypad.ui.security.security_controller import SecurityController
from pypad.ui.editor.syntax_highlighter import CodeSyntaxHighlighter
from pypad.ui.system.updater_controller import UpdaterController
from pypad.ui.system.version_history import VersionHistoryDialog
from pypad.ui.workspace.workspace_controller import WorkspaceController
from pypad.ui.document.document_authoring import PageLayoutConfig, build_layout_html
from pypad.ui.workspace.project_workflow import read_text_with_large_file_preview
from pypad.ui.document.document_fidelity import DocumentFidelityError, export_document_text, import_document_text
from pypad.ui.security.note_crypto import HEADER as ENCRYPTED_NOTE_HEADER
from pypad.logging_utils import get_logger
from .notepadpp_pref_runtime import apply_npp_print_preferences_to_page_layout

_LOGGER = get_logger(__name__)


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
            (
                "All Supported (*.md *.markdown *.mdown *.txt *.html *.htm *.docx *.odt *.pdf *.encnote);;"
                "Markdown Documents (*.md *.markdown *.mdown);;"
                "Text Documents (*.txt);;"
                "Web Documents (*.html *.htm);;"
                "Word Documents (*.docx);;"
                "OpenDocument Text (*.odt);;"
                "PDF Documents (*.pdf);;"
                "Encrypted Notes (*.encnote);;"
                "All Files (*.*)"
            ),
        )
        if not path:
            return
        _LOGGER.debug("file_open dialog selected path=%s", path)
        self.log_event("Info", f'Open requested: "{path}"')
        if not self._open_file_path(path):
            return
        self.log_event("Info", f'Open succeeded: "{path}"')

    def _prompt_password(self, title: str, label: str) -> str | None:
        return self.security_controller.prompt_password(title, label)

    def _load_text_from_path(self, path: str, encoding: str = "utf-8") -> tuple[str, bool, str | None]:
        return self.security_controller.load_text_from_path(path, encoding=encoding)

    def _open_file_path(self, path: str) -> bool:
        suffix = Path(path).suffix.lower()
        structured_import = suffix in {".docx", ".odt", ".html", ".htm", ".pdf"}
        encoding = self._encoding_for_path(path)
        preview = None
        fast_open_enabled = bool(self.settings.get("large_file_fast_open_enabled", True))
        _LOGGER.debug(
            "_open_file_path start path=%s suffix=%s structured=%s encoding=%s fast_open=%s",
            path,
            suffix,
            structured_import,
            encoding,
            fast_open_enabled,
        )
        try:
            size_kb = int(Path(path).stat().st_size / 1024)
        except Exception:
            size_kb = 0
        maybe_encrypted_payload = False
        if structured_import:
            maybe_encrypted_payload = False
        elif Path(path).suffix.lower() != ".encnote":
            try:
                with open(path, "r", encoding=encoding, errors="replace") as _peek:
                    maybe_encrypted_payload = _peek.read(32).startswith(ENCRYPTED_NOTE_HEADER + "\n")
            except Exception:
                maybe_encrypted_payload = False
        if fast_open_enabled and not structured_import and Path(path).suffix.lower() != ".encnote" and not maybe_encrypted_payload:
            try:
                preview = read_text_with_large_file_preview(
                    path,
                    encoding=encoding,
                    fast_threshold_kb=int(self.settings.get("large_file_fast_open_kb", 8192)),
                    head_lines=int(self.settings.get("large_file_preview_head_lines", 2000)),
                    tail_lines=int(self.settings.get("large_file_preview_tail_lines", 250)),
                )
            except Exception:
                preview = None
                _LOGGER.exception("_open_file_path preview read failed path=%s", path)
        _LOGGER.debug(
            "_open_file_path pre-read path=%s size_kb=%s maybe_encrypted=%s preview_partial=%s",
            path,
            size_kb,
            maybe_encrypted_payload,
            bool(preview is not None and getattr(preview, "is_partial", False)),
        )
        imported_markdown_mode = False
        try:
            if structured_import:
                text, imported_markdown_mode = import_document_text(path, encoding=encoding)
                encrypted = False
                password = None
            elif preview is not None and preview.is_partial:
                text = preview.text
                encrypted = False
                password = None
            else:
                text, encrypted, password = self._load_text_from_path(path, encoding=encoding)
        except DocumentFidelityError as e:
            _LOGGER.debug("_open_file_path document fidelity error path=%s error=%s", path, e)
            self.log_event("Error", f'Open failed: "{path}" - {e}')
            QMessageBox.critical(self, "Import Failed", f"Could not import document:\n{e}")
            return False
        except Exception as e:  # noqa: BLE001
            _LOGGER.exception("_open_file_path exception path=%s", path)
            self.log_event("Error", f'Open failed: "{path}" - {e}')
            QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")
            return False

        active = self.active_tab()
        if active and not active.current_file and not active.text_edit.is_modified() and not active.text_edit.get_text().strip():
            tab = active
            tab.text_edit.set_text(text)
        else:
            tab = self.add_new_tab(text=text, file_path=path, make_current=True)
        if hasattr(self, "_ensure_tab_autosave_meta"):
            if suffix == ".pdf" and not bool(self.settings.get("autosave_include_pdf", False)):
                pass
            else:
                self._ensure_tab_autosave_meta(tab)

        tab.current_file = path
        tab.encoding = encoding if not encrypted else "utf-8"
        eol_map = self.settings.get("file_eol_modes", {})
        if isinstance(eol_map, dict) and path in eol_map:
            tab.eol_mode = str(eol_map.get(path) or self._detect_eol_mode(text))
        else:
            tab.eol_mode = self._detect_eol_mode(text)
        try:
            threshold_kb = int(self.settings.get("large_file_threshold_kb", 2048))
            tab.large_file = size_kb >= threshold_kb
        except Exception:
            tab.large_file = False
        tab.zoom_steps = 0
        tab.encryption_enabled = encrypted
        tab.encryption_password = password
        tab.partial_large_preview = bool(preview is not None and preview.is_partial)
        if preview is not None:
            tab.large_file_total_lines = int(preview.total_lines)
            tab.large_file_total_chars = int(preview.total_chars)
        else:
            tab.large_file_total_lines = max(1, text.count("\n") + 1)
            tab.large_file_total_chars = len(text)
        tab.markdown_mode_enabled = (
            imported_markdown_mode if structured_import else self._is_markdown_path(path)
        ) and not tab.large_file
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
        if tab.partial_large_preview:
            tab.read_only = True
            tab.text_edit.set_read_only(True)
            self.show_status_message(
                "Large file preview mode loaded (partial). Use Tools > Load Full Large File to edit.",
                7000,
            )
        elif structured_import and suffix == ".pdf":
            self.show_status_message(
                "PDF imported as extracted text. Save to .md/.txt/.docx/.odt to keep edits.",
                7000,
            )
        _LOGGER.debug(
            "_open_file_path complete path=%s tab_large=%s partial_preview=%s markdown_mode=%s encrypted=%s",
            path,
            bool(getattr(tab, "large_file", False)),
            bool(getattr(tab, "partial_large_preview", False)),
            bool(getattr(tab, "markdown_mode_enabled", False)),
            bool(getattr(tab, "encryption_enabled", False)),
        )
        return True

    def file_save(self) -> bool:
        tab = self.active_tab()
        if tab is None:
            return False
        return self.file_save_tab(tab)

    def file_save_tab(self, tab: EditorTab) -> bool:
        if getattr(tab, "partial_large_preview", False):
            QMessageBox.information(
                self,
                "Large File Preview",
                "This tab is in partial large-file preview mode.\nLoad full file first before saving.",
            )
            return False
        if tab.current_file is None:
            return self.file_save_as_tab(tab)
        suffix = Path(tab.current_file).suffix.lower()
        structured_export = suffix in {".docx", ".odt", ".html", ".htm"}
        _LOGGER.debug(
            "file_save_tab start path=%s suffix=%s structured=%s encrypted=%s modified=%s",
            tab.current_file,
            suffix,
            structured_export,
            bool(getattr(tab, "encryption_enabled", False)),
            bool(tab.text_edit.is_modified()),
        )
        payload = self.security_controller.build_payload_for_save(tab)
        if payload is None:
            _LOGGER.debug("file_save_tab aborted by security_controller path=%s", tab.current_file)
            return False
        if hasattr(self, "_emit_plugin_event"):
            save_mode = "export" if structured_export else "text"
            self._emit_plugin_event("before_save", tab=tab, save_mode=save_mode)
            if structured_export:
                self._emit_plugin_event("before_save_export", tab=tab, export_path=tab.current_file, export_format=suffix)
            else:
                self._emit_plugin_event("before_save_text", tab=tab, save_path=tab.current_file, save_format=suffix)
        if not tab.encryption_enabled and not structured_export:
            payload = self._normalize_eol(payload, tab.eol_mode or "LF")
        try:
            if structured_export and not tab.encryption_enabled:
                export_document_text(
                    tab.current_file,
                    tab.text_edit.get_text(),
                    markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
                )
            else:
                encoding = tab.encoding or self._encoding_for_path(tab.current_file)
                if tab.encryption_enabled:
                    encoding = "utf-8"
                with open(tab.current_file, "w", encoding=encoding, errors="replace") as f:
                    f.write(payload)
        except DocumentFidelityError as e:
            _LOGGER.debug("file_save_tab document fidelity error path=%s error=%s", tab.current_file, e)
            self.log_event("Error", f'Save failed: "{tab.current_file}" - {e}')
            QMessageBox.critical(self, "Save Failed", f"Could not export this format:\n{e}")
            return False
        except Exception as e:  # noqa: BLE001
            _LOGGER.exception("file_save_tab exception path=%s", tab.current_file)
            self.log_event("Error", f'Save failed: "{tab.current_file}" - {e}')
            QMessageBox.critical(self, "Error", f"Could not save file:\n{e}")
            return False
        tab.text_edit.set_modified(False)
        self._refresh_tab_title(tab)
        self.update_window_title()
        tab.version_history.add_snapshot(tab.text_edit.get_text(), label="Saved")
        tab.last_snapshot_time = time.monotonic()
        if hasattr(self, "_persist_tab_local_history"):
            self._persist_tab_local_history(tab)
        if tab.current_file:
            self._persist_encoding_for_path(tab.current_file, tab.encoding or "utf-8")
            self._persist_eol_for_path(tab.current_file, tab.eol_mode or "LF")
        self._persist_file_metadata_for_tab(tab)
        _LOGGER.debug("file_save_tab complete path=%s bytes=%d", tab.current_file, len(payload))
        self._add_recent_file(tab.current_file)
        self._clear_tab_autosave(tab)
        self.log_event("Info", f'Save succeeded: "{tab.current_file}"')
        if hasattr(self, "_emit_plugin_event"):
            save_mode = "export" if structured_export else "text"
            self._emit_plugin_event("after_save", tab=tab, save_mode=save_mode)
            if structured_export:
                self._emit_plugin_event("after_save_export", tab=tab, export_path=tab.current_file, export_format=suffix)
            else:
                self._emit_plugin_event("after_save_text", tab=tab, save_path=tab.current_file, save_format=suffix)
            self._emit_plugin_event("save", tab=tab, save_mode=save_mode)
        return True

    def load_full_large_file_current_tab(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        if not getattr(tab, "partial_large_preview", False):
            self.show_status_message("Current tab is already fully loaded.", 2200)
            return
        try:
            encoding = tab.encoding or self._encoding_for_path(tab.current_file)
            text, encrypted, password = self._load_text_from_path(tab.current_file, encoding=encoding)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load Full Large File", f"Could not load file:\n{exc}")
            return
        tab.text_edit.set_text(text)
        tab.partial_large_preview = False
        tab.large_file_total_lines = max(1, text.count("\n") + 1)
        tab.large_file_total_chars = len(text)
        tab.encoding = encoding if not encrypted else "utf-8"
        tab.encryption_enabled = encrypted
        tab.encryption_password = password
        tab.read_only = self._is_path_read_only(tab.current_file) if hasattr(self, "_is_path_read_only") else False
        tab.text_edit.set_read_only(bool(tab.read_only))
        tab.markdown_mode_enabled = self._is_markdown_path(tab.current_file) and not tab.large_file
        tab.markdown_preview.setVisible(tab.markdown_mode_enabled)
        if tab.markdown_mode_enabled:
            tab.markdown_preview.setMarkdown(text)
        self._apply_syntax_highlighting(tab)
        self._refresh_tab_title(tab)
        self.show_status_message("Full large file loaded.", 3000)

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
            (
                "All Editable (*.md *.markdown *.mdown *.txt *.html *.htm *.docx *.odt *.encnote);;"
                "Markdown Documents (*.md *.markdown *.mdown);;"
                "Text Documents (*.txt);;"
                "Web Documents (*.html *.htm);;"
                "Word Documents (*.docx);;"
                "OpenDocument Text (*.odt);;"
                "Encrypted Notes (*.encnote);;"
                "All Files (*.*)"
            ),
        )
        if not path:
            return False
        _LOGGER.debug(
            "file_save_as_tab selected path=%s was_unsaved=%s previous_favorite=%s",
            path,
            was_unsaved,
            previous_favorite,
        )
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
        # "Save As" should not force read-only mode onto the new file unless the user chooses it.
        tab.read_only = False
        tab.text_edit.set_read_only(False)
        if was_unsaved and previous_favorite:
            tab.favorite = True
        if was_unsaved and previous_tags:
            tab.tags = previous_tags
        if tab.current_file:
            self._persist_file_metadata_for_tab(tab)
            if hasattr(self, "_refresh_recent_files_menu"):
                self._refresh_recent_files_menu()
            if hasattr(self, "save_settings_to_disk"):
                self.save_settings_to_disk()
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
        doc = self._build_print_document(tab)
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
            doc = self._build_print_document(tab)
            try:
                doc.print_(preview_printer)
            except Exception as e:  # noqa: BLE001
                QMessageBox.critical(self, "Print Preview Failed", f"Could not render preview:\n{e}")

        dialog.paintRequested.connect(render_preview)
        dialog.exec()

    def _build_print_document(self, tab: EditorTab) -> QTextDocument:
        doc = QTextDocument()
        print_font = tab.text_edit.current_font()
        if print_font.pointSizeF() <= 0:
            print_font.setPointSizeF(float(self.settings.get("font_size", 11)))
        if not print_font.family().strip():
            fallback_family = str(self.settings.get("font_family", "") or "").strip()
            if fallback_family:
                print_font.setFamily(fallback_family)
        doc.setDefaultFont(print_font)
        text = tab.text_edit.get_text()
        page_cfg = PageLayoutConfig.from_settings(self.settings)
        apply_npp_print_preferences_to_page_layout(self.settings, tab, page_cfg)
        use_layout_render = bool(
            self.settings.get("page_layout_view_enabled", False)
            or page_cfg.header_text.strip()
            or page_cfg.footer_text.strip()
            or (page_cfg.show_page_breaks and ("[[PAGE_BREAK]]" in text or "\f" in text))
        )
        if use_layout_render:
            html_doc = build_layout_html(
                text,
                page_cfg,
                font_family=print_font.family() or str(self.settings.get("font_family", "Segoe UI")),
                font_pt=float(print_font.pointSizeF() if print_font.pointSizeF() > 0 else 11.0),
            )
            doc.setHtml(html_doc)
        elif tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file):
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)
        # Ensure print/preview stays readable even in dark UI themes.
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#000000"))
        cursor.mergeCharFormat(fmt)
        return doc

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


