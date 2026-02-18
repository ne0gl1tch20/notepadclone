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
from typing import TYPE_CHECKING, Any, cast
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal, Slot, QObject
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
    QMenu,
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
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter

from ..debug_logs_dialog import DebugLogsDialog
from ..detachable_tab_bar import DetachableTabBar
from ..editor_tab import EditorTab
from ...app_settings import build_default_settings
from ..ai_controller import AIController
from ..asset_paths import resolve_asset_path
from ..autosave import AutoSaveRecoveryDialog, AutoSaveStore
from ..reminders import ReminderStore, RemindersDialog
from ..security_controller import SecurityController
from ..syntax_highlighter import CodeSyntaxHighlighter
from ..updater_controller import UpdaterController
from ..version_history import VersionHistoryDialog
from ..workspace_controller import WorkspaceController



class UiSetupMixin:
    if TYPE_CHECKING:
        # Cross-mixin attributes injected by Notepad/window composition.
        settings: dict[str, Any]
        tab_widget: QTabWidget
        status: QStatusBar
        window_id: int
        detached_windows: list[Any]
        windows_by_id: dict[int, Any]

        # Cross-mixin methods resolved at runtime via multiple inheritance.
        def _clear_tab_autosave(self, tab: EditorTab) -> None: ...
        def file_save_tab(self, tab: EditorTab) -> bool: ...
        def file_save_as(self) -> bool: ...
        def _refresh_file_watcher(self) -> None: ...
        def _notify_large_file_mode(self, tab: EditorTab) -> None: ...
        def _get_debug_logs_file_path(self) -> Path: ...
        def _get_crash_logs_file_path(self) -> Path: ...
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _force_svg_monochrome(svg_text: str, color_hex: str) -> str:
        # Recolor explicit stroke/fill values (except "none") and currentColor.
        text = re.sub(
            r'\b(stroke|fill)\b\s*=\s*["\'](?!none\b)[^"\']*["\']',
            lambda m: f'{m.group(1)}="{color_hex}"',
            svg_text,
            flags=re.IGNORECASE,
        )
        text = text.replace("currentColor", color_hex)
        return text

    # ---------- UI setup ----------
    def _build_empty_tabs_widget(self) -> QWidget:
        holder = QWidget(self)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)
        label = QLabel("You don't have any tabs ;( Just click File > New!", holder)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setProperty("i18n_skip", True)
        label.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(label)
        layout.addStretch(1)
        return holder

    def _sync_tab_empty_state(self) -> None:
        if not hasattr(self, "central_stack") or not hasattr(self, "empty_tabs_widget"):
            return
        if self.tab_widget.count() == 0:
            self.central_stack.setCurrentWidget(self.empty_tabs_widget)
        else:
            self.central_stack.setCurrentWidget(self.tab_widget)

    def active_tab(self) -> EditorTab | None:
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, EditorTab) else None

    @property
    def text_edit(self):
        tab = self.active_tab()
        if tab is None:
            raise RuntimeError("No active tab")
        return tab.text_edit

    @property
    def markdown_preview(self) -> QTextEdit:
        tab = self.active_tab()
        if tab is None:
            raise RuntimeError("No active tab")
        return tab.markdown_preview

    @property
    def editor_splitter(self) -> QSplitter:
        tab = self.active_tab()
        if tab is None:
            raise RuntimeError("No active tab")
        return tab.editor_splitter

    @property
    def current_file(self) -> str | None:
        tab = self.active_tab()
        return tab.current_file if tab is not None else None

    @current_file.setter
    def current_file(self, value: str | None) -> None:
        tab = self.active_tab()
        if tab is not None:
            tab.current_file = value

    @property
    def zoom_steps(self) -> int:
        tab = self.active_tab()
        return tab.zoom_steps if tab is not None else 0

    @zoom_steps.setter
    def zoom_steps(self, value: int) -> None:
        tab = self.active_tab()
        if tab is not None:
            tab.zoom_steps = value

    @property
    def markdown_mode_enabled(self) -> bool:
        tab = self.active_tab()
        return tab.markdown_mode_enabled if tab is not None else False

    @markdown_mode_enabled.setter
    def markdown_mode_enabled(self, value: bool) -> None:
        tab = self.active_tab()
        if tab is not None:
            tab.markdown_mode_enabled = value

    def _tab_display_name(self, tab: EditorTab) -> str:
        base = Path(tab.current_file).name if tab.current_file else "Untitled"
        prefix = ""
        if tab.encryption_enabled:
            prefix += "[Enc] "
        if tab.large_file:
            prefix += "[Large] "
        suffix = " ðŸ“Œ" if tab.pinned else ""
        return f"{prefix}{base}{suffix}"

    @staticmethod
    def _format_log_line(level: str, message: str) -> str:
        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S.%f")[:-3]
        date = f"{now.month}/{now.day}/{now.year}"
        level_title = level.capitalize()
        return f"[{level_title}] [{timestamp} {date}] {message}"

    def log_event(self, level: str, message: str) -> None:
        line = self._format_log_line(level, message)
        print(line)
        self.debug_logs.append(line)
        if len(self.debug_logs) > 5000:
            self.debug_logs = self.debug_logs[-5000:]
        if bool(self.settings.get("save_debug_logs_to_appdata", False)):
            self._append_line_to_log_file(self._get_debug_logs_file_path(), line)
        if self.debug_logs_dialog is not None and self.debug_logs_dialog.isVisible():
            self.debug_logs_dialog.append_line(line)

    @staticmethod
    def _append_line_to_log_file(path: Path, line: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line.rstrip("\n"))
                handle.write("\n")
        except Exception:
            pass

    def save_crash_traceback(self, traceback_text: str) -> None:
        if not bool(self.settings.get("save_debug_logs_to_appdata", False)):
            return
        header = self._format_log_line("Error", "Unhandled traceback captured")
        self._append_line_to_log_file(self._get_crash_logs_file_path(), header)
        for line in traceback_text.splitlines():
            self._append_line_to_log_file(self._get_crash_logs_file_path(), line)

    def clear_debug_logs(self) -> None:
        self.debug_logs.clear()
        if self.debug_logs_dialog is not None:
            self.debug_logs_dialog.set_lines(self.debug_logs)
        self.log_event("Info", "Debug logs cleared")

    def show_debug_logs(self) -> None:
        if self.debug_logs_dialog is None:
            self.debug_logs_dialog = DebugLogsDialog(self)
            self.debug_logs_dialog.clear_button.clicked.disconnect()
            self.debug_logs_dialog.clear_button.clicked.connect(self.clear_debug_logs)
        self.debug_logs_dialog.set_lines(self.debug_logs)
        self.debug_logs_dialog.show()
        self.debug_logs_dialog.raise_()
        self.debug_logs_dialog.activateWindow()
        self.log_event("Info", "Opened debug logs dialog")

    @staticmethod
    def _default_style_name() -> str:
        available = {name.lower(): name for name in QStyleFactory.keys()}
        for candidate in ("windows 11", "windows11", "windowsvista", "windows"):
            if candidate in available:
                return available[candidate]
        if "fusion" in available:
            return available["fusion"]
        return "Windows"

    @staticmethod
    def _build_default_settings() -> dict:
        return build_default_settings(
            default_style=UiSetupMixin._default_style_name(),
            font_family=QApplication.font().family(),
            font_size=int(QApplication.font().pointSize() or 11),
        )

    @staticmethod
    def _settings_protection_key() -> bytes:
        machine = f"{os.environ.get('COMPUTERNAME', '')}|{os.environ.get('USERNAME', '')}|{Path.home()}"
        return hashlib.sha256(machine.encode("utf-8")).digest()

    @staticmethod
    def _protect_settings_secret(value: str) -> str:
        raw = value.encode("utf-8")
        key = UiSetupMixin._settings_protection_key()
        stream = bytes(key[i % len(key)] for i in range(len(raw)))
        masked = bytes(a ^ b for a, b in zip(raw, stream))
        return base64.urlsafe_b64encode(masked).decode("ascii")

    @staticmethod
    def _unprotect_settings_secret(value: str) -> str:
        if not value:
            return ""
        try:
            raw = base64.urlsafe_b64decode(value.encode("ascii"))
            key = UiSetupMixin._settings_protection_key()
            stream = bytes(key[i % len(key)] for i in range(len(raw)))
            plain = bytes(a ^ b for a, b in zip(raw, stream))
            return plain.decode("utf-8")
        except Exception:
            return ""

    def _tab_icon_for(self, tab: EditorTab) -> QIcon:
        fallback = self._standard_style_icon("SP_FileIcon")
        base_icon = self._file_icon_for_tab(tab, fallback)

        if not (tab.favorite or tab.pinned or tab.read_only):
            return base_icon

        base_pixmap = base_icon.pixmap(18, 18)
        painter = QPainter(base_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        overlay_size = 9
        pad = 0
        if tab.pinned:
            pin_pixmap = self._svg_icon_colored("tab-pin", size=overlay_size).pixmap(overlay_size, overlay_size)
            painter.drawPixmap(pad, pad, pin_pixmap)
        if tab.favorite:
            heart_pixmap = self._svg_icon_colored("tab-heart", size=overlay_size).pixmap(overlay_size, overlay_size)
            painter.drawPixmap(18 - overlay_size - pad, pad, heart_pixmap)
        if tab.read_only:
            lock_pixmap = self._svg_icon_colored("tab-lock", size=overlay_size).pixmap(overlay_size, overlay_size)
            painter.drawPixmap(pad, 18 - overlay_size - pad, lock_pixmap)
        painter.end()
        return QIcon(base_pixmap)

    def _file_icon_for_tab(self, tab: EditorTab, fallback: QIcon) -> QIcon:
        if tab.markdown_mode_enabled:
            return QIcon.fromTheme("text-markdown", fallback)
        suffix = ""
        if tab.current_file:
            suffix = Path(tab.current_file).suffix.lower()
        icon_by_ext = {
            ".py": "text-x-python",
            ".md": "text-markdown",
            ".markdown": "text-markdown",
            ".json": "application-json",
            ".js": "text-x-javascript",
            ".ts": "text-x-typescript",
            ".html": "text-html",
            ".htm": "text-html",
            ".css": "text-css",
            ".xml": "text-xml",
            ".yml": "text-x-yaml",
            ".yaml": "text-x-yaml",
            ".txt": "text-plain",
            ".csv": "text-csv",
            ".ini": "text-x-ini",
            ".toml": "text-x-ini",
            ".log": "text-x-log",
        }
        theme_name = icon_by_ext.get(suffix, "text-x-generic")
        return QIcon.fromTheme(theme_name, fallback)

    def _svg_icon(self, name: str) -> QIcon:
        return self._svg_icon_colored(name, size=18)

    def _standard_style_icon(self, enum_name: str) -> QIcon:
        style = self.style()
        enum_value = getattr(QStyle, enum_name, None)
        if enum_value is None:
            return QIcon()
        return style.standardIcon(enum_value)

    def _svg_icon_colored(self, name: str, size: int = 18) -> QIcon:
        icon_path = resolve_asset_path("icons", f"{name}.svg")
        if icon_path is None:
            return QIcon()
        configured = getattr(self, "_icon_color", None)
        if isinstance(configured, QColor) and configured.isValid():
            color = QColor(configured)
        else:
            dark_mode = bool(getattr(self, "settings", {}).get("dark_mode", False))
            color = QColor("#ffffff" if dark_mode else "#000000")
        svg_text = icon_path.read_text(encoding="utf-8")
        svg_text = self._force_svg_monochrome(svg_text, color.name())
        renderer = QSvgRenderer(svg_text.encode("utf-8"))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _refresh_tab_title(self, tab: EditorTab) -> None:
        index = self.tab_widget.indexOf(tab)
        if index < 0:
            return
        modified = "*" if tab.text_edit.is_modified() else ""
        self.tab_widget.setTabIcon(index, self._tab_icon_for(tab))
        self.tab_widget.setTabText(index, f"{modified}{self._tab_display_name(tab)}")
        if hasattr(self, "_apply_tab_color"):
            self._apply_tab_color(tab)
        if hasattr(self, "_refresh_window_menu_entries"):
            self._refresh_window_menu_entries()

    def _connect_tab_signals(self, tab: EditorTab) -> None:
        tab.text_edit.modificationChanged.connect(self._on_modification_changed)
        tab.text_edit.cursorPositionChanged.connect(self.update_status_bar)
        tab.text_edit.textChanged.connect(self.update_status_bar)
        tab.text_edit.textChanged.connect(self._handle_text_changed)
        tab.text_edit.copyAvailable.connect(self.update_action_states)
        tab.text_edit.undoAvailable.connect(self.update_action_states)
        tab.text_edit.redoAvailable.connect(self.update_action_states)
        tab.text_edit.widget.installEventFilter(cast(QObject, self))

    def _disconnect_tab_signals(self, tab: EditorTab) -> None:
        try:
            tab.text_edit.modificationChanged.disconnect(self._on_modification_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.cursorPositionChanged.disconnect(self.update_status_bar)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.textChanged.disconnect(self.update_status_bar)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.textChanged.disconnect(self._handle_text_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.copyAvailable.disconnect(self.update_action_states)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.undoAvailable.disconnect(self.update_action_states)
        except (TypeError, RuntimeError):
            pass
        try:
            tab.text_edit.redoAvailable.disconnect(self.update_action_states)
        except (TypeError, RuntimeError):
            pass
        tab.text_edit.widget.removeEventFilter(cast(QObject, self))

    def _tab_for_editor(self, editor) -> EditorTab | None:
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if not isinstance(tab, EditorTab):
                continue
            if tab.text_edit is editor or tab.text_edit.widget is editor:
                return tab
        return None

    def _handle_text_changed(self) -> None:
        sender = self.sender()
        tab = None
        if sender is not None:
            tab = self._tab_for_editor(sender)
        if tab is None:
            tab = self.active_tab()
        if tab is None:
            return
        if tab is self.active_tab() and tab.markdown_mode_enabled:
            self.update_markdown_preview()
        self._maybe_snapshot_version(tab)
        if hasattr(self, "_record_change_history_line"):
            self._record_change_history_line()

    def _seed_version_history(self, tab: EditorTab, label: str = "Opened") -> None:
        if tab.large_file:
            return
        tab.version_history.max_entries = int(self.settings.get("version_history_max_entries", 50))
        tab.version_history.add_snapshot(tab.text_edit.get_text(), label=label)
        tab.last_snapshot_time = time.monotonic()

    def _maybe_snapshot_version(self, tab: EditorTab) -> None:
        if tab.large_file:
            return
        if not self.settings.get("version_history_enabled", True):
            return
        interval = max(5, int(self.settings.get("version_history_interval_sec", 30)))
        now = time.monotonic()
        if tab.last_snapshot_time is None or (now - tab.last_snapshot_time) >= interval:
            tab.version_history.max_entries = int(self.settings.get("version_history_max_entries", 50))
            tab.version_history.add_snapshot(tab.text_edit.get_text(), label="Auto")
            tab.last_snapshot_time = now

    def _detect_language_for_tab(self, tab: EditorTab) -> str:
        mode = str(self.settings.get("syntax_highlighting_mode", "Auto"))
        if tab.syntax_language_override:
            return tab.syntax_language_override
        if mode and mode.lower() != "auto":
            return mode.lower()
        if tab.current_file:
            suffix = Path(tab.current_file).suffix.lower()
            ext_map = {
                ".py": "python",
                ".js": "javascript",
                ".ts": "javascript",
                ".json": "json",
                ".md": "markdown",
                ".markdown": "markdown",
                ".mdown": "markdown",
            }
            if suffix in ext_map:
                return ext_map[suffix]
        if tab.markdown_mode_enabled:
            return "markdown"
        return "plain"

    def _apply_syntax_highlighting(self, tab: EditorTab) -> None:
        if not self.settings.get("syntax_highlighting_enabled", True):
            if tab.syntax_highlighter is not None:
                tab.syntax_highlighter.set_language("plain")
            return
        if tab.large_file:
            return
        if tab.text_edit.is_scintilla:
            tab.syntax_highlighter = None
            return
        language = self._detect_language_for_tab(tab)
        if tab.syntax_highlighter is None:
            tab.syntax_highlighter = cast(
                Any,
                CodeSyntaxHighlighter(tab.text_edit.widget.document(), language=language),
            )
        else:
            tab.syntax_highlighter.set_language(language)

    def _apply_focus_mode(self, enabled: bool) -> None:
        hide_menu = bool(self.settings.get("focus_hide_menu", True))
        hide_toolbar = bool(self.settings.get("focus_hide_toolbar", True))
        hide_status = bool(self.settings.get("focus_hide_status", False))
        hide_tabs = bool(self.settings.get("focus_hide_tabs", False))

        self.menuBar().setVisible(not (enabled and hide_menu))
        if enabled and hide_toolbar:
            for toolbar in self.findChildren(QToolBar):
                toolbar.hide()
        else:
            # Restore toolbar layout from persisted visibility settings.
            if hasattr(self, "_layout_top_toolbars"):
                self._layout_top_toolbars()
            else:
                for toolbar in self.findChildren(QToolBar):
                    toolbar.show()
        self.status.setVisible(not (enabled and hide_status))
        self.tab_widget.tabBar().setVisible(not (enabled and hide_tabs))
        if hasattr(self, "focus_mode_action"):
            self.focus_mode_action.blockSignals(True)
            self.focus_mode_action.setChecked(enabled)
            self.focus_mode_action.blockSignals(False)

    def _sync_language_picker(self, tab: EditorTab) -> None:
        if not hasattr(self, "syntax_combo"):
            return
        if tab.syntax_language_override:
            label = tab.syntax_language_override.capitalize()
            if label == "Javascript":
                label = "JavaScript"
        else:
            label = "Auto"
        idx = self.syntax_combo.findText(label, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.syntax_combo.blockSignals(True)
            self.syntax_combo.setCurrentIndex(idx)
            self.syntax_combo.blockSignals(False)

    def _set_active_tab_language(self, label: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        normalized = label.lower()
        if normalized == "auto":
            tab.syntax_language_override = None
        else:
            tab.syntax_language_override = normalized
        self._apply_syntax_highlighting(tab)

    def toggle_focus_mode(self, checked: bool) -> None:
        self._apply_focus_mode(checked)
        self.log_event("Info", f"Focus mode {'enabled' if checked else 'disabled'}")

    def show_version_history(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        dialog = VersionHistoryDialog(self, tab.version_history, tab.text_edit.get_text())
        if dialog.exec():
            selected_text = dialog.selected_text
            if selected_text is not None:
                tab.text_edit.set_text(selected_text)
                self._seed_version_history(tab, label="Restored")
                self.update_status_bar()

    def show_reminders(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        note_ref = tab.current_file or f"tab-{id(tab)}"
        note_title = self._tab_display_name(tab)
        dlg = RemindersDialog(self, self.reminders_store, note_ref, note_title)
        dlg.exec()

    def _check_reminders(self) -> None:
        if not self.settings.get("reminders_enabled", True):
            return
        now = datetime.now()
        fired_any = False
        for reminder in self.reminders_store.reminders:
            if reminder.fired:
                continue
            if reminder.due_datetime <= now:
                if self.settings.get("notifications_enabled", True):
                    details = reminder.notes.strip()
                    message = f"{reminder.title}\nDue: {reminder.due_iso.replace('T', ' ')}"
                    if details:
                        message = f"{message}\n\n{details}"
                    QMessageBox.information(cast(QWidget, self), "Reminder", message)
                if reminder.recurrence and reminder.recurrence != "none":
                    self.reminders_store.reschedule_recurring(reminder)
                else:
                    reminder.fired = True
                fired_any = True
        if fired_any:
            self.reminders_store.save()

    def toggle_task_item(self) -> None:
        if not self.settings.get("checklist_toggle_enabled", True):
            return
        tab = self.active_tab()
        if tab is None:
            return
        line, _ = tab.text_edit.cursor_position()
        text = tab.text_edit.get_line_text(line)
        if text.strip() == "":
            tab.text_edit.insert_text("- [ ] ")
            return
        prefix = text[: len(text) - len(text.lstrip())]
        line = text.strip()
        if line.startswith("- [ ]"):
            new_line = line.replace("- [ ]", "- [x]", 1)
        elif line.startswith("- [x]") or line.startswith("- [X]"):
            new_line = line.replace("- [x]", "- [ ]", 1).replace("- [X]", "- [ ]", 1)
        else:
            new_line = f"- [ ] {line}"
        tab.text_edit.replace_line(line=tab.text_edit.cursor_position()[0], text=prefix + new_line)

    def eventFilter(self, source, event) -> bool:  # type: ignore[override]
        if source is getattr(self, "main_toolbar", None) and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._schedule_main_toolbar_overflow_update()
        if event.type() == QEvent.Type.Wheel:
            if bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                tab = self._tab_for_editor(source)
                if tab is None:
                    return QMainWindow.eventFilter(cast(QMainWindow, self), source, event)
                angle_y = event.angleDelta().y()
                if angle_y == 0:
                    return True
                step = int(angle_y / 120)
                if step == 0:
                    step = 1 if angle_y > 0 else -1
                tab.text_edit.zoom_in(step)
                tab.zoom_steps += step
                if tab is self.active_tab():
                    self.zoom_label.setText(f"{max(10, 100 + (tab.zoom_steps * 10))}%")
                return True
        if event.type() == QEvent.Type.KeyPress and getattr(self, "macro_recording", False):
            if event.modifiers() & (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            ):
                return QMainWindow.eventFilter(cast(QMainWindow, self), source, event)
            key = event.key()
            text = event.text() or ""
            if text:
                self._macro_events.append(("text", text))
            elif key == Qt.Key.Key_Backspace:
                self._macro_events.append(("backspace", ""))
            elif key == Qt.Key.Key_Delete:
                self._macro_events.append(("delete", ""))
            return QMainWindow.eventFilter(cast(QMainWindow, self), source, event)
        return QMainWindow.eventFilter(cast(QMainWindow, self), source, event)

    def _schedule_main_toolbar_overflow_update(self) -> None:
        if getattr(self, "_main_toolbar_overflow_update_scheduled", False):
            return
        self._main_toolbar_overflow_update_scheduled = True

        def _run_update() -> None:
            self._main_toolbar_overflow_update_scheduled = False
            if getattr(self, "_main_toolbar_overflow_menu_open", False):
                self._main_toolbar_overflow_update_pending = True
                return
            self._main_toolbar_overflow_update_pending = False
            self._update_main_toolbar_overflow()

        # Debounce resize bursts so menu popups are not visually disturbed.
        QTimer.singleShot(40, _run_update)

    def _on_main_toolbar_overflow_menu_show(self) -> None:
        self._main_toolbar_overflow_menu_open = True

    def _on_main_toolbar_overflow_menu_hide(self) -> None:
        self._main_toolbar_overflow_menu_open = False
        if getattr(self, "_main_toolbar_overflow_update_pending", False):
            self._schedule_main_toolbar_overflow_update()

    def _position_main_toolbar_overflow_button(self) -> None:
        toolbar = getattr(self, "main_toolbar", None)
        button = getattr(self, "main_toolbar_overflow_button", None)
        if toolbar is None or button is None or not button.isVisible():
            return
        margin = 2
        hint = button.sizeHint()
        rect = toolbar.contentsRect()
        max_x = max(0, rect.right() - hint.width() - margin)
        x = max(rect.left() + margin, max_x)
        y = max(rect.top(), rect.top() + (rect.height() - hint.height()) // 2)
        button.move(x, y)
        button.raise_()

    def _extract_tab_for_transfer(self, index: int) -> EditorTab | None:
        widget = self.tab_widget.widget(index)
        if not isinstance(widget, EditorTab):
            return None
        self._disconnect_tab_signals(widget)
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.add_new_tab(make_current=True)
        self.update_window_title()
        return widget

    def _insert_existing_tab(self, tab: EditorTab, insert_index: int = -1, make_current: bool = True) -> int:
        tab.setParent(self.tab_widget)
        self._connect_tab_signals(tab)
        target_index = insert_index if insert_index >= 0 else self.tab_widget.count()
        target_index = max(0, min(target_index, self.tab_widget.count()))
        new_index = self.tab_widget.insertTab(target_index, tab, self._tab_display_name(tab))
        self._refresh_tab_title(tab)
        if make_current:
            self.tab_widget.setCurrentIndex(new_index)
            self.on_tab_changed(new_index)
        return new_index

    @staticmethod
    def _parse_tab_transfer_payload(raw_payload: bytes) -> tuple[int, int] | None:
        payload = raw_payload.decode("ascii", errors="ignore")
        parts = payload.split(":")
        if len(parts) != 2:
            return None
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None

    def receive_external_tab(self, source_window_id: int, source_index: int, insert_index: int) -> bool:
        source_window = type(self).windows_by_id.get(source_window_id)
        if source_window is None or source_window is self:
            return False

        incoming_tab = source_window._extract_tab_for_transfer(source_index)
        if incoming_tab is None:
            return False

        self._insert_existing_tab(incoming_tab, insert_index=insert_index, make_current=True)
        self.log_event("Info", f'Received tab from another window: "{self._tab_display_name(incoming_tab)}"')
        source_window.update_window_title()
        self.update_window_title()
        return True

    def add_new_tab(self, text: str = "", file_path: str | None = None, make_current: bool = True) -> EditorTab:
        tab = EditorTab(self)
        self._connect_tab_signals(tab)
        tab.text_edit.set_wrap_enabled(self.word_wrap_enabled)
        font = QFont()
        font.setPointSize(self.settings.get("font_size", 11))
        font_family = self.settings.get("font_family")
        if font_family:
            font.setFamily(font_family)
        tab.text_edit.set_font(font)
        tab.text_edit.set_text(text)
        tab.current_file = file_path
        if file_path and file_path in set(self.settings.get("pinned_files", [])):
            tab.pinned = True
        self._apply_file_metadata_to_tab(tab)
        tab.markdown_mode_enabled = self._is_markdown_path(file_path)
        tab.markdown_preview.setVisible(tab.markdown_mode_enabled)
        tab.column_mode = bool(getattr(self, "column_mode_action", None) and self.column_mode_action.isChecked())
        tab.multi_caret = bool(getattr(self, "multi_caret_action", None) and self.multi_caret_action.isChecked())
        tab.code_folding = bool(getattr(self, "code_folding_action", None) is None or self.code_folding_action.isChecked())
        tab.show_space_tab = bool(self.settings.get("show_symbol_space_tab", False))
        tab.show_eol = bool(self.settings.get("show_symbol_eol", False))
        tab.show_non_printing = bool(self.settings.get("show_symbol_non_printing", False))
        tab.show_control_chars = bool(self.settings.get("show_symbol_control_chars", False))
        tab.show_all_chars = bool(self.settings.get("show_symbol_all_chars", False))
        tab.show_indent_guides = bool(self.settings.get("show_symbol_indent_guide", True))
        tab.show_wrap_symbol = bool(self.settings.get("show_symbol_wrap_symbol", False))
        if hasattr(self, "_apply_scintilla_modes"):
            self._apply_scintilla_modes(tab)

        index = self.tab_widget.addTab(tab, self._tab_display_name(tab))
        if make_current:
            self.tab_widget.setCurrentIndex(index)
        tab.text_edit.set_modified(False)
        self._refresh_tab_title(tab)
        if tab.markdown_mode_enabled:
            tab.markdown_preview.setMarkdown(tab.text_edit.get_text())
        self._apply_syntax_highlighting(tab)
        self._seed_version_history(tab, label="New")
        if tab.pinned:
            self._sort_tabs_by_pinned()
        self._sync_tab_empty_state()
        self.log_event("Info", f'New tab created: "{self._tab_display_name(tab)}"')
        return tab

    def on_tab_changed(self, _index: int) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        self.log_event("Info", f'Active tab: "{self._tab_display_name(tab)}"')
        if hasattr(self, "md_toggle_preview_action"):
            self.md_toggle_preview_action.blockSignals(True)
            self.md_toggle_preview_action.setChecked(tab.markdown_mode_enabled)
            self.md_toggle_preview_action.blockSignals(False)
        self.zoom_label.setText(f"{max(10, 100 + (tab.zoom_steps * 10))}%")
        self._sync_language_picker(tab)
        if hasattr(self, "pin_tab_action"):
            self.pin_tab_action.setText("&Unpin Tab" if tab.pinned else "&Pin Tab")
        if hasattr(self, "favorite_tab_action"):
            self.favorite_tab_action.setText("&Unfavorite Tab" if tab.favorite else "&Favorite Tab")
        if hasattr(self, "search_toolbar") and self.search_toolbar.isVisible():
            self._on_search_text_changed()
        if hasattr(self, "column_mode_action"):
            self.column_mode_action.blockSignals(True)
            self.column_mode_action.setChecked(tab.column_mode)
            self.column_mode_action.blockSignals(False)
        if hasattr(self, "multi_caret_action"):
            self.multi_caret_action.blockSignals(True)
            self.multi_caret_action.setChecked(tab.multi_caret)
            self.multi_caret_action.blockSignals(False)
        if hasattr(self, "code_folding_action"):
            self.code_folding_action.blockSignals(True)
            self.code_folding_action.setChecked(tab.code_folding)
            self.code_folding_action.blockSignals(False)
        if hasattr(self, "_apply_scintilla_modes"):
            self._apply_scintilla_modes(tab)
        if hasattr(self, "_sync_symbol_actions"):
            self._sync_symbol_actions(tab)
        if hasattr(self, "_notify_large_file_mode"):
            self._notify_large_file_mode(tab)
        if hasattr(self, "_refresh_window_menu_entries"):
            self._refresh_window_menu_entries()
        self.update_status_bar()
        self.update_window_title()

    def close_tab(self, index: int) -> None:
        widget = self.tab_widget.widget(index)
        if not isinstance(widget, EditorTab):
            return
        self.log_event("Info", f'Requested tab close: "{self._tab_display_name(widget)}"')
        if not self.maybe_save_tab(widget):
            self.log_event("Info", f'Tab close cancelled: "{self._tab_display_name(widget)}"')
            return
        self._clear_tab_autosave(widget)
        self.tab_widget.removeTab(index)
        widget.deleteLater()
        if hasattr(self, "_refresh_file_watcher"):
            self._refresh_file_watcher()
        self._sync_tab_empty_state()
        self.update_status_bar()
        self.update_action_states()
        self.update_window_title()
        if hasattr(self, "_refresh_window_menu_entries"):
            self._refresh_window_menu_entries()
        self.log_event("Info", "Tab closed")

    def detach_tab_to_window(self, index: int, global_pos: QPoint) -> None:
        if self.tab_widget.count() <= 1:
            return
        moving_tab = self._extract_tab_for_transfer(index)
        if moving_tab is None:
            return
        self.log_event("Info", f'Detaching tab into new window: "{self._tab_display_name(moving_tab)}"')

        new_window = type(self)()
        new_window.settings = dict(self.settings)
        new_window.apply_settings()

        placeholder = new_window.active_tab()
        if (
            placeholder is not None
            and not placeholder.text_edit.is_modified()
            and not placeholder.current_file
            and not placeholder.text_edit.get_text().strip()
        ):
            new_window._disconnect_tab_signals(placeholder)
            placeholder_index = new_window.tab_widget.indexOf(placeholder)
            if placeholder_index >= 0:
                new_window.tab_widget.removeTab(placeholder_index)
                placeholder.deleteLater()

        new_window._insert_existing_tab(moving_tab, insert_index=0, make_current=True)

        new_window.move(global_pos)
        new_window.show()
        new_window.update_window_title()
        self.detached_windows.append(new_window)

        self.update_window_title()
        self.log_event("Info", "Detached window created")

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(DetachableTabBar._tab_mime_type):
            event.acceptProposedAction()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        QMainWindow.dragEnterEvent(cast(QMainWindow, self), event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(DetachableTabBar._tab_mime_type):
            event.acceptProposedAction()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        QMainWindow.dragMoveEvent(cast(QMainWindow, self), event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            local_paths = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.isLocalFile()
            ]
            if local_paths and self.workspace_controller.handle_dropped_urls(local_paths):
                event.acceptProposedAction()
                return

        if not event.mimeData().hasFormat(DetachableTabBar._tab_mime_type):
            QMainWindow.dropEvent(cast(QMainWindow, self), event)
            return

        payload = bytes(event.mimeData().data(DetachableTabBar._tab_mime_type))
        parsed = self._parse_tab_transfer_payload(payload)
        if parsed is None:
            event.ignore()
            return

        source_window_id, source_index = parsed
        moved = self.receive_external_tab(source_window_id, source_index, self.tab_widget.count())
        if moved:
            event.acceptProposedAction()
            return
        event.ignore()

    def maybe_save_tab(self, tab: EditorTab) -> bool:
        if not tab.text_edit.is_modified():
            return True
        tab_name = self._tab_display_name(tab)
        ret = QMessageBox.warning(
            cast(QWidget, self),
            "Notepad",
            f'The text in "{tab_name}" has changed.\n\nDo you want to save the changes?',
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if ret == QMessageBox.StandardButton.Save:
            return self.file_save_tab(tab)
        if ret == QMessageBox.StandardButton.Cancel:
            return False
        tab.text_edit.set_modified(False)
        self._clear_tab_autosave(tab)
        return True

    @staticmethod
    def _action_label(text: str) -> str:
        return text.replace("&", "").replace("...", "").strip()

    def configure_action_tooltips(self) -> None:
        action_tips = {
            "New": "Create a new tab",
            "Open": "Open a file",
            "Save": "Save the current tab",
            "Save As": "Save the current tab with a new name",
            "Save All": "Save all modified tabs",
            "Close Tab": "Close the current tab",
            "Close All Tabs": "Close all tabs",
            "Close All But Active": "Close every tab except the active one",
            "Close All But Pinned": "Close all non-pinned tabs",
            "Close All To The Left": "Close tabs left of the active tab",
            "Close All To The Right": "Close tabs right of the active tab",
            "Close All Unchanged": "Close tabs without unsaved changes",
            "UTF-8": "Save this file as UTF-8",
            "UTF-16": "Save this file as UTF-16",
            "ANSI (CP1252)": "Save this file as ANSI (Windows-1252)",
            "Unix (LF)": "Use LF line endings",
            "Windows (CRLF)": "Use CRLF line endings",
            "Print": "Print the current tab",
            "Print Preview": "Preview the current tab before printing",
            "Version History": "Review and restore earlier snapshots",
            "Pin Tab": "Pin or unpin the active tab",
            "Favorite Tab": "Mark or unmark the active tab as favorite",
            "Edit Tags": "Edit tags for the active tab",
            "Export as PDF": "Export active tab content to PDF",
            "Export as Markdown": "Export active tab content to Markdown",
            "Export as HTML": "Export active tab content to HTML",
            "Insert Media": "Insert image or PDF references into the note",
            "Open Workspace Folder": "Choose a workspace folder",
            "Workspace Files": "Browse files in the active workspace",
            "Search Workspace": "Search text across workspace files",
            "Enable Note Encryption": "Enable encrypted saves for the active note",
            "Disable Note Encryption": "Disable encrypted saves for the active note",
            "Change Note Password": "Change encryption password for the active note",
            "Ask AI": "Ask Gemini a free-form question",
            "Explain Selection with AI": "Explain currently selected text",
            "User Guide": "Open full usage guide",
            "Preferences": "Open app preferences",
            "Shortcut Mapper": "Open shortcut mapper and presets",
            "Exit": "Close the app",
            "Save Session": "Save open files and active tab as a session",
            "Save Session As": "Save session to a new file",
            "Load Session": "Load a saved session file",
            "Start Recording": "Start recording typing macro actions",
            "Stop Recording": "Stop recording the current macro",
            "Playback Macro": "Replay the last recorded macro",
            "Save Current Recorded Macro...": "Save the currently recorded macro",
            "Run a Macro Multiple Times...": "Repeat the last recorded macro several times",
            "Trim Trailing Spaces and Save": "Trim trailing spaces in current document and save",
            "Modify Shortcut/Delete Macro...": "Manage saved macros and macro shortcuts",
            "Undo": "Undo last edit",
            "Redo": "Redo last undone edit",
            "Cut": "Cut selected text",
            "Copy": "Copy selected text",
            "Paste": "Paste from clipboard",
            "Delete": "Delete selected text or next character",
            "Select All": "Select all text",
            "Time/Date": "Insert current time and date",
            "Find": "Find text in the current tab",
            "Find Panel": "Open persistent search panel",
            "Find Next": "Find next match",
            "Find Previous": "Find previous match",
            "Replace": "Find and replace text",
            "Replace in Files": "Replace text across workspace files",
            "Toggle Bookmark": "Toggle a bookmark on the current line",
            "Next Bookmark": "Jump to the next bookmark",
            "Previous Bookmark": "Jump to the previous bookmark",
            "Clear Bookmarks": "Clear all bookmarks in this tab",
            "Always on Top": "Keep the window above other windows",
            "Post-it": "Toggle compact always-on-top post-it mode",
            "Distraction Free Mode": "Toggle fullscreen and focus mode together",
            "Focus on Another View": "Move focus to split/preview view when available",
            "Hide Lines": "Hide selected lines (when supported)",
            "Show Hidden Lines": "Restore all hidden lines in the current document",
            "Fold All": "Collapse all foldable sections",
            "Unfold All": "Expand all folded sections",
            "Fold Current Level": "Collapse current fold level",
            "Unfold Current Level": "Expand current fold level",
            "Document Map": "Toggle document minimap panel",
            "Document List": "Open workspace document list",
            "Function List": "Toggle function/symbol outline panel",
            "Text Direction RTL": "Set right-to-left text direction for this tab",
            "Text Direction LTR": "Set left-to-right text direction for this tab",
            "Reminders & Alarms": "Manage reminders for this note",
            "Search with Bing": "Search selected text on Bing",
            "Word Wrap": "Toggle wrapping long lines",
            "Font": "Change editor font",
            "Bold": "Apply bold formatting",
            "Italic": "Apply italic formatting",
            "Underline": "Apply underline formatting",
            "Strikethrough": "Apply strikethrough formatting",
            "Status Bar": "Show or hide status bar",
            "Zoom In": "Increase editor zoom",
            "Zoom Out": "Decrease editor zoom",
            "Restore Default Zoom": "Reset zoom to 100%",
            "Define Your Language...": "Open user-defined language editor",
            "Monitoring (tail -f)...": "Monitor a file like tail -f",
            "Document Summary": "Show document statistics and selection details",
            "Focus Mode": "Hide chrome for a distraction-free view",
            "Column Mode": "Enable rectangular selection (column mode)",
            "Multi-Caret": "Enable multiple selections/carets",
            "Code Folding": "Toggle code folding",
            "Full Screen": "Toggle fullscreen mode",
            "Clone to Other View": "Open a cloned editor view for the current tab",
            "Split View Vertical": "Split the editor side-by-side",
            "Split View Horizontal": "Split the editor top/bottom",
            "Close Split View": "Close the split editor view",
            "Show Markdown Toolbar": "Show or hide the Markdown toolbar",
            "Heading 1": "Insert Markdown heading level 1",
            "Heading 2": "Insert Markdown heading level 2",
            "Heading 3": "Insert Markdown heading level 3",
            "Heading 4": "Insert Markdown heading level 4",
            "Heading 5": "Insert Markdown heading level 5",
            "Heading 6": "Insert Markdown heading level 6",
            "Bold (Markdown)": "Wrap selection with **bold** markers",
            "Italic (Markdown)": "Wrap selection with *italic* markers",
            "Strikethrough (Markdown)": "Wrap selection with ~~strikethrough~~ markers",
            "Inline Code": "Wrap selection with inline code markers",
            "Code Block": "Insert a fenced code block",
            "Bullet List": "Insert Markdown bullet list markers",
            "Numbered List": "Insert Markdown numbered list markers",
            "Task List": "Insert Markdown task list markers",
            "Toggle Task": "Toggle the current line's checklist state",
            "Blockquote": "Insert Markdown blockquote markers",
            "Link": "Insert Markdown link",
            "Image": "Insert Markdown image",
            "Horizontal Rule": "Insert Markdown horizontal rule",
            "Table": "Insert Markdown table template",
            "Live Markdown Preview": "Toggle side-by-side Markdown preview",
            "About Notepad Clone": "Show app information",
            "Show Debug Logs": "Open a live debug log console",
            "Windows...": "Open the window manager for all documents",
            "Name A to Z": "Sort document tabs by name ascending",
            "Name Z to A": "Sort document tabs by name descending",
            "Path A to Z": "Sort document tabs by path ascending",
            "Path Z to A": "Sort document tabs by path descending",
            "Type A to Z": "Sort document tabs by type ascending",
            "Type Z to A": "Sort document tabs by type descending",
            "Content Length Ascending": "Sort document tabs by content length ascending",
            "Content Length Descending": "Sort document tabs by content length descending",
            "Modified Time Ascending": "Sort document tabs by modified time ascending",
            "Modified Time Descending": "Sort document tabs by modified time descending",
        }
        for attr_name, action in vars(self).items():
            if not attr_name.endswith("_action") or not isinstance(action, QAction):
                continue
            try:
                label = self._action_label(action.text())
                base_tip = action_tips.get(label, f"Use {label.lower()}")
                shortcuts = [
                    shortcut.toString(QKeySequence.SequenceFormat.NativeText)
                    for shortcut in action.shortcuts()
                    if not shortcut.isEmpty()
                ]
                if not shortcuts:
                    fallback = action.shortcut()
                    if not fallback.isEmpty():
                        shortcuts = [fallback.toString(QKeySequence.SequenceFormat.NativeText)]
                if shortcuts:
                    tip = f"{base_tip} ({', '.join(shortcuts)})"
                else:
                    tip = base_tip
                action.setToolTip(tip)
                action.setStatusTip(tip)
                action.setWhatsThis(tip)
            except RuntimeError:
                continue
        QApplication.clipboard().dataChanged.connect(self.update_action_states)

    def _connect_action_debug_tracing(self) -> None:
        for attr_name, action in vars(self).items():
            if not attr_name.endswith("_action") or not isinstance(action, QAction):
                continue
            try:
                label = self._action_label(action.text())
                if action.isCheckable():
                    action.triggered.connect(
                        lambda checked, action_name=label: self.log_event(
                            "Info",
                            f'Action triggered: "{action_name}" -> {"On" if checked else "Off"}',
                        )
                    )
                else:
                    action.triggered.connect(
                        lambda _checked=False, action_name=label: self.log_event(
                            "Info",
                            f'Action triggered: "{action_name}"',
                        )
                    )
            except RuntimeError:
                continue

    def configure_menu_tooltips(self) -> None:
        menu_tips = {
            "File": "Create, open, save, and close files",
            "Edit": "Undo and clipboard tools",
            "Search": "Find, replace, navigate, and bookmark tools",
            "Format": "Text styling and editor appearance",
            "View": "Zoom and interface visibility controls",
            "Window": "Sort and manage open documents",
            "Settings": "Preferences and customization",
            "Tools": "Utilities and advanced tooling",
            "Macro": "Record and replay editing macros",
            "Markdown": "Quick Markdown formatting commands",
            "Plugins": "Plugin management and plugin tools",
            "Help": "About information and extra tools",
        }
        for menu_attr, label in (
            ("file_menu", "File"),
            ("edit_menu", "Edit"),
            ("search_menu", "Search"),
            ("format_menu", "Format"),
            ("view_menu", "View"),
            ("window_menu", "Window"),
            ("settings_menu", "Settings"),
            ("tools_menu", "Tools"),
            ("macros_menu", "Macro"),
            ("markdown_menu", "Markdown"),
            ("plugins_menu", "Plugins"),
            ("help_menu", "Help"),
        ):
            menu = getattr(self, menu_attr, None)
            if menu is None:
                continue
            tip = menu_tips[label]
            menu.setToolTipsVisible(True)
            menu.menuAction().setToolTip(tip)
            menu.menuAction().setStatusTip(tip)

    def update_action_states(self, *_args) -> None:
        if not hasattr(self, "save_action"):
            return
        tab = self.active_tab()
        has_tab = tab is not None
        has_text = bool(tab and tab.text_edit.get_text())
        has_selection = bool(tab and tab.text_edit.has_selection())
        can_undo = bool(tab and tab.text_edit.is_undo_available())
        can_redo = bool(tab and tab.text_edit.is_redo_available())
        is_modified = bool(tab and tab.text_edit.is_modified())
        is_read_only = bool(tab and tab.text_edit.is_read_only())
        is_large_file = bool(tab and tab.large_file)
        macro_recording = bool(getattr(self, "macro_recording", False))
        macro_has_events = bool(getattr(self, "_last_macro_events", None))
        has_scintilla = bool(tab and tab.text_edit.is_scintilla)
        ai_private_mode = bool(self.settings.get("ai_private_mode", False))
        has_search_seed = bool(self.last_search_text)
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        has_clipboard_text = bool(mime and mime.hasText())

        # File actions
        self.save_action.setEnabled(has_tab and is_modified)
        self.save_as_action.setEnabled(has_tab)
        self.rename_action.setEnabled(has_tab)
        self.move_recycle_action.setEnabled(has_tab and bool(tab and tab.current_file))
        self.print_action.setEnabled(has_tab)
        self.print_preview_action.setEnabled(has_tab)
        self.save_all_action.setEnabled(has_tab)
        self.save_session_action.setEnabled(True)
        self.save_session_as_action.setEnabled(True)
        self.load_session_action.setEnabled(True)
        self.close_tab_action.setEnabled(has_tab)
        self.close_all_action.setEnabled(has_tab)
        self.close_all_but_active_action.setEnabled(has_tab)
        self.close_all_but_pinned_action.setEnabled(has_tab)
        self.close_all_left_action.setEnabled(has_tab and self.tab_widget.currentIndex() > 0)
        self.close_all_right_action.setEnabled(
            has_tab and self.tab_widget.currentIndex() < (self.tab_widget.count() - 1)
        )
        self.close_all_unchanged_action.setEnabled(has_tab)
        self.encoding_utf8_action.setEnabled(has_tab)
        self.encoding_utf16_action.setEnabled(has_tab)
        self.encoding_ansi_action.setEnabled(has_tab)
        self.eol_lf_action.setEnabled(has_tab)
        self.eol_crlf_action.setEnabled(has_tab)
        self.version_history_action.setEnabled(has_tab and not is_large_file)
        self.pin_tab_action.setEnabled(has_tab)
        self.favorite_tab_action.setEnabled(has_tab)
        self.edit_tags_action.setEnabled(has_tab)
        self.export_pdf_action.setEnabled(has_tab)
        self.export_markdown_action.setEnabled(has_tab)
        self.export_html_action.setEnabled(has_tab)
        self.insert_media_action.setEnabled(has_tab)
        self.encrypt_note_action.setEnabled(has_tab)
        self.decrypt_note_action.setEnabled(has_tab and bool(tab and tab.encryption_enabled))
        self.change_note_password_action.setEnabled(has_tab and bool(tab and tab.encryption_enabled))
        self.ask_ai_action.setEnabled(not ai_private_mode)
        self.ai_chat_panel_action.setEnabled(not ai_private_mode)
        if hasattr(self, "ai_chat_dock"):
            self.ai_chat_panel_action.setChecked(self.ai_chat_dock.isVisible())
        self.explain_selection_ai_action.setEnabled(has_tab and has_selection and not ai_private_mode)
        self.ai_rewrite_shorten_action.setEnabled(has_tab and has_selection and not ai_private_mode and not is_read_only)
        self.ai_rewrite_formal_action.setEnabled(has_tab and has_selection and not ai_private_mode and not is_read_only)
        self.ai_rewrite_grammar_action.setEnabled(has_tab and has_selection and not ai_private_mode and not is_read_only)
        self.ai_rewrite_summarize_action.setEnabled(has_tab and has_selection and not ai_private_mode and not is_read_only)
        self.ai_ask_context_action.setEnabled(has_tab and not ai_private_mode)
        self.ai_run_template_action.setEnabled(has_tab and not ai_private_mode)
        self.ai_save_template_action.setEnabled(True)
        self.ai_usage_summary_action.setEnabled(True)
        self.ai_action_history_action.setEnabled(True)
        self.ai_file_citations_action.setEnabled(has_tab and not ai_private_mode)
        self.ai_commit_changelog_action.setEnabled(has_tab and not ai_private_mode)
        self.ai_batch_refactor_action.setEnabled(not ai_private_mode)
        self.ai_private_mode_action.blockSignals(True)
        self.ai_private_mode_action.setChecked(ai_private_mode)
        self.ai_private_mode_action.blockSignals(False)
        self.insert_meeting_template_action.setEnabled(has_tab)
        self.insert_daily_template_action.setEnabled(has_tab)
        self.insert_checklist_template_action.setEnabled(has_tab)

        # Edit actions
        self.undo_action.setEnabled(has_tab and can_undo and not is_read_only)
        self.redo_action.setEnabled(has_tab and can_redo and not is_read_only)
        self.cut_action.setEnabled(has_tab and has_selection and not is_read_only)
        self.copy_action.setEnabled(has_tab and has_selection)
        self.delete_action.setEnabled(has_tab and has_selection and not is_read_only)
        self.paste_action.setEnabled(has_tab and has_clipboard_text and not is_read_only)
        self.select_all_action.setEnabled(has_tab and has_text)
        self.find_action.setEnabled(has_tab and has_text)
        self.replace_action.setEnabled(has_tab and has_text)
        self.find_next_action.setEnabled(has_tab and has_text and has_search_seed)
        self.find_prev_action.setEnabled(has_tab and has_text and has_search_seed)
        self.search_bing_action.setEnabled(has_tab and (has_selection or has_search_seed))
        self.time_date_action.setEnabled(has_tab)
        self.reminders_action.setEnabled(has_tab)
        self.search_panel_action.setEnabled(has_tab)
        self.replace_in_files_action.setEnabled(True)
        self.find_in_files_action.setEnabled(True)
        self.select_find_next_action.setEnabled(has_tab and has_selection)
        self.select_find_prev_action.setEnabled(has_tab and has_selection)
        self.find_volatile_next_action.setEnabled(has_tab and has_text)
        self.find_volatile_prev_action.setEnabled(has_tab and has_text)
        self.incremental_search_action.setEnabled(has_tab and has_text)
        self.goto_line_action.setEnabled(has_tab and has_text)
        self.mark_action.setEnabled(has_tab and has_text)
        self.change_history_next_action.setEnabled(has_tab)
        self.change_history_prev_action.setEnabled(has_tab)
        self.change_history_clear_action.setEnabled(has_tab)
        self.jump_up_action.setEnabled(has_tab)
        self.jump_down_action.setEnabled(has_tab)
        self.style_all_occurrences_action.setEnabled(has_tab and has_text)
        self.style_one_token_action.setEnabled(has_tab and has_text)
        self.clear_style_action.setEnabled(has_tab and has_text)
        self.copy_styled_text_action.setEnabled(has_tab and has_text)
        self.cut_bookmarked_lines_action.setEnabled(has_tab and not is_read_only)
        self.copy_bookmarked_lines_action.setEnabled(has_tab)
        self.paste_replace_bookmarked_lines_action.setEnabled(has_tab and not is_read_only)
        self.remove_bookmarked_lines_action.setEnabled(has_tab and not is_read_only)
        self.remove_non_bookmarked_lines_action.setEnabled(has_tab and not is_read_only)
        self.inverse_bookmarks_action.setEnabled(has_tab)
        self.start_macro_recording_action.setEnabled(has_tab and not macro_recording)
        self.stop_macro_recording_action.setEnabled(macro_recording)
        self.play_macro_action.setEnabled(has_tab and macro_has_events and not macro_recording and not is_read_only)
        self.save_current_macro_action.setEnabled(macro_has_events and not macro_recording)
        self.run_macro_multiple_times_action.setEnabled(has_tab and macro_has_events and not macro_recording and not is_read_only)
        self.trim_trailing_spaces_and_save_action.setEnabled(has_tab and not is_read_only)
        saved_macros = self.settings.get("saved_macros", {})
        has_saved_macros = isinstance(saved_macros, dict) and bool(saved_macros)
        self.modify_macro_shortcut_delete_action.setEnabled(has_saved_macros)
        self.toggle_bookmark_action.setEnabled(has_tab)
        self.next_bookmark_action.setEnabled(has_tab)
        self.prev_bookmark_action.setEnabled(has_tab)
        self.clear_bookmarks_action.setEnabled(has_tab)
        self.column_mode_action.setEnabled(has_scintilla)
        self.multi_caret_action.setEnabled(has_scintilla)
        self.code_folding_action.setEnabled(has_scintilla)
        self.full_screen_action.setEnabled(True)
        self.always_on_top_action.blockSignals(True)
        self.always_on_top_action.setChecked(bool(self.settings.get("always_on_top", False)))
        self.always_on_top_action.blockSignals(False)
        self.post_it_action.blockSignals(True)
        self.post_it_action.setChecked(bool(self.settings.get("post_it_mode", False)))
        self.post_it_action.blockSignals(False)
        self.distraction_free_action.blockSignals(True)
        self.distraction_free_action.setChecked(bool(self.isFullScreen() and self.focus_mode_action.isChecked()))
        self.distraction_free_action.blockSignals(False)
        self.always_on_top_action.setEnabled(True)
        self.post_it_action.setEnabled(True)
        self.distraction_free_action.setEnabled(has_tab)
        self.focus_other_view_action.setEnabled(has_tab)
        self.hide_lines_action.setEnabled(has_scintilla and has_tab)
        self.show_hidden_lines_action.setEnabled(has_scintilla and has_tab)
        self.view_file_explorer_action.setEnabled(has_tab and bool(tab and tab.current_file))
        self.view_file_default_action.setEnabled(has_tab and bool(tab and tab.current_file))
        self.view_file_cmd_action.setEnabled(has_tab and bool(tab and tab.current_file))
        self.show_space_tab_action.setEnabled(has_scintilla)
        self.show_end_of_line_action.setEnabled(has_scintilla)
        self.show_non_printing_action.setEnabled(has_scintilla)
        self.show_control_unicode_eol_action.setEnabled(has_scintilla)
        self.show_all_chars_action.setEnabled(has_scintilla)
        self.show_indent_guide_action.setEnabled(has_scintilla)
        self.show_wrap_symbol_action.setEnabled(has_scintilla)
        self.fold_all_action.setEnabled(has_scintilla)
        self.unfold_all_action.setEnabled(has_scintilla)
        self.fold_current_level_action.setEnabled(has_scintilla)
        self.unfold_current_level_action.setEnabled(has_scintilla)
        for action in self.fold_level_actions:
            action.setEnabled(has_scintilla)
        for action in self.unfold_level_actions:
            action.setEnabled(has_scintilla)
        self.document_map_action.setEnabled(has_tab)
        self.document_list_action.setEnabled(True)
        self.function_list_action.setEnabled(has_tab)
        has_split = bool(tab and tab.clone_editor and tab.clone_editor.widget.isVisible())
        self.sync_vertical_action.setEnabled(has_split)
        self.sync_horizontal_action.setEnabled(has_split)
        self.define_language_action.setEnabled(True)
        self.monitor_tail_action.setEnabled(True)
        if has_split and hasattr(self, "_apply_split_scroll_sync"):
            self._apply_split_scroll_sync(tab)
        elif tab is not None and hasattr(self, "_disconnect_split_scroll_sync"):
            self._disconnect_split_scroll_sync(tab)
        self.text_direction_rtl_action.setEnabled(has_tab)
        self.text_direction_ltr_action.setEnabled(has_tab)
        sort_enabled = self.tab_widget.count() > 1
        self.window_sort_name_asc_action.setEnabled(sort_enabled)
        self.window_sort_name_desc_action.setEnabled(sort_enabled)
        self.window_sort_path_asc_action.setEnabled(sort_enabled)
        self.window_sort_path_desc_action.setEnabled(sort_enabled)
        self.window_sort_type_asc_action.setEnabled(sort_enabled)
        self.window_sort_type_desc_action.setEnabled(sort_enabled)
        self.window_sort_len_asc_action.setEnabled(sort_enabled)
        self.window_sort_len_desc_action.setEnabled(sort_enabled)
        self.window_sort_modified_asc_action.setEnabled(sort_enabled)
        self.window_sort_modified_desc_action.setEnabled(sort_enabled)
        self.windows_manager_action.setEnabled(has_tab)
        self.clone_view_action.setEnabled(has_tab)
        self.split_vertical_action.setEnabled(has_tab)
        self.split_horizontal_action.setEnabled(has_tab)
        self.split_close_action.setEnabled(has_tab and bool(tab and tab.clone_editor))
        self.minimap_action.setEnabled(has_tab)
        self.symbol_outline_action.setEnabled(has_tab)
        self.goto_definition_action.setEnabled(has_tab)
        self.side_by_side_diff_action.setEnabled(has_tab)
        self.three_way_merge_action.setEnabled(True)
        self.snippet_engine_action.setEnabled(has_tab and not is_read_only)
        self.template_packs_action.setEnabled(True)
        self.task_workflow_action.setEnabled(True)
        self.plugin_manager_action.setEnabled(True)
        self.open_plugins_folder_action.setEnabled(True)
        self.mime_tools_action.setEnabled(has_tab and has_text)
        self.converter_tools_action.setEnabled(has_tab and has_text)
        self.npp_export_tools_action.setEnabled(has_tab and has_text)
        self.backup_scheduler_action.setEnabled(True)
        self.backup_now_action.setEnabled(True)
        self.diagnostics_bundle_action.setEnabled(True)
        self.lan_collaboration_action.setEnabled(True)
        self.annotation_layer_action.setEnabled(has_tab)
        if hasattr(self, "show_symbol_toolbar_button"):
            self.show_symbol_toolbar_button.setEnabled(has_scintilla)
        self.keyboard_only_mode_action.blockSignals(True)
        self.keyboard_only_mode_action.setChecked(bool(self.settings.get("keyboard_only_mode", False)))
        self.keyboard_only_mode_action.blockSignals(False)
        self.command_palette_action.setEnabled(True)
        self.simple_mode_action.blockSignals(True)
        self.simple_mode_action.setChecked(bool(self.settings.get("simple_mode", False)))
        self.simple_mode_action.blockSignals(False)
        if hasattr(self, "search_highlight_checkbox"):
            self.search_highlight_checkbox.setEnabled(not is_large_file)

        # Format / view / markdown actions
        for action in (
            self.bold_action,
            self.italic_action,
            self.underline_action,
            self.strikethrough_action,
            self.font_action,
            self.zoom_in_action,
            self.zoom_out_action,
            self.zoom_reset_action,
            self.summary_action,
            self.md_heading1_action,
            self.md_heading2_action,
            self.md_heading3_action,
            self.md_heading4_action,
            self.md_heading5_action,
            self.md_heading6_action,
            self.md_bold_action,
            self.md_italic_action,
            self.md_strike_action,
            self.md_inline_code_action,
            self.md_code_block_action,
            self.md_bullet_action,
            self.md_numbered_action,
            self.md_task_action,
            self.md_toggle_task_action,
            self.md_quote_action,
            self.md_link_action,
            self.md_image_action,
            self.md_hr_action,
            self.md_table_action,
            self.md_toggle_preview_action,
        ):
            action.setEnabled(has_tab and not is_large_file)

    def create_actions(self: Any) -> None:
        # File actions
        self.new_action = QAction("&New", self)
        self.new_action.setShortcut(QKeySequence(QKeySequence.StandardKey.New))
        self.new_action.triggered.connect(self.file_new)

        self.open_action = QAction("&Open...", self)
        self.open_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Open))
        self.open_action.triggered.connect(self.file_open)

        self.save_action = QAction("&Save", self)
        self.save_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Save))
        self.save_action.triggered.connect(self.file_save)

        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_as_action.triggered.connect(self.file_save_as)
        self.rename_action = QAction("&Rename...", self)
        self.rename_action.triggered.connect(self.rename_active_tab_file)
        self.move_recycle_action = QAction("Move to &Recycle Bin", self)
        self.move_recycle_action.triggered.connect(self.move_active_tab_to_recycle_bin)

        self.save_all_action = QAction("Save A&ll", self)
        self.save_all_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.save_all_action.triggered.connect(self.save_all_tabs)

        self.save_session_action = QAction("Save Session", self)
        self.save_session_action.setShortcut(QKeySequence("Ctrl+Alt+Shift+S"))
        self.save_session_action.triggered.connect(self.save_session)

        self.save_session_as_action = QAction("Save Session As...", self)
        self.save_session_as_action.triggered.connect(self.save_session_as)

        self.load_session_action = QAction("Load Session...", self)
        self.load_session_action.setShortcut(QKeySequence("Ctrl+Alt+Shift+O"))
        self.load_session_action.triggered.connect(self.load_session)

        self.close_tab_action = QAction("&Close Tab", self)
        self.close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        self.close_tab_action.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))

        self.close_all_action = QAction("Close &All Tabs", self)
        self.close_all_action.triggered.connect(self.close_all_tabs)

        self.close_all_but_active_action = QAction("Close All But Active", self)
        self.close_all_but_active_action.triggered.connect(
            lambda: self.close_all_but(self.tab_widget.currentIndex())
        )
        self.close_all_but_pinned_action = QAction("Close All But Pinned", self)
        self.close_all_but_pinned_action.triggered.connect(self.close_all_but_pinned)
        self.close_all_left_action = QAction("Close All To The Left", self)
        self.close_all_left_action.triggered.connect(
            lambda: self.close_all_left_of(self.tab_widget.currentIndex())
        )
        self.close_all_right_action = QAction("Close All To The Right", self)
        self.close_all_right_action.triggered.connect(
            lambda: self.close_all_right_of(self.tab_widget.currentIndex())
        )
        self.close_all_unchanged_action = QAction("Close All Unchanged", self)
        self.close_all_unchanged_action.triggered.connect(self.close_all_unchanged)

        self.encoding_utf8_action = QAction("UTF-8", self)
        self.encoding_utf8_action.triggered.connect(lambda: self.set_tab_encoding("utf-8"))
        self.encoding_utf16_action = QAction("UTF-16", self)
        self.encoding_utf16_action.triggered.connect(lambda: self.set_tab_encoding("utf-16"))
        self.encoding_ansi_action = QAction("ANSI (CP1252)", self)
        self.encoding_ansi_action.triggered.connect(lambda: self.set_tab_encoding("cp1252"))

        self.eol_lf_action = QAction("Unix (LF)", self)
        self.eol_lf_action.triggered.connect(lambda: self.set_tab_eol_mode("LF"))
        self.eol_crlf_action = QAction("Windows (CRLF)", self)
        self.eol_crlf_action.triggered.connect(lambda: self.set_tab_eol_mode("CRLF"))

        self.print_action = QAction("&Print...", self)
        self.print_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Print))
        self.print_action.triggered.connect(self.file_print)

        self.print_preview_action = QAction("Print Pre&view...", self)
        self.print_preview_action.setShortcut(QKeySequence("Ctrl+Alt+P"))
        self.print_preview_action.triggered.connect(self.file_print_preview)

        self.version_history_action = QAction("Version &History...", self)
        self.version_history_action.triggered.connect(self.show_version_history)

        self.pin_tab_action = QAction("&Pin Tab", self)
        self.pin_tab_action.setShortcut(QKeySequence("Ctrl+Alt+P"))
        self.pin_tab_action.triggered.connect(self.toggle_pin_active_tab)

        self.favorite_tab_action = QAction("&Favorite Tab", self)
        self.favorite_tab_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.favorite_tab_action.triggered.connect(self.toggle_favorite_active_tab)

        self.edit_tags_action = QAction("Edit &Tags...", self)
        self.edit_tags_action.triggered.connect(self.edit_active_tab_tags)

        self.new_from_meeting_template_action = QAction("New From Meeting Template", self)
        self.new_from_meeting_template_action.triggered.connect(
            lambda: self.new_tab_from_template("Meeting Notes")
        )
        self.new_from_daily_template_action = QAction("New From Daily Log Template", self)
        self.new_from_daily_template_action.triggered.connect(
            lambda: self.new_tab_from_template("Daily Log")
        )
        self.new_from_checklist_template_action = QAction("New From Checklist Template", self)
        self.new_from_checklist_template_action.triggered.connect(
            lambda: self.new_tab_from_template("Checklist")
        )

        self.insert_meeting_template_action = QAction("Insert Meeting Template", self)
        self.insert_meeting_template_action.triggered.connect(
            lambda: self.insert_template_into_active_tab("Meeting Notes")
        )
        self.insert_daily_template_action = QAction("Insert Daily Log Template", self)
        self.insert_daily_template_action.triggered.connect(
            lambda: self.insert_template_into_active_tab("Daily Log")
        )
        self.insert_checklist_template_action = QAction("Insert Checklist Template", self)
        self.insert_checklist_template_action.triggered.connect(
            lambda: self.insert_template_into_active_tab("Checklist")
        )

        self.export_pdf_action = QAction("Export as PDF...", self)
        self.export_pdf_action.triggered.connect(self.export_active_as_pdf)
        self.export_markdown_action = QAction("Export as Markdown...", self)
        self.export_markdown_action.triggered.connect(self.export_active_as_markdown)
        self.export_html_action = QAction("Export as HTML...", self)
        self.export_html_action.triggered.connect(self.export_active_as_html)
        self.insert_media_action = QAction("Insert Media...", self)
        self.insert_media_action.triggered.connect(self.insert_media_files)

        self.open_workspace_action = QAction("Open Workspace Folder...", self)
        self.open_workspace_action.triggered.connect(self.open_workspace_folder)
        self.workspace_files_action = QAction("Workspace Files...", self)
        self.workspace_files_action.triggered.connect(self.show_workspace_files)
        self.workspace_search_action = QAction("Search Workspace...", self)
        self.workspace_search_action.triggered.connect(self.search_workspace)

        self.encrypt_note_action = QAction("Enable Note Encryption...", self)
        self.encrypt_note_action.triggered.connect(self.enable_note_encryption)
        self.decrypt_note_action = QAction("Disable Note Encryption", self)
        self.decrypt_note_action.triggered.connect(self.disable_note_encryption)
        self.change_note_password_action = QAction("Change Note Password...", self)
        self.change_note_password_action.triggered.connect(self.change_note_password)
        self.ask_ai_action = QAction("Ask AI...", self)
        self.ask_ai_action.triggered.connect(self.ask_ai)
        self.ai_chat_panel_action = QAction("AI Chat Panel", self)
        self.ai_chat_panel_action.setCheckable(True)
        self.ai_chat_panel_action.triggered.connect(self.toggle_ai_chat_panel)
        self.explain_selection_ai_action = QAction("Explain Selection with AI", self)
        self.explain_selection_ai_action.triggered.connect(self.explain_selection_with_ai)
        self.ai_rewrite_shorten_action = QAction("Rewrite Selection: Shorten", self)
        self.ai_rewrite_shorten_action.triggered.connect(lambda: self.ai_rewrite_selection("shorten"))
        self.ai_rewrite_formal_action = QAction("Rewrite Selection: Formal", self)
        self.ai_rewrite_formal_action.triggered.connect(lambda: self.ai_rewrite_selection("formal"))
        self.ai_rewrite_grammar_action = QAction("Rewrite Selection: Fix Grammar", self)
        self.ai_rewrite_grammar_action.triggered.connect(lambda: self.ai_rewrite_selection("fix_grammar"))
        self.ai_rewrite_summarize_action = QAction("Rewrite Selection: Summarize", self)
        self.ai_rewrite_summarize_action.triggered.connect(lambda: self.ai_rewrite_selection("summarize"))
        self.ai_ask_context_action = QAction("Ask About This File...", self)
        self.ai_ask_context_action.triggered.connect(self.ask_ai_about_current_context)
        self.ai_run_template_action = QAction("Run Prompt Template...", self)
        self.ai_run_template_action.triggered.connect(self.run_ai_prompt_template)
        self.ai_save_template_action = QAction("Save Prompt Template...", self)
        self.ai_save_template_action.triggered.connect(self.save_ai_prompt_template)
        self.ai_usage_summary_action = QAction("AI Usage Summary", self)
        self.ai_usage_summary_action.triggered.connect(self.show_ai_usage_summary)
        self.ai_action_history_action = QAction("AI Action History", self)
        self.ai_action_history_action.triggered.connect(self.show_ai_action_history)
        self.ai_private_mode_action = QAction("AI Private Mode", self)
        self.ai_private_mode_action.setCheckable(True)
        self.ai_private_mode_action.setChecked(bool(self.settings.get("ai_private_mode", False)))
        self.ai_private_mode_action.triggered.connect(self.toggle_ai_private_mode)

        self.search_panel_action = QAction("Find &Panel", self)
        self.search_panel_action.setCheckable(True)
        self.search_panel_action.toggled.connect(self.toggle_search_panel)
        self.find_action = QAction("&Find...", self)
        self.find_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Find))
        self.find_action.triggered.connect(self.search_incremental)

        self.settings_action = QAction("&Preferences...", self)
        self.settings_action.triggered.connect(self.open_settings)
        self.command_palette_action = QAction("Command Palette...", self)
        self.command_palette_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.command_palette_action.triggered.connect(self.open_command_palette)
        self.simple_mode_action = QAction("Simple Mode", self)
        self.simple_mode_action.setCheckable(True)
        self.simple_mode_action.setChecked(bool(self.settings.get("simple_mode", False)))
        self.simple_mode_action.triggered.connect(self.toggle_simple_mode)
        self.preset_reading_action = QAction("Preset: Reading", self)
        self.preset_reading_action.triggered.connect(self.apply_reading_preset)
        self.preset_coding_action = QAction("Preset: Coding", self)
        self.preset_coding_action.triggered.connect(self.apply_coding_preset)
        self.preset_focus_action = QAction("Preset: Focus", self)
        self.preset_focus_action.triggered.connect(self.apply_focus_preset)

        self.exit_action = QAction("E&xit", self)
        self.exit_action.triggered.connect(self.close)

        # Edit actions
        self.undo_action = QAction("&Undo", self)
        self.undo_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Undo))
        self.undo_action.triggered.connect(self.edit_undo)

        self.redo_action = QAction("&Redo", self)
        self.redo_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Redo))
        self.redo_action.triggered.connect(self.edit_redo)

        self.cut_action = QAction("Cu&t", self)
        self.cut_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Cut))
        self.cut_action.triggered.connect(self.edit_cut)

        self.copy_action = QAction("&Copy", self)
        self.copy_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Copy))
        self.copy_action.triggered.connect(self.edit_copy)

        self.paste_action = QAction("&Paste", self)
        self.paste_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Paste))
        self.paste_action.triggered.connect(self.edit_paste)

        self.delete_action = QAction("&Delete", self)
        self.delete_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self.delete_action.triggered.connect(self.edit_delete)

        self.select_all_action = QAction("Select &All", self)
        self.select_all_action.setShortcut(QKeySequence(QKeySequence.StandardKey.SelectAll))
        self.select_all_action.triggered.connect(self.edit_select_all)

        self.time_date_action = QAction("Time/&Date", self)
        self.time_date_action.setShortcut(QKeySequence("F5"))
        self.time_date_action.triggered.connect(self.edit_time_date)

        self.find_next_action = QAction("Find &Next", self)
        self.find_next_action.setShortcut(QKeySequence("F3"))
        self.find_next_action.triggered.connect(self.edit_find_next)

        self.find_prev_action = QAction("Find &Previous", self)
        self.find_prev_action.setShortcut(QKeySequence("Shift+F3"))
        self.find_prev_action.triggered.connect(self.edit_find_previous)

        self.find_in_files_action = QAction("Find in Files...", self)
        self.find_in_files_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.find_in_files_action.triggered.connect(self.search_find_in_files)

        self.select_find_next_action = QAction("Select and Find Next", self)
        self.select_find_next_action.setShortcut(QKeySequence("Ctrl+F3"))
        self.select_find_next_action.triggered.connect(self.search_select_and_find_next)

        self.select_find_prev_action = QAction("Select and Find Previous", self)
        self.select_find_prev_action.setShortcut(QKeySequence("Ctrl+Shift+F3"))
        self.select_find_prev_action.triggered.connect(self.search_select_and_find_previous)

        self.find_volatile_next_action = QAction("Find (Volatile) Next", self)
        self.find_volatile_next_action.setShortcut(QKeySequence("Ctrl+Alt+F3"))
        self.find_volatile_next_action.triggered.connect(self.search_find_volatile_next)

        self.find_volatile_prev_action = QAction("Find (Volatile) Previous", self)
        self.find_volatile_prev_action.setShortcut(QKeySequence("Ctrl+Alt+Shift+F3"))
        self.find_volatile_prev_action.triggered.connect(self.search_find_volatile_previous)

        self.incremental_search_action = QAction("Incremental Search", self)
        self.incremental_search_action.setShortcut(QKeySequence("Ctrl+Alt+I"))
        self.incremental_search_action.triggered.connect(self.search_incremental)

        self.search_results_window_action = QAction("Search Results Window", self)
        self.search_results_window_action.setShortcut(QKeySequence("F7"))
        self.search_results_window_action.setEnabled(False)
        self.next_search_result_action = QAction("Next Search Result", self)
        self.next_search_result_action.setShortcut(QKeySequence("F4"))
        self.next_search_result_action.setEnabled(False)
        self.prev_search_result_action = QAction("Previous Search Result", self)
        self.prev_search_result_action.setShortcut(QKeySequence("Shift+F4"))
        self.prev_search_result_action.setEnabled(False)

        self.goto_line_action = QAction("Go to...", self)
        self.goto_line_action.setShortcut(QKeySequence("Ctrl+G"))
        self.goto_line_action.triggered.connect(self.search_goto_line)
        self.goto_matching_brace_action = QAction("Go to Matching Brace", self)
        self.goto_matching_brace_action.setShortcut(QKeySequence("Ctrl+B"))
        self.goto_matching_brace_action.setEnabled(False)
        self.select_in_between_braces_action = QAction("Select All In-between {} [] or ()", self)
        self.select_in_between_braces_action.setShortcut(QKeySequence("Ctrl+Alt+B"))
        self.select_in_between_braces_action.setEnabled(False)
        self.find_chars_in_range_action = QAction("Find characters in range...", self)
        self.find_chars_in_range_action.setEnabled(False)

        self.mark_action = QAction("Mark...", self)
        self.mark_action.setShortcut(QKeySequence("Ctrl+M"))
        self.mark_action.triggered.connect(self.search_mark)

        self.change_history_next_action = QAction("Go to Next Change", self)
        self.change_history_next_action.triggered.connect(self.search_change_history_next)
        self.change_history_prev_action = QAction("Go to Previous Change", self)
        self.change_history_prev_action.triggered.connect(self.search_change_history_previous)
        self.change_history_clear_action = QAction("Clear Change History", self)
        self.change_history_clear_action.triggered.connect(self.search_change_history_clear)

        self.jump_up_action = QAction("Jump Up", self)
        self.jump_up_action.triggered.connect(self.search_jump_up_styled)
        self.jump_down_action = QAction("Jump Down", self)
        self.jump_down_action.triggered.connect(self.search_jump_down_styled)

        self.replace_action = QAction("&Replace...", self)
        self.replace_action.setShortcut(QKeySequence("Ctrl+H"))
        self.replace_action.triggered.connect(self.edit_replace)

        self.replace_in_files_action = QAction("Replace in Files...", self)
        self.replace_in_files_action.triggered.connect(self.replace_in_files)

        self.start_macro_recording_action = QAction("Start Recording", self)
        self.start_macro_recording_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.start_macro_recording_action.triggered.connect(self.start_macro_recording)

        self.stop_macro_recording_action = QAction("Stop Recording", self)
        self.stop_macro_recording_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.stop_macro_recording_action.triggered.connect(self.stop_macro_recording)

        self.play_macro_action = QAction("Playback Macro", self)
        self.play_macro_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.play_macro_action.triggered.connect(self.play_macro)

        self.save_current_macro_action = QAction("Save Current Recorded Macro...", self)
        self.save_current_macro_action.triggered.connect(self.save_current_recorded_macro)

        self.run_macro_multiple_times_action = QAction("Run a Macro Multiple Times...", self)
        self.run_macro_multiple_times_action.triggered.connect(self.run_macro_multiple_times)

        self.trim_trailing_spaces_and_save_action = QAction("Trim Trailing Spaces and Save", self)
        self.trim_trailing_spaces_and_save_action.setShortcut(QKeySequence("Alt+Shift+S"))
        self.trim_trailing_spaces_and_save_action.triggered.connect(self.trim_trailing_spaces_and_save)

        self.modify_macro_shortcut_delete_action = QAction("Modify Shortcut/Delete Macro...", self)
        self.modify_macro_shortcut_delete_action.triggered.connect(self.modify_macro_shortcut_or_delete)

        self.toggle_bookmark_action = QAction("Toggle &Bookmark", self)
        self.toggle_bookmark_action.setShortcut(QKeySequence("Ctrl+F2"))
        self.toggle_bookmark_action.triggered.connect(self.toggle_bookmark)
        self.next_bookmark_action = QAction("Next Bookmark", self)
        self.next_bookmark_action.setShortcut(QKeySequence("F2"))
        self.next_bookmark_action.triggered.connect(self.goto_next_bookmark)
        self.prev_bookmark_action = QAction("Previous Bookmark", self)
        self.prev_bookmark_action.setShortcut(QKeySequence("Shift+F2"))
        self.prev_bookmark_action.triggered.connect(self.goto_prev_bookmark)
        self.clear_bookmarks_action = QAction("Clear Bookmarks", self)
        self.clear_bookmarks_action.triggered.connect(self.clear_bookmarks)
        self.cut_bookmarked_lines_action = QAction("Cut Bookmarked Lines", self)
        self.cut_bookmarked_lines_action.triggered.connect(self.bookmark_cut_lines)
        self.copy_bookmarked_lines_action = QAction("Copy Bookmarked Lines", self)
        self.copy_bookmarked_lines_action.triggered.connect(self.bookmark_copy_lines)
        self.paste_replace_bookmarked_lines_action = QAction("Paste to (Replace) Bookmarked Lines", self)
        self.paste_replace_bookmarked_lines_action.triggered.connect(self.bookmark_paste_replace_lines)
        self.remove_bookmarked_lines_action = QAction("Remove Bookmarked Lines", self)
        self.remove_bookmarked_lines_action.triggered.connect(self.bookmark_remove_lines)
        self.remove_non_bookmarked_lines_action = QAction("Remove Non-Bookmarked Lines", self)
        self.remove_non_bookmarked_lines_action.triggered.connect(self.bookmark_remove_non_bookmarked_lines)
        self.inverse_bookmarks_action = QAction("Inverse Bookmarks", self)
        self.inverse_bookmarks_action.triggered.connect(self.bookmark_inverse)

        self.style_all_occurrences_action = QAction("Style All Occurrences of Token", self)
        self.style_one_token_action = QAction("Style One Token", self)
        self.clear_style_action = QAction("Clear Style", self)
        self.copy_styled_text_action = QAction("Copy Styled Text", self)

        self.style_all_1_action = QAction("Using 1st Style", self)
        self.style_all_1_action.triggered.connect(lambda: self.search_style_all_occurrences(1))
        self.style_all_2_action = QAction("Using 2nd Style", self)
        self.style_all_2_action.triggered.connect(lambda: self.search_style_all_occurrences(2))
        self.style_all_3_action = QAction("Using 3rd Style", self)
        self.style_all_3_action.triggered.connect(lambda: self.search_style_all_occurrences(3))
        self.style_all_4_action = QAction("Using 4th Style", self)
        self.style_all_4_action.triggered.connect(lambda: self.search_style_all_occurrences(4))
        self.style_all_5_action = QAction("Using 5th Style", self)
        self.style_all_5_action.triggered.connect(lambda: self.search_style_all_occurrences(5))
        self.style_all_find_action = QAction("Find Mark Style", self)
        self.style_all_find_action.triggered.connect(lambda: self.search_style_all_occurrences(0))

        self.style_one_1_action = QAction("1st Style", self)
        self.style_one_1_action.setShortcut(QKeySequence("Ctrl+1"))
        self.style_one_1_action.triggered.connect(lambda: self.search_style_one_token(1))
        self.style_one_2_action = QAction("2nd Style", self)
        self.style_one_2_action.setShortcut(QKeySequence("Ctrl+2"))
        self.style_one_2_action.triggered.connect(lambda: self.search_style_one_token(2))
        self.style_one_3_action = QAction("3rd Style", self)
        self.style_one_3_action.setShortcut(QKeySequence("Ctrl+3"))
        self.style_one_3_action.triggered.connect(lambda: self.search_style_one_token(3))
        self.style_one_4_action = QAction("4th Style", self)
        self.style_one_4_action.setShortcut(QKeySequence("Ctrl+4"))
        self.style_one_4_action.triggered.connect(lambda: self.search_style_one_token(4))
        self.style_one_5_action = QAction("5th Style", self)
        self.style_one_5_action.setShortcut(QKeySequence("Ctrl+5"))
        self.style_one_5_action.triggered.connect(lambda: self.search_style_one_token(5))
        self.style_one_find_action = QAction("Find Mark Style", self)
        self.style_one_find_action.setShortcut(QKeySequence("Ctrl+Alt+0"))
        self.style_one_find_action.triggered.connect(lambda: self.search_style_one_token(0))

        self.clear_style_1_action = QAction("Clear 1st Style", self)
        self.clear_style_1_action.triggered.connect(lambda: self.search_clear_style(1))
        self.clear_style_2_action = QAction("Clear 2nd Style", self)
        self.clear_style_2_action.triggered.connect(lambda: self.search_clear_style(2))
        self.clear_style_3_action = QAction("Clear 3rd Style", self)
        self.clear_style_3_action.triggered.connect(lambda: self.search_clear_style(3))
        self.clear_style_4_action = QAction("Clear 4th Style", self)
        self.clear_style_4_action.triggered.connect(lambda: self.search_clear_style(4))
        self.clear_style_5_action = QAction("Clear 5th Style", self)
        self.clear_style_5_action.triggered.connect(lambda: self.search_clear_style(5))
        self.clear_style_all_action = QAction("Clear all Styles", self)
        self.clear_style_all_action.triggered.connect(lambda: self.search_clear_style(None))

        self.copy_styled_1_action = QAction("Copy 1st Styled Text", self)
        self.copy_styled_1_action.triggered.connect(lambda: self.search_copy_styled_text(1))
        self.copy_styled_2_action = QAction("Copy 2nd Styled Text", self)
        self.copy_styled_2_action.triggered.connect(lambda: self.search_copy_styled_text(2))
        self.copy_styled_3_action = QAction("Copy 3rd Styled Text", self)
        self.copy_styled_3_action.triggered.connect(lambda: self.search_copy_styled_text(3))
        self.copy_styled_4_action = QAction("Copy 4th Styled Text", self)
        self.copy_styled_4_action.triggered.connect(lambda: self.search_copy_styled_text(4))
        self.copy_styled_5_action = QAction("Copy 5th Styled Text", self)
        self.copy_styled_5_action.triggered.connect(lambda: self.search_copy_styled_text(5))
        self.copy_styled_all_action = QAction("Copy All Styled Text", self)
        self.copy_styled_all_action.triggered.connect(lambda: self.search_copy_styled_text(None))

        self.reminders_action = QAction("&Reminders && Alarms...", self)
        self.reminders_action.setShortcut(QKeySequence("Ctrl+Alt+R"))
        self.reminders_action.triggered.connect(self.show_reminders)

        self.search_bing_action = QAction("Search with &Bing", self)
        self.search_bing_action.setShortcut(QKeySequence("Ctrl+E"))
        self.search_bing_action.triggered.connect(self.edit_search_bing)

        # Format actions
        self.word_wrap_action = QAction("&Word Wrap", self)
        self.word_wrap_action.setCheckable(True)
        self.word_wrap_action.setChecked(True)
        self.word_wrap_action.triggered.connect(self.toggle_word_wrap)

        self.font_action = QAction("&Font...", self)
        self.font_action.triggered.connect(self.choose_font)

        self.bold_action = QAction("&Bold", self)
        self.bold_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Bold))
        self.bold_action.triggered.connect(self.format_bold)

        self.italic_action = QAction("&Italic", self)
        self.italic_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Italic))
        self.italic_action.triggered.connect(self.format_italic)

        self.underline_action = QAction("&Underline", self)
        self.underline_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Underline))
        self.underline_action.triggered.connect(self.format_underline)

        self.strikethrough_action = QAction("&Strikethrough", self)
        self.strikethrough_action.setShortcut(QKeySequence("Ctrl+Shift+X"))
        self.strikethrough_action.triggered.connect(self.format_strikethrough)

        # View actions
        self.status_bar_action = QAction("&Status Bar", self)
        self.status_bar_action.setCheckable(True)
        self.status_bar_action.setChecked(True)
        self.status_bar_action.triggered.connect(self.toggle_status_bar)

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self.zoom_in_action.triggered.connect(self.view_zoom_in)

        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        self.zoom_out_action.triggered.connect(self.view_zoom_out)

        self.zoom_reset_action = QAction("&Restore Default Zoom", self)
        self.zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        self.zoom_reset_action.triggered.connect(self.view_zoom_reset)

        self.summary_action = QAction("Document &Summary", self)
        self.summary_action.setShortcut(QKeySequence("Ctrl+Alt+D"))
        self.summary_action.triggered.connect(self.show_document_summary)

        self.focus_mode_action = QAction("&Focus Mode", self)
        self.focus_mode_action.setCheckable(True)
        self.focus_mode_action.setShortcut(QKeySequence("Ctrl+Alt+Shift+F"))
        self.focus_mode_action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        self.focus_mode_action.triggered.connect(self.toggle_focus_mode)

        self.full_screen_action = QAction("&Full Screen", self)
        self.full_screen_action.setCheckable(True)
        self.full_screen_action.setShortcut(QKeySequence("F11"))
        self.full_screen_action.triggered.connect(self.toggle_full_screen)

        self.always_on_top_action = QAction("Always on Top", self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(bool(self.settings.get("always_on_top", False)))
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)

        self.post_it_action = QAction("Post-it", self)
        self.post_it_action.setCheckable(True)
        self.post_it_action.setShortcut(QKeySequence("F12"))
        self.post_it_action.setChecked(bool(self.settings.get("post_it_mode", False)))
        self.post_it_action.triggered.connect(self.toggle_post_it_mode)

        self.distraction_free_action = QAction("Distraction Free Mode", self)
        self.distraction_free_action.setCheckable(True)
        self.distraction_free_action.triggered.connect(self.toggle_distraction_free_mode)

        self.view_file_explorer_action = QAction("Folder in Explorer", self)
        self.view_file_explorer_action.triggered.connect(self.view_current_file_in_explorer)
        self.view_file_default_action = QAction("Default Viewer", self)
        self.view_file_default_action.triggered.connect(self.view_current_file_in_default_viewer)
        self.view_file_cmd_action = QAction("Command Prompt Here", self)
        self.view_file_cmd_action.triggered.connect(self.view_current_file_in_cmd)

        self.show_space_tab_action = QAction("Show Space and Tab", self)
        self.show_space_tab_action.setCheckable(True)
        self.show_space_tab_action.setChecked(bool(self.settings.get("show_symbol_space_tab", False)))
        self.show_space_tab_action.triggered.connect(self.toggle_show_space_tab)
        self.show_end_of_line_action = QAction("Show End of Line", self)
        self.show_end_of_line_action.setCheckable(True)
        self.show_end_of_line_action.setChecked(bool(self.settings.get("show_symbol_eol", False)))
        self.show_end_of_line_action.triggered.connect(self.toggle_show_end_of_line)
        self.show_non_printing_action = QAction("Show Non-Printing Characters", self)
        self.show_non_printing_action.setCheckable(True)
        self.show_non_printing_action.setChecked(bool(self.settings.get("show_symbol_non_printing", False)))
        self.show_non_printing_action.triggered.connect(self.toggle_show_non_printing)
        self.show_control_unicode_eol_action = QAction("Show Control Characters && Unicode EOL", self)
        self.show_control_unicode_eol_action.setCheckable(True)
        self.show_control_unicode_eol_action.setChecked(bool(self.settings.get("show_symbol_control_chars", False)))
        self.show_control_unicode_eol_action.triggered.connect(self.toggle_show_control_unicode_eol)
        self.show_all_chars_action = QAction("Show All Characters", self)
        self.show_all_chars_action.setCheckable(True)
        self.show_all_chars_action.setChecked(bool(self.settings.get("show_symbol_all_chars", False)))
        self.show_all_chars_action.triggered.connect(self.toggle_show_all_chars)
        self.show_indent_guide_action = QAction("Show Indent Guide", self)
        self.show_indent_guide_action.setCheckable(True)
        self.show_indent_guide_action.setChecked(bool(self.settings.get("show_symbol_indent_guide", True)))
        self.show_indent_guide_action.triggered.connect(self.toggle_show_indent_guide)
        self.show_wrap_symbol_action = QAction("Show Wrap Symbol", self)
        self.show_wrap_symbol_action.setCheckable(True)
        self.show_wrap_symbol_action.setChecked(bool(self.settings.get("show_symbol_wrap_symbol", False)))
        self.show_wrap_symbol_action.triggered.connect(self.toggle_show_wrap_symbol)

        self.focus_other_view_action = QAction("Focus on Another View", self)
        self.focus_other_view_action.setShortcut(QKeySequence("F8"))
        self.focus_other_view_action.triggered.connect(self.focus_on_another_view)
        self.hide_lines_action = QAction("Hide Lines", self)
        self.hide_lines_action.setShortcut(QKeySequence("Alt+H"))
        self.hide_lines_action.triggered.connect(self.hide_lines)
        self.show_hidden_lines_action = QAction("Show Hidden Lines", self)
        self.show_hidden_lines_action.setShortcut(QKeySequence("Alt+Shift+H"))
        self.show_hidden_lines_action.triggered.connect(self.show_hidden_lines)

        self.fold_all_action = QAction("Fold All", self)
        self.fold_all_action.setShortcut(QKeySequence("Alt+0"))
        self.fold_all_action.triggered.connect(self.fold_all)
        self.unfold_all_action = QAction("Unfold All", self)
        self.unfold_all_action.setShortcut(QKeySequence("Alt+Shift+0"))
        self.unfold_all_action.triggered.connect(self.unfold_all)
        self.fold_current_level_action = QAction("Fold Current Level", self)
        self.fold_current_level_action.setShortcut(QKeySequence("Ctrl+Alt+F"))
        self.fold_current_level_action.triggered.connect(self.fold_current_level)
        self.unfold_current_level_action = QAction("Unfold Current Level", self)
        self.unfold_current_level_action.setShortcut(QKeySequence("Ctrl+Alt+Shift+F"))
        self.unfold_current_level_action.triggered.connect(self.unfold_current_level)
        self.fold_level_actions: list[QAction] = []
        self.unfold_level_actions: list[QAction] = []
        for level in range(1, 9):
            fold_action = QAction(f"Level {level}", self)
            fold_action.triggered.connect(lambda _checked=False, lvl=level: self.fold_level(lvl))
            self.fold_level_actions.append(fold_action)
            unfold_action = QAction(f"Level {level}", self)
            unfold_action.triggered.connect(lambda _checked=False, lvl=level: self.unfold_level(lvl))
            self.unfold_level_actions.append(unfold_action)

        self.document_map_action = QAction("Document Map", self)
        self.document_map_action.triggered.connect(self.open_document_map)
        self.document_list_action = QAction("Document List", self)
        self.document_list_action.triggered.connect(self.open_document_list)
        self.function_list_action = QAction("Function List", self)
        self.function_list_action.triggered.connect(self.open_function_list)
        self.sync_vertical_action = QAction("Synchronize Vertical Scrolling", self)
        self.sync_vertical_action.setCheckable(True)
        self.sync_vertical_action.setChecked(bool(self.settings.get("sync_vertical_scrolling", False)))
        self.sync_vertical_action.triggered.connect(self.toggle_sync_vertical_scrolling)
        self.sync_horizontal_action = QAction("Synchronize Horizontal Scrolling", self)
        self.sync_horizontal_action.setCheckable(True)
        self.sync_horizontal_action.setChecked(bool(self.settings.get("sync_horizontal_scrolling", False)))
        self.sync_horizontal_action.triggered.connect(self.toggle_sync_horizontal_scrolling)
        self.define_language_action = QAction("Define Your Language...", self)
        self.define_language_action.triggered.connect(self.open_define_language_dialog)
        self.monitor_tail_action = QAction("Monitoring (tail -f)...", self)
        self.monitor_tail_action.triggered.connect(self.open_monitoring_tail_dialog)

        self.text_direction_rtl_action = QAction("Text Direction RTL", self)
        self.text_direction_rtl_action.setShortcut(QKeySequence("Ctrl+Alt+R"))
        self.text_direction_rtl_action.triggered.connect(self.set_text_direction_rtl)
        self.text_direction_ltr_action = QAction("Text Direction LTR", self)
        self.text_direction_ltr_action.setShortcut(QKeySequence("Ctrl+Alt+L"))
        self.text_direction_ltr_action.triggered.connect(self.set_text_direction_ltr)

        self.column_mode_action = QAction("Column Mode", self)
        self.column_mode_action.setCheckable(True)
        self.column_mode_action.setShortcut(QKeySequence("Alt+Shift+C"))
        self.column_mode_action.triggered.connect(self.toggle_column_mode)

        self.multi_caret_action = QAction("Multi-Caret", self)
        self.multi_caret_action.setCheckable(True)
        self.multi_caret_action.setShortcut(QKeySequence("Alt+Shift+M"))
        self.multi_caret_action.triggered.connect(self.toggle_multi_caret)

        self.code_folding_action = QAction("Code Folding", self)
        self.code_folding_action.setCheckable(True)
        self.code_folding_action.setChecked(True)
        self.code_folding_action.triggered.connect(self.toggle_code_folding)

        self.clone_view_action = QAction("Clone to Other View", self)
        self.clone_view_action.setShortcut(QKeySequence("Ctrl+Shift+Alt+V"))
        self.clone_view_action.triggered.connect(self.clone_to_other_view)

        self.split_vertical_action = QAction("Split View Vertical", self)
        self.split_vertical_action.triggered.connect(self.split_view_vertical)
        self.split_horizontal_action = QAction("Split View Horizontal", self)
        self.split_horizontal_action.triggered.connect(self.split_view_horizontal)
        self.split_close_action = QAction("Close Split View", self)
        self.split_close_action.triggered.connect(self.close_split_view)

        # Window actions
        self.window_sort_name_asc_action = QAction("Name A to Z", self)
        self.window_sort_name_asc_action.triggered.connect(lambda: self.window_sort_tabs("name_asc"))
        self.window_sort_name_desc_action = QAction("Name Z to A", self)
        self.window_sort_name_desc_action.triggered.connect(lambda: self.window_sort_tabs("name_desc"))
        self.window_sort_path_asc_action = QAction("Path A to Z", self)
        self.window_sort_path_asc_action.triggered.connect(lambda: self.window_sort_tabs("path_asc"))
        self.window_sort_path_desc_action = QAction("Path Z to A", self)
        self.window_sort_path_desc_action.triggered.connect(lambda: self.window_sort_tabs("path_desc"))
        self.window_sort_type_asc_action = QAction("Type A to Z", self)
        self.window_sort_type_asc_action.triggered.connect(lambda: self.window_sort_tabs("type_asc"))
        self.window_sort_type_desc_action = QAction("Type Z to A", self)
        self.window_sort_type_desc_action.triggered.connect(lambda: self.window_sort_tabs("type_desc"))
        self.window_sort_len_asc_action = QAction("Content Length Ascending", self)
        self.window_sort_len_asc_action.triggered.connect(lambda: self.window_sort_tabs("content_len_asc"))
        self.window_sort_len_desc_action = QAction("Content Length Descending", self)
        self.window_sort_len_desc_action.triggered.connect(lambda: self.window_sort_tabs("content_len_desc"))
        self.window_sort_modified_asc_action = QAction("Modified Time Ascending", self)
        self.window_sort_modified_asc_action.triggered.connect(lambda: self.window_sort_tabs("modified_asc"))
        self.window_sort_modified_desc_action = QAction("Modified Time Descending", self)
        self.window_sort_modified_desc_action.triggered.connect(lambda: self.window_sort_tabs("modified_desc"))
        self.windows_manager_action = QAction("Windows...", self)
        self.windows_manager_action.triggered.connect(self.show_windows_manager)

        # Markdown actions
        self.md_heading1_action = QAction("Heading &1", self)
        self.md_heading1_action.setShortcut(QKeySequence("Ctrl+Alt+1"))
        self.md_heading1_action.triggered.connect(lambda: self.markdown_heading(1))

        self.md_heading2_action = QAction("Heading &2", self)
        self.md_heading2_action.setShortcut(QKeySequence("Ctrl+Alt+2"))
        self.md_heading2_action.triggered.connect(lambda: self.markdown_heading(2))

        self.md_heading3_action = QAction("Heading &3", self)
        self.md_heading3_action.setShortcut(QKeySequence("Ctrl+Alt+3"))
        self.md_heading3_action.triggered.connect(lambda: self.markdown_heading(3))

        self.md_heading4_action = QAction("Heading &4", self)
        self.md_heading4_action.setShortcut(QKeySequence("Ctrl+Alt+4"))
        self.md_heading4_action.triggered.connect(lambda: self.markdown_heading(4))

        self.md_heading5_action = QAction("Heading &5", self)
        self.md_heading5_action.setShortcut(QKeySequence("Ctrl+Alt+5"))
        self.md_heading5_action.triggered.connect(lambda: self.markdown_heading(5))

        self.md_heading6_action = QAction("Heading &6", self)
        self.md_heading6_action.setShortcut(QKeySequence("Ctrl+Alt+6"))
        self.md_heading6_action.triggered.connect(lambda: self.markdown_heading(6))

        self.md_bold_action = QAction("Bold (Markdown)", self)
        self.md_bold_action.triggered.connect(lambda: self.insert_markdown_wrapper("**", "**", "bold text"))

        self.md_italic_action = QAction("Italic (Markdown)", self)
        self.md_italic_action.triggered.connect(lambda: self.insert_markdown_wrapper("*", "*", "italic text"))

        self.md_strike_action = QAction("Strikethrough (Markdown)", self)
        self.md_strike_action.triggered.connect(lambda: self.insert_markdown_wrapper("~~", "~~", "struck text"))

        self.md_inline_code_action = QAction("Inline Code", self)
        self.md_inline_code_action.setShortcut(QKeySequence("Ctrl+`"))
        self.md_inline_code_action.triggered.connect(lambda: self.insert_markdown_wrapper("`", "`", "code"))

        self.md_code_block_action = QAction("Code Block", self)
        self.md_code_block_action.setShortcut(QKeySequence("Ctrl+Shift+`"))
        self.md_code_block_action.triggered.connect(self.markdown_code_block)

        self.md_bullet_action = QAction("Bullet List", self)
        self.md_bullet_action.setShortcut(QKeySequence("Ctrl+Shift+8"))
        self.md_bullet_action.triggered.connect(self.markdown_bullet_list)

        self.md_numbered_action = QAction("Numbered List", self)
        self.md_numbered_action.setShortcut(QKeySequence("Ctrl+Shift+7"))
        self.md_numbered_action.triggered.connect(self.markdown_numbered_list)

        self.md_task_action = QAction("Task List", self)
        self.md_task_action.triggered.connect(self.markdown_task_list)

        self.md_toggle_task_action = QAction("Toggle Task", self)
        self.md_toggle_task_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.md_toggle_task_action.triggered.connect(self.toggle_task_item)

        self.md_quote_action = QAction("Blockquote", self)
        self.md_quote_action.setShortcut(QKeySequence("Ctrl+Shift+Q"))
        self.md_quote_action.triggered.connect(self.markdown_blockquote)

        self.md_link_action = QAction("Link", self)
        self.md_link_action.setShortcut(QKeySequence("Ctrl+Shift+K"))
        self.md_link_action.triggered.connect(self.markdown_link)

        self.md_image_action = QAction("Image", self)
        self.md_image_action.triggered.connect(self.markdown_image)

        self.md_hr_action = QAction("Horizontal Rule", self)
        self.md_hr_action.triggered.connect(self.markdown_horizontal_rule)

        self.md_table_action = QAction("Table", self)
        self.md_table_action.triggered.connect(self.markdown_table)

        self.md_toggle_preview_action = QAction("Live Markdown Preview", self)
        self.md_toggle_preview_action.setCheckable(True)
        self.md_toggle_preview_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.md_toggle_preview_action.triggered.connect(self.toggle_markdown_preview)

        self.md_toolbar_visible_action = QAction("Show Markdown Toolbar", self)
        self.md_toolbar_visible_action.setCheckable(True)
        self.md_toolbar_visible_action.setChecked(bool(self.settings.get("show_markdown_toolbar", False)))
        self.md_toolbar_visible_action.triggered.connect(self.toggle_markdown_toolbar)

        self._apply_markdown_icons()
        self._apply_format_icons()

        # Help actions
        self.about_action = QAction("&About Notepad Clone", self)
        self.about_action.triggered.connect(self.show_about)
        self.user_guide_action = QAction("&User Guide...", self)
        self.user_guide_action.triggered.connect(self.show_user_guide)
        self.first_time_tutorial_action = QAction("First Time Tutorial", self)
        self.first_time_tutorial_action.triggered.connect(self.show_first_time_tutorial)
        self.check_updates_action = QAction("Check for &Updates...", self)
        self.check_updates_action.triggered.connect(lambda _checked=False: self.check_for_updates(manual=True))
        self.show_debug_logs_action = QAction("Show Debug Logs", self)
        self.show_debug_logs_action.triggered.connect(self.show_debug_logs)
        self.shortcut_mapper_action = QAction("Shortcut Mapper...", self)
        self.shortcut_mapper_action.triggered.connect(self.open_shortcut_mapper)
        self.plugin_manager_action = QAction("Plugin Manager...", self)
        self.plugin_manager_action.triggered.connect(self.open_plugin_manager)
        self.open_plugins_folder_action = QAction("Open Plugins Folder", self)
        self.open_plugins_folder_action.triggered.connect(self.open_plugins_folder)
        self.mime_tools_action = QAction("MIME Tools...", self)
        self.mime_tools_action.triggered.connect(self.open_mime_tools)
        self.converter_tools_action = QAction("Converter...", self)
        self.converter_tools_action.triggered.connect(self.open_converter_tools)
        self.npp_export_tools_action = QAction("NPP Export...", self)
        self.npp_export_tools_action.triggered.connect(self.open_npp_export_tools)

        self.minimap_action = QAction("Minimap", self)
        self.minimap_action.setCheckable(True)
        self.minimap_action.triggered.connect(self.toggle_minimap_panel)
        self.symbol_outline_action = QAction("Symbol Outline", self)
        self.symbol_outline_action.setCheckable(True)
        self.symbol_outline_action.triggered.connect(self.toggle_symbol_outline_panel)
        self.goto_definition_action = QAction("Go To Definition", self)
        self.goto_definition_action.setShortcut(QKeySequence("F12"))
        self.goto_definition_action.triggered.connect(self.goto_definition_basic)

        self.side_by_side_diff_action = QAction("Side-by-side Diff...", self)
        self.side_by_side_diff_action.triggered.connect(self.open_side_by_side_diff)
        self.three_way_merge_action = QAction("3-way Merge Helper...", self)
        self.three_way_merge_action.triggered.connect(self.open_three_way_merge)

        self.snippet_engine_action = QAction("Snippet Engine...", self)
        self.snippet_engine_action.triggered.connect(self.open_snippet_engine)
        self.template_packs_action = QAction("Install Shared Template Packs", self)
        self.template_packs_action.triggered.connect(self.install_template_packs)

        self.task_workflow_action = QAction("Task Workflow...", self)
        self.task_workflow_action.triggered.connect(self.show_task_workflow_panel)

        self.ai_file_citations_action = QAction("Ask About File (Citations)...", self)
        self.ai_file_citations_action.triggered.connect(self.ai_ask_file_with_citations)
        self.ai_commit_changelog_action = QAction("Generate Commit/Changelog Draft", self)
        self.ai_commit_changelog_action.triggered.connect(self.ai_commit_message_generator)
        self.ai_batch_refactor_action = QAction("Batch AI Refactor Preview...", self)
        self.ai_batch_refactor_action.triggered.connect(self.ai_batch_refactor_preview)

        self.backup_scheduler_action = QAction("Backup Scheduler...", self)
        self.backup_scheduler_action.triggered.connect(self.configure_backup_scheduler)
        self.backup_now_action = QAction("Run Backup Now", self)
        self.backup_now_action.triggered.connect(self.run_backup_now)
        self.diagnostics_bundle_action = QAction("Export Diagnostics Bundle...", self)
        self.diagnostics_bundle_action.triggered.connect(self.export_diagnostics_bundle)

        self.keyboard_only_mode_action = QAction("Keyboard-only Mode", self)
        self.keyboard_only_mode_action.setCheckable(True)
        self.keyboard_only_mode_action.setChecked(bool(self.settings.get("keyboard_only_mode", False)))
        self.keyboard_only_mode_action.triggered.connect(self.toggle_keyboard_only_mode)
        self.accessibility_high_contrast_action = QAction("Accessibility Preset: High Contrast", self)
        self.accessibility_high_contrast_action.triggered.connect(self.apply_accessibility_high_contrast)
        self.accessibility_dyslexic_action = QAction("Accessibility Preset: Dyslexic Font", self)
        self.accessibility_dyslexic_action.triggered.connect(self.apply_accessibility_dyslexic_font)

        self.lan_collaboration_action = QAction("LAN Collaboration...", self)
        self.lan_collaboration_action.triggered.connect(self.open_lan_collaboration)
        self.annotation_layer_action = QAction("Comment/Annotation Layer...", self)
        self.annotation_layer_action.triggered.connect(self.open_annotation_layer)

        if hasattr(self, "_capture_default_shortcuts"):
            self._capture_default_shortcuts()

    def _apply_markdown_icons(self) -> None:
        icon_map = {
            self.md_heading1_action: "md-heading",
            self.md_heading2_action: "md-heading",
            self.md_heading3_action: "md-heading",
            self.md_heading4_action: "md-heading",
            self.md_heading5_action: "md-heading",
            self.md_heading6_action: "md-heading",
            self.md_bold_action: "md-bold",
            self.md_italic_action: "md-italic",
            self.md_strike_action: "md-strike",
            self.md_inline_code_action: "md-inline-code",
            self.md_code_block_action: "md-code-block",
            self.md_bullet_action: "md-bullets",
            self.md_numbered_action: "md-numbers",
            self.md_task_action: "md-task",
            self.md_toggle_task_action: "md-task",
            self.md_quote_action: "md-quote",
            self.md_link_action: "md-link",
            self.md_image_action: "md-image",
            self.md_hr_action: "md-hr",
            self.md_table_action: "md-table",
            self.md_toggle_preview_action: "md-preview",
        }
        for action, icon_name in icon_map.items():
            action.setIcon(self._svg_icon(icon_name))

    def _apply_format_icons(self) -> None:
        icon_map = {
            self.bold_action: "format-bold",
            self.italic_action: "format-italic",
            self.underline_action: "format-underline",
            self.strikethrough_action: "format-strike",
        }
        for action, icon_name in icon_map.items():
            action.setIcon(self._svg_icon(icon_name))

    def _apply_main_toolbar_icons(self) -> None:
        fallback = self._standard_style_icon("SP_FileIcon")
        icon_cut = self._svg_icon("edit-cut")
        icon_copy = self._svg_icon("edit-copy")
        icon_paste = self._svg_icon("edit-paste")
        icon_undo = self._svg_icon("edit-undo")
        icon_redo = self._svg_icon("edit-redo")
        icon_new = self._svg_icon("document-new")
        icon_open = self._svg_icon("document-open")
        icon_save = self._svg_icon("document-save")
        icon_save_all = self._svg_icon("document-save-all")
        icon_print = self._svg_icon("document-print")
        icon_find = self._svg_icon("edit-find")
        icon_replace = self._svg_icon("edit-find-replace")
        icon_wrap = self._svg_icon("format-text-wrapping")
        icon_zoom_in = self._svg_icon("zoom-in")
        icon_zoom_out = self._svg_icon("zoom-out")
        icon_close_tab = self._svg_icon("tab-close")
        icon_full_screen = self._svg_icon("view-fullscreen")
        icon_macro_start = self._svg_icon("macro-record-start")
        icon_macro_stop = self._svg_icon("macro-record-stop")
        icon_macro_run_multi = self._svg_icon("macro-run-multi")
        icon_macro_save = self._svg_icon("macro-save")
        icon_ai_chat = self._svg_icon("ai-sparkles")
        icon_sync_v = self._svg_icon("sync-vertical")
        icon_sync_h = self._svg_icon("sync-horizontal")
        icon_doc_map = self._svg_icon("document-map")
        icon_doc_list = self._svg_icon("document-list")
        icon_func_list = self._svg_icon("function-list")
        icon_define_lang = self._svg_icon("language-define")
        icon_tail = self._svg_icon("tail-follow")
        icon_show_all_chars = self._svg_icon("show-all-chars")
        icon_indent_guide = self._svg_icon("indent-guide")
        icon_map = {
            self.new_action: ("document-new", icon_new if not icon_new.isNull() else fallback),
            self.open_action: ("document-open", icon_open if not icon_open.isNull() else self._standard_style_icon("SP_DialogOpenButton")),
            self.save_action: ("document-save", icon_save if not icon_save.isNull() else self._standard_style_icon("SP_DialogSaveButton")),
            self.save_all_action: ("document-save-all", icon_save_all if not icon_save_all.isNull() else self._standard_style_icon("SP_DialogSaveButton")),
            self.close_tab_action: ("window-close", icon_close_tab if not icon_close_tab.isNull() else self._standard_style_icon("SP_DialogCloseButton")),
            self.close_all_action: ("edit-delete", self._standard_style_icon("SP_TrashIcon")),
            self.print_action: ("document-print", icon_print if not icon_print.isNull() else fallback),
            self.cut_action: ("edit-cut", icon_cut if not icon_cut.isNull() else fallback),
            self.copy_action: ("edit-copy", icon_copy if not icon_copy.isNull() else fallback),
            self.paste_action: ("edit-paste", icon_paste if not icon_paste.isNull() else fallback),
            self.undo_action: ("edit-undo", icon_undo if not icon_undo.isNull() else fallback),
            self.redo_action: ("edit-redo", icon_redo if not icon_redo.isNull() else fallback),
            self.find_action: ("edit-find", icon_find if not icon_find.isNull() else fallback),
            self.replace_action: ("edit-find-replace", icon_replace if not icon_replace.isNull() else fallback),
            self.start_macro_recording_action: ("macro-record-start", icon_macro_start if not icon_macro_start.isNull() else fallback),
            self.stop_macro_recording_action: ("macro-record-stop", icon_macro_stop if not icon_macro_stop.isNull() else fallback),
            self.run_macro_multiple_times_action: ("macro-run-multi", icon_macro_run_multi if not icon_macro_run_multi.isNull() else fallback),
            self.save_current_macro_action: ("macro-save", icon_macro_save if not icon_macro_save.isNull() else fallback),
            self.ai_chat_panel_action: ("ai-sparkles", icon_ai_chat if not icon_ai_chat.isNull() else fallback),
            self.zoom_in_action: ("zoom-in", icon_zoom_in if not icon_zoom_in.isNull() else fallback),
            self.zoom_out_action: ("zoom-out", icon_zoom_out if not icon_zoom_out.isNull() else fallback),
            self.word_wrap_action: ("format-text-wrapping", icon_wrap if not icon_wrap.isNull() else fallback),
            self.show_all_chars_action: ("show-all-chars", icon_show_all_chars if not icon_show_all_chars.isNull() else fallback),
            self.show_indent_guide_action: ("indent-guide", icon_indent_guide if not icon_indent_guide.isNull() else fallback),
            self.sync_vertical_action: ("sync-vertical", icon_sync_v if not icon_sync_v.isNull() else fallback),
            self.sync_horizontal_action: ("sync-horizontal", icon_sync_h if not icon_sync_h.isNull() else fallback),
            self.document_map_action: ("document-map", icon_doc_map if not icon_doc_map.isNull() else fallback),
            self.document_list_action: ("document-list", icon_doc_list if not icon_doc_list.isNull() else fallback),
            self.function_list_action: ("function-list", icon_func_list if not icon_func_list.isNull() else fallback),
            self.define_language_action: ("language-define", icon_define_lang if not icon_define_lang.isNull() else fallback),
            self.monitor_tail_action: ("tail-follow", icon_tail if not icon_tail.isNull() else fallback),
            self.full_screen_action: ("view-fullscreen", icon_full_screen if not icon_full_screen.isNull() else self._standard_style_icon("SP_TitleBarMaxButton")),
        }
        # Use deterministic in-app fallbacks for consistent contrast across platforms/styles.
        for action, (_theme_name, fallback_icon) in icon_map.items():
            action.setIcon(fallback_icon)

    def _update_main_toolbar_overflow(self) -> None:
        toolbar = getattr(self, "main_toolbar", None)
        overflow_button = getattr(self, "main_toolbar_overflow_button", None)
        overflow_menu = getattr(self, "main_toolbar_overflow_menu", None)
        if toolbar is None or overflow_button is None or overflow_menu is None:
            return
        if overflow_menu.isVisible():
            self._main_toolbar_overflow_update_pending = True
            return

        managed: list[QAction] = []
        for action in toolbar.actions():
            try:
                _ = action.isSeparator()
            except RuntimeError:
                continue
            managed.append(action)
        if not managed:
            overflow_button.setVisible(False)
            overflow_menu.clear()
            return

        def _apply_layout(available_width: int) -> list[QAction]:
            used = 0
            hidden: list[QAction] = []
            for action in managed:
                try:
                    is_separator = action.isSeparator()
                except RuntimeError:
                    continue
                if is_separator:
                    action.setVisible(True)
                    widget = toolbar.widgetForAction(action)
                    if widget is not None:
                        used += max(0, widget.sizeHint().width())
                    continue
                widget = toolbar.widgetForAction(action)
                if widget is None:
                    hidden.append(action)
                    continue
                needed = max(0, widget.sizeHint().width())
                if used + needed <= available_width:
                    action.setVisible(True)
                    used += needed
                else:
                    action.setVisible(False)
                    hidden.append(action)

            # Trim separators that have no visible action on one or both sides.
            for idx, action in enumerate(managed):
                try:
                    is_separator = action.isSeparator()
                except RuntimeError:
                    continue
                if not is_separator:
                    continue
                prev_visible = False
                for j in range(idx - 1, -1, -1):
                    candidate = managed[j]
                    try:
                        if candidate.isSeparator():
                            continue
                    except RuntimeError:
                        continue
                    prev_visible = candidate.isVisible()
                    break
                next_visible = False
                for j in range(idx + 1, len(managed)):
                    candidate = managed[j]
                    try:
                        if candidate.isSeparator():
                            continue
                    except RuntimeError:
                        continue
                    next_visible = candidate.isVisible()
                    break
                action.setVisible(prev_visible and next_visible)
            return hidden

        full_width = max(0, toolbar.width() - 8)
        for action in managed:
            action.setVisible(True)
        hidden = _apply_layout(full_width)
        if hidden:
            reserve = max(24, overflow_button.sizeHint().width() + 8)
            hidden = _apply_layout(max(0, full_width - reserve))

        overflow_menu.clear()
        for action in hidden:
            try:
                if action.isSeparator():
                    continue
            except RuntimeError:
                continue
            try:
                label = action.text().strip()
            except RuntimeError:
                continue
            if not label:
                continue
            proxy = overflow_menu.addAction(action.icon(), label)
            try:
                proxy.setEnabled(action.isEnabled())
                proxy.setCheckable(action.isCheckable())
                if action.isCheckable():
                    proxy.setChecked(action.isChecked())
            except RuntimeError:
                overflow_menu.removeAction(proxy)
                continue
            proxy.triggered.connect(
                lambda checked=False, source_action=action: source_action.trigger()
            )
        overflow_button.setVisible(bool(overflow_menu.actions()))
        self._position_main_toolbar_overflow_button()

    def create_menus(self: Any) -> None:
        menu_bar = self.menuBar()

        # File
        self.file_menu = menu_bar.addMenu("&File")
        self.file_menu.addAction(self.new_action)
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction(self.save_as_action)
        self.file_menu.addAction(self.rename_action)
        self.file_menu.addAction(self.move_recycle_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.close_tab_action)
        self.file_menu.addAction(self.close_all_action)
        close_multi_menu = self.file_menu.addMenu("Close Multiple Documents")
        close_multi_menu.addAction(self.close_all_but_active_action)
        close_multi_menu.addAction(self.close_all_but_pinned_action)
        close_multi_menu.addAction(self.close_all_left_action)
        close_multi_menu.addAction(self.close_all_right_action)
        close_multi_menu.addAction(self.close_all_unchanged_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.print_action)
        self.file_menu.addAction(self.print_preview_action)
        self.file_menu.addAction(self.version_history_action)
        self.file_menu.addAction(self.pin_tab_action)
        self.file_menu.addAction(self.favorite_tab_action)
        self.file_menu.addAction(self.edit_tags_action)
        self.file_menu.addSeparator()
        self.templates_menu = self.file_menu.addMenu("Templates")
        self.templates_menu.addAction(self.new_from_meeting_template_action)
        self.templates_menu.addAction(self.new_from_daily_template_action)
        self.templates_menu.addAction(self.new_from_checklist_template_action)
        self.templates_menu.addSeparator()
        self.templates_menu.addAction(self.insert_meeting_template_action)
        self.templates_menu.addAction(self.insert_daily_template_action)
        self.templates_menu.addAction(self.insert_checklist_template_action)
        self.export_menu = self.file_menu.addMenu("Export")
        self.export_menu.addAction(self.export_pdf_action)
        self.export_menu.addAction(self.export_markdown_action)
        self.export_menu.addAction(self.export_html_action)
        self.encoding_menu = self.file_menu.addMenu("Encoding")
        self.encoding_menu.addAction(self.encoding_utf8_action)
        self.encoding_menu.addAction(self.encoding_utf16_action)
        self.encoding_menu.addAction(self.encoding_ansi_action)
        self.eol_menu = self.file_menu.addMenu("EOL")
        self.eol_menu.addAction(self.eol_lf_action)
        self.eol_menu.addAction(self.eol_crlf_action)
        self.workspace_menu = self.file_menu.addMenu("Workspace")
        self.workspace_menu.addAction(self.open_workspace_action)
        self.workspace_menu.addAction(self.workspace_files_action)
        self.workspace_menu.addAction(self.workspace_search_action)
        self.session_menu = self.file_menu.addMenu("Session")
        self.session_menu.addAction(self.save_session_action)
        self.session_menu.addAction(self.save_session_as_action)
        self.session_menu.addAction(self.load_session_action)
        self.security_menu = self.file_menu.addMenu("Security")
        self.security_menu.addAction(self.encrypt_note_action)
        self.security_menu.addAction(self.decrypt_note_action)
        self.security_menu.addAction(self.change_note_password_action)
        self.ai_menu = self.file_menu.addMenu("AI")
        self.ai_menu.addAction(self.ask_ai_action)
        self.ai_menu.addAction(self.ai_chat_panel_action)
        self.ai_menu.addAction(self.explain_selection_ai_action)
        self.ai_menu.addSeparator()
        self.ai_menu.addAction(self.ai_rewrite_shorten_action)
        self.ai_menu.addAction(self.ai_rewrite_formal_action)
        self.ai_menu.addAction(self.ai_rewrite_grammar_action)
        self.ai_menu.addAction(self.ai_rewrite_summarize_action)
        self.ai_menu.addSeparator()
        self.ai_menu.addAction(self.ai_ask_context_action)
        self.ai_menu.addAction(self.ai_run_template_action)
        self.ai_menu.addAction(self.ai_save_template_action)
        self.ai_menu.addSeparator()
        self.ai_menu.addAction(self.ai_usage_summary_action)
        self.ai_menu.addAction(self.ai_action_history_action)
        self.ai_menu.addAction(self.ai_private_mode_action)
        self.ai_menu.addSeparator()
        self.ai_menu.addAction(self.ai_file_citations_action)
        self.ai_menu.addAction(self.ai_commit_changelog_action)
        self.ai_menu.addAction(self.ai_batch_refactor_action)
        self.recent_files_menu = self.file_menu.addMenu("Recent Files")
        self._refresh_recent_files_menu()
        self.favorite_files_menu = self.file_menu.addMenu("Favorite Files")
        self._refresh_favorite_files_menu()
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        # Edit
        self.edit_menu = menu_bar.addMenu("&Edit")
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.cut_action)
        self.edit_menu.addAction(self.copy_action)
        self.edit_menu.addAction(self.paste_action)
        self.edit_menu.addAction(self.delete_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.insert_media_action)
        self.edit_menu.addAction(self.reminders_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.select_all_action)
        self.edit_menu.addAction(self.time_date_action)

        # Search
        self.search_menu = menu_bar.addMenu("&Search")
        self.search_menu.addAction(self.find_action)
        self.search_menu.addAction(self.find_in_files_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.find_next_action)
        self.search_menu.addAction(self.find_prev_action)
        self.search_menu.addAction(self.select_find_next_action)
        self.search_menu.addAction(self.select_find_prev_action)
        self.search_menu.addAction(self.find_volatile_next_action)
        self.search_menu.addAction(self.find_volatile_prev_action)
        self.search_menu.addAction(self.replace_action)
        self.search_menu.addAction(self.replace_in_files_action)
        self.search_menu.addAction(self.search_bing_action)
        self.search_menu.addAction(self.incremental_search_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.search_results_window_action)
        self.search_menu.addAction(self.next_search_result_action)
        self.search_menu.addAction(self.prev_search_result_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.goto_line_action)
        self.search_menu.addAction(self.goto_matching_brace_action)
        self.search_menu.addAction(self.select_in_between_braces_action)
        self.search_menu.addAction(self.mark_action)
        self.search_menu.addSeparator()
        change_history_menu = self.search_menu.addMenu("Change History")
        change_history_menu.addAction(self.change_history_next_action)
        change_history_menu.addAction(self.change_history_prev_action)
        change_history_menu.addAction(self.change_history_clear_action)
        style_all_menu = self.search_menu.addMenu("Style All Occurrences of Token")
        style_all_menu.addAction(self.style_all_1_action)
        style_all_menu.addAction(self.style_all_2_action)
        style_all_menu.addAction(self.style_all_3_action)
        style_all_menu.addAction(self.style_all_4_action)
        style_all_menu.addAction(self.style_all_5_action)
        style_all_menu.addAction(self.style_all_find_action)
        style_one_menu = self.search_menu.addMenu("Style One Token")
        style_one_menu.addAction(self.style_one_1_action)
        style_one_menu.addAction(self.style_one_2_action)
        style_one_menu.addAction(self.style_one_3_action)
        style_one_menu.addAction(self.style_one_4_action)
        style_one_menu.addAction(self.style_one_5_action)
        style_one_menu.addAction(self.style_one_find_action)
        clear_style_menu = self.search_menu.addMenu("Clear Style")
        clear_style_menu.addAction(self.clear_style_1_action)
        clear_style_menu.addAction(self.clear_style_2_action)
        clear_style_menu.addAction(self.clear_style_3_action)
        clear_style_menu.addAction(self.clear_style_4_action)
        clear_style_menu.addAction(self.clear_style_5_action)
        clear_style_menu.addAction(self.clear_style_all_action)
        self.search_menu.addAction(self.jump_up_action)
        self.search_menu.addAction(self.jump_down_action)
        copy_styled_menu = self.search_menu.addMenu("Copy Styled Text")
        copy_styled_menu.addAction(self.copy_styled_1_action)
        copy_styled_menu.addAction(self.copy_styled_2_action)
        copy_styled_menu.addAction(self.copy_styled_3_action)
        copy_styled_menu.addAction(self.copy_styled_4_action)
        copy_styled_menu.addAction(self.copy_styled_5_action)
        copy_styled_menu.addAction(self.copy_styled_all_action)
        self.search_menu.addSeparator()
        bookmark_menu = self.search_menu.addMenu("Bookmark")
        bookmark_menu.addAction(self.toggle_bookmark_action)
        bookmark_menu.addAction(self.next_bookmark_action)
        bookmark_menu.addAction(self.prev_bookmark_action)
        bookmark_menu.addAction(self.clear_bookmarks_action)
        bookmark_menu.addSeparator()
        bookmark_menu.addAction(self.cut_bookmarked_lines_action)
        bookmark_menu.addAction(self.copy_bookmarked_lines_action)
        bookmark_menu.addAction(self.paste_replace_bookmarked_lines_action)
        bookmark_menu.addAction(self.remove_bookmarked_lines_action)
        bookmark_menu.addAction(self.remove_non_bookmarked_lines_action)
        bookmark_menu.addAction(self.inverse_bookmarks_action)
        self.search_menu.addSeparator()
        self.search_menu.addAction(self.find_chars_in_range_action)

        # Format
        self.format_menu = menu_bar.addMenu("F&ormat")
        self.format_menu.addAction(self.bold_action)
        self.format_menu.addAction(self.italic_action)
        self.format_menu.addAction(self.underline_action)
        self.format_menu.addAction(self.strikethrough_action)
        self.format_menu.addSeparator()
        self.format_menu.addAction(self.word_wrap_action)
        self.format_menu.addAction(self.font_action)

        # View
        self.view_menu = menu_bar.addMenu("&View")
        self.view_menu.addAction(self.always_on_top_action)
        self.view_menu.addAction(self.full_screen_action)
        self.view_menu.addAction(self.post_it_action)
        self.view_menu.addAction(self.distraction_free_action)
        self.view_menu.addSeparator()
        view_current_file_menu = self.view_menu.addMenu("View Current File in")
        view_current_file_menu.addAction(self.view_file_explorer_action)
        view_current_file_menu.addAction(self.view_file_default_action)
        view_current_file_menu.addAction(self.view_file_cmd_action)
        show_symbol_menu = self.view_menu.addMenu("Show Symbol")
        show_symbol_menu.addAction(self.show_space_tab_action)
        show_symbol_menu.addAction(self.show_end_of_line_action)
        show_symbol_menu.addAction(self.show_non_printing_action)
        show_symbol_menu.addAction(self.show_control_unicode_eol_action)
        show_symbol_menu.addAction(self.show_all_chars_action)
        show_symbol_menu.addSeparator()
        show_symbol_menu.addAction(self.show_indent_guide_action)
        show_symbol_menu.addAction(self.show_wrap_symbol_action)
        zoom_menu = self.view_menu.addMenu("&Zoom")
        zoom_menu.addAction(self.zoom_in_action)
        zoom_menu.addAction(self.zoom_out_action)
        zoom_menu.addSeparator()
        zoom_menu.addAction(self.zoom_reset_action)
        move_clone_menu = self.view_menu.addMenu("Move/Clone Current Document")
        move_clone_menu.addAction(self.clone_view_action)
        move_clone_menu.addAction(self.split_vertical_action)
        move_clone_menu.addAction(self.split_horizontal_action)
        move_clone_menu.addAction(self.split_close_action)
        self.view_menu.addAction(self.word_wrap_action)
        self.view_menu.addAction(self.focus_other_view_action)
        self.view_menu.addAction(self.hide_lines_action)
        self.view_menu.addAction(self.show_hidden_lines_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.fold_all_action)
        self.view_menu.addAction(self.unfold_all_action)
        self.view_menu.addAction(self.fold_current_level_action)
        self.view_menu.addAction(self.unfold_current_level_action)
        fold_level_menu = self.view_menu.addMenu("Fold Level")
        for action in self.fold_level_actions:
            fold_level_menu.addAction(action)
        unfold_level_menu = self.view_menu.addMenu("Unfold Level")
        for action in self.unfold_level_actions:
            unfold_level_menu.addAction(action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.summary_action)
        self.view_menu.addSeparator()
        project_panels_menu = self.view_menu.addMenu("Project Panels")
        project_panels_menu.addAction(self.document_map_action)
        project_panels_menu.addAction(self.document_list_action)
        project_panels_menu.addAction(self.function_list_action)
        project_panels_menu.addSeparator()
        project_panels_menu.addAction(self.minimap_action)
        project_panels_menu.addAction(self.symbol_outline_action)
        self.view_menu.addAction(self.define_language_action)
        self.view_menu.addAction(self.open_workspace_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.sync_vertical_action)
        self.view_menu.addAction(self.sync_horizontal_action)
        self.view_menu.addAction(self.monitor_tail_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.text_direction_rtl_action)
        self.view_menu.addAction(self.text_direction_ltr_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.ai_chat_panel_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.status_bar_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.focus_mode_action)
        self.view_menu.addAction(self.column_mode_action)
        self.view_menu.addAction(self.multi_caret_action)
        self.view_menu.addAction(self.code_folding_action)
        self.view_menu.addSeparator()
        self.view_menu.addAction(self.keyboard_only_mode_action)

        # Settings
        self.settings_menu = menu_bar.addMenu("&Settings")
        self.settings_menu.addAction(self.settings_action)
        self.settings_menu.addAction(self.shortcut_mapper_action)
        self.settings_menu.addAction(self.command_palette_action)
        self.settings_menu.addAction(self.simple_mode_action)
        self.ui_presets_menu = self.settings_menu.addMenu("UI Presets")
        self.ui_presets_menu.addAction(self.preset_reading_action)
        self.ui_presets_menu.addAction(self.preset_coding_action)
        self.ui_presets_menu.addAction(self.preset_focus_action)
        self.accessibility_menu = self.settings_menu.addMenu("Accessibility")
        self.accessibility_menu.addAction(self.accessibility_high_contrast_action)
        self.accessibility_menu.addAction(self.accessibility_dyslexic_action)

        self.tools_menu = menu_bar.addMenu("&Tools")
        self.tools_menu.addAction(self.goto_definition_action)
        self.tools_menu.addAction(self.side_by_side_diff_action)
        self.tools_menu.addAction(self.three_way_merge_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.snippet_engine_action)
        self.tools_menu.addAction(self.template_packs_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.task_workflow_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.backup_scheduler_action)
        self.tools_menu.addAction(self.backup_now_action)
        self.tools_menu.addAction(self.diagnostics_bundle_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.lan_collaboration_action)
        self.tools_menu.addAction(self.annotation_layer_action)

        # Macros
        self.macros_menu = menu_bar.addMenu("&Macro")
        self.macros_menu.addAction(self.start_macro_recording_action)
        self.macros_menu.addAction(self.stop_macro_recording_action)
        self.macros_menu.addAction(self.play_macro_action)
        self.macros_menu.addAction(self.save_current_macro_action)
        self.macros_menu.addSeparator()
        self.macros_menu.addAction(self.run_macro_multiple_times_action)
        self.macros_menu.addSeparator()
        self.macros_menu.addAction(self.trim_trailing_spaces_and_save_action)
        self.macros_menu.addSeparator()
        self.macros_menu.addAction(self.modify_macro_shortcut_delete_action)
        self.macros_menu.aboutToShow.connect(self._sync_saved_macro_actions)
        self._sync_saved_macro_actions()

        # Markdown
        self.markdown_menu = menu_bar.addMenu("&Markdown")
        headings_menu = self.markdown_menu.addMenu("&Headings")
        headings_menu.addAction(self.md_heading1_action)
        headings_menu.addAction(self.md_heading2_action)
        headings_menu.addAction(self.md_heading3_action)
        headings_menu.addAction(self.md_heading4_action)
        headings_menu.addAction(self.md_heading5_action)
        headings_menu.addAction(self.md_heading6_action)

        self.markdown_menu.addAction(self.md_bold_action)
        self.markdown_menu.addAction(self.md_italic_action)
        self.markdown_menu.addAction(self.md_strike_action)
        self.markdown_menu.addAction(self.md_inline_code_action)
        self.markdown_menu.addAction(self.md_code_block_action)
        self.markdown_menu.addSeparator()
        self.markdown_menu.addAction(self.md_bullet_action)
        self.markdown_menu.addAction(self.md_numbered_action)
        self.markdown_menu.addAction(self.md_task_action)
        self.markdown_menu.addAction(self.md_toggle_task_action)
        self.markdown_menu.addAction(self.md_quote_action)
        self.markdown_menu.addSeparator()
        self.markdown_menu.addAction(self.md_link_action)
        self.markdown_menu.addAction(self.md_image_action)
        self.markdown_menu.addAction(self.md_table_action)
        self.markdown_menu.addAction(self.md_hr_action)
        self.markdown_menu.addSeparator()
        self.markdown_menu.addAction(self.md_toggle_preview_action)
        self.markdown_menu.addAction(self.md_toolbar_visible_action)

        # Plugins
        self.plugins_menu = menu_bar.addMenu("&Plugins")
        self.plugins_menu.addAction(self.plugin_manager_action)
        self.plugins_menu.addAction(self.open_plugins_folder_action)
        self.plugins_menu.addSeparator()
        self.plugins_menu.addAction(self.mime_tools_action)
        self.plugins_menu.addAction(self.converter_tools_action)
        self.plugins_menu.addAction(self.npp_export_tools_action)

        # Window
        self.window_menu = menu_bar.addMenu("&Window")
        sort_by_menu = self.window_menu.addMenu("Sort By")
        sort_by_menu.addAction(self.window_sort_name_asc_action)
        sort_by_menu.addAction(self.window_sort_name_desc_action)
        sort_by_menu.addAction(self.window_sort_path_asc_action)
        sort_by_menu.addAction(self.window_sort_path_desc_action)
        sort_by_menu.addAction(self.window_sort_type_asc_action)
        sort_by_menu.addAction(self.window_sort_type_desc_action)
        sort_by_menu.addAction(self.window_sort_len_asc_action)
        sort_by_menu.addAction(self.window_sort_len_desc_action)
        sort_by_menu.addAction(self.window_sort_modified_asc_action)
        sort_by_menu.addAction(self.window_sort_modified_desc_action)
        self.window_menu.addAction(self.windows_manager_action)
        self.window_tabs_separator = self.window_menu.addSeparator()
        self._refresh_window_menu_entries()

        # Help
        self.help_menu = menu_bar.addMenu("&Help")
        self.help_menu.addAction(self.user_guide_action)
        self.help_menu.addAction(self.first_time_tutorial_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.check_updates_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.show_debug_logs_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_action)

    def create_toolbars(self: Any) -> None:
        main_toolbar = QToolBar("Main", self)
        main_toolbar.setMovable(False)
        self.main_toolbar = main_toolbar

        # 1) Cut/Copy/Paste
        for action in (
            self.cut_action,
            self.copy_action,
            self.paste_action,
        ):
            main_toolbar.addAction(action)
        main_toolbar.addSeparator()

        # 2) Undo/Redo
        for action in (
            self.undo_action,
            self.redo_action,
        ):
            main_toolbar.addAction(action)
        main_toolbar.addSeparator()

        # 3) Find/Replace + AI
        for action in (
            self.find_action,
            self.replace_action,
            self.ai_chat_panel_action,
        ):
            main_toolbar.addAction(action)
        main_toolbar.addSeparator()

        # 4) Remaining tools (non-macro)
        symbol_menu = QMenu(main_toolbar)
        symbol_menu.addAction(self.show_space_tab_action)
        symbol_menu.addAction(self.show_end_of_line_action)
        symbol_menu.addAction(self.show_non_printing_action)
        symbol_menu.addAction(self.show_control_unicode_eol_action)
        symbol_menu.addAction(self.show_all_chars_action)
        symbol_menu.addSeparator()
        symbol_menu.addAction(self.show_indent_guide_action)
        symbol_menu.addAction(self.show_wrap_symbol_action)
        self.show_symbol_toolbar_button = QToolButton(main_toolbar)
        self.show_symbol_toolbar_button.setText("Symbols")
        self.show_symbol_toolbar_button.setToolTip("Show All Characters options")
        self.show_symbol_toolbar_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.show_symbol_toolbar_button.setMenu(symbol_menu)
        self.show_symbol_toolbar_button.setIcon(self._svg_icon("show-symbol"))
        self.show_symbol_toolbar_action = main_toolbar.addWidget(self.show_symbol_toolbar_button)
        self.show_symbol_toolbar_action.setText("Show Symbol Options")
        main_toolbar.addSeparator()
        for action in (
            self.new_action,
            self.open_action,
            self.save_action,
            self.save_all_action,
            self.close_tab_action,
            self.print_action,
            self.full_screen_action,
            self.zoom_in_action,
            self.zoom_out_action,
            self.word_wrap_action,
            self.show_all_chars_action,
            self.show_indent_guide_action,
            self.sync_vertical_action,
            self.sync_horizontal_action,
            self.document_map_action,
            self.document_list_action,
            self.function_list_action,
            self.define_language_action,
            self.monitor_tail_action,
        ):
            main_toolbar.addAction(action)
        main_toolbar.addSeparator()

        # Macros last
        for action in (
            self.start_macro_recording_action,
            self.stop_macro_recording_action,
            self.run_macro_multiple_times_action,
            self.save_current_macro_action,
        ):
            main_toolbar.addAction(action)

        self.main_toolbar_overflow_menu = QMenu(main_toolbar)
        self.main_toolbar_overflow_button = QToolButton(main_toolbar)
        self.main_toolbar_overflow_button.setText(">>")
        self.main_toolbar_overflow_button.setToolTip("More tools")
        self.main_toolbar_overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.main_toolbar_overflow_button.setMenu(self.main_toolbar_overflow_menu)
        self._main_toolbar_overflow_menu_open = False
        self._main_toolbar_overflow_update_pending = False
        self._main_toolbar_overflow_update_scheduled = False
        self.main_toolbar_overflow_menu.aboutToShow.connect(self._on_main_toolbar_overflow_menu_show)
        self.main_toolbar_overflow_menu.aboutToHide.connect(self._on_main_toolbar_overflow_menu_hide)
        self.main_toolbar_overflow_button.hide()
        main_toolbar.installEventFilter(self)
        self._schedule_main_toolbar_overflow_update()

        markdown_toolbar = QToolBar("Markdown", self)
        markdown_toolbar.setMovable(False)
        self.markdown_toolbar = markdown_toolbar
        show_md_toolbar = bool(self.settings.get("show_markdown_toolbar", False))
        self.md_toolbar_visible_action.blockSignals(True)
        self.md_toolbar_visible_action.setChecked(show_md_toolbar)
        self.md_toolbar_visible_action.blockSignals(False)

        markdown_toolbar.addAction(self.bold_action)
        markdown_toolbar.addAction(self.italic_action)
        markdown_toolbar.addAction(self.underline_action)
        markdown_toolbar.addAction(self.strikethrough_action)
        markdown_toolbar.addSeparator()
        markdown_toolbar.addAction(self.md_heading1_action)
        markdown_toolbar.addAction(self.md_heading2_action)
        markdown_toolbar.addAction(self.md_heading3_action)
        markdown_toolbar.addSeparator()
        markdown_toolbar.addAction(self.md_bullet_action)
        markdown_toolbar.addAction(self.md_numbered_action)
        markdown_toolbar.addAction(self.md_toggle_task_action)
        markdown_toolbar.addAction(self.md_quote_action)
        markdown_toolbar.addSeparator()
        markdown_toolbar.addAction(self.md_inline_code_action)
        markdown_toolbar.addAction(self.md_code_block_action)
        markdown_toolbar.addAction(self.md_link_action)
        markdown_toolbar.addSeparator()
        markdown_toolbar.addAction(self.md_toggle_preview_action)

        self.search_toolbar = QToolBar("Search", self)
        self.search_toolbar.setMovable(False)
        show_find_panel = bool(self.settings.get("show_find_panel", False))
        self.search_panel_action.blockSignals(True)
        self.search_panel_action.setChecked(show_find_panel)
        self.search_panel_action.blockSignals(False)

        self.search_input = QLineEdit(self.search_toolbar)
        self.search_input.setPlaceholderText("Find text...")
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_toolbar.addWidget(QLabel("Find:", self.search_toolbar))
        self.search_toolbar.addWidget(self.search_input)

        self.search_highlight_checkbox = QCheckBox("Highlight all", self.search_toolbar)
        self.search_highlight_checkbox.setChecked(True)
        self.search_highlight_checkbox.toggled.connect(self._on_search_text_changed)
        self.search_toolbar.addWidget(self.search_highlight_checkbox)

        self.search_case_checkbox = QCheckBox("Match case", self.search_toolbar)
        self.search_case_checkbox.setChecked(False)
        self.search_case_checkbox.toggled.connect(self._on_search_text_changed)
        self.search_toolbar.addWidget(self.search_case_checkbox)

        self.search_prev_btn = QPushButton("Previous", self.search_toolbar)
        self.search_prev_btn.clicked.connect(self.edit_find_previous)
        self.search_toolbar.addWidget(self.search_prev_btn)

        self.search_next_btn = QPushButton("Next", self.search_toolbar)
        self.search_next_btn.clicked.connect(self.edit_find_next)
        self.search_toolbar.addWidget(self.search_next_btn)

        self.search_close_btn = QPushButton("Close", self.search_toolbar)
        self.search_close_btn.clicked.connect(self.hide_search_panel)
        self.search_toolbar.addWidget(self.search_close_btn)

        self._layout_top_toolbars()

    def _layout_top_toolbars(self) -> None:
        main_toolbar = getattr(self, "main_toolbar", None)
        markdown_toolbar = getattr(self, "markdown_toolbar", None)
        search_toolbar = getattr(self, "search_toolbar", None)
        if main_toolbar is None:
            return

        # Rebuild toolbar rows to avoid empty rows left by previous breaks.
        for toolbar in (search_toolbar, markdown_toolbar, main_toolbar):
            if toolbar is not None:
                self.removeToolBar(toolbar)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, main_toolbar)
        show_main_toolbar = bool(self.settings.get("show_main_toolbar", True))
        main_toolbar.setVisible(show_main_toolbar)
        if show_main_toolbar:
            self._schedule_main_toolbar_overflow_update()

        show_md_toolbar = bool(self.settings.get("show_markdown_toolbar", False))
        if markdown_toolbar is not None:
            markdown_toolbar.setVisible(show_md_toolbar)
            if show_md_toolbar:
                self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, markdown_toolbar)

        show_find_panel = bool(self.settings.get("show_find_panel", False))
        if search_toolbar is not None:
            search_toolbar.setVisible(show_find_panel)
            if show_find_panel:
                self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, search_toolbar)

