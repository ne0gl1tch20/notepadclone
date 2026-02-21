# Literally my biggest script ever
from __future__ import annotations
import getpass
import base64
import hashlib
import json
import os
import random
import re
import sys
import time
import webbrowser
import subprocess
from typing import TYPE_CHECKING, Any
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from html import escape as html_escape
from urllib.parse import quote as url_quote, unquote as url_unquote

from PySide6.QtCore import QByteArray, QEvent, QPoint, QSize, Qt, QTimer, Signal, Slot
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
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFileSystemModel,
    QFontDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStyle,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter

from ..debug_logs_dialog import DebugLogsDialog
from ..detachable_tab_bar import DetachableTabBar
from ..editor_tab import EditorTab
from ...app_settings import (
    get_crash_logs_file_path,
    get_debug_logs_file_path,
    normalize_ui_visibility_settings,
    migrate_settings,
    get_autosave_dir_path,
    get_legacy_settings_file_path,
    get_password_file_path,
    get_reminders_file_path,
    get_settings_file_path,
    get_translation_cache_path,
)
from ...app_settings.defaults import DEFAULT_UPDATE_FEED_URL
from ..ai_controller import AIController
from ..ai_edit_preview_dialog import AIEditPreviewDialog
from ..asset_paths import resolve_asset_path
from ..autosave import AutoSaveRecoveryDialog, AutoSaveStore
from ..reminders import ReminderStore, RemindersDialog
from ..security_controller import SecurityController
from ..syntax_highlighter import CodeSyntaxHighlighter
from ..updater_controller import UpdaterController
from ..version_history import VersionEntry, VersionHistoryDialog
from ..workspace_controller import WorkspaceController
from ..session_recovery import local_history_key
from ..advanced_text_tools import build_line_refs, export_line_refs_text
from ..document_fidelity import DocumentFidelityError, export_document_text, render_text_to_html
from ..extensibility_ops import discover_window_actions
from ..ai_collaboration import (
    build_ai_conflict_merge_prompt,
    build_conflict_markers,
    build_project_qa_prompt,
    build_workspace_citation_snippets,
    build_collab_presence_text,
    paragraph_bounds,
    strip_model_fences,
)
from .settings_dialog import SettingsDialog as SidebarSettingsDialog
from ..tutorial_dialog import InteractiveTutorialDialog
from ..shortcut_mapper import PRESET_SHORTCUTS, ShortcutActionRow, ShortcutMapperDialog, parse_shortcut_value, sequence_to_string
from ..command_palette import CommandPaletteDialog, PaletteItem
from ...i18n.translator import language_code_for



class MiscMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    # ---------- Misc ----------
    @staticmethod
    def _get_settings_file_path() -> Path:
        return get_settings_file_path()

    @staticmethod
    def _get_legacy_settings_file_path() -> Path:
        return get_legacy_settings_file_path()

    @staticmethod
    def _get_password_file_path() -> Path:
        return get_password_file_path()

    @staticmethod
    def _get_reminders_file_path() -> Path:
        return get_reminders_file_path()

    @staticmethod
    def _get_autosave_dir_path() -> Path:
        return get_autosave_dir_path()

    @staticmethod
    def _get_translation_cache_path() -> Path:
        return get_translation_cache_path()

    @staticmethod
    def _get_debug_logs_file_path() -> Path:
        return get_debug_logs_file_path()

    @staticmethod
    def _get_crash_logs_file_path() -> Path:
        return get_crash_logs_file_path()

    def _add_recent_file(self, path: str | None) -> None:
        if not path:
            return
        recent = [p for p in self.settings.get("recent_files", []) if isinstance(p, str) and p]
        recent = [p for p in recent if p != path]
        recent.insert(0, path)
        self.settings["recent_files"] = recent[:15]
        self._refresh_recent_files_menu()
        self._refresh_favorite_files_menu()

    @staticmethod
    def _normalize_tags(raw: list[str] | tuple[str, ...] | str) -> list[str]:
        if isinstance(raw, str):
            tokens = [part.strip() for part in raw.split(",")]
        else:
            tokens = [str(part).strip() for part in raw]
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if not token:
                continue
            key = token.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(token)
        return deduped

    @staticmethod
    def _is_path_read_only(path: str) -> bool:
        try:
            return not os.access(path, os.W_OK)
        except OSError:
            return False

    def _apply_tab_color(self, tab: EditorTab) -> None:
        index = self.tab_widget.indexOf(tab)
        if index < 0:
            return
        bar = self.tab_widget.tabBar()
        if tab.tab_color:
            color = QColor(tab.tab_color)
            if color.isValid():
                bar.setTabData(index, tab.tab_color)
                bar.setTabTextColor(index, color)
                return
        bar.setTabData(index, None)
        bar.setTabTextColor(index, self.palette().color(QPalette.Text))

    def _color_swatch_icon(self, color_hex: str, size: int = 12) -> QIcon:
        color = QColor(color_hex)
        if not color.isValid():
            return QIcon()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#666666"))
        painter.setBrush(color)
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
        painter.end()
        return QIcon(pixmap)

    def _apply_file_metadata_to_tab(self, tab: EditorTab) -> None:
        if not tab.current_file:
            tab.favorite = False
            tab.tags = []
            tab.tab_color = None
            tab.read_only = False
            tab.text_edit.set_read_only(False)
            return
        favorites = set(self.settings.get("favorite_files", []))
        tags_map = self.settings.get("file_tags", {})
        colors_map = self.settings.get("file_colors", {})
        tags = []
        if isinstance(tags_map, dict):
            raw = tags_map.get(tab.current_file, [])
            tags = self._normalize_tags(raw if isinstance(raw, (list, tuple, str)) else [])
        tab.favorite = tab.current_file in favorites
        tab.tags = tags
        if isinstance(colors_map, dict):
            color = colors_map.get(tab.current_file)
            if color:
                tab.tab_color = str(color)
            else:
                tab.tab_color = tab.tab_color or None
        else:
            tab.tab_color = tab.tab_color or None
        tab.read_only = self._is_path_read_only(tab.current_file)
        tab.text_edit.set_read_only(tab.read_only)
        self._apply_tab_color(tab)
        self._refresh_tab_title(tab)

    def _persist_file_metadata_for_tab(self, tab: EditorTab) -> None:
        if not tab.current_file:
            return
        favorites = [p for p in self.settings.get("favorite_files", []) if isinstance(p, str)]
        if tab.favorite and tab.current_file not in favorites:
            favorites.append(tab.current_file)
        if not tab.favorite:
            favorites = [p for p in favorites if p != tab.current_file]
        self.settings["favorite_files"] = favorites

        tags_map = self.settings.get("file_tags", {})
        if not isinstance(tags_map, dict):
            tags_map = {}
        cleaned = self._normalize_tags(tab.tags)
        if cleaned:
            tags_map[tab.current_file] = cleaned
        else:
            tags_map.pop(tab.current_file, None)
        self.settings["file_tags"] = tags_map
        colors_map = self.settings.get("file_colors", {})
        if not isinstance(colors_map, dict):
            colors_map = {}
        if tab.tab_color:
            colors_map[tab.current_file] = tab.tab_color
        else:
            colors_map.pop(tab.current_file, None)
        self.settings["file_colors"] = colors_map
        self._refresh_favorite_files_menu()

    def _refresh_recent_files_menu(self) -> None:
        menu = getattr(self, "recent_files_menu", None)
        if menu is None:
            return
        try:
            menu.clear()
        except RuntimeError:
            # Stale Qt wrapper; menus can be recreated during lifecycle/theme/apply cycles.
            self.recent_files_menu = None
            return
        files = [p for p in self.settings.get("recent_files", []) if isinstance(p, str) and p]
        pinned = set(p for p in self.settings.get("pinned_files", []) if isinstance(p, str))
        favorites = set(p for p in self.settings.get("favorite_files", []) if isinstance(p, str))
        if not files:
            action = QAction("(No recent files)", self)
            action.setEnabled(False)
            try:
                menu.addAction(action)
            except RuntimeError:
                self.recent_files_menu = None
            return
        for path in files:
            action = QAction(path, self)
            if path in favorites:
                action.setIcon(self._svg_icon("tab-heart"))
            elif path in pinned:
                action.setIcon(self._svg_icon("tab-pin"))
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_file(p))
            try:
                menu.addAction(action)
            except RuntimeError:
                self.recent_files_menu = None
                return

    def _refresh_favorite_files_menu(self) -> None:
        menu = getattr(self, "favorite_files_menu", None)
        if menu is None:
            return
        try:
            menu.clear()
        except RuntimeError:
            self.favorite_files_menu = None
            return
        files = [p for p in self.settings.get("favorite_files", []) if isinstance(p, str) and p]
        pinned = set(p for p in self.settings.get("pinned_files", []) if isinstance(p, str))
        if not files:
            action = QAction("(No favorite files)", self)
            action.setEnabled(False)
            try:
                menu.addAction(action)
            except RuntimeError:
                self.favorite_files_menu = None
            return
        for path in files:
            action = QAction(path, self)
            if path in pinned:
                action.setIcon(self._svg_icon("tab-pin"))
            else:
                action.setIcon(self._svg_icon("tab-heart"))
            action.triggered.connect(lambda _checked=False, p=path: self._open_recent_file(p))
            try:
                menu.addAction(action)
            except RuntimeError:
                self.favorite_files_menu = None
                return

    def _tab_at_index(self, index: int) -> EditorTab | None:
        widget = self.tab_widget.widget(index)
        return widget if isinstance(widget, EditorTab) else None

    def _close_tabs_by_indices(self, indices: list[int]) -> None:
        for index in sorted(indices, reverse=True):
            if 0 <= index < self.tab_widget.count():
                self.close_tab(index)

    def close_all_tabs(self) -> None:
        self._close_tabs_by_indices(list(range(self.tab_widget.count())))

    def close_all_but(self, index: int) -> None:
        self._close_tabs_by_indices([i for i in range(self.tab_widget.count()) if i != index])

    def close_all_but_pinned(self) -> None:
        indices = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is not None and not tab.pinned:
                indices.append(i)
        self._close_tabs_by_indices(indices)

    def close_all_left_of(self, index: int) -> None:
        self._close_tabs_by_indices(list(range(0, index)))

    def close_all_right_of(self, index: int) -> None:
        self._close_tabs_by_indices(list(range(index + 1, self.tab_widget.count())))

    def close_all_unchanged(self) -> None:
        indices = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is not None and not tab.text_edit.is_modified():
                indices.append(i)
        self._close_tabs_by_indices(indices)

    def save_all_tabs(self) -> None:
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.text_edit.is_modified():
                self.file_save_tab(tab)

    def _window_tab_type(self, tab: EditorTab) -> str:
        if tab.text_edit.is_read_only():
            return "read-only"
        if tab.text_edit.is_modified():
            return "modified"
        return "normal"

    def _window_tab_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for index in range(self.tab_widget.count()):
            tab = self._tab_at_index(index)
            if tab is None:
                continue
            path = tab.current_file or ""
            tab_type = self._window_tab_type(tab)
            if path and Path(path).exists():
                try:
                    stat = Path(path).stat()
                    size = int(stat.st_size)
                    modified_ts = float(stat.st_mtime)
                    modified_text = datetime.fromtimestamp(modified_ts).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    size = len(tab.text_edit.get_text().encode("utf-8", errors="replace"))
                    modified_ts = 0.0
                    modified_text = "-"
            else:
                size = len(tab.text_edit.get_text().encode("utf-8", errors="replace"))
                modified_ts = 0.0
                modified_text = "-"
            rows.append(
                {
                    "index": index,
                    "tab": tab,
                    "name": self._tab_display_name(tab),
                    "path": path,
                    "type": tab_type,
                    "size": size,
                    "modified_ts": modified_ts,
                    "modified_text": modified_text,
                    "content_len": len(tab.text_edit.get_text()),
                }
            )
        return rows

    def window_sort_tabs(self, mode: str) -> None:
        tabs: list[EditorTab] = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is not None:
                tabs.append(tab)
        if len(tabs) < 2:
            return

        current = self.active_tab()

        def key_for(tab: EditorTab) -> tuple:
            name = self._tab_display_name(tab).lower()
            path = (tab.current_file or "").lower()
            tab_type = self._window_tab_type(tab).lower()
            content_len = len(tab.text_edit.get_text())
            modified_ts = 0.0
            if tab.current_file and Path(tab.current_file).exists():
                try:
                    modified_ts = float(Path(tab.current_file).stat().st_mtime)
                except Exception:
                    modified_ts = 0.0
            if mode == "name_asc" or mode == "name_desc":
                return (name,)
            if mode == "path_asc" or mode == "path_desc":
                return (path, name)
            if mode == "type_asc" or mode == "type_desc":
                return (tab_type, name)
            if mode == "content_len_asc" or mode == "content_len_desc":
                return (content_len, name)
            if mode == "modified_asc" or mode == "modified_desc":
                return (modified_ts, name)
            return (name,)

        reverse = mode.endswith("_desc")
        sorted_tabs = sorted(tabs, key=key_for, reverse=reverse)
        if sorted_tabs == tabs:
            return

        while self.tab_widget.count():
            self.tab_widget.removeTab(0)
        for tab in sorted_tabs:
            self.tab_widget.addTab(tab, self._tab_display_name(tab))
            self._refresh_tab_title(tab)
        if current is not None:
            self.tab_widget.setCurrentWidget(current)
        self._sync_tab_empty_state()
        self.update_action_states()
        self.update_window_title()
        self._refresh_window_menu_entries()
        self.show_status_message("Window tabs sorted.", 2000)

    def _refresh_window_menu_entries(self) -> None:
        menu = getattr(self, "window_menu", None)
        tabs_separator = getattr(self, "window_tabs_separator", None)
        if menu is None or tabs_separator is None:
            return
        try:
            actions = list(menu.actions())
        except RuntimeError:
            self.window_menu = None
            self.window_tabs_separator = None
            return
        if tabs_separator not in actions:
            return
        sep_index = actions.index(tabs_separator)
        for action in actions[sep_index + 1 :]:
            try:
                menu.removeAction(action)
            except RuntimeError:
                self.window_menu = None
                self.window_tabs_separator = None
                return
        current_index = self.tab_widget.currentIndex()
        if self.tab_widget.count() <= 0:
            empty = QAction("(No documents)", self)
            empty.setEnabled(False)
            try:
                menu.addAction(empty)
            except RuntimeError:
                self.window_menu = None
                self.window_tabs_separator = None
            return
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            action = QAction(f"{i + 1}: {self._tab_display_name(tab)}", self)
            action.setCheckable(True)
            action.setChecked(i == current_index)
            action.triggered.connect(lambda _checked=False, idx=i: self.tab_widget.setCurrentIndex(idx))
            try:
                menu.addAction(action)
            except RuntimeError:
                self.window_menu = None
                self.window_tabs_separator = None
                return

    def show_windows_manager(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Windows - Total documents: {self.tab_widget.count()}")
        dialog.resize(760, 520)

        root = QHBoxLayout(dialog)
        table = QTableWidget(dialog)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Name", "Path", "Type", "Size", "Modified time"])
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(table, 1)

        button_col = QVBoxLayout()
        activate_btn = QPushButton("Activate", dialog)
        save_btn = QPushButton("Save", dialog)
        close_btn = QPushButton("Close window(s)", dialog)
        sort_btn = QPushButton("Sort tabs", dialog)
        ok_btn = QPushButton("OK", dialog)
        for btn in (activate_btn, save_btn, close_btn, sort_btn):
            button_col.addWidget(btn)
        button_col.addStretch(1)
        button_col.addWidget(ok_btn)
        root.addLayout(button_col)

        sort_modes = [
            ("Name A to Z", "name_asc"),
            ("Name Z to A", "name_desc"),
            ("Path A to Z", "path_asc"),
            ("Path Z to A", "path_desc"),
            ("Type A to Z", "type_asc"),
            ("Type Z to A", "type_desc"),
            ("Content Length Ascending", "content_len_asc"),
            ("Content Length Descending", "content_len_desc"),
            ("Modified Time Ascending", "modified_asc"),
            ("Modified Time Descending", "modified_desc"),
        ]
        sort_map = {label: mode for label, mode in sort_modes}

        def populate() -> None:
            rows = self._window_tab_rows()
            dialog.setWindowTitle(f"Windows - Total documents: {len(rows)}")
            table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                name_item = QTableWidgetItem(str(row["name"]))
                name_item.setData(Qt.UserRole, int(row["index"]))
                table.setItem(row_idx, 0, name_item)
                table.setItem(row_idx, 1, QTableWidgetItem(str(row["path"])))
                table.setItem(row_idx, 2, QTableWidgetItem(str(row["type"])))
                table.setItem(row_idx, 3, QTableWidgetItem(str(row["size"])))
                table.setItem(row_idx, 4, QTableWidgetItem(str(row["modified_text"])))

        def selected_indices() -> list[int]:
            rows = sorted({item.row() for item in table.selectedItems()})
            indices: list[int] = []
            for row in rows:
                item = table.item(row, 0)
                if item is None:
                    continue
                data = item.data(Qt.UserRole)
                if isinstance(data, int):
                    indices.append(data)
            return sorted(indices)

        def activate_selected() -> None:
            idxs = selected_indices()
            if not idxs:
                return
            self.tab_widget.setCurrentIndex(idxs[0])
            self._refresh_window_menu_entries()
            populate()

        def save_selected() -> None:
            for idx in selected_indices():
                tab = self._tab_at_index(idx)
                if tab is not None:
                    self.file_save_tab(tab)
            populate()

        def close_selected() -> None:
            idxs = selected_indices()
            if not idxs:
                return
            for idx in sorted(idxs, reverse=True):
                self.close_tab(idx)
            populate()

        def sort_selected_mode() -> None:
            labels = [label for label, _mode in sort_modes]
            choice, ok = QInputDialog.getItem(dialog, "Sort tabs", "Sort mode:", labels, 0, False)
            if not ok or not choice:
                return
            self.window_sort_tabs(sort_map.get(choice, "name_asc"))
            populate()

        activate_btn.clicked.connect(activate_selected)
        save_btn.clicked.connect(save_selected)
        close_btn.clicked.connect(close_selected)
        sort_btn.clicked.connect(sort_selected_mode)
        ok_btn.clicked.connect(dialog.accept)
        table.itemDoubleClicked.connect(lambda _item: activate_selected())

        populate()
        dialog.exec()

    def _notify_large_file_mode(self, tab: EditorTab) -> None:
        if not tab.large_file:
            tab.large_file_notice_shown = False
            return
        if tab.large_file_notice_shown:
            return
        tab.large_file_notice_shown = True
        if getattr(tab, "partial_large_preview", False):
            self.show_status_message(
                "Large File Preview mode: partial content loaded; use 'Load Full Large File' before editing/saving.",
                7000,
            )
        else:
            self.show_status_message(
                "Large File Mode enabled: syntax highlighting, markdown formatting, and snapshots are limited.",
                6000,
            )

    def reload_tab_from_disk(self, tab: EditorTab) -> None:
        if not tab.current_file:
            return
        if tab.text_edit.is_modified():
            ret = QMessageBox.warning(
                self,
                "Reload Tab",
                "This tab has unsaved changes.\n\nReload from disk and discard changes?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        try:
            encoding = tab.encoding or self._encoding_for_path(tab.current_file)
            text, encrypted, password = self._load_text_from_path(tab.current_file, encoding=encoding)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Reload Failed", f"Could not reload file:\n{e}")
            return
        tab.text_edit.set_text(text)
        tab.encoding = encoding if not encrypted else "utf-8"
        tab.eol_mode = self._detect_eol_mode(text)
        try:
            threshold_kb = int(self.settings.get("large_file_threshold_kb", 2048))
            tab.large_file = int(Path(tab.current_file).stat().st_size / 1024) >= threshold_kb
        except Exception:
            tab.large_file = False
        tab.encryption_enabled = encrypted
        tab.encryption_password = password
        tab.partial_large_preview = False
        tab.large_file_total_lines = max(1, text.count("\n") + 1)
        tab.large_file_total_chars = len(text)
        tab.markdown_mode_enabled = self._is_markdown_path(tab.current_file) and not tab.large_file
        tab.markdown_preview.setVisible(tab.markdown_mode_enabled)
        if tab.markdown_mode_enabled:
            tab.markdown_preview.setMarkdown(text)
        self._notify_large_file_mode(tab)
        tab.text_edit.set_modified(False)
        self._apply_file_metadata_to_tab(tab)
        self._apply_syntax_highlighting(tab)
        self._refresh_tab_title(tab)
        self.update_window_title()

    def _set_file_read_only(self, path: str, read_only: bool) -> bool:
        try:
            mode = os.stat(path).st_mode
            if read_only:
                os.chmod(path, mode & ~0o222)
            else:
                os.chmod(path, mode | 0o222)
            return True
        except OSError:
            return False

    def toggle_tab_read_only(self, tab: EditorTab) -> None:
        if not tab.current_file:
            return
        new_state = not self._is_path_read_only(tab.current_file)
        if not self._set_file_read_only(tab.current_file, new_state):
            QMessageBox.warning(self, "Read-Only", "Could not update read-only attribute.")
            return
        tab.read_only = new_state
        tab.text_edit.set_read_only(tab.read_only)
        self._refresh_tab_title(tab)
        self.show_status_message("Read-only enabled" if tab.read_only else "Read-only disabled", 3000)

    def set_tab_color(self, tab: EditorTab, color_hex: str | None) -> None:
        tab.tab_color = color_hex
        self._apply_tab_color(tab)
        self._persist_file_metadata_for_tab(tab)

    def _update_path_references(self, old: str, new: str) -> None:
        if old == new:
            return
        def _replace_in_list(values: list[str]) -> list[str]:
            return [new if p == old else p for p in values]
        self.settings["recent_files"] = _replace_in_list(self.settings.get("recent_files", []))
        self.settings["pinned_files"] = _replace_in_list(self.settings.get("pinned_files", []))
        self.settings["favorite_files"] = _replace_in_list(self.settings.get("favorite_files", []))
        tags_map = self.settings.get("file_tags", {})
        if isinstance(tags_map, dict) and old in tags_map:
            tags_map[new] = tags_map.pop(old)
        colors_map = self.settings.get("file_colors", {})
        if isinstance(colors_map, dict) and old in colors_map:
            colors_map[new] = colors_map.pop(old)
        enc_map = self.settings.get("file_encodings", {})
        if isinstance(enc_map, dict) and old in enc_map:
            enc_map[new] = enc_map.pop(old)
        eol_map = self.settings.get("file_eol_modes", {})
        if isinstance(eol_map, dict) and old in eol_map:
            eol_map[new] = eol_map.pop(old)
        self.settings["file_tags"] = tags_map
        self.settings["file_colors"] = colors_map
        self.settings["file_encodings"] = enc_map
        self.settings["file_eol_modes"] = eol_map
        self._refresh_recent_files_menu()
        self._refresh_favorite_files_menu()
        if hasattr(self, "_refresh_file_watcher"):
            self._refresh_file_watcher()

    def _move_to_recycle_bin(self, path: str) -> bool:
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return False

        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        class SHFILEOPSTRUCT(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.UINT),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        op = SHFILEOPSTRUCT()
        op.wFunc = FO_DELETE
        op.pFrom = path + "\0\0"
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return res == 0 and not op.fAnyOperationsAborted

    def show_tab_context_menu(self, index: int, global_pos: QPoint) -> None:
        tab = self._tab_at_index(index)
        if tab is None:
            return
        self.tab_widget.setCurrentIndex(index)

        menu = QMenu(self)
        pin_action = menu.addAction("Unpin Tab" if tab.pinned else "Pin Tab")
        pin_action.setCheckable(True)
        pin_action.setChecked(tab.pinned)
        menu.addSeparator()
        close_action = menu.addAction("Close Tab")
        close_multi_menu = menu.addMenu("Close Multiple Tabs")
        close_all_but_action = close_multi_menu.addAction("Close All But This")
        close_all_but_pinned_action = close_multi_menu.addAction("Close All But Pinned")
        close_all_left_action = close_multi_menu.addAction("Close All To The Left")
        close_all_right_action = close_multi_menu.addAction("Close All To The Right")
        close_all_unchanged_action = close_multi_menu.addAction("Close All Unchanged")

        menu.addSeparator()
        save_action = menu.addAction("Save")
        save_as_action = menu.addAction("Save As...")

        menu.addSeparator()
        open_menu = menu.addMenu("Open In")
        open_explorer_action = open_menu.addAction("Explorer")
        open_cmd_action = open_menu.addAction("Command Prompt")
        open_workspace_action = open_menu.addAction("Workspace")
        open_default_action = open_menu.addAction("Default Viewer")

        menu.addSeparator()
        rename_action = menu.addAction("Rename")
        move_recycle_action = menu.addAction("Move to Recycle Bin")
        reload_action = menu.addAction("Reload")

        menu.addSeparator()
        print_action = menu.addAction("Print...")
        read_only_action = menu.addAction("Toggle Read-Only")
        read_only_action.setCheckable(True)
        read_only_action.setChecked(tab.read_only)

        menu.addSeparator()
        copy_menu = menu.addMenu("Copy To Clipboard")
        copy_path_action = copy_menu.addAction("Copy File Path")
        copy_name_action = copy_menu.addAction("Copy File Name")

        menu.addSeparator()
        color_menu = menu.addMenu("Change Tab Color")
        current_color = tab.tab_color if tab.tab_color else "Default"
        color_preview_action = color_menu.addAction(f"Current: {current_color}")
        color_preview_action.setEnabled(False)
        if tab.tab_color:
            color_preview_action.setIcon(self._color_swatch_icon(tab.tab_color))
        color_menu.addSeparator()
        clear_color_action = color_menu.addAction("Use Default")
        preset_colors = [
            ("#e81123", "Red"),
            ("#ff8c00", "Orange"),
            ("#ffd800", "Yellow"),
            ("#107c10", "Green"),
            ("#0078d4", "Blue"),
            ("#5c2d91", "Purple"),
            ("#c239b3", "Pink"),
            ("#6b6b6b", "Gray"),
        ]
        color_actions: dict[QAction, str] = {}
        for hex_color, label in preset_colors:
            preset_action = color_menu.addAction(label)
            preset_action.setIcon(self._color_swatch_icon(hex_color))
            color_actions[preset_action] = hex_color
        color_menu.addSeparator()
        custom_color_action = color_menu.addAction("Custom...")

        has_file = bool(tab.current_file and Path(tab.current_file).exists())
        for action in (
            open_explorer_action,
            open_cmd_action,
            open_workspace_action,
            open_default_action,
            move_recycle_action,
            reload_action,
            read_only_action,
            copy_path_action,
            copy_name_action,
        ):
            action.setEnabled(has_file)
        rename_action.setEnabled(True)

        chosen = menu.exec(global_pos)
        if chosen is None:
            return

        if chosen == pin_action:
            self.toggle_pin_active_tab()
        elif chosen == close_action:
            self.close_tab(index)
        elif chosen == close_all_but_action:
            self.close_all_but(index)
        elif chosen == close_all_but_pinned_action:
            self.close_all_but_pinned()
        elif chosen == close_all_left_action:
            self.close_all_left_of(index)
        elif chosen == close_all_right_action:
            self.close_all_right_of(index)
        elif chosen == close_all_unchanged_action:
            self.close_all_unchanged()
        elif chosen == save_action:
            self.file_save_tab(tab)
        elif chosen == save_as_action:
            self.file_save_as_tab(tab)
        elif chosen == open_explorer_action and tab.current_file:
            os.startfile(os.path.dirname(tab.current_file))
        elif chosen == open_cmd_action and tab.current_file:
            folder = os.path.dirname(tab.current_file)  # Get folder of current file
            
            # Open Command Prompt in that folder
            try:
                subprocess.Popen(f'cmd.exe /K cd /d "{folder}"', shell=True)
            except Exception as e:
                print(f"Failed to open CMD: {e}")
        elif chosen == open_workspace_action and tab.current_file:
            folder = os.path.dirname(tab.current_file)
            self.settings["workspace_root"] = folder
            self.show_status_message(f"Workspace: {folder}", 3000)
            self.show_workspace_files()
        elif chosen == open_default_action and tab.current_file:
            os.startfile(tab.current_file)
        elif chosen == rename_action:
            self.rename_tab_file(tab)
        elif chosen == move_recycle_action and tab.current_file:
            if self._move_to_recycle_bin(tab.current_file):
                self.close_tab(index)
            else:
                QMessageBox.warning(self, "Recycle Bin", "Could not move file to Recycle Bin.")
        elif chosen == reload_action:
            self.reload_tab_from_disk(tab)
        elif chosen == print_action:
            self.file_print()
        elif chosen == read_only_action:
            self.toggle_tab_read_only(tab)
        elif chosen == copy_path_action and tab.current_file:
            QApplication.clipboard().setText(tab.current_file)
        elif chosen == copy_name_action and tab.current_file:
            QApplication.clipboard().setText(Path(tab.current_file).name)
        elif chosen == clear_color_action:
            self.set_tab_color(tab, None)
        elif chosen in color_actions:
            self.set_tab_color(tab, color_actions[chosen])
        elif chosen == custom_color_action:
            current = QColor(tab.tab_color) if tab.tab_color else QColor()
            color = QColorDialog.getColor(current, self, "Tab Color")
            if color.isValid():
                self.set_tab_color(tab, color.name())

    def _open_recent_file(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "Recent Files", f"File not found:\n{path}")
            self.settings["recent_files"] = [p for p in self.settings.get("recent_files", []) if p != path]
            self._refresh_recent_files_menu()
            return
        self._open_file_path(path)

    def toggle_pin_active_tab(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.pinned = not tab.pinned
        pinned_files = [p for p in self.settings.get("pinned_files", []) if isinstance(p, str)]
        if tab.current_file:
            if tab.pinned and tab.current_file not in pinned_files:
                pinned_files.append(tab.current_file)
            if not tab.pinned:
                pinned_files = [p for p in pinned_files if p != tab.current_file]
        self.settings["pinned_files"] = pinned_files
        self._refresh_tab_title(tab)
        self._sort_tabs_by_pinned()
        self.pin_tab_action.setText("&Unpin Tab" if tab.pinned else "&Pin Tab")

    def toggle_favorite_active_tab(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.favorite = not tab.favorite
        self._persist_file_metadata_for_tab(tab)
        self._refresh_tab_title(tab)
        self.favorite_tab_action.setText("&Unfavorite Tab" if tab.favorite else "&Favorite Tab")

    def edit_active_tab_tags(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        current = ", ".join(tab.tags)
        text, ok = QInputDialog.getText(self, "Edit Tags", "Comma-separated tags:", text=current)
        if not ok:
            return
        tab.tags = self._normalize_tags(text)
        self._persist_file_metadata_for_tab(tab)
        self._refresh_tab_title(tab)

    def rename_active_tab_file(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        self.rename_tab_file(tab)

    def move_active_tab_to_recycle_bin(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if not tab.current_file or not Path(tab.current_file).exists():
            QMessageBox.information(self, "Move to Recycle Bin", "Current tab is not a saved file.")
            return
        name = Path(tab.current_file).name
        answer = QMessageBox.question(
            self,
            "Move to Recycle Bin",
            f'Move "{name}" to Recycle Bin?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        index = self.tab_widget.indexOf(tab)
        if self._move_to_recycle_bin(tab.current_file):
            if index >= 0:
                self.close_tab(index)
            self.show_status_message(f'Moved "{name}" to Recycle Bin.', 3000)
        else:
            QMessageBox.warning(self, "Move to Recycle Bin", "Could not move file to Recycle Bin.")

    def rename_tab_file(self, tab: EditorTab) -> None:
        if not tab.current_file:
            QMessageBox.information(
                self,
                "Rename",
                "This tab has no file yet. Use Save As to choose a file name.",
            )
            self.file_save_as_tab(tab)
            return
        current_path = Path(tab.current_file)
        if not current_path.exists():
            QMessageBox.warning(self, "Rename", "Current file does not exist on disk.")
            return

        new_name, ok = QInputDialog.getText(self, "Rename File", "New file name:", text=current_path.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if any(sep in new_name for sep in ("/", "\\")):
            QMessageBox.warning(self, "Rename Failed", "Please provide only a file name, not a path.")
            return

        new_path = current_path.with_name(new_name)
        if new_path == current_path:
            return
        if new_path.exists():
            QMessageBox.warning(self, "Rename Failed", "A file with that name already exists.")
            return
        try:
            current_path.rename(new_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rename Failed", f"Could not rename file:\n{exc}")
            return

        old_path = str(current_path)
        tab.current_file = str(new_path)
        self._update_path_references(old_path, str(new_path))
        self._refresh_tab_title(tab)
        self.update_window_title()
        self.show_status_message(f'Renamed to "{new_path.name}"', 3000)

    def new_tab_from_template(self, template_name: str) -> None:
        template = self.templates.get(template_name)
        if template is None:
            return
        tab = self.add_new_tab(text=template, file_path=None, make_current=True)
        tab.text_edit.set_modified(True)
        self.update_window_title()

    def insert_template_into_active_tab(self, template_name: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        template = self.templates.get(template_name)
        if template is None:
            return
        tab.text_edit.insert_text(template)

    def _export_document_html(self, tab: EditorTab) -> str:
        text = tab.text_edit.get_text()
        return render_text_to_html(
            text,
            markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
        )

    def export_active_as_markdown(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Markdown",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".md",
            "Markdown Files (*.md);;All Files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(tab.text_edit.get_text(), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export Markdown:\n{e}")
            return
        self.show_status_message(f"Exported Markdown: {path}", 3000)

    def export_active_as_html(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as HTML",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".html",
            "HTML Files (*.html *.htm);;All Files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._export_document_html(tab), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export HTML:\n{e}")
            return
        self.show_status_message(f"Exported HTML: {path}", 3000)

    def export_active_as_docx(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as DOCX",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".docx",
            "Word Documents (*.docx);;All Files (*.*)",
        )
        if not path:
            return
        try:
            export_document_text(
                path,
                tab.text_edit.get_text(),
                markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
            )
        except DocumentFidelityError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export DOCX:\n{e}")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export DOCX:\n{e}")
            return
        self.show_status_message(f"Exported DOCX: {path}", 3000)

    def export_active_as_odt(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as ODT",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".odt",
            "OpenDocument Text (*.odt);;All Files (*.*)",
        )
        if not path:
            return
        try:
            export_document_text(
                path,
                tab.text_edit.get_text(),
                markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
            )
        except DocumentFidelityError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export ODT:\n{e}")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export ODT:\n{e}")
            return
        self.show_status_message(f"Exported ODT: {path}", 3000)

    def export_active_as_pdf(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as PDF",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".pdf",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not path:
            return
        writer = QPdfWriter(path)
        doc = QTextDocument()
        text = tab.text_edit.get_text()
        if tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file):
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)
        try:
            doc.print_(writer)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export PDF:\n{e}")
            return
        self.show_status_message(f"Exported PDF: {path}", 3000)

    def enable_note_encryption(self) -> None:
        self.security_controller.enable_note_encryption()

    def disable_note_encryption(self) -> None:
        self.security_controller.disable_note_encryption()

    def change_note_password(self) -> None:
        self.security_controller.change_note_password()

    def insert_media_files(self) -> None:
        self.workspace_controller.insert_media_files()

    def _insert_media_paths(self, paths: list[str]) -> None:
        self.workspace_controller.insert_media_paths(paths)

    def open_workspace_folder(self) -> None:
        self.workspace_controller.open_workspace_folder()

    def _workspace_root(self) -> str | None:
        return self.workspace_controller.workspace_root()

    def _workspace_files(self) -> list[str]:
        return self.workspace_controller.workspace_files()

    def show_workspace_files(self) -> None:
        self.workspace_controller.show_workspace_files()

    def search_workspace(self) -> None:
        self.workspace_controller.search_workspace()

    def replace_in_files(self) -> None:
        self.workspace_controller.replace_in_files()

    def start_macro_recording(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        self.macro_recording = True
        self._macro_events = []
        self.show_status_message("Macro recording started", 3000)
        self.update_action_states()

    def stop_macro_recording(self) -> None:
        if not self.macro_recording:
            return
        self.macro_recording = False
        self._last_macro_events = list(self._macro_events)
        self._macro_events = []
        self.show_status_message(
            f"Macro recording stopped ({len(self._last_macro_events)} event(s))",
            3000,
        )
        self.update_action_states()

    def play_macro(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        events = list(getattr(self, "_last_macro_events", []))
        if not events:
            QMessageBox.information(self, "Playback Macro", "No recorded macro to replay.")
            return
        if tab.text_edit.is_read_only():
            QMessageBox.information(self, "Playback Macro", "Current tab is read-only.")
            return
        if self.macro_recording:
            self.stop_macro_recording()

        self.macro_playing = True
        try:
            self._apply_macro_events(tab, events)
            self.show_status_message("Macro playback completed", 3000)
        finally:
            self.macro_playing = False
            self.update_action_states()

    def _apply_macro_events(self, tab: EditorTab, events: list[tuple[str, str]]) -> None:
        for op, value in events:
            if op == "text":
                tab.text_edit.insert_text(value)
            elif op == "backspace":
                tab.text_edit.delete_backspace()
            elif op == "delete":
                tab.text_edit.delete_delete()

    def _normalized_saved_macros(self) -> dict[str, dict[str, Any]]:
        raw = self.settings.get("saved_macros", {})
        cleaned: dict[str, dict[str, Any]] = {}
        if not isinstance(raw, dict):
            return cleaned
        for key, entry in raw.items():
            name = str(key).strip()
            if not name or not isinstance(entry, dict):
                continue
            raw_events = entry.get("events", [])
            events: list[list[str]] = []
            if isinstance(raw_events, list):
                for item in raw_events:
                    if not isinstance(item, (list, tuple)) or len(item) != 2:
                        continue
                    op = str(item[0]).strip().lower()
                    value = str(item[1])
                    if op in {"text", "backspace", "delete"}:
                        events.append([op, value])
            if not events:
                continue
            shortcut = str(entry.get("shortcut", "") or "").strip()
            cleaned[name] = {"events": events, "shortcut": shortcut}
        return cleaned

    def _macro_events_from_saved_entry(self, entry: dict[str, Any]) -> list[tuple[str, str]]:
        raw_events = entry.get("events", [])
        parsed: list[tuple[str, str]] = []
        if not isinstance(raw_events, list):
            return parsed
        for item in raw_events:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                continue
            op = str(item[0]).strip().lower()
            value = str(item[1])
            if op in {"text", "backspace", "delete"}:
                parsed.append((op, value))
        return parsed

    def _save_saved_macros(self, macros: dict[str, dict[str, Any]]) -> None:
        self.settings["saved_macros"] = macros
        self.save_settings_to_disk()
        self._sync_saved_macro_actions()
        self.update_action_states()

    def _sync_saved_macro_actions(self) -> None:
        menu = getattr(self, "macros_menu", None)
        if menu is None:
            return
        for action in getattr(self, "_saved_macro_menu_actions", []):
            menu.removeAction(action)
        separator = getattr(self, "_saved_macro_menu_separator", None)
        if separator is not None:
            menu.removeAction(separator)
        self._saved_macro_menu_actions = []
        self._saved_macro_menu_separator = None

        saved = self._normalized_saved_macros()
        if not saved:
            return

        self._saved_macro_menu_separator = menu.addSeparator()
        for name in sorted(saved.keys(), key=str.lower):
            action = QAction(name, self)
            shortcut = str(saved[name].get("shortcut", "") or "").strip()
            if shortcut:
                seq = QKeySequence(shortcut)
                if not seq.isEmpty():
                    action.setShortcut(seq)
            action.triggered.connect(lambda _checked=False, macro_name=name: self.run_saved_macro(macro_name))
            menu.addAction(action)
            self._saved_macro_menu_actions.append(action)

    def save_current_recorded_macro(self) -> None:
        if self.macro_recording:
            self.stop_macro_recording()
        events = list(getattr(self, "_last_macro_events", []))
        if not events:
            QMessageBox.information(self, "Save Macro", "No recorded macro to save.")
            return
        saved = self._normalized_saved_macros()
        default_name = f"Macro {len(saved) + 1}"
        name, ok = QInputDialog.getText(self, "Save Current Recorded Macro", "Macro name:", text=default_name)
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in saved:
            ret = QMessageBox.question(
                self,
                "Save Current Recorded Macro",
                f'A macro named "{name}" already exists. Overwrite it?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        existing_shortcut = str(saved.get(name, {}).get("shortcut", "") or "")
        shortcut, ok = QInputDialog.getText(
            self,
            "Macro Shortcut",
            "Shortcut (optional):",
            text=existing_shortcut,
        )
        if not ok:
            return
        shortcut = shortcut.strip()
        if shortcut:
            seq = QKeySequence(shortcut)
            if seq.isEmpty():
                QMessageBox.warning(self, "Save Macro", "Invalid shortcut format.")
                return
            shortcut = seq.toString(QKeySequence.SequenceFormat.PortableText)

        saved[name] = {
            "events": [[str(op), str(value)] for op, value in events],
            "shortcut": shortcut,
        }
        self._save_saved_macros(saved)
        self.show_status_message(f'Saved macro "{name}".', 3000)

    def _macro_run_options(self) -> list[tuple[str, str, list[tuple[str, str]]]]:
        options: list[tuple[str, str, list[tuple[str, str]]]] = []
        events = list(getattr(self, "_last_macro_events", []))
        if events:
            options.append(("Current Recorded Macro", "events", events))
        saved = self._normalized_saved_macros()
        for name in sorted(saved.keys(), key=str.lower):
            parsed = self._macro_events_from_saved_entry(saved[name])
            if parsed:
                options.append((name, "events", parsed))
        options.append(("Trim Trailing Space and Save", "trim_save", []))
        return options

    def _execute_macro_mode(
        self,
        tab: EditorTab,
        mode: str,
        events: list[tuple[str, str]],
        *,
        repeat_count: int,
        until_end: bool,
    ) -> tuple[bool, int]:
        if mode == "trim_save":
            self.trim_trailing_spaces_and_save()
            return True, 1

        if not events:
            return False, 0

        runs = 0
        if until_end:
            max_loops = 50000
            while runs < max_loops:
                before = tab.text_edit.get_text()
                at_end_before = tab.text_edit.widget.textCursor().atEnd()
                if at_end_before:
                    break
                self._apply_macro_events(tab, events)
                runs += 1
                after = tab.text_edit.get_text()
                at_end_after = tab.text_edit.widget.textCursor().atEnd()
                if after == before:
                    break
                if at_end_after:
                    break
            return True, runs

        for _ in range(max(1, repeat_count)):
            self._apply_macro_events(tab, events)
            runs += 1
        return True, runs

    def run_macro_multiple_times(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if tab.text_edit.is_read_only():
            QMessageBox.information(self, "Run Macro", "Current tab is read-only.")
            return
        options = self._macro_run_options()
        if not options:
            QMessageBox.information(self, "Run Macro", "No macro is available to run.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Run a Macro Multiple Times")
        dialog.setModal(True)

        root = QVBoxLayout(dialog)
        macro_group = QGroupBox("Macro to run", dialog)
        macro_layout = QVBoxLayout(macro_group)
        macro_combo = QComboBox(macro_group)
        for label, mode, events in options:
            macro_combo.addItem(label, (mode, events))
        trim_index = macro_combo.findText("Trim Trailing Space and Save")
        if trim_index >= 0:
            macro_combo.setCurrentIndex(trim_index)
        macro_layout.addWidget(macro_combo)
        root.addWidget(macro_group)

        count_row = QHBoxLayout()
        run_radio = QRadioButton("Run", dialog)
        run_radio.setChecked(True)
        count_spin = QSpinBox(dialog)
        count_spin.setRange(1, 100000)
        count_spin.setValue(1)
        times_label = QLabel("times", dialog)
        count_row.addWidget(run_radio)
        count_row.addWidget(count_spin)
        count_row.addWidget(times_label)
        count_row.addStretch(1)
        root.addLayout(count_row)

        until_eof_radio = QRadioButton("Run until the end of file", dialog)
        root.addWidget(until_eof_radio)

        def _sync_repeat_controls() -> None:
            enabled = run_radio.isChecked()
            count_spin.setEnabled(enabled)
            times_label.setEnabled(enabled)

        run_radio.toggled.connect(_sync_repeat_controls)
        _sync_repeat_controls()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        run_btn = QPushButton("Run", dialog)
        cancel_btn = QPushButton("Cancel", dialog)
        run_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(run_btn)
        buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        selected = macro_combo.currentData()
        if not isinstance(selected, tuple) or len(selected) != 2:
            return
        mode = str(selected[0])
        selected_events = selected[1] if isinstance(selected[1], list) else []

        if self.macro_recording:
            self.stop_macro_recording()
        self.macro_playing = True
        try:
            ok, runs = self._execute_macro_mode(
                tab,
                mode,
                selected_events,
                repeat_count=int(count_spin.value()),
                until_end=until_eof_radio.isChecked(),
            )
            if ok:
                self.show_status_message(f"Macro playback completed ({runs} run(s)).", 3000)
        finally:
            self.macro_playing = False
            self.update_action_states()

    def trim_trailing_spaces_and_save(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if tab.text_edit.is_read_only():
            QMessageBox.information(self, "Trim Trailing Spaces and Save", "Current tab is read-only.")
            return
        text = tab.text_edit.get_text()
        lines = text.splitlines()
        trimmed_lines = [re.sub(r"[ \t]+$", "", line) for line in lines]
        changed_count = sum(1 for old, new in zip(lines, trimmed_lines) if old != new)
        eol = "\r\n" if str(tab.eol_mode or "LF").upper() == "CRLF" else "\n"
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        trimmed = eol.join(trimmed_lines)
        if lines and had_trailing_newline:
            trimmed += eol
        if trimmed != text:
            tab.text_edit.set_text(trimmed)
            tab.text_edit.set_modified(True)
        if self.file_save_tab(tab):
            self.show_status_message(f"Trimmed trailing spaces on {changed_count} line(s) and saved.", 3000)

    def run_saved_macro(self, macro_name: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if tab.text_edit.is_read_only():
            QMessageBox.information(self, "Run Saved Macro", "Current tab is read-only.")
            return
        saved = self._normalized_saved_macros()
        entry = saved.get(macro_name)
        if not entry:
            QMessageBox.information(self, "Run Saved Macro", f'No saved macro named "{macro_name}".')
            return
        events = self._macro_events_from_saved_entry(entry)
        if not events:
            QMessageBox.information(self, "Run Saved Macro", "Saved macro has no executable events.")
            return
        if self.macro_recording:
            self.stop_macro_recording()
        self.macro_playing = True
        try:
            self._apply_macro_events(tab, events)
            self.show_status_message(f'Ran saved macro "{macro_name}".', 3000)
        finally:
            self.macro_playing = False
            self.update_action_states()

    def modify_macro_shortcut_or_delete(self) -> None:
        saved = self._normalized_saved_macros()
        if not saved:
            QMessageBox.information(self, "Modify Shortcut/Delete Macro", "No saved macros found.")
            return
        names = sorted(saved.keys(), key=str.lower)
        name, ok = QInputDialog.getItem(self, "Modify Shortcut/Delete Macro", "Macro:", names, 0, False)
        if not ok or not name:
            return
        options = ["Modify shortcut", "Delete macro"]
        choice, ok = QInputDialog.getItem(self, "Modify Shortcut/Delete Macro", "Action:", options, 0, False)
        if not ok or not choice:
            return

        if choice == "Delete macro":
            ret = QMessageBox.question(
                self,
                "Delete Macro",
                f'Delete macro "{name}"?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
            saved.pop(name, None)
            self._save_saved_macros(saved)
            self.show_status_message(f'Deleted macro "{name}".', 3000)
            return

        current_shortcut = str(saved.get(name, {}).get("shortcut", "") or "")
        shortcut, ok = QInputDialog.getText(
            self,
            "Modify Shortcut",
            f'Shortcut for "{name}" (leave empty to clear):',
            text=current_shortcut,
        )
        if not ok:
            return
        shortcut = shortcut.strip()
        if shortcut:
            seq = QKeySequence(shortcut)
            if seq.isEmpty():
                QMessageBox.warning(self, "Modify Shortcut", "Invalid shortcut format.")
                return
            shortcut = seq.toString(QKeySequence.SequenceFormat.PortableText)
        saved[name]["shortcut"] = shortcut
        self._save_saved_macros(saved)
        self.show_status_message(f'Updated shortcut for "{name}".', 3000)

    def ask_ai(self) -> None:
        self.ai_controller.ask_ai()

    # ---------- Edit extensions ----------
    def edit_insert_datetime_short(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.insert_text(datetime.now().strftime("%Y-%m-%d"))

    def edit_insert_datetime_long(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.insert_text(datetime.now().strftime("%A, %B %d, %Y %H:%M:%S"))

    def edit_insert_datetime_custom(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        fmt, ok = QInputDialog.getText(self, "Date Time (customized)", "strftime format:", text="%Y-%m-%d %H:%M:%S")
        if not ok or not fmt.strip():
            return
        try:
            tab.text_edit.insert_text(datetime.now().strftime(fmt.strip()))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Date Time", f"Invalid format string:\n{exc}")

    def edit_copy_current_full_file_path(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(tab.current_file)

    def edit_copy_current_filename(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(Path(tab.current_file).name)

    def edit_copy_current_dir_path(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(str(Path(tab.current_file).parent))

    def edit_copy_all_filenames(self) -> None:
        names: list[str] = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            names.append(Path(tab.current_file).name if tab.current_file else "Untitled")
        if names:
            QApplication.clipboard().setText("\n".join(names))

    def edit_copy_all_filepaths(self) -> None:
        paths: list[str] = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file:
                paths.append(tab.current_file)
        if paths:
            QApplication.clipboard().setText("\n".join(paths))

    def edit_column_editor(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Column Editor")
        dlg.resize(420, 320)
        root = QVBoxLayout(dlg)

        text_radio = QRadioButton("Text to Insert")
        text_radio.setChecked(True)
        text_input = QLineEdit(dlg)

        number_radio = QRadioButton("Number to Insert")
        number_group = QGroupBox("Format", dlg)
        number_layout = QHBoxLayout(number_group)
        format_dec = QRadioButton("Dec")
        format_dec.setChecked(True)
        format_hex = QRadioButton("Hex")
        format_oct = QRadioButton("Oct")
        format_bin = QRadioButton("Bin")
        hex_case = QComboBox(dlg)
        hex_case.addItems(["a-f", "A-F"])
        hex_case.setEnabled(False)
        for widget in (format_dec, format_hex, format_oct, format_bin, hex_case):
            number_layout.addWidget(widget)

        form = QFormLayout()
        initial_input = QLineEdit(dlg)
        increment_input = QLineEdit(dlg)
        repeat_input = QLineEdit(dlg)
        leading_combo = QComboBox(dlg)
        leading_combo.addItems(["None", "Zeroes"])
        form.addRow("Initial number:", initial_input)
        form.addRow("Increase by:", increment_input)
        form.addRow("Repeat:", repeat_input)
        form.addRow("Leading:", leading_combo)

        def _toggle_number_widgets(checked: bool) -> None:
            number_group.setEnabled(checked)
            initial_input.setEnabled(checked)
            increment_input.setEnabled(checked)
            repeat_input.setEnabled(checked)
            leading_combo.setEnabled(checked)
            text_input.setEnabled(not checked)

        def _toggle_hex_case() -> None:
            hex_case.setEnabled(format_hex.isChecked())

        format_hex.toggled.connect(lambda _checked: _toggle_hex_case())
        _toggle_number_widgets(False)
        number_radio.toggled.connect(_toggle_number_widgets)

        root.addWidget(text_radio)
        root.addWidget(text_input)
        root.addSpacing(6)
        root.addWidget(number_radio)
        root.addWidget(number_group)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        root.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.Accepted:
            return

        if text_radio.isChecked():
            insert_values = []
            value = text_input.text()
            if not value:
                return
        else:
            try:
                initial = int(initial_input.text().strip() or "0")
                increment = int(increment_input.text().strip() or "1")
                repeat = max(1, int(repeat_input.text().strip() or "1"))
            except ValueError:
                QMessageBox.warning(self, "Column Editor", "Please enter valid numbers.")
                return

            def _format_num(num: int) -> str:
                if format_hex.isChecked():
                    formatted = f"{num:x}"
                    if hex_case.currentText() == "A-F":
                        formatted = formatted.upper()
                    return formatted
                if format_oct.isChecked():
                    return f"{num:o}"
                if format_bin.isChecked():
                    return f"{num:b}"
                return str(num)

            insert_values = []
            value = initial
            counter = 0
            line_count = 0
            selection = tab.text_edit.selection_range()
            if selection is not None:
                line1, _c1, line2, c2 = selection
                if line2 > line1 and c2 == 0:
                    line2 -= 1
                line_count = max(1, line2 - line1 + 1)
            if line_count <= 0:
                line_count = 1
            for _ in range(line_count):
                insert_values.append(_format_num(value))
                counter += 1
                if counter >= repeat:
                    value += increment
                    counter = 0
            if leading_combo.currentText() == "Zeroes":
                width = max(len(val) for val in insert_values)
                insert_values = [val.zfill(width) for val in insert_values]

        selection = tab.text_edit.selection_range()
        if selection is None:
            line1, col1 = tab.text_edit.cursor_position()
            line2 = line1
            col2 = col1
        else:
            line1, col1, line2, col2 = selection
            if line2 < line1:
                line1, line2 = line2, line1
                col1, col2 = col2, col1
            if line2 > line1 and col2 == 0:
                line2 -= 1
        if line2 < line1:
            return

        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            lines = [""]
        line2 = min(line2, len(lines) - 1)
        targets = list(range(line1, line2 + 1))
        if text_radio.isChecked():
            insert_values = [value for _ in targets]
        if len(insert_values) < len(targets):
            insert_values.extend([insert_values[-1]] * (len(targets) - len(insert_values)))

        for idx, line_no in enumerate(targets):
            line = lines[line_no]
            if col1 > len(line):
                line = line + (" " * (col1 - len(line)))
            insert_text = insert_values[idx]
            lines[line_no] = line[:col1] + insert_text + line[col1:]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_character_panel(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Character Panel")
        dlg.resize(520, 420)
        layout = QVBoxLayout(dlg)
        table = QTableWidget(dlg)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Value", "Hex", "Character"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        rows = list(range(32, 127))
        table.setRowCount(len(rows))
        for row_idx, value in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(str(value)))
            table.setItem(row_idx, 1, QTableWidgetItem(f"{value:02X}"))
            table.setItem(row_idx, 2, QTableWidgetItem(chr(value)))
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(dlg)
        insert_btn = buttons.addButton("Insert", QDialogButtonBox.AcceptRole)
        copy_btn = buttons.addButton("Copy", QDialogButtonBox.ActionRole)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        layout.addWidget(buttons)

        def _selected_char() -> str:
            row = table.currentRow()
            if row < 0:
                return ""
            item = table.item(row, 2)
            return item.text() if item is not None else ""

        def _insert() -> None:
            ch = _selected_char()
            if not ch:
                return
            tab.text_edit.insert_text(ch)
            dlg.accept()

        def _copy() -> None:
            ch = _selected_char()
            if ch:
                QApplication.clipboard().setText(ch)

        insert_btn.clicked.connect(_insert)
        copy_btn.clicked.connect(_copy)
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def _edit_replace_selection_or_all(self, transform) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        if tab.text_edit.has_selection():
            source = tab.text_edit.selected_text()
            tab.text_edit.replace_selection(transform(source))
            return
        source = tab.text_edit.get_text()
        tab.text_edit.set_text(transform(source))
        tab.text_edit.set_modified(True)

    def edit_convert_uppercase(self) -> None:
        self._edit_replace_selection_or_all(lambda s: s.upper())

    def edit_convert_lowercase(self) -> None:
        self._edit_replace_selection_or_all(lambda s: s.lower())

    def edit_convert_proper_case(self) -> None:
        self._edit_replace_selection_or_all(lambda s: " ".join(word.capitalize() for word in s.split(" ")))

    def edit_convert_sentence_case(self) -> None:
        def _sentence(s: str) -> str:
            parts = re.split(r"([.!?]\s+)", s)
            out: list[str] = []
            for idx in range(0, len(parts), 2):
                seg = parts[idx].strip()
                sep = parts[idx + 1] if idx + 1 < len(parts) else ""
                out.append((seg[:1].upper() + seg[1:].lower()) if seg else seg)
                out.append(sep)
            return "".join(out)

        self._edit_replace_selection_or_all(_sentence)

    def edit_convert_invert_case(self) -> None:
        def _invert(s: str) -> str:
            return "".join(ch.lower() if ch.isupper() else ch.upper() if ch.islower() else ch for ch in s)

        self._edit_replace_selection_or_all(_invert)

    def edit_convert_random_case(self) -> None:
        def _random_case(s: str) -> str:
            return "".join(ch.upper() if ch.isalpha() and random.random() > 0.5 else ch.lower() if ch.isalpha() else ch for ch in s)

        self._edit_replace_selection_or_all(_random_case)

    def _edit_line_bounds(self) -> tuple[int, int]:
        tab = self.active_tab()
        if tab is None:
            return 0, 0
        line, _col = tab.text_edit.cursor_position()
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return 0, 0
        line = max(0, min(len(lines) - 1, line))
        return line, len(lines)

    def _edit_selected_line_range(self) -> tuple[int, int]:
        tab = self.active_tab()
        if tab is None:
            return 0, -1
        selection = tab.text_edit.selection_range()
        if selection is None:
            line, _col = tab.text_edit.cursor_position()
            return line, line
        line1, _c1, line2, c2 = selection
        if line2 < line1:
            line1, line2 = line2, line1
        if line2 > line1 and c2 == 0:
            line2 -= 1
        return line1, line2

    def edit_indent_selection(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        line1, line2 = self._edit_selected_line_range()
        if line2 < line1:
            return
        tab_width = int(self.settings.get("tab_width", 4) or 4)
        indent = " " * max(1, tab_width)
        for idx in range(line1, min(line2, len(lines) - 1) + 1):
            lines[idx] = indent + lines[idx]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_unindent_selection(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        line1, line2 = self._edit_selected_line_range()
        if line2 < line1:
            return
        tab_width = int(self.settings.get("tab_width", 4) or 4)
        for idx in range(line1, min(line2, len(lines) - 1) + 1):
            line = lines[idx]
            if line.startswith("\t"):
                lines[idx] = line[1:]
                continue
            if line.startswith(" "):
                trim = min(tab_width, len(line) - len(line.lstrip(" ")))
                lines[idx] = line[trim:]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def _text_eol_mode(self, text: str) -> str:
        if hasattr(self, "_detect_eol_mode"):
            try:
                return self._detect_eol_mode(text)
            except Exception:
                pass
        if "\r\n" in text:
            return "CRLF"
        if "\n" in text:
            return "LF"
        return "LF"

    def edit_trim_trailing_spaces(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        trimmed_lines = [re.sub(r"[ \t]+$", "", line) for line in lines]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        if trimmed != text:
            tab.text_edit.set_text(trimmed)
            tab.text_edit.set_modified(True)
            self.show_status_message("Trimmed trailing spaces.", 2500)

    def edit_trim_leading_spaces(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        trimmed_lines = [re.sub(r"^[ \t]+", "", line) for line in lines]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        if trimmed != text:
            tab.text_edit.set_text(trimmed)
            tab.text_edit.set_modified(True)
            self.show_status_message("Trimmed leading spaces.", 2500)

    def edit_remove_leading_blank_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx <= 0:
            return
        trimmed_lines = lines[idx:]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        tab.text_edit.set_text(trimmed)
        tab.text_edit.set_modified(True)
        self.show_status_message("Removed leading blank lines.", 2500)

    def edit_remove_trailing_blank_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        idx = len(lines) - 1
        while idx >= 0 and not lines[idx].strip():
            idx -= 1
        if idx >= len(lines) - 1:
            return
        trimmed_lines = lines[: idx + 1]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        tab.text_edit.set_text(trimmed)
        tab.text_edit.set_modified(True)
        self.show_status_message("Removed trailing blank lines.", 2500)

    def edit_begin_end_select(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        anchor = getattr(self, "_begin_select_anchor", None)
        if anchor is None:
            self._begin_select_anchor = (tab.text_edit.cursor_position(), False)
            self.show_status_message("Selection start set.", 1500)
            return
        (line, col), _column = anchor
        cur_line, cur_col = tab.text_edit.cursor_position()
        tab.text_edit.set_selection_by_index(
            tab.text_edit.index_from_line_col(line, col),
            tab.text_edit.index_from_line_col(cur_line, cur_col),
        )
        self._begin_select_anchor = None

    def edit_begin_end_select_column(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.text_edit.is_scintilla:
            return
        anchor = getattr(self, "_begin_select_anchor", None)
        if anchor is None:
            self._begin_select_anchor = (tab.text_edit.cursor_position(), True)
            self.show_status_message("Column selection start set.", 1500)
            return
        (line, col), is_column = anchor
        cur_line, cur_col = tab.text_edit.cursor_position()
        if is_column and not tab.column_mode:
            tab.column_mode = True
            if hasattr(self, "column_mode_action"):
                self.column_mode_action.blockSignals(True)
                self.column_mode_action.setChecked(True)
                self.column_mode_action.blockSignals(False)
            tab.text_edit.set_column_mode(True)
        if tab.text_edit.is_scintilla and hasattr(tab.text_edit.widget, "setSelection"):
            tab.text_edit.widget.setSelection(line, col, cur_line, cur_col)
            tab.text_edit.widget.setCursorPosition(cur_line, cur_col)
        else:
            tab.text_edit.set_selection_by_index(
                tab.text_edit.index_from_line_col(line, col),
                tab.text_edit.index_from_line_col(cur_line, cur_col),
            )
        self._begin_select_anchor = None

    def edit_line_duplicate_current(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, total = self._edit_line_bounds()
        if total <= 0:
            return
        lines = tab.text_edit.get_text().splitlines()
        lines.insert(line + 1, lines[line])
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_join_selected(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if selected.strip():
            tab.text_edit.replace_selection(" ".join(selected.splitlines()))
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line >= total - 1:
            return
        lines[line] = f"{lines[line].rstrip()} {lines[line + 1].lstrip()}".strip()
        del lines[line + 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_split_selected(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if not selected.strip():
            return
        tab.text_edit.replace_selection("\n".join(selected.split()))

    def edit_line_move_up(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line <= 0:
            return
        lines[line - 1], lines[line] = lines[line], lines[line - 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line - 1, 0)

    def edit_line_move_down(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line >= total - 1:
            return
        lines[line + 1], lines[line] = lines[line], lines[line + 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line + 1, 0)

    def edit_line_remove_duplicate_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        seen = set()
        unique: list[str] = []
        for line in tab.text_edit.get_text().splitlines():
            if line in seen:
                continue
            seen.add(line)
            unique.append(line)
        tab.text_edit.set_text("\n".join(unique))
        tab.text_edit.set_modified(True)

    def edit_line_remove_consecutive_duplicate_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        deduped = [lines[0]]
        for line in lines[1:]:
            if line != deduped[-1]:
                deduped.append(line)
        tab.text_edit.set_text("\n".join(deduped))
        tab.text_edit.set_modified(True)

    def edit_line_insert_blank_above(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 0:
            lines = [""]
            line = 0
        else:
            lines.insert(line, "")
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line, 0)

    def edit_line_insert_blank_below(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 0:
            lines = [""]
            line = 0
        else:
            lines.insert(line + 1, "")
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line + 1, 0)

    def edit_line_remove_empty(self, include_whitespace: bool = True) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if include_whitespace:
            lines = [line for line in lines if line.strip()]
        else:
            lines = [line for line in lines if line != ""]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_reverse(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        lines.reverse()
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_sort(self, ascending: bool = True, ignore_case: bool = False) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        key = (lambda s: s.lower()) if ignore_case else (lambda s: s)
        lines = sorted(lines, key=key, reverse=not ascending)
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def _line_comment_prefix(self) -> str:
        tab = self.active_tab()
        lang = self._detect_language_for_tab(tab) if tab is not None else "plain"
        if lang in {"python", "markdown", "yaml", "toml"}:
            return "# "
        if lang in {"javascript", "json", "css", "typescript"}:
            return "// "
        return "# "

    def edit_single_line_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        prefix = self._line_comment_prefix()
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line)
        tab.text_edit.replace_line(line, prefix + current)
        tab.text_edit.set_modified(True)

    def edit_single_line_uncomment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line)
        for marker in ("# ", "// ", "#", "//"):
            stripped = current.lstrip()
            if stripped.startswith(marker):
                lead = current[: len(current) - len(stripped)]
                current = lead + stripped[len(marker) :]
                break
        tab.text_edit.replace_line(line, current)
        tab.text_edit.set_modified(True)

    def edit_toggle_single_line_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line).lstrip()
        if current.startswith(("#", "//")):
            self.edit_single_line_uncomment()
        else:
            self.edit_single_line_comment()

    def edit_block_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only() or not tab.text_edit.has_selection():
            return
        selected = tab.text_edit.selected_text()
        tab.text_edit.replace_selection(f"/* {selected} */")
        tab.text_edit.set_modified(True)

    def edit_block_uncomment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if selected.strip().startswith("/*") and selected.strip().endswith("*/"):
            stripped = selected.strip()[2:-2].strip()
            tab.text_edit.replace_selection(stripped)
            tab.text_edit.set_modified(True)

    def edit_set_eol_mac(self) -> None:
        self.set_tab_eol_mode("CR")

    def edit_open_selection_file(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        candidate = tab.text_edit.selected_text().strip().strip("\"'")
        if not candidate:
            return
        path = Path(candidate)
        if path.exists() and path.is_file():
            self._open_file_path(str(path))

    def edit_open_selection_folder(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        candidate = tab.text_edit.selected_text().strip().strip("\"'")
        if not candidate:
            return
        path = Path(candidate)
        folder = path.parent if path.is_file() else path
        if folder.exists() and folder.is_dir():
            os.startfile(str(folder))  # type: ignore[attr-defined]

    def edit_search_selection_internet(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        query = tab.text_edit.selected_text().strip() or self.last_search_text or ""
        if not query:
            return
        webbrowser.open(f"https://www.bing.com/search?q={quote_plus(query)}")

    def edit_toggle_read_only_current(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        next_state = not bool(tab.read_only)
        if tab.current_file and hasattr(self, "_set_file_read_only"):
            self._set_file_read_only(tab.current_file, next_state)
        tab.read_only = next_state
        tab.text_edit.set_read_only(next_state)
        self._refresh_tab_title(tab)
        self.update_action_states()

    def edit_toggle_read_only_all(self) -> None:
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file and hasattr(self, "_set_file_read_only"):
                self._set_file_read_only(tab.current_file, True)
            tab.read_only = True
            tab.text_edit.set_read_only(True)
            self._refresh_tab_title(tab)
        self.update_action_states()

    def edit_clear_read_only_all(self) -> None:
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file and hasattr(self, "_set_file_read_only"):
                self._set_file_read_only(tab.current_file, False)
            tab.read_only = False
            tab.text_edit.set_read_only(False)
            self._refresh_tab_title(tab)
        self.update_action_states()

    def _capture_clipboard_history(self) -> None:
        clip = QApplication.clipboard()
        if clip is None:
            return
        text = (clip.text() or "").strip()
        if not text:
            return
        history = getattr(self, "_clipboard_history", None)
        if not isinstance(history, list):
            history = []
        if history and history[0] == text:
            return
        history.insert(0, text)
        self._clipboard_history = history[:100]

    def show_clipboard_history(self) -> None:
        history = getattr(self, "_clipboard_history", [])
        if not isinstance(history, list):
            history = []
        dlg = QDialog(self)
        dlg.setWindowTitle("Clipboard History")
        dlg.resize(760, 420)
        lay = QVBoxLayout(dlg)
        table = QTableWidget(dlg)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["#", "Text"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setRowCount(len(history))
        for idx, value in enumerate(history):
            table.setItem(idx, 0, QTableWidgetItem(str(idx + 1)))
            preview = value if len(value) <= 500 else (value[:497] + "...")
            table.setItem(idx, 1, QTableWidgetItem(preview))
        table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(table, 1)
        buttons = QDialogButtonBox(dlg)
        paste_btn = buttons.addButton("Paste Selected", QDialogButtonBox.AcceptRole)
        copy_btn = buttons.addButton("Copy Selected", QDialogButtonBox.ActionRole)
        clear_btn = buttons.addButton("Clear History", QDialogButtonBox.DestructiveRole)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        lay.addWidget(buttons)

        def _selected_text() -> str:
            row = table.currentRow()
            if row < 0 or row >= len(history):
                return ""
            return str(history[row])

        def _paste() -> None:
            text = _selected_text()
            if not text:
                return
            tab = self.active_tab()
            if tab is None or tab.text_edit.is_read_only():
                return
            tab.text_edit.insert_text(text)
            dlg.accept()

        def _copy() -> None:
            text = _selected_text()
            if text:
                QApplication.clipboard().setText(text)

        def _clear() -> None:
            self._clipboard_history = []
            table.setRowCount(0)

        paste_btn.clicked.connect(_paste)
        copy_btn.clicked.connect(_copy)
        clear_btn.clicked.connect(_clear)
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def _set_breadcrumb_text(self, text: str) -> None:
        if hasattr(self, "breadcrumb_label") and self.breadcrumb_label is not None:
            self.breadcrumb_label.setText(text)

    def open_plugin_manager(self) -> None:
        self.advanced_features.open_plugin_manager()

    def open_plugins_folder(self) -> None:
        plugins_dir = Path(getattr(self.advanced_features.plugin_host, "plugins_dir", Path(__file__).resolve().parents[4] / "plugins"))
        plugins_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(plugins_dir))  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open Plugins Folder", f"Could not open folder:\n{exc}")

    def open_mime_tools(self) -> None:
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "MIME Tools", "Open a tab first.")
            return
        source = tab.text_edit.selected_text() or tab.text_edit.get_text()
        if not source:
            QMessageBox.information(self, "MIME Tools", "Nothing to process.")
            return
        options = [
            "Base64 Encode",
            "Base64 Decode",
            "URL Encode",
            "URL Decode",
            "Hex Encode",
            "Hex Decode",
        ]
        choice, ok = QInputDialog.getItem(self, "MIME Tools", "Operation:", options, 0, False)
        if not ok or not choice:
            return
        try:
            if choice == "Base64 Encode":
                result = base64.b64encode(source.encode("utf-8")).decode("ascii")
            elif choice == "Base64 Decode":
                result = base64.b64decode(source.encode("ascii"), validate=False).decode("utf-8", errors="replace")
            elif choice == "URL Encode":
                result = url_quote(source)
            elif choice == "URL Decode":
                result = url_unquote(source)
            elif choice == "Hex Encode":
                result = source.encode("utf-8").hex()
            else:  # Hex Decode
                result = bytes.fromhex(source.strip()).decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "MIME Tools", f"Conversion failed:\n{exc}")
            return
        if tab.text_edit.has_selection():
            tab.text_edit.replace_selection(result)
        else:
            tab.text_edit.set_text(result)
            tab.text_edit.set_modified(True)
        self.show_status_message("MIME tools conversion applied.", 2500)

    def open_converter_tools(self) -> None:
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "Converter", "Open a tab first.")
            return
        source = tab.text_edit.selected_text() or tab.text_edit.get_text()
        if not source:
            QMessageBox.information(self, "Converter", "Nothing to convert.")
            return
        options = [
            "UPPERCASE",
            "lowercase",
            "Title Case",
            "Indent JSON (Pretty)",
            "Compact JSON",
            "Convert EOL to LF",
            "Convert EOL to CRLF",
        ]
        choice, ok = QInputDialog.getItem(self, "Converter", "Operation:", options, 0, False)
        if not ok or not choice:
            return
        try:
            if choice == "UPPERCASE":
                result = source.upper()
            elif choice == "lowercase":
                result = source.lower()
            elif choice == "Title Case":
                result = source.title()
            elif choice == "Indent JSON (Pretty)":
                result = json.dumps(json.loads(source), indent=2, ensure_ascii=False)
            elif choice == "Compact JSON":
                result = json.dumps(json.loads(source), separators=(",", ":"), ensure_ascii=False)
            elif choice == "Convert EOL to LF":
                result = source.replace("\r\n", "\n").replace("\r", "\n")
            else:  # Convert EOL to CRLF
                result = source.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Converter", f"Conversion failed:\n{exc}")
            return
        if tab.text_edit.has_selection():
            tab.text_edit.replace_selection(result)
        else:
            tab.text_edit.set_text(result)
            tab.text_edit.set_modified(True)
        self.show_status_message("Converter operation applied.", 2500)

    def open_npp_export_tools(self) -> None:
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "NPP Export", "Open a tab first.")
            return
        text = tab.text_edit.get_text()
        if not text:
            QMessageBox.information(self, "NPP Export", "Nothing to export.")
            return
        options = [
            "Export as HTML (with line numbers)",
            "Copy HTML to Clipboard",
            "Export as TXT (line numbers)",
        ]
        choice, ok = QInputDialog.getItem(self, "NPP Export", "Export mode:", options, 0, False)
        if not ok or not choice:
            return

        lines = text.splitlines()
        html_lines = "\n".join(
            f'<span style="color:#888">{i + 1:4d}</span>  {html_escape(line)}'
            for i, line in enumerate(lines)
        )
        html_doc = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{font-family:Consolas,monospace;background:#fff;color:#111;white-space:pre;}</style>"
            "</head><body>"
            f"{html_lines}"
            "</body></html>"
        )
        txt_num = "\n".join(f"{i + 1:4d}  {line}" for i, line in enumerate(lines))

        if choice == "Copy HTML to Clipboard":
            QApplication.clipboard().setText(html_doc)
            self.show_status_message("HTML copied to clipboard.", 2500)
            return

        if choice == "Export as HTML (with line numbers)":
            default_name = (Path(tab.current_file).stem if tab.current_file else "note") + "_npp_export.html"
            path, _ = QFileDialog.getSaveFileName(self, "NPP Export HTML", default_name, "HTML Files (*.html)")
            if not path:
                return
            try:
                Path(path).write_text(html_doc, encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "NPP Export", f"Export failed:\n{exc}")
                return
            self.show_status_message(f"NPP HTML export saved: {path}", 3000)
            return

        default_name = (Path(tab.current_file).stem if tab.current_file else "note") + "_npp_export.txt"
        path, _ = QFileDialog.getSaveFileName(self, "NPP Export TXT", default_name, "Text Files (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(txt_num, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "NPP Export", f"Export failed:\n{exc}")
            return
        self.show_status_message(f"NPP TXT export saved: {path}", 3000)

    def toggle_minimap_panel(self, checked: bool) -> None:
        self.advanced_features.toggle_minimap(checked)

    def toggle_symbol_outline_panel(self, checked: bool) -> None:
        self.advanced_features.toggle_outline(checked)

    def goto_definition_basic(self) -> None:
        self.advanced_features.go_to_definition()

    def open_side_by_side_diff(self) -> None:
        self.advanced_features.open_diff()

    def open_three_way_merge(self) -> None:
        self.advanced_features.open_merge_helper()

    def apply_patch_file_to_active_tab(self) -> None:
        self.advanced_features.apply_patch_file_to_active()

    def load_full_large_file(self) -> None:
        self.load_full_large_file_current_tab()

    def open_snippet_engine(self) -> None:
        self.advanced_features.open_snippets()

    def install_template_packs(self) -> None:
        self.advanced_features.ensure_template_packs()

    def show_task_workflow_panel(self) -> None:
        self.advanced_features.show_tasks()

    def configure_backup_scheduler(self) -> None:
        self.advanced_features.configure_backup()

    def run_backup_now(self) -> None:
        self.advanced_features.backup_now()

    def export_diagnostics_bundle(self) -> None:
        self.advanced_features.export_diagnostics()

    def toggle_keyboard_only_mode(self, checked: bool) -> None:
        self.advanced_features.toggle_keyboard_only(checked)

    def apply_accessibility_high_contrast(self) -> None:
        self.advanced_features.apply_accessibility_high_contrast()

    def apply_accessibility_dyslexic_font(self) -> None:
        self.advanced_features.apply_accessibility_dyslexic()

    def open_lan_collaboration(self) -> None:
        self.advanced_features.open_collaboration()

    def open_annotation_layer(self) -> None:
        self.advanced_features.open_annotations()

    def ai_commit_message_generator(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        prompt = (
            "Write a concise commit message and a changelog entry for this file update.\n\n"
            f"File: {tab.current_file or 'Untitled'}\n\n"
            + tab.text_edit.get_text()[:20000]
        )
        self.ai_controller._start_generation(prompt, "AI Commit + Changelog", action_name="Commit/Changelog Draft")

    def ai_batch_refactor_preview(self) -> None:
        root = self._workspace_root()
        if not root:
            QMessageBox.information(self, "Batch Refactor", "Set a workspace folder first.")
            return
        files = self._workspace_files()[:30]
        if not files:
            QMessageBox.information(self, "Batch Refactor", "No workspace files found.")
            return
        instruction, ok = QInputDialog.getMultiLineText(
            self,
            "Batch AI Refactor",
            "Refactor instruction to apply across files:",
        )
        if not ok or not instruction.strip():
            return
        preview_lines = [f"Instruction: {instruction.strip()}", "", "Planned files:"]
        for p in files:
            preview_lines.append(f"- {p}")
        QMessageBox.information(self, "Batch Refactor Preview", "\n".join(preview_lines[:200]))

    def ai_ask_file_with_citations(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        question, ok = QInputDialog.getMultiLineText(self, "Ask About This File (Citations)", "Question:")
        if not ok or not question.strip():
            return
        numbered = []
        for idx, line in enumerate(tab.text_edit.get_text().splitlines(), start=1):
            numbered.append(f"{idx:04d}: {line}")
        payload = "\n".join(numbered[:1200])
        prompt = (
            "Answer the question using the file content and include citations like [line:123].\n\n"
            f"Question:\n{question.strip()}\n\nFile:\n{payload}"
        )
        self.ai_controller._start_generation(prompt, "AI File Answer + Citations", action_name="Ask File with Citations")

    def ai_inline_edit_with_preview(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        if not source.strip():
            QMessageBox.information(self, "AI Inline Edit", "Current document is empty.")
            return
        selection = tab.text_edit.selected_text()
        if selection.strip():
            sel = tab.text_edit.selection_range()
            if not sel:
                return
            start = tab.text_edit.index_from_line_col(sel[0], sel[1])
            end = tab.text_edit.index_from_line_col(sel[2], sel[3])
            target_text = source[start:end]
            target_label = "selection"
        else:
            start, end = paragraph_bounds(source, tab.text_edit.cursor_index())
            target_text = source[start:end]
            target_label = "current paragraph"
        if not target_text.strip():
            QMessageBox.information(self, "AI Inline Edit", "Select some text or place cursor in a non-empty paragraph.")
            return
        instruction, ok = QInputDialog.getMultiLineText(
            self,
            "AI Inline Edit",
            f"Instruction for {target_label}:",
        )
        if not ok or not instruction.strip():
            return
        prompt = (
            "Apply the instruction to the text and return only the revised text, without commentary.\n\n"
            f"Instruction:\n{instruction.strip()}\n\n"
            f"Text:\n{target_text}"
        )

        def _on_result(result: str) -> None:
            revised = strip_model_fences(result).strip()
            if not revised:
                QMessageBox.information(self, "AI Inline Edit", "AI returned an empty result.")
                return
            dlg = AIEditPreviewDialog(self, target_text, revised, title="AI Inline Edit Preview")
            if dlg.exec() != QDialog.Accepted:
                return
            latest = tab.text_edit.get_text()
            tab.text_edit.set_text(latest[:start] + dlg.final_text + latest[end:])
            tab.text_edit.set_selection_by_index(start, start + len(dlg.final_text))
            tab.text_edit.set_modified(True)
            self.show_status_message("AI inline edit applied.", 3000)

        self.ai_controller._start_generation(
            prompt,
            "AI Inline Edit",
            action_name="AI Inline Edit",
            on_result=_on_result,
        )

    def ai_ask_workspace_with_citations(self) -> None:
        root = self._workspace_root()
        if not root:
            QMessageBox.information(self, "Workspace Q&A", "Set a workspace folder first.")
            return
        question, ok = QInputDialog.getMultiLineText(self, "Ask Workspace (Citations)", "Question:")
        if not ok or not question.strip():
            return
        files = self._workspace_files()
        if not files:
            QMessageBox.information(self, "Workspace Q&A", "No workspace files found.")
            return
        snippets = build_workspace_citation_snippets(
            question.strip(),
            files,
            max_files=int(self.settings.get("ai_workspace_qa_max_files", 10) or 10),
            max_lines_per_file=int(self.settings.get("ai_workspace_qa_max_lines_per_file", 60) or 60),
            max_total_chars=30000,
        )
        if not snippets:
            QMessageBox.information(self, "Workspace Q&A", "No matching file excerpts found for this question.")
            return
        prompt = build_project_qa_prompt(question.strip(), snippets)
        self.ai_controller._start_generation(
            prompt,
            "AI Workspace Answer + Citations",
            action_name="Ask Workspace with Citations",
        )

    def show_collaboration_presence(self) -> None:
        snapshot = self.advanced_features.collaboration_snapshot()
        QMessageBox.information(self, "Collaboration Presence", build_collab_presence_text(snapshot))

    def resolve_collaboration_conflict(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        snapshot = self.advanced_features.collaboration_snapshot()
        if not bool(snapshot.get("running", False)):
            QMessageBox.information(self, "Collaboration Conflict", "Collaboration server is not running.")
            return
        local_text = tab.text_edit.get_text()
        shared_text = self.advanced_features.collaboration_shared_text()
        if local_text == shared_text:
            QMessageBox.information(self, "Collaboration Conflict", "Local and shared text are already in sync.")
            return
        options = [
            "Open Merge Markers Preview",
            "Use Shared Version",
            "Push Local Version to Shared",
            "AI Merge Draft (Preview)",
        ]
        choice, ok = QInputDialog.getItem(self, "Resolve Collaboration Conflict", "Strategy:", options, 0, False)
        if not ok or not choice:
            return

        def _apply_and_optionally_push(merged_text: str, push: bool = False) -> None:
            tab.text_edit.set_text(merged_text)
            tab.text_edit.set_modified(True)
            if push:
                self.advanced_features.collaboration_set_shared_text(merged_text, source="host-local")
            self.show_status_message("Collaboration conflict resolution applied.", 3200)

        if choice == "Use Shared Version":
            _apply_and_optionally_push(shared_text, push=False)
            return
        if choice == "Push Local Version to Shared":
            _apply_and_optionally_push(local_text, push=True)
            return
        if choice == "Open Merge Markers Preview":
            merged = build_conflict_markers(local_text, shared_text)
            dlg = AIEditPreviewDialog(self, local_text, merged, title="Collaboration Merge Markers Preview")
            if dlg.exec() == QDialog.Accepted:
                _apply_and_optionally_push(dlg.final_text, push=False)
            return
        if choice == "AI Merge Draft (Preview)":
            prompt = build_ai_conflict_merge_prompt(local_text, shared_text)

            def _on_merge_result(result: str) -> None:
                merged = strip_model_fences(result).strip()
                if not merged:
                    QMessageBox.information(self, "AI Merge Draft", "AI returned an empty merge result.")
                    return
                dlg = AIEditPreviewDialog(self, local_text, merged, title="AI Collaboration Merge Preview")
                if dlg.exec() != QDialog.Accepted:
                    return
                push = QMessageBox.question(
                    self,
                    "Push Merge to Shared?",
                    "Apply merged text locally and push to collaboration shared state?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                _apply_and_optionally_push(dlg.final_text, push=(push == QMessageBox.Yes))

            self.ai_controller._start_generation(
                prompt,
                "AI Collaboration Merge",
                action_name="AI Collaboration Merge",
                on_result=_on_merge_result,
            )

    def record_ai_usage(self, *, tokens: int, estimated_cost: float) -> None:
        usage = getattr(self, "ai_usage_session", None)
        if not isinstance(usage, dict):
            usage = {"requests": 0, "tokens": 0, "estimated_cost": 0.0}
            self.ai_usage_session = usage
        usage["requests"] = int(usage.get("requests", 0)) + 1
        usage["tokens"] = int(usage.get("tokens", 0)) + max(0, int(tokens))
        usage["estimated_cost"] = float(usage.get("estimated_cost", 0.0)) + max(0.0, float(estimated_cost))
        self._refresh_ai_usage_label()

    def _refresh_ai_usage_label(self) -> None:
        label = getattr(self, "ai_usage_label", None)
        usage = getattr(self, "ai_usage_session", {})
        if label is None or not isinstance(usage, dict):
            return
        requests = int(usage.get("requests", 0))
        tokens = int(usage.get("tokens", 0))
        cost = float(usage.get("estimated_cost", 0.0))
        label.setText(f"AI: {requests} req | ~{tokens} tok | ~${cost:.4f}")

    def _ai_templates(self) -> dict[str, str]:
        templates = self.settings.get("ai_prompt_templates", {})
        if not isinstance(templates, dict):
            templates = {}
        defaults = {
            "Explain selection": "Explain this clearly:\n\n{selection}",
            "Summarize file": "Summarize this file with key points and action items:\n\n{file_text}",
            "Code review notes": "Review this file for bugs and risks:\n\n{file_text}",
        }
        merged = dict(defaults)
        for key, value in templates.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                merged[key.strip()] = value
        return merged

    def open_command_palette(self) -> None:
        actions: list[PaletteItem] = []
        for entry in discover_window_actions(self):
            actions.append(
                PaletteItem(
                    label=entry.label,
                    section=entry.section,
                    action=entry.action,
                    shortcut=entry.shortcut_text,
                    keywords=f"{entry.action_id} {entry.section}",
                )
            )
        dialog = CommandPaletteDialog(self, actions)
        if dialog.exec() != QDialog.Accepted or dialog.selected_action is None:
            return
        dialog.selected_action.trigger()

    def ai_rewrite_selection(self, mode: str) -> None:
        self.ai_controller.rewrite_selection(mode)

    def ask_ai_about_current_context(self) -> None:
        self.ai_controller.ask_about_context()

    def run_ai_prompt_template(self) -> None:
        templates = self._ai_templates()
        names = sorted(templates.keys())
        if not names:
            QMessageBox.information(self, "AI Templates", "No templates available.")
            return
        name, ok = QInputDialog.getItem(self, "AI Prompt Templates", "Template:", names, 0, False)
        if not ok or not name:
            return
        template = templates.get(name, "")
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "AI Templates", "Open a tab first.")
            return
        text = tab.text_edit.get_text()
        selection = tab.text_edit.selected_text() or text[:5000]
        rendered = (
            template.replace("{selection}", selection)
            .replace("{file_text}", text[:20000])
            .replace("{file_name}", tab.current_file or "Untitled")
        )
        self.ai_controller._start_generation(rendered, f"Template: {name}", action_name=f"Template: {name}")

    def save_ai_prompt_template(self) -> None:
        name, ok = QInputDialog.getText(self, "Save AI Template", "Template name:")
        if not ok or not name.strip():
            return
        body, ok = QInputDialog.getMultiLineText(
            self,
            "Save AI Template",
            "Template body (use {selection}, {file_text}, {file_name}):",
        )
        if not ok or not body.strip():
            return
        templates = self.settings.get("ai_prompt_templates", {})
        if not isinstance(templates, dict):
            templates = {}
        templates[name.strip()] = body.strip()
        self.settings["ai_prompt_templates"] = templates
        self.save_settings_to_disk()
        self.show_status_message(f'Saved AI template "{name.strip()}".', 3000)

    def show_ai_action_history(self) -> None:
        history = self.settings.get("ai_action_history", [])
        if not isinstance(history, list):
            history = []
        if not history:
            QMessageBox.information(self, "AI Action History", "No AI actions recorded yet.")
            return
        lines: list[str] = []
        for row in history[-120:]:
            if not isinstance(row, dict):
                continue
            ts = str(row.get("timestamp", ""))
            action = str(row.get("action", "AI"))
            model = str(row.get("model", ""))
            p = int(row.get("prompt_chars", 0) or 0)
            r = int(row.get("response_chars", 0) or 0)
            lines.append(f"{ts} | {action} | {model} | prompt={p} chars | response={r} chars")
        dlg = QDialog(self)
        dlg.setWindowTitle("AI Action History")
        dlg.resize(780, 480)
        v = QVBoxLayout(dlg)
        view = QTextEdit(dlg)
        view.setReadOnly(True)
        view.setPlainText("\n".join(lines))
        v.addWidget(view)
        btn = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        btn.rejected.connect(dlg.reject)
        btn.accepted.connect(dlg.accept)
        v.addWidget(btn)
        dlg.exec()

    def show_ai_usage_summary(self) -> None:
        usage = getattr(self, "ai_usage_session", {})
        requests = int(usage.get("requests", 0))
        tokens = int(usage.get("tokens", 0))
        cost = float(usage.get("estimated_cost", 0.0))
        QMessageBox.information(
            self,
            "AI Usage Summary",
            f"Session requests: {requests}\nEstimated tokens: {tokens}\nEstimated cost: ${cost:.4f}",
        )

    def toggle_ai_private_mode(self, checked: bool) -> None:
        self.settings["ai_private_mode"] = bool(checked)
        if checked:
            self.toggle_ai_chat_panel(False)
            self.show_status_message("AI private mode enabled (AI actions disabled).", 3000)
        else:
            self.show_status_message("AI private mode disabled.", 3000)
        self.save_settings_to_disk()
        self.update_action_states()

    def toggle_simple_mode(self, checked: bool) -> None:
        self.settings["simple_mode"] = bool(checked)
        if checked:
            self.menuBar().setVisible(True)
            if hasattr(self, "markdown_menu"):
                self.markdown_menu.menuAction().setVisible(False)
            if hasattr(self, "macros_menu"):
                self.macros_menu.menuAction().setVisible(False)
            if hasattr(self, "search_toolbar"):
                self.search_toolbar.hide()
            self.settings["show_find_panel"] = False
            self.settings["show_markdown_toolbar"] = False
        else:
            if hasattr(self, "markdown_menu"):
                self.markdown_menu.menuAction().setVisible(True)
            if hasattr(self, "macros_menu"):
                self.macros_menu.menuAction().setVisible(True)
        self._layout_top_toolbars()
        self.save_settings_to_disk()

    def apply_reading_preset(self) -> None:
        self.settings["font_size"] = 15
        self.settings["word_wrap"] = True
        self.word_wrap_enabled = True
        self.word_wrap_action.setChecked(True)
        self.apply_settings()
        self.show_status_message("Applied Reading preset.", 2500)

    def apply_coding_preset(self) -> None:
        self.settings["font_size"] = 12
        self.settings["tab_width"] = 4
        self.word_wrap_enabled = False
        self.word_wrap_action.setChecked(False)
        self.apply_settings()
        self.show_status_message("Applied Coding preset.", 2500)

    def apply_focus_preset(self) -> None:
        self.focus_mode_action.setChecked(True)
        self.toggle_focus_mode(True)
        self.show_status_message("Applied Focus preset.", 2500)

    def toggle_ai_chat_panel(self, checked: bool | None = None) -> None:
        if not hasattr(self, "ai_chat_dock"):
            return
        desired = not self.ai_chat_dock.isVisible() if checked is None else bool(checked)
        self.ai_chat_dock.setVisible(desired)
        if desired:
            self.ai_chat_dock.raise_()
            self.ai_chat_dock.focus_prompt()
        if hasattr(self, "ai_chat_panel_action"):
            self.ai_chat_panel_action.blockSignals(True)
            self.ai_chat_panel_action.setChecked(desired)
            self.ai_chat_panel_action.blockSignals(False)

    def explain_selection_with_ai(self) -> None:
        self.ai_controller.explain_selection()

    def generate_text_to_tab_with_ai(self) -> None:
        self.ai_controller.generate_to_tab()

    def check_for_updates(self, manual: bool = True) -> None:
        self.updater_controller.check_for_updates(manual=manual)

    def _sort_tabs_by_pinned(self) -> None:
        tabs: list[EditorTab] = []
        for index in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(index)
            if isinstance(widget, EditorTab):
                tabs.append(widget)
        if len(tabs) < 2:
            return
        current = self.active_tab()
        ordered = sorted(tabs, key=lambda t: (not t.pinned, not t.favorite, self._tab_display_name(t).lower()))
        if ordered == tabs:
            return
        while self.tab_widget.count():
            self.tab_widget.removeTab(0)
        for tab in ordered:
            self.tab_widget.addTab(tab, self._tab_display_name(tab))
            self._refresh_tab_title(tab)
        if current is not None:
            self.tab_widget.setCurrentWidget(current)

    def _ensure_tab_autosave_meta(self, tab: EditorTab) -> None:
        if tab.autosave_id:
            return
        tab.autosave_id = self.autosave_store.new_id()
        tab.autosave_path = str(self.autosave_store.autosave_file(tab.autosave_id))

    def _local_history_cache(self) -> dict[str, list[dict[str, str]]]:
        if not self.settings.get("local_history_persist_enabled", True):
            return {}
        cache = getattr(self, "_local_history_index_cache", None)
        if isinstance(cache, dict):
            return cache
        store = getattr(self, "recovery_state_store", None)
        if store is None:
            cache = {}
        else:
            cache = store.load_local_history()
        self._local_history_index_cache = cache
        return cache

    def _restore_tab_local_history(self, tab: EditorTab) -> None:
        if not self.settings.get("local_history_persist_enabled", True):
            return
        try:
            key = local_history_key(tab.current_file, tab.autosave_id, self._tab_display_name(tab))
            rows = self._local_history_cache().get(key, [])
            if not rows:
                return
            max_entries = int(self.settings.get("version_history_max_entries", 50))
            rebuilt: list[VersionEntry] = []
            for row in rows[-max_entries:]:
                rebuilt.append(
                    VersionEntry(
                        timestamp=str(row.get("timestamp", "")),
                        label=str(row.get("label", "Snapshot")),
                        text=str(row.get("text", "")),
                    )
                )
            if rebuilt:
                tab.version_history.entries = rebuilt
        except Exception:
            return

    def _persist_tab_local_history(self, tab: EditorTab) -> None:
        if not self.settings.get("local_history_persist_enabled", True):
            return
        entries = getattr(tab.version_history, "entries", [])
        if not entries:
            return
        key = local_history_key(tab.current_file, tab.autosave_id, self._tab_display_name(tab))
        payload: list[dict[str, str]] = []
        max_entries = int(self.settings.get("version_history_max_entries", 50))
        for entry in entries[-max_entries:]:
            payload.append(
                {
                    "timestamp": str(getattr(entry, "timestamp", "")),
                    "label": str(getattr(entry, "label", "Snapshot")),
                    "text": str(getattr(entry, "text", "")),
                }
            )
        if not payload:
            return
        cache = self._local_history_cache()
        cache[key] = payload
        store = getattr(self, "recovery_state_store", None)
        if store is not None:
            store.save_local_history(cache)

    def _capture_crash_snapshot(self) -> None:
        store = getattr(self, "recovery_state_store", None)
        if not self.settings.get("crash_snapshot_enabled", True):
            if store is not None:
                store.clear_crash_snapshot()
            return
        if store is None:
            return
        tabs_payload: list[dict[str, str]] = []
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if not isinstance(tab, EditorTab):
                continue
            if not tab.text_edit.is_modified():
                continue
            tabs_payload.append(
                {
                    "title": self._tab_display_name(tab),
                    "original_path": str(tab.current_file or ""),
                    "text": tab.text_edit.get_text(),
                    "autosave_id": str(tab.autosave_id or ""),
                }
            )
        if not tabs_payload:
            store.clear_crash_snapshot()
            return
        active = self.active_tab()
        active_file = str(active.current_file if active is not None and active.current_file else "")
        store.save_crash_snapshot(
            tabs=tabs_payload,
            active_file=active_file,
            workspace_root=str(self.settings.get("workspace_root", "") or ""),
        )

    def _restore_from_snapshot_payload(self, payload: dict[str, object]) -> int:
        raw_tabs = payload.get("tabs", [])
        if not isinstance(raw_tabs, list):
            return 0
        restored = 0
        selected_active_path = str(payload.get("active_file", "") or "")
        for row in raw_tabs:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text", ""))
            if not text:
                continue
            original_path = str(row.get("original_path", "") or "")
            path_for_tab = original_path if original_path else None
            tab = self.add_new_tab(text=text, file_path=path_for_tab, make_current=False)
            tab.text_edit.set_modified(True)
            tab.autosave_id = str(row.get("autosave_id", "") or "") or tab.autosave_id
            if tab.autosave_id:
                tab.autosave_path = str(self.autosave_store.autosave_file(tab.autosave_id))
            self._seed_version_history(tab, label="Recovered Snapshot")
            self._apply_file_metadata_to_tab(tab)
            restored += 1
        if restored:
            workspace_root = str(payload.get("workspace_root", "") or "")
            if workspace_root and Path(workspace_root).exists():
                self.settings["workspace_root"] = workspace_root
            if selected_active_path:
                for index in range(self.tab_widget.count()):
                    tab = self.tab_widget.widget(index)
                    if isinstance(tab, EditorTab) and tab.current_file == selected_active_path:
                        self.tab_widget.setCurrentIndex(index)
                        break
            self.update_window_title()
            self.update_status_bar()
        return restored

    def _run_autosave_cycle(self) -> None:
        if not self.settings.get("autosave_enabled", True):
            return
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if not isinstance(tab, EditorTab):
                continue
            if tab.large_file:
                continue
            if not tab.text_edit.is_modified():
                if tab.autosave_id:
                    self._clear_tab_autosave(tab)
                continue
            self._ensure_tab_autosave_meta(tab)
            if not tab.autosave_id or not tab.autosave_path:
                continue
            try:
                autosave_file = Path(tab.autosave_path)
                autosave_file.parent.mkdir(parents=True, exist_ok=True)
                autosave_file.write_text(tab.text_edit.get_text(), encoding="utf-8")
                self.autosave_store.upsert(
                    autosave_id=tab.autosave_id,
                    autosave_path=tab.autosave_path,
                    original_path=tab.current_file or "",
                    title=self._tab_display_name(tab),
                )
                if hasattr(self, "_persist_tab_local_history"):
                    self._persist_tab_local_history(tab)
            except Exception:
                continue
        self.autosave_store.save()
        self._capture_crash_snapshot()

    def _clear_tab_autosave(self, tab: EditorTab) -> None:
        if not tab.autosave_id:
            return
        if tab.autosave_path:
            try:
                path = Path(tab.autosave_path)
                if path.exists():
                    path.unlink()
            except Exception:
                pass
        self.autosave_store.remove(tab.autosave_id)
        self.autosave_store.save()
        tab.autosave_id = None
        tab.autosave_path = None

    def _offer_crash_recovery(self) -> None:
        discard_days = int(self.settings.get("recovery_discard_after_days", 14))
        try:
            self.autosave_store.prune_older_than_days(discard_days)
            self.autosave_store.save()
        except Exception:
            pass
        store = getattr(self, "recovery_state_store", None)
        if store is not None and self.settings.get("local_history_persist_enabled", True):
            try:
                store.prune_local_history(800, int(self.settings.get("version_history_max_entries", 50)))
            except Exception:
                pass
        mode = str(self.settings.get("recovery_mode", "ask") or "ask")
        entries = list(self.autosave_store.entries.values())
        snapshot_payload = (
            store.load_crash_snapshot()
            if (store is not None and self.settings.get("crash_snapshot_enabled", True))
            else None
        )
        has_snapshot_tabs = bool(snapshot_payload and isinstance(snapshot_payload.get("tabs", []), list) and snapshot_payload.get("tabs"))
        if not entries and not has_snapshot_tabs:
            return
        if mode == "auto_discard":
            for entry in entries:
                try:
                    path = Path(entry.autosave_path)
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass
                self.autosave_store.remove(entry.autosave_id)
            self.autosave_store.save()
            if store is not None:
                store.clear_crash_snapshot()
            return
        if mode == "auto_restore":
            for entry in entries:
                try:
                    text = Path(entry.autosave_path).read_text(encoding="utf-8")
                except Exception:
                    text = ""
                tab = self.add_new_tab(text=text, file_path=entry.original_path or None, make_current=True)
                tab.autosave_id = entry.autosave_id
                tab.autosave_path = entry.autosave_path
                self._seed_version_history(tab, label="Recovered")
                self._apply_file_metadata_to_tab(tab)
                tab.text_edit.set_modified(True)
            if not entries and snapshot_payload:
                self._restore_from_snapshot_payload(snapshot_payload)
            self.autosave_store.save()
            if store is not None:
                store.clear_crash_snapshot()
            return
        startup_ready_cb = QApplication.instance().property("startup_ready_callback")
        if callable(startup_ready_cb):
            startup_ready_cb(self)
        if entries:
            dlg = AutoSaveRecoveryDialog(self, entries)
            if dlg.exec() != QDialog.Accepted:
                return
            for autosave_id in dlg.selected_ids:
                entry = self.autosave_store.entries.get(autosave_id)
                if entry is None:
                    continue
                if dlg.selected_action == "discard":
                    try:
                        path = Path(entry.autosave_path)
                        if path.exists():
                            path.unlink()
                    except Exception:
                        pass
                    self.autosave_store.remove(autosave_id)
                    continue
                try:
                    text = Path(entry.autosave_path).read_text(encoding="utf-8")
                except Exception:
                    text = ""
                tab = self.add_new_tab(text=text, file_path=entry.original_path or None, make_current=True)
                tab.autosave_id = entry.autosave_id
                tab.autosave_path = entry.autosave_path
                self._seed_version_history(tab, label="Recovered")
                self._apply_file_metadata_to_tab(tab)
                tab.text_edit.set_modified(True)
        elif snapshot_payload:
            answer = QMessageBox.question(
                self,
                "Recover Last Crash Snapshot",
                "Restore recovered tabs from the last crash snapshot?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self._restore_from_snapshot_payload(snapshot_payload)
            else:
                if store is not None:
                    store.clear_crash_snapshot()
        self.autosave_store.save()
        if store is not None:
            store.clear_crash_snapshot()

    def load_settings_from_disk(self) -> None:
        path = self.settings_file
        if not path.exists():
            legacy_path = self._get_legacy_settings_file_path()
            if legacy_path.exists():
                path = legacy_path
        if not path.exists():
            return
        try:
            loaded = json.loads(path.read_bytes().decode("utf-8"))
        except Exception:
            return
        if not isinstance(loaded, dict):
            return
        self.settings.update(loaded)
        self.settings = migrate_settings(self.settings)
        normalize_ui_visibility_settings(self.settings)
        if str(self.settings.get("app_style", "")).strip() in {"", "System Default"}:
            self.settings["app_style"] = self._default_style_name()
        password_data = self._load_password_data_from_disk()
        if not self.settings.get("lock_password"):
            from_bin = self._unprotect_settings_secret(str(password_data.get("lock_password_enc", "")))
            from_legacy = self._unprotect_settings_secret(str(loaded.get("lock_password_enc", "")))
            self.settings["lock_password"] = from_bin or from_legacy
        if not self.settings.get("lock_pin"):
            from_bin = self._unprotect_settings_secret(str(password_data.get("lock_pin_enc", "")))
            from_legacy = self._unprotect_settings_secret(str(loaded.get("lock_pin_enc", "")))
            self.settings["lock_pin"] = from_bin or from_legacy

    def save_settings_to_disk(self) -> None:
        path = self.settings_file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = migrate_settings(dict(self.settings))
            self.settings = dict(payload)
            lock_password = str(payload.get("lock_password", "") or "")
            lock_pin = str(payload.get("lock_pin", "") or "")
            self._save_password_data_to_disk(lock_password, lock_pin)
            # Keep plaintext values only in-memory.
            payload["lock_password"] = ""
            payload["lock_pin"] = ""
            payload.pop("lock_password_enc", None)
            payload.pop("lock_pin_enc", None)
            payload.pop("focus_mode_enabled", None)
            path.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))
        except Exception:
            pass

    def _load_password_data_from_disk(self) -> dict:
        path = self._get_password_file_path()
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_bytes().decode("utf-8"))
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            return {}
        return {}

    def _save_password_data_to_disk(self, lock_password: str, lock_pin: str) -> None:
        path = self._get_password_file_path()
        payload = {
            "lock_password_enc": self._protect_settings_secret(lock_password) if lock_password else "",
            "lock_pin_enc": self._protect_settings_secret(lock_pin) if lock_pin else "",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(payload, indent=2).encode("utf-8"))

    @staticmethod
    def _normalize_hex_color(value: str) -> str | None:
        text = (value or "").strip()
        if not text:
            return None
        if not text.startswith("#"):
            text = f"#{text}"
        if len(text) not in (4, 7):
            return None
        hex_part = text[1:]
        if not all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
            return None
        return text

    def apply_settings(self) -> None:
        self.settings = migrate_settings(dict(self.settings))
        if hasattr(self, "apply_shortcut_settings"):
            self.apply_shortcut_settings()
        app = QApplication.instance()
        if app is not None:
            requested_style = str(self.settings.get("app_style", "System Default") or "System Default")
            if requested_style == "System Default":
                default_name = type(self).system_style_name or ""
                default_style = QStyleFactory.create(default_name) if default_name else None
                if default_style is not None:
                    app.setStyle(default_style)
            else:
                style_obj = QStyleFactory.create(requested_style)
                if style_obj is not None:
                    app.setStyle(style_obj)

        # Font size & family
        font = QFont()
        font.setPointSize(self.settings.get("font_size", 11))
        font_family = self.settings.get("font_family")
        if font_family:
            font.setFamily(font_family)
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.text_edit.set_font(font)

        if hasattr(self, "snap_dock_left_action"):
            enable_snap = bool(self.settings.get("snap_dock_shortcuts_enabled", True))
            self.snap_dock_left_action.setShortcut(QKeySequence("Ctrl+Alt+Left") if enable_snap else QKeySequence())
            self.snap_dock_right_action.setShortcut(QKeySequence("Ctrl+Alt+Right") if enable_snap else QKeySequence())
            self.snap_dock_bottom_action.setShortcut(QKeySequence("Ctrl+Alt+Down") if enable_snap else QKeySequence())

        # Theming: apply dark mode, presets, and optional custom overrides.
        theme = self.settings.get("theme", "Default")
        palette_map = {
            "Default": {"window_bg": "#ffffff", "text_color": "#000000", "chrome_bg": "#f0f0f0"},
            "Soft Light": {"window_bg": "#f5f5f7", "text_color": "#222222", "chrome_bg": "#e1e1e6"},
            "High Contrast": {"window_bg": "#000000", "text_color": "#ffffff", "chrome_bg": "#000000"},
            "Solarized Light": {"window_bg": "#fdf6e3", "text_color": "#586e75", "chrome_bg": "#eee8d5"},
            "Ocean Blue": {"window_bg": "#eaf4ff", "text_color": "#10324a", "chrome_bg": "#d6e9fb"},
        }

        if self.settings.get("dark_mode"):
            window_bg = "#202124"
            text_color = "#e8eaed"
            chrome_bg = "#303134"
            scrollbar_border = "#3c4043"
            scrollbar_handle = "#5f6368"
            scrollbar_hover = "#80868b"
            selection_bg = "#3c4043"
            toolbar_checked_bg = "#3a3f45"
            toolbar_checked_hover_bg = "#444a51"
            tab_hover_bg = "#3a3f45"
            dock_button_bg = "#3a3f45"
            dock_button_hover_bg = "#444a51"
            dock_button_pressed_bg = "#2d3136"
        else:
            palette = palette_map.get(theme, palette_map["Default"])
            window_bg = palette["window_bg"]
            text_color = palette["text_color"]
            chrome_bg = palette["chrome_bg"]
            scrollbar_border = "#c0c0c0"
            scrollbar_handle = "#aeb6c0"
            scrollbar_hover = "#8f98a4"
            selection_bg = "#cce0ff"
            toolbar_checked_bg = "#eceff5"
            toolbar_checked_hover_bg = "#e4e9f2"
            tab_hover_bg = "#e9eef7"
            dock_button_bg = "#f3f6fb"
            dock_button_hover_bg = "#e6edf8"
            dock_button_pressed_bg = "#d9e3f3"

        accent_color = self._normalize_hex_color(self.settings.get("accent_color", "")) or "#4a90e2"
        toolbar_hover_bg = accent_color
        density = str(self.settings.get("ui_density", "comfortable"))
        tool_padding = "2px 4px" if density == "compact" else "3px 6px"
        close_button_visibility_qss = ""
        if str(self.settings.get("tab_close_button_mode", "always")) == "hover":
            close_button_visibility_qss = f"""
            QTabBar::close-button {
                image: none;
                background: transparent;
                border: none;
            }
            QTabBar::tab:hover QTabBar::close-button {
                image: url("{tab_close_icon_url}");
                background: #d13438;
                border: 1px solid #b72b2f;
                border-radius: 2px;
            }
            """
        if self.settings.get("use_custom_colors"):
            custom_editor_bg = self._normalize_hex_color(self.settings.get("custom_editor_bg", ""))
            custom_editor_fg = self._normalize_hex_color(self.settings.get("custom_editor_fg", ""))
            custom_chrome_bg = self._normalize_hex_color(self.settings.get("custom_chrome_bg", ""))
            if custom_editor_bg:
                window_bg = custom_editor_bg
            if custom_editor_fg:
                text_color = custom_editor_fg
            if custom_chrome_bg:
                chrome_bg = custom_chrome_bg
        chrome_color = QColor(chrome_bg)
        if chrome_color.isValid():
            self._icon_color = QColor("#000000" if chrome_color.lightnessF() >= 0.55 else "#ffffff")
        else:
            self._icon_color = QColor("#ffffff" if self.settings.get("dark_mode") else "#000000")

        tab_close_icon_name = "tab-close-dark.svg" if self.settings.get("dark_mode") else "tab-close-light.svg"
        tab_close_icon_path = resolve_asset_path("icons", tab_close_icon_name) or resolve_asset_path("icons", "tab-close.svg")
        tab_close_icon_url = tab_close_icon_path.as_posix() if tab_close_icon_path else ""

        qss = f"""
            QMainWindow {{
                background-color: {window_bg};
                color: {text_color};
            }}
            QTextEdit {{
                background-color: {window_bg};
                color: {text_color};
                selection-background-color: {selection_bg};
                selection-color: {text_color};
                border: 1px solid {accent_color};
            }}
            QMenuBar, QMenu, QStatusBar, QToolBar {{
                background-color: {chrome_bg};
                color: {text_color};
            }}
            QMenuBar {{
                border-bottom: 1px solid {scrollbar_border};
            }}
            QMenuBar::item:selected, QMenu::item:selected {{
                background: {accent_color};
                color: #ffffff;
            }}
            QToolBar {{
                border-top: 1px solid {scrollbar_border};
                border-bottom: 1px solid {scrollbar_border};
                spacing: 2px;
            }}
            QDockWidget::title {{
                background: {chrome_bg};
                color: {text_color};
                border: 1px solid {scrollbar_border};
                padding: 4px 6px;
                text-align: left;
            }}
            QDockWidget::close-button,
            QDockWidget::float-button {{
                background: {dock_button_bg};
                border: 1px solid {scrollbar_border};
                border-radius: 2px;
                padding: 0px;
                margin: 1px;
            }}
            QDockWidget::close-button:hover,
            QDockWidget::float-button:hover {{
                background: {dock_button_hover_bg};
                border: 1px solid {accent_color};
            }}
            QDockWidget::close-button:pressed,
            QDockWidget::float-button:pressed {{
                background: {dock_button_pressed_bg};
            }}
            QToolButton {{
                color: {text_color};
                background: transparent;
                border: 1px solid transparent;
                padding: {tool_padding};
            }}
            QToolButton:hover {{
                background: {toolbar_hover_bg};
                color: #ffffff;
                border: 1px solid {accent_color};
            }}
            QToolButton:pressed {{
                background: {accent_color};
                color: #ffffff;
            }}
            QToolButton:checked {{
                background: {toolbar_checked_bg};
                color: {text_color};
                border: 1px solid {accent_color};
            }}
            QToolButton:checked:hover {{
                background: {toolbar_checked_hover_bg};
                color: {text_color};
                border: 1px solid {accent_color};
            }}
            QToolBar QLabel,
            QToolBar QCheckBox {{
                color: {text_color};
                background: transparent;
            }}
            QToolBar QLineEdit {{
                background: {window_bg};
                color: {text_color};
                border: 1px solid {scrollbar_border};
                min-height: 22px;
            }}
            QToolBar QPushButton {{
                background: {chrome_bg};
                color: {text_color};
                border: 1px solid {scrollbar_border};
                min-height: 22px;
                padding: 2px 10px;
            }}
            QToolBar QPushButton:hover {{
                background: {accent_color};
                color: #ffffff;
                border: 1px solid {accent_color};
            }}
            QToolBar QPushButton:pressed {{
                background: {accent_color};
                color: #ffffff;
            }}
            QStatusBar QLabel, QStatusBar::item {{
                color: {text_color};
            }}
            QStatusBar QComboBox {{
                background: {chrome_bg};
                color: {text_color};
                border: 1px solid {scrollbar_border};
                padding: 1px 4px;
            }}
            QStatusBar QComboBox QAbstractItemView {{
                background: {window_bg};
                color: {text_color};
                selection-background-color: {accent_color};
                selection-color: #ffffff;
            }}
            QTabWidget::pane {{
                border: 1px solid {scrollbar_border};
                background: {chrome_bg};
            }}
            QTabBar::tab {{
                background: {chrome_bg};
                color: {text_color};
                border: 1px solid {scrollbar_border};
                padding: 6px 26px 6px 10px;
                margin-right: 2px;
                min-height: 22px;
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
                subcontrol-origin: padding;
                margin-right: 4px;
                margin-top: 0px;
                margin-left: 6px;
                width: 14px;
                height: 14px;
                image: url("{tab_close_icon_url}");
                background: #d13438;
                border: 1px solid #b72b2f;
                border-radius: 2px;
            }}
            QTabBar::close-button:hover {{
                background: #e74856;
                border: 1px solid #c8373c;
            }}
            QTabBar::close-button:pressed {{
                background: #a4262c;
                border: 1px solid #8f1f24;
            }}
            {close_button_visibility_qss}
            QTabBar::tab:selected {{
                background: {window_bg};
                color: {text_color};
                font-weight: 600;
                border: 1px solid {scrollbar_border};
            }}
            QTabBar::tab:hover {{
                background: {tab_hover_bg};
                color: {text_color};
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: {window_bg};
                border: 1px solid {scrollbar_border};
                margin: 0px;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {scrollbar_handle};
                min-height: 20px;
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {scrollbar_hover};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                background: {window_bg};
                border: none;
                width: 0px;
                height: 0px;
            }}
        """
        if app is not None:
            app.setStyleSheet(qss)
        else:
            self.setStyleSheet(qss)
        self._apply_main_toolbar_icons()
        self._apply_markdown_icons()
        self._apply_format_icons()
        icon_px = int(self.settings.get("icon_size_px", 18))
        label_mode = str(self.settings.get("toolbar_label_mode", "icons_only"))
        style_map = {
            "icons_only": Qt.ToolButtonStyle.ToolButtonIconOnly,
            "text_only": Qt.ToolButtonStyle.ToolButtonTextOnly,
            "icons_text": Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
        }
        tool_style = style_map.get(label_mode, Qt.ToolButtonStyle.ToolButtonIconOnly)
        for toolbar_name in ("main_toolbar", "markdown_toolbar", "search_toolbar"):
            toolbar = getattr(self, toolbar_name, None)
            if toolbar is None:
                continue
            toolbar.setIconSize(QSize(icon_px, icon_px))
            toolbar.setToolButtonStyle(tool_style)

        show_main_toolbar = bool(self.settings.get("show_main_toolbar", True))
        if hasattr(self, "main_toolbar") and self.main_toolbar is not None:
            self.main_toolbar.setVisible(show_main_toolbar)
        show_md_toolbar = bool(self.settings.get("show_markdown_toolbar", False))
        if hasattr(self, "md_toolbar_visible_action"):
            self.md_toolbar_visible_action.blockSignals(True)
            self.md_toolbar_visible_action.setChecked(show_md_toolbar)
            self.md_toolbar_visible_action.blockSignals(False)
        show_find_panel = bool(self.settings.get("show_find_panel", False))
        if hasattr(self, "search_panel_action"):
            self.search_panel_action.blockSignals(True)
            self.search_panel_action.setChecked(show_find_panel)
            self.search_panel_action.blockSignals(False)
        if hasattr(self, "_layout_top_toolbars"):
            self._layout_top_toolbars()
        if hasattr(self, "_restore_layout_from_settings") and not getattr(self, "_layout_restored_once", False):
            self._layout_restored_once = True
            self._restore_layout_from_settings()
        if hasattr(self, "_apply_layout_lock"):
            self._apply_layout_lock()
        focus_checked = bool(self.focus_mode_action.isChecked()) if hasattr(self, "focus_mode_action") else False
        self._apply_focus_mode(focus_checked)
        self._page_layout_view_enabled = bool(self.settings.get("page_layout_view_enabled", False))
        if hasattr(self, "page_layout_view_action"):
            self.page_layout_view_action.blockSignals(True)
            self.page_layout_view_action.setChecked(self._page_layout_view_enabled)
            self.page_layout_view_action.blockSignals(False)
        if hasattr(self, "_set_editor_print_view_styles"):
            self._set_editor_print_view_styles(bool(self._page_layout_view_enabled and not getattr(self, "_print_view_enabled", False)))

        reminder_interval = int(self.settings.get("reminder_check_interval_sec", 30))
        if self.settings.get("reminders_enabled", True) and reminder_interval > 0:
            self.reminder_timer.start(reminder_interval * 1000)
        else:
            self.reminder_timer.stop()

        autosave_interval = int(self.settings.get("autosave_interval_sec", 30))
        if self.settings.get("autosave_enabled", True) and autosave_interval > 0:
            self.autosave_timer.start(autosave_interval * 1000)
        else:
            self.autosave_timer.stop()

        if hasattr(self, "syntax_combo"):
            self.syntax_combo.setEnabled(self.settings.get("syntax_highlighting_enabled", True))
            self.syntax_label.setEnabled(self.settings.get("syntax_highlighting_enabled", True))
        self._refresh_recent_files_menu()
        self._refresh_favorite_files_menu()
        if hasattr(self, "advanced_features"):
            self.advanced_features.apply_backup_schedule()
            self.advanced_features.toggle_keyboard_only(bool(self.settings.get("keyboard_only_mode", False)))

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                self._apply_syntax_highlighting(tab)
                tab.version_history.max_entries = int(self.settings.get("version_history_max_entries", 50))
                self._apply_tab_color(tab)
                tab.show_space_tab = bool(self.settings.get("show_symbol_space_tab", False))
                tab.show_eol = bool(self.settings.get("show_symbol_eol", False))
                tab.show_non_printing = bool(self.settings.get("show_symbol_non_printing", False))
                tab.show_control_chars = bool(self.settings.get("show_symbol_control_chars", False))
                tab.show_all_chars = bool(self.settings.get("show_symbol_all_chars", False))
                tab.show_indent_guides = bool(self.settings.get("show_symbol_indent_guide", True))
                tab.show_wrap_symbol = bool(self.settings.get("show_symbol_wrap_symbol", False))
                if hasattr(self, "_apply_scintilla_modes"):
                    self._apply_scintilla_modes(tab)
        if hasattr(self, "ai_chat_dock") and self.ai_chat_dock is not None:
            self.ai_chat_dock.refresh_theme()
        if bool(self.settings.get("simple_mode", False)):
            self.toggle_simple_mode(True)
        else:
            self.toggle_simple_mode(False)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings.get("always_on_top", False)))
        self.setWindowFlag(Qt.Tool, bool(self.settings.get("post_it_mode", False)))
        self.show()
        self._refresh_ai_usage_label()
        self.apply_language()

    def apply_language(self) -> None:
        lang_label = str(self.settings.get("language", "English") or "English")
        lang_code = language_code_for(lang_label)
        self._ui_language_code = lang_code
        self._translate_actions(lang_code)
        self._translate_widgets(lang_code)

    def clear_translation_cache(self) -> None:
        translator = getattr(self, "translator", None)
        if translator is None:
            return
        translator.clear_cache()
        self.log_event("Info", "Translation cache cleared")

    def show_status_message(self, text: str, timeout_ms: int = 0) -> None:
        lang_code = getattr(self, "_ui_language_code", "en")
        self.status.showMessage(self._translate_text(text, lang_code), timeout_ms)

    def _record_jump_history(self, *, reason: str = "cursor") -> None:
        if getattr(self, "_suspend_jump_recording", False):
            return
        tab = self.active_tab()
        if tab is None:
            return
        line, col = tab.text_edit.cursor_position()
        entry = {
            "tab_id": id(tab),
            "file": tab.current_file or "",
            "line": int(line),
            "col": int(col),
            "reason": reason,
        }
        history = getattr(self, "_jump_history", [])
        if history:
            last = history[-1]
            if (
                int(last.get("tab_id", -1)) == entry["tab_id"]
                and int(last.get("line", -1)) == entry["line"]
                and int(last.get("col", -1)) == entry["col"]
            ):
                return
        idx = int(getattr(self, "_jump_history_index", -1))
        if idx < len(history) - 1:
            history = history[: idx + 1]
        history.append(entry)
        if len(history) > 600:
            history = history[-600:]
        self._jump_history = history
        self._jump_history_index = len(history) - 1

    def _on_cursor_position_changed_for_jump_history(self) -> None:
        self._record_jump_history(reason="cursor")

    def can_jump_history_back(self) -> bool:
        return int(getattr(self, "_jump_history_index", -1)) > 0

    def can_jump_history_forward(self) -> bool:
        history = getattr(self, "_jump_history", [])
        return 0 <= int(getattr(self, "_jump_history_index", -1)) < len(history) - 1

    def _jump_history_move(self, direction: int) -> None:
        history = getattr(self, "_jump_history", [])
        if not history:
            return
        idx = int(getattr(self, "_jump_history_index", len(history) - 1))
        target = idx + direction
        if target < 0 or target >= len(history):
            return
        entry = history[target]
        tab_id = int(entry.get("tab_id", -1))
        target_tab = None
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if widget is not None and id(widget) == tab_id:
                target_tab = widget
                self.tab_widget.setCurrentIndex(i)
                break
        if target_tab is None:
            target_file = str(entry.get("file", "")).strip()
            if target_file and Path(target_file).exists():
                self._open_file_path(target_file)
                target_tab = self.active_tab()
        if target_tab is None:
            return
        line = max(0, int(entry.get("line", 0)))
        col = max(0, int(entry.get("col", 0)))
        self._suspend_jump_recording = True
        try:
            self.active_tab().text_edit.set_cursor_position(line, col)
        finally:
            self._suspend_jump_recording = False
        self._jump_history_index = target
        self.update_action_states()

    def jump_history_back(self) -> None:
        self._jump_history_move(-1)

    def jump_history_forward(self) -> None:
        self._jump_history_move(1)

    def show_jump_history(self) -> None:
        history = list(getattr(self, "_jump_history", []))
        if not history:
            QMessageBox.information(self, "Jump History", "No jump history yet.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Jump History")
        dlg.resize(700, 420)
        layout = QVBoxLayout(dlg)
        list_widget = QListWidget(dlg)
        for idx, entry in enumerate(history):
            name = Path(str(entry.get("file", "") or "Untitled")).name
            line = int(entry.get("line", 0)) + 1
            col = int(entry.get("col", 0)) + 1
            reason = str(entry.get("reason", "cursor"))
            item = QListWidgetItem(f"{name}  Ln {line}, Col {col}  ({reason})", list_widget)
            item.setData(Qt.UserRole, idx)
        layout.addWidget(list_widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        jump_btn = QPushButton("Jump", dlg)
        buttons.addButton(jump_btn, QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)
        buttons.rejected.connect(dlg.reject)

        def _jump_selected() -> None:
            current = list_widget.currentItem()
            if current is None:
                return
            idx = current.data(Qt.UserRole)
            if not isinstance(idx, int):
                return
            self._jump_history_index = idx
            self._jump_history_move(0)
            dlg.accept()

        list_widget.itemDoubleClicked.connect(lambda _item: _jump_selected())
        jump_btn.clicked.connect(_jump_selected)
        list_widget.setCurrentRow(len(history) - 1)
        dlg.exec()

    def _translate_text(self, text: str, lang_code: str) -> str:
        if not text:
            return text
        if not lang_code or lang_code == "en":
            return text
        translator = getattr(self, "translator", None)
        if translator is None:
            return text
        return translator.translate(text, lang_code)

    def _translate_action_text(self, text: str, lang_code: str) -> str:
        if not text:
            return text
        if not lang_code or lang_code == "en":
            return text
        has_accel = "&" in text
        raw = text.replace("&", "")
        translated = self._translate_text(raw, lang_code)
        if has_accel and translated:
            return f"&{translated}"
        return translated

    def _translate_actions(self, lang_code: str) -> None:
        for action in self.findChildren(QAction):
            if action.property("i18n_skip"):
                continue
            original_text = action.property("i18n_original_text") or action.text()
            action.setProperty("i18n_original_text", original_text)
            action.setText(self._translate_action_text(str(original_text), lang_code))

            original_tip = action.property("i18n_original_tooltip") or action.toolTip()
            action.setProperty("i18n_original_tooltip", original_tip)
            if original_tip:
                action.setToolTip(self._translate_text(str(original_tip), lang_code))

            original_status = action.property("i18n_original_statustip") or action.statusTip()
            action.setProperty("i18n_original_statustip", original_status)
            if original_status:
                action.setStatusTip(self._translate_text(str(original_status), lang_code))

    def _translate_widgets(self, lang_code: str) -> None:
        for widget in self.findChildren(QWidget):
            if widget.property("i18n_skip"):
                continue
            if isinstance(widget, QMainWindow):
                continue
            if isinstance(widget, QMenu):
                original = widget.property("i18n_original_title") or widget.title()
                widget.setProperty("i18n_original_title", original)
                widget.setTitle(self._translate_text(str(original), lang_code))
                continue
            if isinstance(widget, QDialog):
                original = widget.property("i18n_original_window_title") or widget.windowTitle()
                widget.setProperty("i18n_original_window_title", original)
                widget.setWindowTitle(self._translate_text(str(original), lang_code))
            if isinstance(widget, (QLabel, QGroupBox, QCheckBox, QPushButton)):
                original = widget.property("i18n_original_text") or widget.text()
                widget.setProperty("i18n_original_text", original)
                widget.setText(self._translate_text(str(original), lang_code))
            if isinstance(widget, QLineEdit):
                original = widget.property("i18n_original_placeholder") or widget.placeholderText()
                widget.setProperty("i18n_original_placeholder", original)
                if original:
                    widget.setPlaceholderText(self._translate_text(str(original), lang_code))
            original_tooltip = widget.property("i18n_original_tooltip") or widget.toolTip()
            widget.setProperty("i18n_original_tooltip", original_tooltip)
            if original_tooltip:
                widget.setToolTip(self._translate_text(str(original_tooltip), lang_code))
            if isinstance(widget, QDialogButtonBox):
                for button in widget.buttons():
                    original = button.property("i18n_original_text") or button.text()
                    button.setProperty("i18n_original_text", original)
                    button.setText(self._translate_text(str(original), lang_code))

    def open_settings(self) -> None:
        dlg = SidebarSettingsDialog(self, self.settings)
        self.apply_language()
        if dlg.exec():
            if getattr(dlg, "reset_to_defaults_requested", False):
                self.reset_settings_to_default_and_close()
                return
            self.settings = dlg.get_settings()
            self.apply_settings()
            self.save_settings_to_disk()
            self.log_event("Info", "Settings applied and saved")

    def get_shortcut_action_rows(self) -> list[ShortcutActionRow]:
        rows: list[ShortcutActionRow] = []
        for entry in discover_window_actions(self):
            try:
                entry.action.setObjectName(entry.action_id)
                label = f"{entry.label} [{entry.section}]"
            except RuntimeError:
                # Skip stale Python wrappers whose underlying Qt object was deleted.
                continue
            rows.append(ShortcutActionRow(action_id=entry.action_id, label=label, action=entry.action))
        rows.sort(key=lambda r: r.label.lower())
        return rows

    def _capture_default_shortcuts(self) -> None:
        rows = self.get_shortcut_action_rows()
        defaults: dict[str, list[str]] = {}
        for row in rows:
            try:
                seqs = [sequence_to_string(s).strip() for s in row.action.shortcuts() if not s.isEmpty()]
                if not seqs:
                    fallback = row.action.shortcut()
                    if not fallback.isEmpty():
                        seqs = [sequence_to_string(fallback).strip()]
            except RuntimeError:
                continue
            defaults[row.action_id] = [s for s in seqs if s]
        self._default_shortcuts_by_action_id = defaults

    def _resolve_effective_shortcuts(self) -> dict[str, list[str]]:
        profile = str(self.settings.get("shortcut_profile", "vscode"))
        custom_map = self.settings.get("shortcut_map", {})
        base = dict(getattr(self, "_default_shortcuts_by_action_id", {}))
        for aid, seq in PRESET_SHORTCUTS.get(profile, {}).items():
            base[aid] = [str(seq)]
        if isinstance(custom_map, dict):
            for aid, value in custom_map.items():
                if not isinstance(aid, str):
                    continue
                seqs = [sequence_to_string(q).strip() for q in parse_shortcut_value(value) if not q.isEmpty()]
                base[aid] = seqs
        return base

    def apply_shortcut_settings(self) -> None:
        mapping = self._resolve_effective_shortcuts()
        rows = self.get_shortcut_action_rows()
        for row in rows:
            seqs = mapping.get(row.action_id)
            if seqs is None:
                continue
            keyseqs = [QKeySequence(text) for text in seqs if text]
            try:
                row.action.setShortcuts(keyseqs)
            except RuntimeError:
                continue
        if hasattr(self, "configure_action_tooltips"):
            self.configure_action_tooltips()

    def open_shortcut_mapper(self) -> None:
        if not hasattr(self, "_default_shortcuts_by_action_id"):
            self._capture_default_shortcuts()
        rows = self.get_shortcut_action_rows()
        dlg = ShortcutMapperDialog(self, rows, dict(getattr(self, "_default_shortcuts_by_action_id", {})), dict(self.settings))
        dlg.exec()

    def edit_settings_json_in_app(self) -> None:
        self.save_settings_to_disk()
        path = str(self.settings_file)
        if not self._open_file_path(path):
            try:
                text = Path(path).read_text(encoding="utf-8")
            except Exception:
                text = "{}\n"
            self.add_new_tab(text=text, file_path=path, make_current=True)

    def reset_settings_to_default_and_close(self) -> None:
        self.settings = self._build_default_settings()
        self.save_settings_to_disk()
        self.log_event("Info", "Settings reset to defaults. Closing app.")
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if (
            event.key() == Qt.Key_Escape
            and hasattr(self, "focus_mode_action")
            and self.focus_mode_action.isChecked()
            and self.settings.get("focus_allow_escape_exit", True)
        ):
            self.toggle_focus_mode(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def update_window_title(self) -> None:
        tab = self.active_tab()
        if tab is None:
            self.setWindowTitle("Pypad")
            return
        name = tab.current_file if tab.current_file else "Untitled"
        modified_marker = "*" if tab.text_edit.is_modified() else ""
        self.setWindowTitle(f"{modified_marker}{name} - Pypad")

    def _on_modification_changed(self, _changed: bool) -> None:
        sender_editor = self.sender()
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab) and tab.text_edit is sender_editor:
                self._refresh_tab_title(tab)
                break
        self.update_window_title()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        tabs: list[EditorTab] = []
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tabs.append(tab)
        for tab in tabs:
            self.tab_widget.setCurrentWidget(tab)
            if not self.maybe_save_tab(tab):
                self.log_event("Info", "Close cancelled by user")
                event.ignore()
                return
        session_state = self._collect_session_state()
        self.settings["last_session_files"] = session_state["files"]
        self.settings["last_session_active_file"] = session_state["active_file"]
        self.settings["last_session_workspace_root"] = session_state["workspace_root"]
        if hasattr(self, "save_current_layout"):
            try:
                self.save_current_layout()
            except Exception as exc:  # noqa: BLE001
                self.log_event("Error", f"Failed to persist layout on close: {exc}")
        self.save_settings_to_disk()
        try:
            self.reminders_store.save()
        except Exception as exc:  # noqa: BLE001
            self.log_event("Error", f"Failed to save reminders: {exc}")
        try:
            self._run_autosave_cycle()
        except Exception as exc:  # noqa: BLE001
            self.log_event("Error", f"Failed during autosave cycle on shutdown: {exc}")
        try:
            if hasattr(self, "recovery_state_store"):
                self.recovery_state_store.clear_crash_snapshot()
        except Exception:
            pass
        self.log_event("Info", "Application closing")
        type(self).windows_by_id.pop(self.window_id, None)
        event.accept()

    def _collect_session_state(self) -> dict[str, object]:
        files: list[str] = []
        seen: set[str] = set()
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if not isinstance(tab, EditorTab) or not tab.current_file:
                continue
            if tab.current_file in seen:
                continue
            seen.add(tab.current_file)
            files.append(tab.current_file)
        active_tab = self.active_tab()
        active_file = active_tab.current_file if active_tab is not None and active_tab.current_file else ""
        workspace_root = str(self.settings.get("workspace_root", "") or "")
        return {
            "version": 1,
            "files": files,
            "active_file": active_file,
            "workspace_root": workspace_root,
        }

    def _save_session_to_path(self, path: str) -> bool:
        payload = self._collect_session_state()
        try:
            Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save Session", f"Could not save session file:\n{exc}")
            return False
        self.settings["last_session_file_path"] = path
        self.save_settings_to_disk()
        self.show_status_message(f"Session saved: {path}", 3000)
        return True

    def save_session(self) -> None:
        path = str(self.settings.get("last_session_file_path", "") or "").strip()
        if not path:
            self.save_session_as()
            return
        self._save_session_to_path(path)

    def save_session_as(self) -> None:
        default_path = str(self.settings.get("last_session_file_path", "") or "").strip()
        if not default_path:
            default_path = str(Path.home() / "pypad.session.json")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Session As",
            default_path,
            "Session Files (*.session.json *.json);;All Files (*.*)",
        )
        if not path:
            return
        self._save_session_to_path(path)

    def _open_session_payload(self, payload: dict[str, object]) -> bool:
        raw_files = payload.get("files", [])
        files = [str(path) for path in raw_files if isinstance(path, str) and path]
        unique_files: list[str] = []
        seen: set[str] = set()
        for path in files:
            if path in seen:
                continue
            seen.add(path)
            unique_files.append(path)

        active_file = str(payload.get("active_file", "") or "")
        workspace_root = str(payload.get("workspace_root", "") or "")

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                self.tab_widget.setCurrentWidget(tab)
                if not self.maybe_save_tab(tab):
                    return False

        while self.tab_widget.count():
            tab = self.tab_widget.widget(0)
            if isinstance(tab, EditorTab):
                self._clear_tab_autosave(tab)
            self.tab_widget.removeTab(0)
            if tab is not None:
                tab.deleteLater()

        opened: list[str] = []
        for path in unique_files:
            if not Path(path).exists():
                continue
            if self._open_file_path(path):
                tab = self.active_tab()
                if tab is not None and hasattr(self, "_ensure_tab_autosave_meta"):
                    self._ensure_tab_autosave_meta(tab)
                opened.append(path)

        resolved_active_file = active_file if active_file in opened else (opened[0] if opened else "")

        if not opened:
            tab = self.add_new_tab(make_current=True)
            if hasattr(self, "_ensure_tab_autosave_meta"):
                self._ensure_tab_autosave_meta(tab)
        elif resolved_active_file:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                if isinstance(tab, EditorTab) and tab.current_file == resolved_active_file:
                    self.tab_widget.setCurrentIndex(index)
                    break

        if workspace_root and Path(workspace_root).exists():
            self.settings["workspace_root"] = workspace_root

        self.settings["last_session_files"] = opened
        self.settings["last_session_active_file"] = resolved_active_file
        self.settings["last_session_workspace_root"] = workspace_root
        self.update_window_title()
        self.update_status_bar()
        return True

    def load_session(self) -> None:
        start_dir = str(self.settings.get("last_session_file_path", "") or "").strip()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Session",
            start_dir,
            "Session Files (*.session.json *.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            payload_raw = Path(path).read_text(encoding="utf-8")
            payload = json.loads(payload_raw)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load Session", f"Could not load session file:\n{exc}")
            return
        if not isinstance(payload, dict):
            QMessageBox.warning(self, "Load Session", "Invalid session file format.")
            return
        if not self._open_session_payload(payload):
            return
        self.settings["last_session_file_path"] = path
        self.save_settings_to_disk()
        self.show_status_message(f"Session loaded: {path}", 3000)

    def restore_last_session(self) -> None:
        if not self.settings.get("restore_last_session", True):
            return
        files = [p for p in self.settings.get("last_session_files", []) if isinstance(p, str) and p]
        if not files:
            return
        active = self.active_tab()
        if (
            active is not None
            and not active.current_file
            and not active.text_edit.is_modified()
            and not active.text_edit.get_text().strip()
        ):
            self.close_tab(self.tab_widget.indexOf(active))
        if active is not None and not active.current_file and hasattr(self, "_ensure_tab_autosave_meta"):
            self._ensure_tab_autosave_meta(active)
        active_file = str(self.settings.get("last_session_active_file", "") or "")
        workspace_root = str(self.settings.get("last_session_workspace_root", "") or "")
        for path in files:
            if Path(path).exists():
                if self._open_file_path(path):
                    tab = self.active_tab()
                    if tab is not None and hasattr(self, "_ensure_tab_autosave_meta"):
                        self._ensure_tab_autosave_meta(tab)
        if active_file:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                if isinstance(tab, EditorTab) and tab.current_file == active_file:
                    self.tab_widget.setCurrentIndex(index)
                    break
        if workspace_root and Path(workspace_root).exists():
            self.settings["workspace_root"] = workspace_root

    def _watch_file(self, path: str) -> None:
        watcher = getattr(self, "file_watcher", None)
        if watcher is None:
            return
        if path and path not in watcher.files():
            watcher.addPath(path)

    def _refresh_file_watcher(self) -> None:
        watcher = getattr(self, "file_watcher", None)
        if watcher is None:
            return
        open_files = {
            tab.current_file
            for tab in (self.tab_widget.widget(i) for i in range(self.tab_widget.count()))
            if isinstance(tab, EditorTab) and tab.current_file
        }
        for path in list(watcher.files()):
            if path not in open_files:
                watcher.removePath(path)
        for path in open_files:
            if path not in watcher.files():
                watcher.addPath(path)

    def _on_file_changed(self, path: str) -> None:
        if not path:
            return
        tab = None
        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if isinstance(widget, EditorTab) and widget.current_file == path:
                tab = widget
                break
        if tab is None:
            return
        if not Path(path).exists():
            QMessageBox.warning(self, "File Changed", f"File was removed or renamed:\n{path}")
            return
        if tab.text_edit.is_modified():
            ret = QMessageBox.question(
                self,
                "File Changed",
                f'"{Path(path).name}" changed on disk.\n\nReload and discard your changes?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return
        self.reload_tab_from_disk(tab)

    def _bookmark_marker_id(self, tab: EditorTab) -> int | None:
        if not tab.text_edit.is_scintilla:
            return None
        marker_id = tab.bookmark_marker_id
        if marker_id is not None:
            return marker_id
        try:
            from PySide6.Qsci import QsciScintilla
        except Exception:
            return None
        if hasattr(tab.text_edit.widget, "markerDefine"):
            marker_id = tab.text_edit.widget.markerDefine(QsciScintilla.RightArrow)
            tab.text_edit.widget.setMarkerBackgroundColor(QColor("#ffcc00"), marker_id)
            tab.bookmark_marker_id = marker_id
            return marker_id
        return None

    def _sync_scintilla_bookmark_markers(self, tab: EditorTab) -> None:
        marker_id = self._bookmark_marker_id(tab)
        if marker_id is None or not tab.text_edit.is_scintilla:
            return
        try:
            tab.text_edit.widget.markerDeleteAll(marker_id)
        except Exception:
            pass
        for line in sorted(tab.bookmarks):
            try:
                tab.text_edit.widget.markerAdd(line, marker_id)
            except Exception:
                pass

    def _tab_style_lines(self, tab: EditorTab) -> dict[int, int]:
        raw = getattr(tab, "styled_lines", None)
        if isinstance(raw, dict):
            return raw
        styled: dict[int, int] = {}
        setattr(tab, "styled_lines", styled)
        return styled

    def _style_color(self, style_id: int) -> QColor:
        colors = {
            1: QColor("#9fd3a8"),
            2: QColor("#f6f4a0"),
            3: QColor("#f0a5b5"),
            4: QColor("#7bc67b"),
            5: QColor("#9d8df1"),
            0: QColor("#ff1493"),  # find-mark style
        }
        return colors.get(style_id, QColor("#9fd3a8"))

    def _apply_line_styles(self, tab: EditorTab) -> None:
        if tab.text_edit.is_scintilla:
            return
        styled = self._tab_style_lines(tab)
        if not styled:
            # Keep search highlights if enabled.
            if hasattr(self, "_on_search_text_changed"):
                self._on_search_text_changed()
            return
        selections: list[QTextEdit.ExtraSelection] = []
        for line, style_id in styled.items():
            block = tab.text_edit.widget.document().findBlockByNumber(line)
            if not block.isValid():
                continue
            cursor = QTextCursor(block)
            cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            color = self._style_color(style_id)
            color.setAlpha(90)
            sel.format.setBackground(color)
            selections.append(sel)
        tab.text_edit.widget.setExtraSelections(selections)

    def _record_change_history_line(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        line, _ = tab.text_edit.cursor_position()
        lines = getattr(tab, "change_history_lines", None)
        if not isinstance(lines, list):
            lines = []
            setattr(tab, "change_history_lines", lines)
        if line not in lines:
            lines.append(line)
            lines.sort()
        if len(lines) > 4000:
            del lines[: len(lines) - 4000]

    def toggle_bookmark(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        line, _ = tab.text_edit.cursor_position()
        marker_id = self._bookmark_marker_id(tab)
        if line in tab.bookmarks:
            tab.bookmarks.remove(line)
            if marker_id is not None and tab.text_edit.is_scintilla:
                tab.text_edit.widget.markerDelete(line, marker_id)
        else:
            tab.bookmarks.add(line)
            if marker_id is not None and tab.text_edit.is_scintilla:
                tab.text_edit.widget.markerAdd(line, marker_id)

    def _goto_bookmark(self, forward: bool) -> None:
        tab = self.active_tab()
        if tab is None or not tab.bookmarks:
            return
        line, _ = tab.text_edit.cursor_position()
        sorted_marks = sorted(tab.bookmarks)
        if forward:
            for target in sorted_marks:
                if target > line:
                    tab.text_edit.set_cursor_position(target, 0)
                    return
            tab.text_edit.set_cursor_position(sorted_marks[0], 0)
        else:
            for target in reversed(sorted_marks):
                if target < line:
                    tab.text_edit.set_cursor_position(target, 0)
                    return
            tab.text_edit.set_cursor_position(sorted_marks[-1], 0)

    def goto_next_bookmark(self) -> None:
        self._goto_bookmark(forward=True)

    def goto_prev_bookmark(self) -> None:
        self._goto_bookmark(forward=False)

    def clear_bookmarks(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        marker_id = self._bookmark_marker_id(tab)
        if marker_id is not None and tab.text_edit.is_scintilla:
            for line in list(tab.bookmarks):
                tab.text_edit.widget.markerDelete(line, marker_id)
        tab.bookmarks.clear()

    def show_marks_bookmarks_panel(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        source = tab.text_edit.get_text()
        styled = self._tab_style_lines(tab)

        dlg = QDialog(self)
        dlg.setWindowTitle("Marks/Bookmarks Panel")
        dlg.resize(840, 560)
        layout = QVBoxLayout(dlg)

        options_row = QHBoxLayout()
        include_bookmarks = QCheckBox("Bookmarks", dlg)
        include_bookmarks.setChecked(True)
        include_marks = QCheckBox("Marks", dlg)
        include_marks.setChecked(True)
        options_row.addWidget(include_bookmarks)
        options_row.addWidget(include_marks)
        options_row.addStretch(1)
        layout.addLayout(options_row)

        table = QTableWidget(dlg)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Line", "Kind", "Style", "Text"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        jump_btn = QPushButton("Jump", dlg)
        remove_btn = QPushButton("Remove Selected", dlg)
        clear_btn = QPushButton("Clear All Shown", dlg)
        export_btn = QPushButton("Export...", dlg)
        buttons.addButton(jump_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(remove_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(clear_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(export_btn, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        refs_cache = []

        def _refresh() -> None:
            nonlocal refs_cache
            refs_cache = build_line_refs(
                source,
                set(tab.bookmarks),
                dict(styled),
                include_bookmarks=include_bookmarks.isChecked(),
                include_marks=include_marks.isChecked(),
            )
            table.setRowCount(len(refs_cache))
            for row_idx, row in enumerate(refs_cache):
                line_item = QTableWidgetItem(str(row.line_no))
                line_item.setData(Qt.ItemDataRole.UserRole, row_idx)
                table.setItem(row_idx, 0, line_item)
                table.setItem(row_idx, 1, QTableWidgetItem(row.kind))
                table.setItem(row_idx, 2, QTableWidgetItem("" if row.style_id is None else str(row.style_id)))
                table.setItem(row_idx, 3, QTableWidgetItem(row.text))

        def _selected_ref_indices() -> list[int]:
            out: list[int] = []
            for item in table.selectedItems():
                row = item.row()
                if row not in out:
                    out.append(row)
            return sorted(out)

        def _jump() -> None:
            idxs = _selected_ref_indices()
            if not idxs:
                return
            row = refs_cache[idxs[0]]
            tab.text_edit.set_cursor_position(max(0, row.line_no - 1), 0)
            self.update_status_bar()
            self.show_status_message(f"Jumped to line {row.line_no}.", 2000)

        def _remove_selected() -> None:
            idxs = _selected_ref_indices()
            if not idxs:
                return
            for idx in reversed(idxs):
                row = refs_cache[idx]
                line_idx = row.line_no - 1
                if row.kind == "bookmark":
                    tab.bookmarks.discard(line_idx)
                elif row.kind == "mark":
                    styled.pop(line_idx, None)
            self._sync_scintilla_bookmark_markers(tab)
            self._apply_line_styles(tab)
            _refresh()
            self.show_status_message("Selected entries removed.", 2200)

        def _clear_shown() -> None:
            for row in refs_cache:
                line_idx = row.line_no - 1
                if row.kind == "bookmark":
                    tab.bookmarks.discard(line_idx)
                elif row.kind == "mark":
                    styled.pop(line_idx, None)
            self._sync_scintilla_bookmark_markers(tab)
            self._apply_line_styles(tab)
            _refresh()
            self.show_status_message("Displayed marks/bookmarks cleared.", 2200)

        def _export() -> None:
            if not refs_cache:
                QMessageBox.information(self, "Marks/Bookmarks Panel", "Nothing to export.")
                return
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Marks/Bookmarks",
                "marks_bookmarks.txt",
                "Text Files (*.txt);;All Files (*.*)",
            )
            if not path:
                return
            try:
                Path(path).write_text(export_line_refs_text(refs_cache), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Marks/Bookmarks Panel", f"Export failed:\n{exc}")
                return
            self.show_status_message(f"Exported marks/bookmarks: {path}", 3000)

        include_bookmarks.toggled.connect(lambda _checked: _refresh())
        include_marks.toggled.connect(lambda _checked: _refresh())
        table.itemDoubleClicked.connect(lambda _item: _jump())
        jump_btn.clicked.connect(_jump)
        remove_btn.clicked.connect(_remove_selected)
        clear_btn.clicked.connect(_clear_shown)
        export_btn.clicked.connect(_export)
        _refresh()
        dlg.exec()

    # ---- Search menu extensions (Notepad++-style baseline) ----
    def search_find_in_files(self) -> None:
        self.search_workspace()

    def _set_search_results(self, query: str, items: list[dict[str, object]]) -> None:
        self._search_results_query = query
        self._search_results_items = list(items)
        self._search_results_index = -1 if not items else 0
        self._refresh_search_results_dock()
        self.update_action_states()

    def _init_layout_docks(self) -> None:
        if getattr(self, "_layout_docks_ready", False):
            return
        self._layout_docks_ready = True
        self._build_workspace_dock()
        self._build_search_results_dock()
        self._build_status_panel_dock()
        self._ensure_default_layout()
        self._sync_layout_panel_actions()
        self._install_layout_auto_save()

    def _build_workspace_dock(self) -> None:
        if hasattr(self, "workspace_dock"):
            return
        dock = QDockWidget("Workspace", self)
        dock.setObjectName("workspaceDock")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        container = QWidget(dock)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        header = QHBoxLayout()
        self.workspace_path_label = QLabel("No workspace selected", container)
        self.workspace_set_btn = QPushButton("Set Workspace", container)
        self.workspace_set_btn.clicked.connect(self.open_workspace_folder)
        header.addWidget(self.workspace_path_label, 1)
        header.addWidget(self.workspace_set_btn)
        layout.addLayout(header)

        self.workspace_tree = QTreeView(container)
        self.workspace_tree.setHeaderHidden(False)
        self.workspace_tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.workspace_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.workspace_model = QFileSystemModel(self.workspace_tree)
        self.workspace_model.setRootPath("")
        self.workspace_tree.setModel(self.workspace_model)
        self.workspace_tree.doubleClicked.connect(self._on_workspace_tree_open)
        layout.addWidget(self.workspace_tree, 1)
        dock.setWidget(container)
        self.workspace_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        dock.hide()
        dock.visibilityChanged.connect(lambda _visible: self._sync_layout_panel_actions())
        self._refresh_workspace_dock()

    def _refresh_workspace_dock(self) -> None:
        if not hasattr(self, "workspace_dock"):
            return
        root = str(self.settings.get("workspace_root", "") or "").strip()
        if not root or not Path(root).exists():
            self.workspace_path_label.setText("No workspace selected")
            self.workspace_tree.setRootIndex(self.workspace_model.index(""))
            return
        self.workspace_path_label.setText(root)
        self.workspace_model.setRootPath(root)
        self.workspace_tree.setRootIndex(self.workspace_model.index(root))
        for col in range(1, self.workspace_model.columnCount()):
            self.workspace_tree.hideColumn(col)

    def _on_workspace_tree_open(self, index) -> None:
        if not hasattr(self, "workspace_model"):
            return
        path = self.workspace_model.filePath(index)
        if path and Path(path).is_file():
            self._open_file_path(path)

    def _build_search_results_dock(self) -> None:
        if hasattr(self, "search_results_dock"):
            return
        dock = QDockWidget("Search Results", self)
        dock.setObjectName("searchResultsDock")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        container = QWidget(dock)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        self.search_results_label = QLabel("No search results", container)
        layout.addWidget(self.search_results_label)
        self.search_results_list = QListWidget(container)
        self.search_results_list.itemDoubleClicked.connect(self._open_search_result_from_dock)
        layout.addWidget(self.search_results_list, 1)
        dock.setWidget(container)
        self.search_results_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.hide()
        dock.visibilityChanged.connect(lambda _visible: self._sync_layout_panel_actions())
        self._refresh_search_results_dock()

    def _refresh_search_results_dock(self) -> None:
        if not hasattr(self, "search_results_dock"):
            return
        items = list(getattr(self, "_search_results_items", []))
        query = str(getattr(self, "_search_results_query", "") or "")
        if not items:
            self.search_results_label.setText("No search results")
        else:
            self.search_results_label.setText(f"Query: {query} ({len(items)} result(s))")
        self.search_results_list.clear()
        for idx, item in enumerate(items):
            path = Path(str(item.get("path", "") or ""))
            line_no = int(item.get("line_no", 1) or 1)
            line_text = str(item.get("line_text", "") or "").strip()
            row = f"{path.name}:{line_no} | {line_text}"
            lw_item = QListWidgetItem(row, self.search_results_list)
            lw_item.setToolTip(str(path))
            lw_item.setData(Qt.UserRole, idx)

    def _open_search_result_from_dock(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        items = list(getattr(self, "_search_results_items", []))
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            return
        self._search_results_index = idx
        self._open_search_result(items[idx])

    def _build_status_panel_dock(self) -> None:
        if hasattr(self, "status_panel_dock"):
            return
        dock = QDockWidget("Status Panel", self)
        dock.setObjectName("statusPanelDock")
        dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        container = QWidget(dock)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        self.status_panel_position_label = QLabel("Ln -, Col -", container)
        self.status_panel_zoom_label = QLabel("100%", container)
        self.status_panel_eol_label = QLabel("", container)
        self.status_panel_encoding_label = QLabel("UTF-8", container)
        self.status_panel_syntax_label = QLabel("Lang: Auto", container)
        self.status_panel_breadcrumb_label = QLabel("-", container)
        self.status_panel_ruler_label = QLabel("", container)
        self.status_panel_ai_usage_label = QLabel("AI: 0 req | ~0 tok | ~$0.0000", container)
        for label in (
            self.status_panel_position_label,
            self.status_panel_zoom_label,
            self.status_panel_eol_label,
            self.status_panel_encoding_label,
            self.status_panel_syntax_label,
            self.status_panel_breadcrumb_label,
            self.status_panel_ruler_label,
            self.status_panel_ai_usage_label,
        ):
            label.setMargin(3)
            layout.addWidget(label)
        layout.addStretch(1)
        dock.setWidget(container)
        self.status_panel_dock = dock
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.hide()
        dock.visibilityChanged.connect(lambda _visible: self._sync_layout_panel_actions())

    def _sync_layout_panel_actions(self) -> None:
        if hasattr(self, "workspace_panel_action") and hasattr(self, "workspace_dock"):
            self.workspace_panel_action.blockSignals(True)
            self.workspace_panel_action.setChecked(self.workspace_dock.isVisible())
            self.workspace_panel_action.blockSignals(False)
        if hasattr(self, "search_results_panel_action") and hasattr(self, "search_results_dock"):
            self.search_results_panel_action.blockSignals(True)
            self.search_results_panel_action.setChecked(self.search_results_dock.isVisible())
            self.search_results_panel_action.blockSignals(False)
        if hasattr(self, "status_panel_action") and hasattr(self, "status_panel_dock"):
            self.status_panel_action.blockSignals(True)
            self.status_panel_action.setChecked(self.status_panel_dock.isVisible())
            self.status_panel_action.blockSignals(False)
        if hasattr(self, "editor_panel_action") and hasattr(self, "editor_dock"):
            self.editor_panel_action.blockSignals(True)
            self.editor_panel_action.setChecked(self.editor_dock.isVisible())
            self.editor_panel_action.blockSignals(False)
        if hasattr(self, "lock_layout_action"):
            self.lock_layout_action.blockSignals(True)
            self.lock_layout_action.setChecked(bool(self.settings.get("layout_locked", False)))
            self.lock_layout_action.blockSignals(False)

    def _install_layout_auto_save(self) -> None:
        if getattr(self, "_layout_auto_save_ready", False):
            return
        self._layout_auto_save_ready = True
        self._layout_auto_save_timer = QTimer(self)
        self._layout_auto_save_timer.setSingleShot(True)
        self._layout_auto_save_timer.timeout.connect(self._persist_layout_snapshot)
        if hasattr(self, "toolBarAreaChanged"):
            self.toolBarAreaChanged.connect(lambda _tb=None: self._schedule_layout_auto_save())
        for name in (
            "editor_dock",
            "ai_chat_dock",
            "workspace_dock",
            "search_results_dock",
            "status_panel_dock",
            "minimap_dock",
            "outline_dock",
        ):
            dock = getattr(self, name, None)
            if dock is None:
                continue
            dock.dockLocationChanged.connect(lambda _area, _dock=dock: self._schedule_layout_auto_save())
            dock.topLevelChanged.connect(lambda _floating, _dock=dock: self._schedule_layout_auto_save())
            dock.visibilityChanged.connect(lambda _visible, _dock=dock: self._schedule_layout_auto_save())
        for toolbar_name in ("main_toolbar", "markdown_toolbar", "search_toolbar"):
            toolbar = getattr(self, toolbar_name, None)
            if toolbar is None:
                continue
            toolbar.topLevelChanged.connect(lambda _floating, _tb=toolbar: self._schedule_layout_auto_save())
            toolbar.visibilityChanged.connect(lambda _visible, _tb=toolbar: self._schedule_layout_auto_save())

    def _schedule_layout_auto_save(self) -> None:
        if getattr(self, "_layout_restore_in_progress", False):
            return
        if not bool(self.settings.get("layout_auto_save_enabled", True)):
            return
        if not hasattr(self, "_layout_auto_save_timer"):
            return
        self._layout_auto_save_timer.start(400)

    def _persist_layout_snapshot(self) -> None:
        if getattr(self, "_layout_restore_in_progress", False):
            return
        if hasattr(self, "save_current_layout"):
            try:
                self.save_current_layout()
                if hasattr(self, "save_settings_to_disk"):
                    self.save_settings_to_disk()
            except Exception as exc:  # noqa: BLE001
                self.log_event("Error", f"Failed to auto-save layout: {exc}")

    def _restore_editor_splitter_sizes(self, tab: EditorTab) -> None:
        sizes = None
        if bool(self.settings.get("per_tab_splitter_sizes_enabled", True)):
            key = self._splitter_key_for_tab(tab)
            by_path = self.settings.get("editor_splitter_sizes_by_path", {})
            if isinstance(by_path, dict):
                sizes = by_path.get(key)
        if sizes is None:
            sizes = self.settings.get("editor_splitter_sizes", None)
        if not isinstance(sizes, list) or not sizes:
            return
        try:
            sizes = [int(x) for x in sizes]
        except Exception:
            return
        if hasattr(tab, "editor_splitter") and tab.editor_splitter.count() == len(sizes):
            tab.editor_splitter.setSizes(sizes)

    def _splitter_key_for_tab(self, tab: EditorTab) -> str:
        if tab.current_file:
            return tab.current_file
        if tab.autosave_id:
            return f"autosave:{tab.autosave_id}"
        title = self._tab_display_name(tab) if hasattr(self, "_tab_display_name") else "Untitled"
        return f"unsaved:{title}"

    def _on_editor_splitter_moved(self, _pos: int, _index: int, splitter: QSplitter) -> None:
        sizes = splitter.sizes()
        if not sizes:
            return
        tab = self.active_tab()
        if tab is not None and bool(self.settings.get("per_tab_splitter_sizes_enabled", True)):
            if not tab.current_file and not tab.autosave_id and hasattr(self, "_ensure_tab_autosave_meta"):
                self._ensure_tab_autosave_meta(tab)
            key = self._splitter_key_for_tab(tab)
            by_path = self.settings.get("editor_splitter_sizes_by_path", {})
            if not isinstance(by_path, dict):
                by_path = {}
            by_path[key] = list(sizes)
            self.settings["editor_splitter_sizes_by_path"] = by_path
        self.settings["editor_splitter_sizes"] = list(sizes)
        self._schedule_layout_auto_save()
    def toggle_workspace_panel(self, checked: bool) -> None:
        if not hasattr(self, "workspace_dock"):
            return
        self.workspace_dock.setVisible(bool(checked))

    def toggle_search_results_panel(self, checked: bool) -> None:
        if not hasattr(self, "search_results_dock"):
            return
        self.search_results_dock.setVisible(bool(checked))

    def toggle_status_panel(self, checked: bool) -> None:
        if not hasattr(self, "status_panel_dock"):
            return
        self.status_panel_dock.setVisible(bool(checked))

    def toggle_editor_panel(self, checked: bool) -> None:
        if not hasattr(self, "editor_dock"):
            return
        self.editor_dock.setVisible(bool(checked))

    def toggle_layout_lock(self, checked: bool) -> None:
        self.settings["layout_locked"] = bool(checked)
        self._apply_layout_lock()
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message("Layout locked." if checked else "Layout unlocked.", 2000)

    def _apply_layout_lock(self) -> None:
        locked = bool(self.settings.get("layout_locked", False))
        docks = []
        for name in (
            "editor_dock",
            "ai_chat_dock",
            "workspace_dock",
            "search_results_dock",
            "status_panel_dock",
            "minimap_dock",
            "outline_dock",
        ):
            dock = getattr(self, name, None)
            if dock is not None:
                docks.append(dock)
        if not hasattr(self, "_dock_default_features"):
            self._dock_default_features = {}
        for dock in docks:
            if dock not in self._dock_default_features:
                self._dock_default_features[dock] = dock.features()
        for dock in docks:
            if locked:
                defaults = self._dock_default_features.get(dock, dock.features())
                if defaults & QDockWidget.DockWidgetClosable:
                    dock.setFeatures(QDockWidget.DockWidgetClosable)
                else:
                    dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
            else:
                defaults = self._dock_default_features.get(dock, dock.features())
                dock.setFeatures(defaults)
        for toolbar_name in ("main_toolbar", "markdown_toolbar", "search_toolbar"):
            toolbar = getattr(self, toolbar_name, None)
            if toolbar is None:
                continue
            toolbar.setMovable(not locked)
            toolbar.setFloatable(not locked)
        if hasattr(self, "tab_widget"):
            self.tab_widget.setMovable(not locked)
            tab_bar = self.tab_widget.tabBar()
            if hasattr(tab_bar, "detach_enabled"):
                tab_bar.detach_enabled = not locked

    def _focused_dock_widget(self) -> QDockWidget | None:
        focus = QApplication.focusWidget()
        if focus is not None:
            widget = focus
            while widget is not None:
                if isinstance(widget, QDockWidget):
                    return widget
                widget = widget.parentWidget()
        docks = [d for d in self.findChildren(QDockWidget) if d.isVisible()]
        if len(docks) == 1:
            return docks[0]
        return None

    def _snap_focused_dock(self, area: Qt.DockWidgetArea, label: str) -> None:
        dock = self._focused_dock_widget()
        if dock is None:
            self.show_status_message("Focus a dock panel to snap it.", 2500)
            return
        self.addDockWidget(area, dock)
        dock.raise_()
        self.show_status_message(f'Snapped "{dock.windowTitle()}" to {label}.', 2200)

    def snap_dock_left(self) -> None:
        self._snap_focused_dock(Qt.LeftDockWidgetArea, "left")

    def snap_dock_right(self) -> None:
        self._snap_focused_dock(Qt.RightDockWidgetArea, "right")

    def snap_dock_bottom(self) -> None:
        self._snap_focused_dock(Qt.BottomDockWidgetArea, "bottom")

    def _encode_layout_bytes(self, data: QByteArray) -> str:
        return base64.b64encode(bytes(data)).decode("ascii")

    def _decode_layout_bytes(self, data: str) -> QByteArray:
        try:
            return QByteArray(base64.b64decode(data.encode("ascii")))
        except Exception:
            return QByteArray()

    def _layout_snapshot(self) -> dict[str, str]:
        return {
            "state": self._encode_layout_bytes(self.saveState()),
            "geometry": self._encode_layout_bytes(self.saveGeometry()),
        }

    def _ensure_default_layout(self) -> None:
        layouts = self.settings.get("layout_presets")
        if not isinstance(layouts, dict):
            layouts = {}
        if "Default" not in layouts:
            layouts["Default"] = self._layout_snapshot()
        self.settings["layout_presets"] = layouts
        if not self.settings.get("layout_active"):
            self.settings["layout_active"] = "Default"

    def _restore_layout_from_settings(self) -> None:
        if getattr(self, "_layout_restore_in_progress", False):
            return
        name = str(self.settings.get("layout_active", "") or "")
        layouts = self.settings.get("layout_presets", {})
        if not isinstance(layouts, dict) or not name or name not in layouts:
            return
        payload = layouts.get(name, {})
        if not isinstance(payload, dict):
            return
        self._layout_restore_in_progress = True
        try:
            geo = self._decode_layout_bytes(str(payload.get("geometry", "") or ""))
            state = self._decode_layout_bytes(str(payload.get("state", "") or ""))
            if not geo.isEmpty():
                self.restoreGeometry(geo)
            if not state.isEmpty():
                self.restoreState(state)
        finally:
            self._layout_restore_in_progress = False
        self._sync_layout_panel_actions()

    def save_current_layout(self) -> None:
        name = str(self.settings.get("layout_active", "") or "Default")
        layouts = self.settings.get("layout_presets", {})
        if not isinstance(layouts, dict):
            layouts = {}
        layouts[name] = self._layout_snapshot()
        self.settings["layout_presets"] = layouts
        self.settings["layout_active"] = name
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message(f'Layout saved: "{name}"', 2500)

    def save_layout_as(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Layout As", "Layout name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        layouts = self.settings.get("layout_presets", {})
        if not isinstance(layouts, dict):
            layouts = {}
        layouts[name] = self._layout_snapshot()
        self.settings["layout_presets"] = layouts
        self.settings["layout_active"] = name
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message(f'Layout saved: "{name}"', 2500)

    def load_layout(self) -> None:
        layouts = self.settings.get("layout_presets", {})
        if not isinstance(layouts, dict) or not layouts:
            QMessageBox.information(self, "Load Layout", "No saved layouts yet.")
            return
        names = sorted(layouts.keys())
        current = str(self.settings.get("layout_active", "") or "")
        start_idx = max(0, names.index(current)) if current in names else 0
        name, ok = QInputDialog.getItem(self, "Load Layout", "Layout:", names, start_idx, False)
        if not ok or not name:
            return
        self.settings["layout_active"] = name
        self._restore_layout_from_settings()
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message(f'Layout loaded: "{name}"', 2500)

    def reset_layout(self) -> None:
        self._ensure_default_layout()
        self.settings["layout_active"] = "Default"
        self._restore_layout_from_settings()
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message("Layout reset to Default.", 2500)

    def _open_search_result(self, item: dict[str, object]) -> None:
        path = str(item.get("path", "") or "")
        line_no = int(item.get("line_no", 1) or 1)
        if not path:
            return
        if not self._open_file_path(path):
            return
        tab = self.active_tab()
        if tab is None:
            return
        target_line = max(0, line_no - 1)
        tab.text_edit.set_cursor_position(target_line, 0)
        self.update_status_bar()

    def search_next_result(self) -> None:
        items = list(getattr(self, "_search_results_items", []))
        if not items:
            QMessageBox.information(self, "Search Results", "No search results available.")
            return
        idx = int(getattr(self, "_search_results_index", -1))
        idx = (idx + 1) % len(items)
        self._search_results_index = idx
        self._open_search_result(items[idx])

    def search_prev_result(self) -> None:
        items = list(getattr(self, "_search_results_items", []))
        if not items:
            QMessageBox.information(self, "Search Results", "No search results available.")
            return
        idx = int(getattr(self, "_search_results_index", -1))
        if idx < 0:
            idx = 0
        idx = (idx - 1) % len(items)
        self._search_results_index = idx
        self._open_search_result(items[idx])

    def show_search_results_window(self) -> None:
        items = list(getattr(self, "_search_results_items", []))
        if not items:
            QMessageBox.information(self, "Search Results", "No search results available.")
            return
        dlg = QDialog(self)
        query = str(getattr(self, "_search_results_query", "") or "")
        dlg.setWindowTitle("Search Results")
        dlg.resize(900, 540)
        layout = QVBoxLayout(dlg)
        header = QLabel(f"Query: {query} ({len(items)} result(s))", dlg)
        layout.addWidget(header)
        list_widget = QListWidget(dlg)
        for idx, item in enumerate(items):
            path = Path(str(item.get("path", "") or ""))
            line_no = int(item.get("line_no", 1) or 1)
            line_text = str(item.get("line_text", "") or "").strip()
            row = f"{path.name}:{line_no} | {line_text}"
            lw_item = QListWidgetItem(row, list_widget)
            lw_item.setToolTip(str(path))
            lw_item.setData(Qt.UserRole, idx)
        layout.addWidget(list_widget, 1)
        btns = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        open_btn = QPushButton("Open", dlg)
        export_btn = QPushButton("Export...", dlg)
        btns.addButton(open_btn, QDialogButtonBox.ActionRole)
        btns.addButton(export_btn, QDialogButtonBox.ActionRole)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        def _open_selected() -> None:
            current = list_widget.currentItem()
            if current is None:
                return
            idx = current.data(Qt.UserRole)
            if not isinstance(idx, int) or idx < 0 or idx >= len(items):
                return
            self._search_results_index = idx
            self._open_search_result(items[idx])
            dlg.accept()

        def _export_results() -> None:
            default = "search_results.txt"
            path, _ = QFileDialog.getSaveFileName(self, "Export Search Results", default, "Text Files (*.txt)")
            if not path:
                return
            lines = [f"Query: {query}", f"Results: {len(items)}", ""]
            for item in items:
                lines.append(
                    f"{item.get('path','')}:{int(item.get('line_no',1) or 1)} | {str(item.get('line_text','') or '').strip()}"
                )
            try:
                Path(path).write_text("\n".join(lines), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Search Results", f"Export failed:\n{exc}")
                return
            self.show_status_message(f"Search results exported: {path}", 3000)

        list_widget.itemDoubleClicked.connect(lambda _item: _open_selected())
        open_btn.clicked.connect(_open_selected)
        export_btn.clicked.connect(_export_results)
        list_widget.setCurrentRow(max(0, int(getattr(self, "_search_results_index", 0))))
        dlg.exec()

    def search_select_and_find_next(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        selected = tab.text_edit.selected_text().strip()
        if selected:
            self.last_search_text = selected
        self.edit_find_next()

    def search_select_and_find_previous(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        selected = tab.text_edit.selected_text().strip()
        if selected:
            self.last_search_text = selected
        self.edit_find_previous()

    def search_find_volatile_next(self) -> None:
        self.edit_find_next()

    def search_find_volatile_previous(self) -> None:
        self.edit_find_previous()

    def search_incremental(self) -> None:
        self.show_search_panel()
        if hasattr(self, "search_input"):
            self.search_input.setFocus()

    def search_goto_line(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        total_lines = max(1, len(tab.text_edit.get_text().splitlines()) or 1)
        line, ok = QInputDialog.getInt(self, "Go To", "Line number:", 1, 1, total_lines)
        if not ok:
            return
        tab.text_edit.set_cursor_position(line - 1, 0)
        self.update_status_bar()

    def search_mark(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        text = tab.text_edit.selected_text().strip() or (self.last_search_text or "")
        if not text:
            text, ok = QInputDialog.getText(self, "Mark", "Text to mark:")
            if not ok or not text.strip():
                return
        style_id = 0
        source = tab.text_edit.get_text()
        styled = self._tab_style_lines(tab)
        for i, line in enumerate(source.splitlines()):
            if text in line:
                styled[i] = style_id
        self._apply_line_styles(tab)
        self.show_status_message("Marked search matches.", 2500)

    def search_change_history_next(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        lines = getattr(tab, "change_history_lines", [])
        if not lines:
            return
        cur, _ = tab.text_edit.cursor_position()
        for ln in lines:
            if ln > cur:
                tab.text_edit.set_cursor_position(ln, 0)
                return
        tab.text_edit.set_cursor_position(lines[0], 0)

    def search_change_history_previous(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        lines = getattr(tab, "change_history_lines", [])
        if not lines:
            return
        cur, _ = tab.text_edit.cursor_position()
        for ln in reversed(lines):
            if ln < cur:
                tab.text_edit.set_cursor_position(ln, 0)
                return
        tab.text_edit.set_cursor_position(lines[-1], 0)

    def search_change_history_clear(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        setattr(tab, "change_history_lines", [])
        self.show_status_message("Change history cleared.", 2500)

    def search_style_all_occurrences(self, style_id: int) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        token = tab.text_edit.selected_text().strip()
        if not token:
            token = self.last_search_text or ""
        if not token:
            QMessageBox.information(self, "Style All Occurrences", "Select text or perform Find first.")
            return
        styled = self._tab_style_lines(tab)
        for i, line in enumerate(tab.text_edit.get_text().splitlines()):
            if token in line:
                styled[i] = style_id
        self._apply_line_styles(tab)

    def search_style_one_token(self, style_id: int) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        line, _ = tab.text_edit.cursor_position()
        styled = self._tab_style_lines(tab)
        styled[line] = style_id
        self._apply_line_styles(tab)

    def search_clear_style(self, style_id: int | None = None) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        styled = self._tab_style_lines(tab)
        if style_id is None:
            styled.clear()
        else:
            to_delete = [ln for ln, sid in styled.items() if sid == style_id]
            for ln in to_delete:
                styled.pop(ln, None)
        self._apply_line_styles(tab)

    def search_jump_up_styled(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        styled = self._tab_style_lines(tab)
        if not styled:
            return
        cur, _ = tab.text_edit.cursor_position()
        lines = sorted(styled.keys())
        for ln in reversed(lines):
            if ln < cur:
                tab.text_edit.set_cursor_position(ln, 0)
                return
        tab.text_edit.set_cursor_position(lines[-1], 0)

    def search_jump_down_styled(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        styled = self._tab_style_lines(tab)
        if not styled:
            return
        cur, _ = tab.text_edit.cursor_position()
        lines = sorted(styled.keys())
        for ln in lines:
            if ln > cur:
                tab.text_edit.set_cursor_position(ln, 0)
                return
        tab.text_edit.set_cursor_position(lines[0], 0)

    def search_copy_styled_text(self, style_id: int | None = None) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        styled = self._tab_style_lines(tab)
        if not styled:
            return
        lines = tab.text_edit.get_text().splitlines()
        selected_lines: list[str] = []
        for ln, sid in sorted(styled.items()):
            if style_id is not None and sid != style_id:
                continue
            if 0 <= ln < len(lines):
                selected_lines.append(lines[ln])
        if not selected_lines:
            return
        QApplication.clipboard().setText("\n".join(selected_lines))
        self.show_status_message("Styled text copied.", 2500)

    # ---- Bookmark line operations ----
    def _bookmarked_lines_sorted(self, tab: EditorTab) -> list[int]:
        return sorted(int(x) for x in tab.bookmarks if isinstance(x, int))

    def bookmark_cut_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        marks = self._bookmarked_lines_sorted(tab)
        if not marks:
            return
        cut = [lines[i] for i in marks if 0 <= i < len(lines)]
        QApplication.clipboard().setText("\n".join(cut))
        kept = [line for idx, line in enumerate(lines) if idx not in set(marks)]
        tab.text_edit.set_text("\n".join(kept))
        tab.text_edit.set_modified(True)
        tab.bookmarks.clear()
        self._sync_scintilla_bookmark_markers(tab)

    def bookmark_copy_lines(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        lines = tab.text_edit.get_text().splitlines()
        marks = self._bookmarked_lines_sorted(tab)
        if not marks:
            return
        copied = [lines[i] for i in marks if 0 <= i < len(lines)]
        QApplication.clipboard().setText("\n".join(copied))
        self.show_status_message("Bookmarked lines copied.", 2500)

    def bookmark_paste_replace_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        marks = self._bookmarked_lines_sorted(tab)
        if not marks:
            return
        clip = QApplication.clipboard().text()
        if not clip:
            return
        repl = clip.splitlines()
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        for i, ln in enumerate(marks):
            if 0 <= ln < len(lines):
                lines[ln] = repl[i] if i < len(repl) else repl[-1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def bookmark_remove_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        marks = set(self._bookmarked_lines_sorted(tab))
        if not marks:
            return
        lines = tab.text_edit.get_text().splitlines()
        kept = [line for i, line in enumerate(lines) if i not in marks]
        tab.text_edit.set_text("\n".join(kept))
        tab.text_edit.set_modified(True)
        tab.bookmarks.clear()
        self._sync_scintilla_bookmark_markers(tab)

    def bookmark_remove_non_bookmarked_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        marks = set(self._bookmarked_lines_sorted(tab))
        if not marks:
            return
        lines = tab.text_edit.get_text().splitlines()
        kept = [line for i, line in enumerate(lines) if i in marks]
        tab.text_edit.set_text("\n".join(kept))
        tab.text_edit.set_modified(True)
        tab.bookmarks = set(range(len(kept)))
        self._sync_scintilla_bookmark_markers(tab)

    def bookmark_inverse(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        line_count = len(tab.text_edit.get_text().splitlines())
        all_lines = set(range(line_count))
        tab.bookmarks = all_lines.difference(set(tab.bookmarks))
        self._sync_scintilla_bookmark_markers(tab)

    def show_about(self) -> None:
        username = getpass.getuser()
        self.log_event("Info", "Opened About dialog")
        app_mode_text = "You are using the production app." if getattr(sys, "frozen", False) else "You are using the development app."

        # --- Read version from file ---
        version_path = resolve_asset_path("version.txt")
        if version_path is None:
            version = "v?.?.?"  # fallback if missing
        else:
            try:
                version = version_path.read_text(encoding="utf-8").strip()
            except OSError:
                version = "v?.?.?"  # fallback if missing
        capsule_path = str(self.settings.get("pending_update_installer_path", "") or "").strip()
        capsule_version = str(self.settings.get("pending_update_version", "") or "").strip()
        if capsule_path:
            capsule_text = f"{html_escape(capsule_version or 'unknown')} @ {html_escape(capsule_path)}"
        else:
            capsule_text = "none"

        about_box = QMessageBox(self)
        about_box.setWindowTitle("About Pypad")
        about_box.setIcon(QMessageBox.Information)
        about_box.setTextFormat(Qt.RichText)
        about_box.setTextInteractionFlags(Qt.TextBrowserInteraction)
        about_box.setStandardButtons(QMessageBox.Ok)

        # --- Add version info dynamically ---
        about_box.setText(
            f"""
    <a href="easteregg"><b>Pypad</b></a><br>
    Simple Pypad implemented with PySide6<br>
    Version: <b>{version}</b><br><br>
    <b>{html_escape(app_mode_text)}</b><br><br>
    Pending update capsule: <b>{capsule_text}</b><br><br>

    &copy; 2026 Pypad Project<br>
    Inspired by Windows 10 Notepad<br><br>

    <b>This product is registered to:</b><br>
    {username}
    """
        )

        # --- Handle easter egg link ---
        text_label = about_box.findChild(QLabel, "qt_msgbox_label")
        if text_label is not None:
            text_label.setOpenExternalLinks(False)
            text_label.linkActivated.connect(
                lambda link: (
                    about_box.done(0),
                    self.log_event("Info", "About dialog easter egg link clicked"),
                    self.trigger_easter_egg(),
                )
                if link == "easteregg"
                else None
            )

        about_box.exec()

    def _maybe_show_welcome_tutorial(self) -> None:
        if self.settings.get("welcome_tutorial_seen", False):
            return
        self.show_first_time_tutorial()

    def show_first_time_tutorial(self) -> None:
        tutorial = InteractiveTutorialDialog(self)
        tutorial.exec()
        self.settings["welcome_tutorial_seen"] = True
        self.save_settings_to_disk()
        self.show_status_message("First time tutorial completed.", 2500)

    def show_user_guide(self) -> None:
        guide_text = """
Pypad User Guide 📘

1. Core Editing ✍️
- New/Open/Save/Save As are in File menu.
- Drag a text file into the app to open it.
- Use Ctrl+F for search panel, F3/Shift+F3 for next/previous.

2. Tabs 🗂️
- Middle-click any tab to close it.
- Pin Tab keeps important tabs grouped at the top.
- Favorite Tab marks important files and lists them under File > Favorite Files.

3. Markdown and Code 🧠
- Use Markdown menu for headings, lists, links, tables.
- Live Markdown Preview toggles side-by-side preview.
- Syntax language picker is in status bar.

4. Versioning and Recovery ♻️
- Version History restores earlier snapshots and shows diffs.
- Autosave periodically captures unsaved changes.
- On startup, crash recovery offers unsaved autosave drafts.

5. Reminders and Tasks ⏰
- Reminders & Alarms let you schedule alerts, recurrence, and snooze.
- Checklist shortcuts can toggle - [ ] and - [x] tasks.

6. Templates and Export 📤
- File > Templates inserts meeting, daily log, and checklist templates.
- File > Export supports PDF, Markdown, HTML, DOCX, and ODT.

7. Workspace 📁
- File > Workspace > Open Workspace Folder sets active project folder.
- Browse files via Workspace Files.
- Search across workspace with Search Workspace.

8. Security 🔐
- File > Security enables per-note encryption.
- Use .encnote extension for encrypted note files.
- Open encrypted notes by entering the note password.

9. AI Features 🤖
- File > AI > Ask AI for general prompts.
- Explain Selection with AI explains selected text.
- AI Inline Edit (Preview) edits selection/paragraph with hunk-level accept/reject.
- Ask Workspace (Citations) answers from workspace excerpts with file+line citations.
- AI Chat Panel (left dock) supports prompt/response bubbles with live generation.
- AI results open in a panel with Copy / Insert / Replace Selection.
- Configure API key and model in Settings > AI & Updates.
- Tools > Collaboration Presence shows active clients and revision state.
- Tools > Resolve Collaboration Conflict supports shared/local/merge-marker/AI-merge workflows.

10. Updates 🚀
- Help > Check for Updates reads the update feed and shows changelog notes.
- Downloaded updates can be opened directly from the app.
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("User Guide")
        dlg.resize(760, 560)
        layout = QVBoxLayout(dlg)
        viewer = QTextEdit(dlg)
        viewer.setReadOnly(True)
        viewer.setPlainText(guide_text.strip())
        layout.addWidget(viewer)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        buttons.button(QDialogButtonBox.Close).clicked.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

    @staticmethod
    def _fmt_timestamp(ts: float | None) -> str:
        if ts is None:
            return "N/A"
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "N/A"

    def show_document_summary(self) -> None:
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "Document Summary", "No active document.")
            return

        text = tab.text_edit.get_text()
        file_path = tab.current_file or "(unsaved)"
        created = None
        modified = None
        if tab.current_file:
            try:
                st = Path(tab.current_file).stat()
                created = st.st_ctime
                modified = st.st_mtime
            except Exception:
                created = None
                modified = None

        chars_no_eol = len(text.replace("\r", "").replace("\n", ""))
        words = len(re.findall(r"\S+", text))
        lines = text.count("\n") + (1 if text else 0)

        selection = tab.text_edit.selection_range()
        selected_chars = 0
        selected_bytes = 0
        selected_range = "None"
        if selection is not None:
            l1, c1, l2, c2 = selection
            selected_text = tab.text_edit.selected_text()
            selected_chars = len(selected_text)
            selected_bytes = len(selected_text.encode("utf-8"))
            start_index = tab.text_edit.index_from_line_col(l1, c1)
            end_index = tab.text_edit.index_from_line_col(l2, c2)
            selected_range = (
                f"L{l1 + 1}:C{c1 + 1} -> L{l2 + 1}:C{c2 + 1} "
                f"(index {start_index}..{end_index})"
            )

        summary = (
            f"Path: {file_path}\n"
            f"Created: {self._fmt_timestamp(created)}\n"
            f"Modified: {self._fmt_timestamp(modified)}\n\n"
            f"Characters (without line endings): {chars_no_eol}\n"
            f"Words: {words}\n"
            f"Lines: {lines}\n\n"
            f"Selected characters: {selected_chars}\n"
            f"Selected bytes (UTF-8): {selected_bytes}\n"
            f"Selection range: {selected_range}\n"
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Document Summary")
        dlg.resize(700, 460)
        layout = QVBoxLayout(dlg)
        viewer = QTextEdit(dlg)
        viewer.setReadOnly(True)
        viewer.setPlainText(summary)
        layout.addWidget(viewer)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, Qt.Orientation.Horizontal, dlg)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec()

    def enforce_privacy_lock(self) -> None:
        """Show a simple lock screen if privacy_lock is enabled.

        The user can unlock with either the configured password or PIN.
        This is intentionally lightweight and not cryptographically secure.
        """
        if not self.settings.get("privacy_lock", False):
            return

        stored_password = (self.settings.get("lock_password") or "").strip()
        stored_pin = (self.settings.get("lock_pin") or "").strip()

        # If no credentials are configured, don't block the user.
        if not stored_password and not stored_pin:
            return

        class LockDialog(QDialog):
            def __init__(self, parent=None, want_password: bool = True, want_pin: bool = True) -> None:
                super().__init__(parent)
                self.setWindowTitle("Unlock Pypad")
                layout = QFormLayout(self)

                self.password_edit: QLineEdit | None = None
                self.pin_edit: QLineEdit | None = None

                if want_password:
                    self.password_edit = QLineEdit(self)
                    self.password_edit.setEchoMode(QLineEdit.Password)
                    layout.addRow("Password:", self.password_edit)

                if want_pin:
                    self.pin_edit = QLineEdit(self)
                    self.pin_edit.setMaxLength(10)
                    self.pin_edit.setPlaceholderText("Digits only")
                    layout.addRow("PIN:", self.pin_edit)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                    Qt.Horizontal,
                    self,
                )
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)

            def get_values(self) -> tuple[str, str]:
                pw = self.password_edit.text() if self.password_edit is not None else ""
                pin = self.pin_edit.text() if self.pin_edit is not None else ""
                return pw.strip(), pin.strip()

        dlg = LockDialog(
            self,
            want_password=bool(stored_password),
            want_pin=bool(stored_pin),
        )

        while True:
            result = dlg.exec()
            if result != QDialog.Accepted:
                # User cancelled: close the window.
                self.close()
                return

            entered_password, entered_pin = dlg.get_values()
            ok_password = bool(stored_password) and entered_password == stored_password
            ok_pin = bool(stored_pin) and entered_pin == stored_pin

            if ok_password or ok_pin:
                # Successfully unlocked.
                return

            QMessageBox.warning(
                self,
                "Unlock Failed",
                "Incorrect password or PIN. Please try again.",
            )

    def trigger_easter_egg(self) -> None:
        """Play a short colorful theme animation, then restore normal theming."""
        if self._easter_egg_running:
            self.log_event("Debug", "Color burst ignored because one is already running")
            return
        self._easter_egg_running = True
        self.log_event("Info", "Color burst started")

        # Small palette of bright color combinations
        palettes: list[tuple[str, str]] = [
            ("#ff1744", "#ffffff"),  # red
            ("#ff9100", "#000000"),  # orange
            ("#ffea00", "#000000"),  # yellow
            ("#00e676", "#000000"),  # green
            ("#00b0ff", "#ffffff"),  # blue
            ("#d500f9", "#ffffff"),  # purple
        ]
        random.shuffle(palettes)

        step_ms = 150
        total_steps = len(palettes)
        original_settings = dict(self.settings)

        def apply_step(index: int) -> None:
            if index >= total_steps:
                self.settings = original_settings
                self.apply_settings()
                self._easter_egg_running = False
                self.log_event("Info", "Color burst finished")
                return

            bg, text = palettes[index]
            self.settings["use_custom_colors"] = True
            self.settings["custom_editor_bg"] = bg
            self.settings["custom_chrome_bg"] = bg
            self.settings["custom_editor_fg"] = text
            self.settings["accent_color"] = bg
            self.apply_settings()
            QTimer.singleShot(step_ms, lambda: apply_step(index + 1))

        apply_step(0)



class SettingsDialog(QDialog):
    def __init__(self, parent: Notepad, settings: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 500)
        self._settings = dict(settings)
        self.reset_to_defaults_requested = False

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget(scroll)
        scroll.setWidget(container)

        vbox = QVBoxLayout(container)

        # Dark Mode
        dark_group = QGroupBox("Dark Mode \U0001F319", container)
        dark_layout = QVBoxLayout(dark_group)
        self.dark_checkbox = QCheckBox("Enable dark mode (night theme)", dark_group)
        self.dark_checkbox.setChecked(self._settings.get("dark_mode", False))
        self.app_style_combo = QComboBox(dark_group)
        available_styles = sorted(QStyleFactory.keys())
        self.app_style_combo.addItem("System Default")
        self.app_style_combo.addItems(available_styles)
        current_style = str(self._settings.get("app_style", "System Default") or "System Default")
        style_index = self.app_style_combo.findText(current_style)
        if style_index >= 0:
            self.app_style_combo.setCurrentIndex(style_index)
        dark_layout.addWidget(self.dark_checkbox)
        dark_layout.addWidget(QLabel("Widget style engine:", dark_group))
        dark_layout.addWidget(self.app_style_combo)
        vbox.addWidget(dark_group)

        # Theme Customization
        theme_group = QGroupBox("Theme Customization \U0001F3A8", container)
        theme_form = QFormLayout(theme_group)
        self.theme_combo = QComboBox(theme_group)
        self.theme_combo.addItems(["Default", "Soft Light", "High Contrast", "Solarized Light", "Ocean Blue"])
        current_theme = self._settings.get("theme", "Default")
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self.accent_color_value = self._normalized_or_default(self._settings.get("accent_color", "#4a90e2"), "#4a90e2")
        self.custom_editor_bg_value = self._normalized_or_default(self._settings.get("custom_editor_bg", ""), "")
        self.custom_editor_fg_value = self._normalized_or_default(self._settings.get("custom_editor_fg", ""), "")
        self.custom_chrome_bg_value = self._normalized_or_default(self._settings.get("custom_chrome_bg", ""), "")

        self.accent_color_label, accent_color_row = self._build_color_picker_row(
            "Pick accent...", self.accent_color_value, allow_empty=False
        )
        self.use_custom_colors_checkbox = QCheckBox("Use custom colors", theme_group)
        self.use_custom_colors_checkbox.setChecked(self._settings.get("use_custom_colors", False))
        self.custom_editor_bg_label, custom_editor_bg_row = self._build_color_picker_row(
            "Pick editor bg...", self.custom_editor_bg_value, allow_empty=True
        )
        self.custom_editor_fg_label, custom_editor_fg_row = self._build_color_picker_row(
            "Pick editor text...", self.custom_editor_fg_value, allow_empty=True
        )
        self.custom_chrome_bg_label, custom_chrome_bg_row = self._build_color_picker_row(
            "Pick chrome bg...", self.custom_chrome_bg_value, allow_empty=True
        )
        self.background_input = QLineEdit(theme_group)
        self.background_input.setPlaceholderText("Background hint (e.g. 'paper', 'code', 'midnight')")
        theme_form.addRow("Theme preset:", self.theme_combo)
        theme_form.addRow("Accent color:", accent_color_row)
        theme_form.addRow(self.use_custom_colors_checkbox)
        theme_form.addRow("Editor bg:", custom_editor_bg_row)
        theme_form.addRow("Editor text:", custom_editor_fg_row)
        theme_form.addRow("Chrome bg:", custom_chrome_bg_row)
        theme_form.addRow("Background style hint:", self.background_input)
        vbox.addWidget(theme_group)

        # Font Size & Style
        font_group = QGroupBox("Font Size & Style \u270F\uFE0F", container)
        font_layout = QFormLayout(font_group)
        self.font_family_edit = QLineEdit(font_group)
        self.font_family_edit.setText(self._settings.get("font_family", ""))
        self.font_size_slider = QSlider(Qt.Horizontal, font_group)
        self.font_size_slider.setMinimum(8)
        self.font_size_slider.setMaximum(32)
        self.font_size_slider.setValue(self._settings.get("font_size", 11))
        self.font_size_label = QLabel(str(self.font_size_slider.value()), font_group)

        size_row = QHBoxLayout()
        size_row.addWidget(self.font_size_slider)
        size_row.addWidget(self.font_size_label)

        font_layout.addRow("Font family:", self.font_family_edit)
        font_layout.addRow("Font size:", QWidget())
        font_layout.itemAt(font_layout.rowCount() - 1, QFormLayout.FieldRole).widget().setLayout(size_row)

        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_label.setText(str(v))
        )
        vbox.addWidget(font_group)

        # Sound Settings
        sound_group = QGroupBox("Sound Settings \U0001F50A", container)
        sound_layout = QVBoxLayout(sound_group)
        self.sound_checkbox = QCheckBox("Enable sound effects / notifications", sound_group)
        self.sound_checkbox.setChecked(self._settings.get("sound_enabled", True))
        self.music_checkbox = QCheckBox("Allow background music (where supported)", sound_group)
        self.music_checkbox.setChecked(self._settings.get("background_music", False))
        sound_layout.addWidget(self.sound_checkbox)
        sound_layout.addWidget(self.music_checkbox)
        vbox.addWidget(sound_group)

        # Language
        lang_group = QGroupBox("Language \U0001F310", container)
        lang_layout = QFormLayout(lang_group)
        self.lang_combo = QComboBox(lang_group)
        self.lang_combo.addItems(["English", "EspaÃ±ol", "Deutsch", "FranÃ§ais"])
        current_lang = self._settings.get("language", "English")
        idx = self.lang_combo.findText(current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        lang_layout.addRow("App language:", self.lang_combo)
        vbox.addWidget(lang_group)

        # Notifications
        notif_group = QGroupBox("Notifications \U0001F6CE\uFE0F", container)
        notif_layout = QVBoxLayout(notif_group)
        self.notifications_checkbox = QCheckBox("Show pop-up notifications and alerts", notif_group)
        self.notifications_checkbox.setChecked(self._settings.get("notifications_enabled", True))
        notif_layout.addWidget(self.notifications_checkbox)
        vbox.addWidget(notif_group)

        # Productivity & Focus
        productivity_group = QGroupBox("Productivity & Focus \U0001F9E0", container)
        productivity_form = QFormLayout(productivity_group)

        self.version_history_checkbox = QCheckBox("Enable version history", productivity_group)
        self.version_history_checkbox.setChecked(self._settings.get("version_history_enabled", True))
        self.version_history_interval_spin = QSpinBox(productivity_group)
        self.version_history_interval_spin.setRange(5, 600)
        self.version_history_interval_spin.setValue(int(self._settings.get("version_history_interval_sec", 30)))
        self.version_history_max_spin = QSpinBox(productivity_group)
        self.version_history_max_spin.setRange(5, 500)
        self.version_history_max_spin.setValue(int(self._settings.get("version_history_max_entries", 50)))

        self.autosave_checkbox = QCheckBox("Enable autosave", productivity_group)
        self.autosave_checkbox.setChecked(self._settings.get("autosave_enabled", True))
        self.autosave_interval_spin = QSpinBox(productivity_group)
        self.autosave_interval_spin.setRange(10, 600)
        self.autosave_interval_spin.setValue(int(self._settings.get("autosave_interval_sec", 30)))

        self.reminders_checkbox = QCheckBox("Enable reminders & alarms", productivity_group)
        self.reminders_checkbox.setChecked(self._settings.get("reminders_enabled", True))
        self.reminder_interval_spin = QSpinBox(productivity_group)
        self.reminder_interval_spin.setRange(10, 600)
        self.reminder_interval_spin.setValue(int(self._settings.get("reminder_check_interval_sec", 30)))

        self.syntax_highlight_checkbox = QCheckBox("Enable code syntax highlighting", productivity_group)
        self.syntax_highlight_checkbox.setChecked(self._settings.get("syntax_highlighting_enabled", True))
        self.syntax_mode_combo = QComboBox(productivity_group)
        self.syntax_mode_combo.addItems(["Auto", "Python", "JavaScript", "JSON", "Markdown", "Plain"])
        current_mode = str(self._settings.get("syntax_highlighting_mode", "Auto"))
        idx = self.syntax_mode_combo.findText(current_mode, Qt.MatchFixedString)
        if idx >= 0:
            self.syntax_mode_combo.setCurrentIndex(idx)

        self.checklist_toggle_checkbox = QCheckBox("Enable checklist toggle action", productivity_group)
        self.checklist_toggle_checkbox.setChecked(self._settings.get("checklist_toggle_enabled", True))

        self.focus_hide_menu_checkbox = QCheckBox("Hide menu bar in focus mode", productivity_group)
        self.focus_hide_menu_checkbox.setChecked(self._settings.get("focus_hide_menu", True))
        self.focus_hide_toolbar_checkbox = QCheckBox("Hide toolbars in focus mode", productivity_group)
        self.focus_hide_toolbar_checkbox.setChecked(self._settings.get("focus_hide_toolbar", True))
        self.focus_hide_status_checkbox = QCheckBox("Hide status bar in focus mode", productivity_group)
        self.focus_hide_status_checkbox.setChecked(self._settings.get("focus_hide_status", False))
        self.focus_hide_tabs_checkbox = QCheckBox("Hide tabs in focus mode", productivity_group)
        self.focus_hide_tabs_checkbox.setChecked(self._settings.get("focus_hide_tabs", False))
        self.focus_escape_exit_checkbox = QCheckBox("Allow Esc to disable focus mode", productivity_group)
        self.focus_escape_exit_checkbox.setChecked(self._settings.get("focus_allow_escape_exit", True))

        productivity_form.addRow(self.version_history_checkbox)
        productivity_form.addRow("Version snapshot interval (sec):", self.version_history_interval_spin)
        productivity_form.addRow("Max history entries:", self.version_history_max_spin)
        productivity_form.addRow(self.autosave_checkbox)
        productivity_form.addRow("Autosave interval (sec):", self.autosave_interval_spin)
        productivity_form.addRow(self.reminders_checkbox)
        productivity_form.addRow("Reminder check interval (sec):", self.reminder_interval_spin)
        productivity_form.addRow(self.syntax_highlight_checkbox)
        productivity_form.addRow("Syntax mode:", self.syntax_mode_combo)
        productivity_form.addRow(self.checklist_toggle_checkbox)
        productivity_form.addRow(self.focus_hide_menu_checkbox)
        productivity_form.addRow(self.focus_hide_toolbar_checkbox)
        productivity_form.addRow(self.focus_hide_status_checkbox)
        productivity_form.addRow(self.focus_hide_tabs_checkbox)
        productivity_form.addRow(self.focus_escape_exit_checkbox)
        vbox.addWidget(productivity_group)

        # Privacy & Security
        privacy_group = QGroupBox("Privacy & Security \U0001F512", container)
        privacy_layout = QFormLayout(privacy_group)
        self.privacy_lock_checkbox = QCheckBox("Enable lock screen on open", privacy_group)
        self.privacy_lock_checkbox.setChecked(self._settings.get("privacy_lock", False))
        self.lock_password_edit = QLineEdit(privacy_group)
        self.lock_password_edit.setEchoMode(QLineEdit.Password)
        self.lock_password_edit.setPlaceholderText("Optional password")
        self.lock_password_edit.setText(self._settings.get("lock_password", ""))
        self.lock_pin_edit = QLineEdit(privacy_group)
        self.lock_pin_edit.setMaxLength(10)
        self.lock_pin_edit.setPlaceholderText("Optional PIN (digits)")
        self.lock_pin_edit.setText(self._settings.get("lock_pin", ""))

        privacy_layout.addRow(self.privacy_lock_checkbox)
        privacy_layout.addRow("Password:", self.lock_password_edit)
        privacy_layout.addRow("PIN:", self.lock_pin_edit)
        vbox.addWidget(privacy_group)

        # AI & Updates
        ai_group = QGroupBox("AI & Updates", container)
        ai_form = QFormLayout(ai_group)
        self.gemini_api_key_edit = QLineEdit(ai_group)
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("Gemini API key")
        self.gemini_api_key_edit.setText(self._settings.get("gemini_api_key", ""))
        self.ai_model_edit = QLineEdit(ai_group)
        self.ai_model_edit.setPlaceholderText("gemini-3-flash-preview")
        self.ai_model_edit.setText(self._settings.get("ai_model", "gemini-3-flash-preview"))
        self.update_feed_url_edit = QLineEdit(ai_group)
        self.update_feed_url_edit.setPlaceholderText(DEFAULT_UPDATE_FEED_URL)
        self.update_feed_url_edit.setReadOnly(True)
        self.update_feed_url_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.update_feed_url_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_feed_url_edit.setToolTip("Update feed URL is managed by the app and is read-only.")
        self.update_feed_url_edit.setText(
            self._settings.get("update_feed_url", DEFAULT_UPDATE_FEED_URL)
        )
        self.auto_check_updates_checkbox = QCheckBox("Check for updates on startup", ai_group)
        self.auto_check_updates_checkbox.setChecked(self._settings.get("auto_check_updates", True))

        ai_form.addRow("Gemini API key:", self.gemini_api_key_edit)
        ai_form.addRow("Model:", self.ai_model_edit)
        ai_form.addRow("Update feed URL:", self.update_feed_url_edit)
        ai_form.addRow(self.auto_check_updates_checkbox)
        vbox.addWidget(ai_group)

        # Backup & Restore
        backup_group = QGroupBox("Backup & Restore \U0001F4BE", container)
        backup_layout = QHBoxLayout(backup_group)
        self.backup_btn = QPushButton("Backup Settings...", backup_group)
        self.restore_btn = QPushButton("Restore Settings...", backup_group)
        self.reset_defaults_btn = QPushButton("Reset to Default (Close App)", backup_group)
        backup_layout.addWidget(self.backup_btn)
        backup_layout.addWidget(self.restore_btn)
        backup_layout.addWidget(self.reset_defaults_btn)
        vbox.addWidget(backup_group)

        # Advanced Options
        adv_group = QGroupBox("Advanced Options \u2699\uFE0F", container)
        adv_layout = QVBoxLayout(adv_group)
        self.experimental_checkbox = QCheckBox("Enable experimental features", adv_group)
        adv_layout.addWidget(self.experimental_checkbox)
        vbox.addWidget(adv_group)

        vbox.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        main_layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.backup_btn.clicked.connect(self.backup_settings)
        self.restore_btn.clicked.connect(self.restore_settings)
        self.reset_defaults_btn.clicked.connect(self.reset_to_defaults_and_close)

    @staticmethod
    def _normalized_or_default(value: str, fallback: str) -> str:
        normalized = MiscMixin._normalize_hex_color(value)
        if normalized is not None:
            return normalized
        return fallback

    def _build_color_picker_row(self, button_text: str, initial_hex: str, allow_empty: bool) -> tuple[QLabel, QWidget]:
        holder = QWidget(self)
        row_layout = QHBoxLayout(holder)
        row_layout.setContentsMargins(0, 0, 0, 0)
        value_label = QLabel(initial_hex if initial_hex else "(auto)", holder)
        value_label.setMinimumWidth(90)
        pick_button = QPushButton(button_text, holder)
        clear_button = QPushButton("Clear", holder)
        clear_button.setVisible(allow_empty)

        def apply_value(hex_value: str) -> None:
            if hex_value:
                value_label.setText(hex_value)
                value_label.setStyleSheet(f"background-color: {hex_value}; border: 1px solid #888; padding: 2px;")
            else:
                value_label.setText("(auto)")
                value_label.setStyleSheet("")

        def pick_color() -> None:
            initial = value_label.text() if value_label.text() != "(auto)" else "#ffffff"
            color = QColorDialog.getColor(QColor(initial), self, "Select Color")
            if color.isValid():
                apply_value(color.name())

        pick_button.clicked.connect(pick_color)
        clear_button.clicked.connect(lambda: apply_value(""))
        apply_value(initial_hex)

        row_layout.addWidget(value_label)
        row_layout.addWidget(pick_button)
        row_layout.addWidget(clear_button)
        return value_label, holder

    @staticmethod
    def _label_color_value(label: QLabel) -> str:
        value = label.text().strip()
        if value == "(auto)":
            return ""
        return value

    def get_settings(self) -> dict:
        s = dict(self._settings)
        s["app_style"] = self.app_style_combo.currentText()
        s["dark_mode"] = self.dark_checkbox.isChecked()
        s["theme"] = self.theme_combo.currentText()
        s["accent_color"] = self._normalized_or_default(self._label_color_value(self.accent_color_label), "#4a90e2")
        s["use_custom_colors"] = self.use_custom_colors_checkbox.isChecked()
        s["custom_editor_bg"] = self._normalized_or_default(self._label_color_value(self.custom_editor_bg_label), "")
        s["custom_editor_fg"] = self._normalized_or_default(self._label_color_value(self.custom_editor_fg_label), "")
        s["custom_chrome_bg"] = self._normalized_or_default(self._label_color_value(self.custom_chrome_bg_label), "")
        s["font_family"] = self.font_family_edit.text().strip() or s.get("font_family")
        s["font_size"] = int(self.font_size_slider.value())
        s["sound_enabled"] = self.sound_checkbox.isChecked()
        s["background_music"] = self.music_checkbox.isChecked()
        s["language"] = self.lang_combo.currentText()
        s["notifications_enabled"] = self.notifications_checkbox.isChecked()
        s["version_history_enabled"] = self.version_history_checkbox.isChecked()
        s["version_history_interval_sec"] = int(self.version_history_interval_spin.value())
        s["version_history_max_entries"] = int(self.version_history_max_spin.value())
        s["autosave_enabled"] = self.autosave_checkbox.isChecked()
        s["autosave_interval_sec"] = int(self.autosave_interval_spin.value())
        s["reminders_enabled"] = self.reminders_checkbox.isChecked()
        s["reminder_check_interval_sec"] = int(self.reminder_interval_spin.value())
        s["syntax_highlighting_enabled"] = self.syntax_highlight_checkbox.isChecked()
        s["syntax_highlighting_mode"] = self.syntax_mode_combo.currentText()
        s["checklist_toggle_enabled"] = self.checklist_toggle_checkbox.isChecked()
        s["focus_hide_menu"] = self.focus_hide_menu_checkbox.isChecked()
        s["focus_hide_toolbar"] = self.focus_hide_toolbar_checkbox.isChecked()
        s["focus_hide_status"] = self.focus_hide_status_checkbox.isChecked()
        s["focus_hide_tabs"] = self.focus_hide_tabs_checkbox.isChecked()
        s["focus_allow_escape_exit"] = self.focus_escape_exit_checkbox.isChecked()
        s["privacy_lock"] = self.privacy_lock_checkbox.isChecked()
        s["lock_password"] = self.lock_password_edit.text()
        s["lock_pin"] = self.lock_pin_edit.text()
        s["gemini_api_key"] = self.gemini_api_key_edit.text().strip()
        s["ai_model"] = self.ai_model_edit.text().strip() or "gemini-3-flash-preview"
        s["update_feed_url"] = self.update_feed_url_edit.text().strip() or DEFAULT_UPDATE_FEED_URL
        s["auto_check_updates"] = self.auto_check_updates_checkbox.isChecked()
        return s

    def backup_settings(self) -> None:
        import json

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup Settings",
            "",
            "Settings Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.get_settings(), f, indent=2)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Backup Failed", f"Could not save settings:\n{e}")

    def restore_settings(self) -> None:
        import json

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Settings",
            "",
            "Settings Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Restore Failed", f"Could not load settings:\n{e}")
            return

        # Update UI from loaded settings (best-effort)
        self._settings.update(loaded)
        style_idx = self.app_style_combo.findText(str(self._settings.get("app_style", "System Default")))
        if style_idx >= 0:
            self.app_style_combo.setCurrentIndex(style_idx)
        else:
            self.app_style_combo.setCurrentIndex(0)
        self.dark_checkbox.setChecked(self._settings.get("dark_mode", False))
        idx = self.theme_combo.findText(self._settings.get("theme", "Default"))
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        restored_accent = self._normalized_or_default(self._settings.get("accent_color", "#4a90e2"), "#4a90e2")
        self.accent_color_label.setText(restored_accent)
        self.accent_color_label.setStyleSheet(
            f"background-color: {restored_accent}; border: 1px solid #888; padding: 2px;"
        )
        self.use_custom_colors_checkbox.setChecked(self._settings.get("use_custom_colors", False))
        restored_editor_bg = self._normalized_or_default(self._settings.get("custom_editor_bg", ""), "")
        restored_editor_fg = self._normalized_or_default(self._settings.get("custom_editor_fg", ""), "")
        restored_chrome_bg = self._normalized_or_default(self._settings.get("custom_chrome_bg", ""), "")
        self.custom_editor_bg_label.setText(restored_editor_bg if restored_editor_bg else "(auto)")
        self.custom_editor_bg_label.setStyleSheet(
            f"background-color: {restored_editor_bg}; border: 1px solid #888; padding: 2px;"
            if restored_editor_bg else ""
        )
        self.custom_editor_fg_label.setText(restored_editor_fg if restored_editor_fg else "(auto)")
        self.custom_editor_fg_label.setStyleSheet(
            f"background-color: {restored_editor_fg}; border: 1px solid #888; padding: 2px;"
            if restored_editor_fg else ""
        )
        self.custom_chrome_bg_label.setText(restored_chrome_bg if restored_chrome_bg else "(auto)")
        self.custom_chrome_bg_label.setStyleSheet(
            f"background-color: {restored_chrome_bg}; border: 1px solid #888; padding: 2px;"
            if restored_chrome_bg else ""
        )
        self.font_family_edit.setText(self._settings.get("font_family", ""))
        self.font_size_slider.setValue(self._settings.get("font_size", 11))
        self.sound_checkbox.setChecked(self._settings.get("sound_enabled", True))
        self.music_checkbox.setChecked(self._settings.get("background_music", False))
        lang_idx = self.lang_combo.findText(self._settings.get("language", "English"))
        if lang_idx >= 0:
            self.lang_combo.setCurrentIndex(lang_idx)
        self.notifications_checkbox.setChecked(self._settings.get("notifications_enabled", True))
        self.version_history_checkbox.setChecked(self._settings.get("version_history_enabled", True))
        self.version_history_interval_spin.setValue(int(self._settings.get("version_history_interval_sec", 30)))
        self.version_history_max_spin.setValue(int(self._settings.get("version_history_max_entries", 50)))
        self.autosave_checkbox.setChecked(self._settings.get("autosave_enabled", True))
        self.autosave_interval_spin.setValue(int(self._settings.get("autosave_interval_sec", 30)))
        self.reminders_checkbox.setChecked(self._settings.get("reminders_enabled", True))
        self.reminder_interval_spin.setValue(int(self._settings.get("reminder_check_interval_sec", 30)))
        self.syntax_highlight_checkbox.setChecked(self._settings.get("syntax_highlighting_enabled", True))
        syntax_mode = str(self._settings.get("syntax_highlighting_mode", "Auto"))
        syntax_idx = self.syntax_mode_combo.findText(syntax_mode, Qt.MatchFixedString)
        if syntax_idx >= 0:
            self.syntax_mode_combo.setCurrentIndex(syntax_idx)
        self.checklist_toggle_checkbox.setChecked(self._settings.get("checklist_toggle_enabled", True))
        self.focus_hide_menu_checkbox.setChecked(self._settings.get("focus_hide_menu", True))
        self.focus_hide_toolbar_checkbox.setChecked(self._settings.get("focus_hide_toolbar", True))
        self.focus_hide_status_checkbox.setChecked(self._settings.get("focus_hide_status", False))
        self.focus_hide_tabs_checkbox.setChecked(self._settings.get("focus_hide_tabs", False))
        self.focus_escape_exit_checkbox.setChecked(self._settings.get("focus_allow_escape_exit", True))
        self.privacy_lock_checkbox.setChecked(self._settings.get("privacy_lock", False))
        self.lock_password_edit.setText(self._settings.get("lock_password", ""))
        self.lock_pin_edit.setText(self._settings.get("lock_pin", ""))
        self.gemini_api_key_edit.setText(self._settings.get("gemini_api_key", ""))
        self.ai_model_edit.setText(self._settings.get("ai_model", "gemini-3-flash-preview"))
        self.update_feed_url_edit.setText(
            self._settings.get("update_feed_url", DEFAULT_UPDATE_FEED_URL)
        )
        self.auto_check_updates_checkbox.setChecked(self._settings.get("auto_check_updates", True))

    def reset_to_defaults_and_close(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to default and close the app?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.reset_to_defaults_requested = True
        self.accept()
