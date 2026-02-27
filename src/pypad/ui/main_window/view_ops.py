from __future__ import annotations
import getpass
import base64
import hashlib
import json
import os
import random
import subprocess
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
from pypad.app_settings.scintilla_profile import ScintillaProfile
from pypad.ui.editor.editor_widget import EditorWidget
from pypad.ui.ai.ai_controller import AIController
from pypad.ui.theme.asset_paths import resolve_asset_path
from pypad.ui.system.autosave import AutoSaveRecoveryDialog, AutoSaveStore
from pypad.ui.system.reminders import ReminderStore, RemindersDialog
from pypad.ui.security.security_controller import SecurityController
from pypad.ui.editor.syntax_highlighter import CodeSyntaxHighlighter
from pypad.ui.system.updater_controller import UpdaterController
from pypad.ui.system.version_history import VersionHistoryDialog
from pypad.ui.workspace.workspace_controller import WorkspaceController
from pypad.ui.theme.theme_tokens import build_dialog_theme_qss_from_tokens, build_tokens_from_settings, build_tool_dialog_qss
from pypad.ui.document.document_authoring import (
    PageLayoutConfig,
    PageLayoutDialog,
    apply_style_to_text,
    build_markdown_toc,
    build_ruler_text,
    extract_markdown_headings,
)
from pypad.ui.document.document_review import (
    accept_all_changes,
    accept_or_reject_change_at_cursor,
    add_comment,
    extract_heading_targets,
    has_tracked_changes,
    insert_cross_reference as insert_cross_reference_link,
    insert_note,
    insert_tracked_insertion,
    list_comments,
    mark_tracked_deletion,
    next_change_span,
    reject_all_changes,
    remove_comment,
)



class ViewOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    # ---------- Format / View ----------
    def toggle_markdown_toolbar(self, checked: bool) -> None:
        toolbar = getattr(self, "markdown_toolbar", None)
        if toolbar is None:
            return
        toolbar.setVisible(checked)
        self.settings["show_markdown_toolbar"] = bool(checked)
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        if hasattr(self, "_layout_top_toolbars"):
            self._layout_top_toolbars()

    def toggle_full_screen(self, checked: bool) -> None:
        if checked and getattr(self, "_print_view_enabled", False) and hasattr(self, "toggle_print_view"):
            self.toggle_print_view(False)
        if checked:
            self.showFullScreen()
        else:
            self.showNormal()
        if hasattr(self, "full_screen_action"):
            self.full_screen_action.blockSignals(True)
            self.full_screen_action.setChecked(bool(self.isFullScreen()))
            self.full_screen_action.blockSignals(False)

    def toggle_always_on_top(self, checked: bool) -> None:
        self.settings["always_on_top"] = bool(checked)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(checked))
        self.show()
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message("Always on top enabled." if checked else "Always on top disabled.", 2500)

    def toggle_post_it_mode(self, checked: bool) -> None:
        self.settings["post_it_mode"] = bool(checked)
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        if checked:
            if not hasattr(self, "_post_it_prev_geometry"):
                self._post_it_prev_geometry = self.geometry()
            self.setWindowFlag(Qt.Tool, True)
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.showNormal()
            self.resize(420, 320)
            self.show()
            self.show_status_message("Post-it mode enabled.", 2500)
            return
        self.setWindowFlag(Qt.Tool, False)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings.get("always_on_top", False)))
        self.showNormal()
        if hasattr(self, "_post_it_prev_geometry"):
            try:
                self.setGeometry(self._post_it_prev_geometry)
            except Exception:
                pass
        self.show()
        self.show_status_message("Post-it mode disabled.", 2500)

    def toggle_distraction_free_mode(self, checked: bool) -> None:
        if hasattr(self, "focus_mode_action"):
            self.focus_mode_action.blockSignals(True)
            self.focus_mode_action.setChecked(checked)
            self.focus_mode_action.blockSignals(False)
            self.toggle_focus_mode(checked)
        if hasattr(self, "full_screen_action"):
            self.full_screen_action.blockSignals(True)
            self.full_screen_action.setChecked(checked)
            self.full_screen_action.blockSignals(False)
            self.toggle_full_screen(checked)

    def _set_editor_print_view_styles(self, enabled: bool) -> None:
        styles = getattr(self, "_print_view_editor_styles", {})
        if not isinstance(styles, dict):
            styles = {}
        for idx in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(idx)
            if not isinstance(tab, EditorTab):
                continue
            editor_widget = tab.text_edit.widget
            markdown_widget = tab.markdown_preview
            tab_id = id(tab)
            if enabled:
                if tab_id not in styles:
                    styles[tab_id] = {
                        "editor": editor_widget.styleSheet(),
                        "preview": markdown_widget.styleSheet(),
                    }
                editor_widget.setStyleSheet(
                    "QTextEdit, QPlainTextEdit {"
                    "background-color: #ffffff;"
                    "color: #111111;"
                    "selection-background-color: #cfe8ff;"
                    "selection-color: #111111;"
                    "}"
                )
                markdown_widget.setStyleSheet(
                    "QTextEdit {"
                    "background-color: #ffffff;"
                    "color: #111111;"
                    "}"
                )
            else:
                old = styles.get(tab_id, {})
                if isinstance(old, dict):
                    editor_widget.setStyleSheet(str(old.get("editor", "")))
                    markdown_widget.setStyleSheet(str(old.get("preview", "")))
        if enabled:
            self._print_view_editor_styles = styles
        else:
            self._print_view_editor_styles = {}

    def toggle_print_view(self, checked: bool) -> None:
        if checked and not self.isMaximized():
            QMessageBox.information(self, "Print View", "Print View is only available when the app window is maximized.")
            if hasattr(self, "print_view_action"):
                self.print_view_action.blockSignals(True)
                self.print_view_action.setChecked(False)
                self.print_view_action.blockSignals(False)
            self._print_view_enabled = False
            return
        if checked and getattr(self, "_page_layout_view_enabled", False):
            self.toggle_page_layout_view(False)

        if checked:
            toolbar_state: dict[str, bool] = {}
            for toolbar in self.findChildren(QToolBar):
                key = toolbar.objectName().strip() or f"toolbar-{id(toolbar)}"
                toolbar_state[key] = toolbar.isVisible()
            self._print_view_prev_state = {
                "menu": self.menuBar().isVisible(),
                "status": self.status.isVisible(),
                "tabs": self.tab_widget.tabBar().isVisible(),
                "toolbars": toolbar_state,
            }
            self.menuBar().setVisible(False)
            self.status.setVisible(False)
            self.tab_widget.tabBar().setVisible(False)
            for toolbar in self.findChildren(QToolBar):
                toolbar.hide()
            self._set_editor_print_view_styles(True)
            self._print_view_enabled = True
            self.show_status_message("Print View enabled.", 2500)
        else:
            prev = getattr(self, "_print_view_prev_state", {})
            if isinstance(prev, dict):
                self.menuBar().setVisible(bool(prev.get("menu", True)))
                self.status.setVisible(bool(prev.get("status", True)))
                self.tab_widget.tabBar().setVisible(bool(prev.get("tabs", True)))
                old_toolbars = prev.get("toolbars", {})
                for toolbar in self.findChildren(QToolBar):
                    key = toolbar.objectName().strip() or f"toolbar-{id(toolbar)}"
                    if isinstance(old_toolbars, dict):
                        toolbar.setVisible(bool(old_toolbars.get(key, True)))
            self._set_editor_print_view_styles(False)
            self._print_view_prev_state = {}
            self._print_view_enabled = False
            if hasattr(self, "_layout_top_toolbars"):
                self._layout_top_toolbars()
            self.show_status_message("Print View disabled.", 2500)

        if hasattr(self, "print_view_action"):
            self.print_view_action.blockSignals(True)
            self.print_view_action.setChecked(bool(self._print_view_enabled))
            self.print_view_action.blockSignals(False)

    def focus_on_another_view(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if tab.clone_editor is not None and tab.clone_editor.widget.isVisible():
            tab.clone_editor.widget.setFocus()
            return
        if tab.markdown_preview.isVisible():
            tab.markdown_preview.setFocus()
            return
        tab.text_edit.widget.setFocus()

    def _apply_scintilla_modes(self, tab: EditorTab) -> None:
        if not tab.text_edit.is_scintilla:
            return
        profile = ScintillaProfile.from_settings(getattr(self, "settings", {}))
        tab.text_edit.set_column_mode(tab.column_mode)
        tab.text_edit.set_multi_caret(tab.multi_caret)
        tab.text_edit.set_code_folding(tab.code_folding)
        tab.text_edit.set_auto_completion_mode(tab.auto_completion_mode, threshold=profile.auto_completion_threshold)
        tab.text_edit.set_caret_width(profile.caret_width_px)
        tab.text_edit.set_highlight_current_line(profile.highlight_current_line)
        tab.text_edit.set_margin_padding(left=profile.margin_left_px, right=profile.margin_right_px)
        tab.text_edit.set_line_number_width(
            mode=profile.line_number_width_mode,
            width_px=profile.line_number_width_px,
        )
        # Keep visibility as the final step so width/padding setup cannot re-show the gutter.
        tab.text_edit.set_line_numbers_visible(bool(getattr(tab, "show_line_numbers", True)))
        if tab.auto_completion_mode == "open_docs":
            tab.text_edit.set_auto_completion_words(self._build_open_docs_word_list())
        self._apply_scintilla_visuals(tab)

    def _apply_scintilla_visuals(self, tab: EditorTab) -> None:
        if not tab.text_edit.is_scintilla:
            return
        show_space_tab = bool(tab.show_space_tab or tab.show_non_printing or tab.show_all_chars)
        show_eol = bool(tab.show_eol or tab.show_non_printing or tab.show_all_chars)
        show_control = bool(tab.show_control_chars or tab.show_all_chars)
        tab.text_edit.set_show_space_tab(show_space_tab)
        tab.text_edit.set_show_eol(show_eol)
        tab.text_edit.set_show_control_chars(show_control)
        tab.text_edit.set_show_indent_guides(bool(tab.show_indent_guides))
        tab.text_edit.set_show_wrap_symbol(bool(tab.show_wrap_symbol))

    def _sync_symbol_actions(self, tab: EditorTab | None) -> None:
        for attr, checked in (
            ("show_space_tab_action", bool(tab and tab.show_space_tab)),
            ("show_end_of_line_action", bool(tab and tab.show_eol)),
            ("show_non_printing_action", bool(tab and tab.show_non_printing)),
            ("show_control_unicode_eol_action", bool(tab and tab.show_control_chars)),
            ("show_all_chars_action", bool(tab and tab.show_all_chars)),
            ("show_indent_guide_action", bool(tab is None or tab.show_indent_guides)),
            ("show_wrap_symbol_action", bool(tab and tab.show_wrap_symbol)),
        ):
            action = getattr(self, attr, None)
            if action is None:
                continue
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

    def _require_scintilla_feature(self, feature_name: str = "This feature") -> bool:
        tab = self.active_tab()
        if tab is None:
            return False
        if tab.text_edit.is_scintilla:
            return True
        QMessageBox.information(
            self,
            "Feature Unavailable",
            (
                f"{feature_name} requires QScintilla (PySide6.Qsci).\n\n"
                "Fallback editor mode is active, so advanced multi-caret/column and symbol rendering features are limited."
            ),
        )
        return False

    def view_current_file_in_explorer(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        try:
            os.startfile(str(Path(tab.current_file).parent))
        except Exception as exc:
            QMessageBox.warning(self, "View Current File in", f"Could not open folder:\n{exc}")

    def view_current_file_in_default_viewer(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        try:
            os.startfile(tab.current_file)
        except Exception as exc:
            QMessageBox.warning(self, "View Current File in", f"Could not open file:\n{exc}")

    def view_current_file_in_cmd(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        folder = str(Path(tab.current_file).parent)
        try:
            subprocess.Popen(f'cmd.exe /K cd /d "{folder}"', shell=True)
        except Exception as exc:
            QMessageBox.warning(self, "View Current File in", f"Could not open command prompt:\n{exc}")

    def _toggle_symbol_state(self, attr: str, checked: bool) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        settings_map = {
            "show_space_tab": "show_symbol_space_tab",
            "show_eol": "show_symbol_eol",
            "show_non_printing": "show_symbol_non_printing",
            "show_control_chars": "show_symbol_control_chars",
            "show_all_chars": "show_symbol_all_chars",
            "show_indent_guides": "show_symbol_indent_guide",
            "show_wrap_symbol": "show_symbol_wrap_symbol",
        }
        setattr(tab, attr, bool(checked))
        setting_key = settings_map.get(attr)
        if setting_key:
            self.settings[setting_key] = bool(checked)
        if attr != "show_all_chars" and checked:
            tab.show_all_chars = False
        if attr == "show_all_chars":
            if checked:
                tab.show_space_tab = True
                tab.show_eol = True
                tab.show_non_printing = True
                tab.show_control_chars = True
            else:
                tab.show_space_tab = False
                tab.show_eol = False
                tab.show_non_printing = False
                tab.show_control_chars = False
        if attr == "show_non_printing":
            if checked:
                tab.show_space_tab = True
                tab.show_eol = True
            else:
                tab.show_all_chars = False
        self.settings["show_symbol_space_tab"] = bool(tab.show_space_tab)
        self.settings["show_symbol_eol"] = bool(tab.show_eol)
        self.settings["show_symbol_non_printing"] = bool(tab.show_non_printing)
        self.settings["show_symbol_control_chars"] = bool(tab.show_control_chars)
        self.settings["show_symbol_all_chars"] = bool(tab.show_all_chars)
        self.settings["show_symbol_indent_guide"] = bool(tab.show_indent_guides)
        self.settings["show_symbol_wrap_symbol"] = bool(tab.show_wrap_symbol)
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self._apply_scintilla_visuals(tab)
        self._sync_symbol_actions(tab)

    def toggle_show_space_tab(self, checked: bool) -> None:
        self._toggle_symbol_state("show_space_tab", checked)

    def toggle_show_end_of_line(self, checked: bool) -> None:
        self._toggle_symbol_state("show_eol", checked)

    def toggle_show_non_printing(self, checked: bool) -> None:
        self._toggle_symbol_state("show_non_printing", checked)

    def toggle_show_control_unicode_eol(self, checked: bool) -> None:
        self._toggle_symbol_state("show_control_chars", checked)

    def toggle_show_all_chars(self, checked: bool) -> None:
        self._toggle_symbol_state("show_all_chars", checked)

    def toggle_show_indent_guide(self, checked: bool) -> None:
        self._toggle_symbol_state("show_indent_guides", checked)

    def toggle_show_wrap_symbol(self, checked: bool) -> None:
        self._toggle_symbol_state("show_wrap_symbol", checked)

    def fold_all(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_all(expand=False)

    def unfold_all(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_all(expand=True)

    def fold_current_level(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_current(expand=False)

    def unfold_current_level(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_current(expand=True)

    def fold_level(self, level: int) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_level(level=level, expand=False)

    def unfold_level(self, level: int) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.fold_level(level=level, expand=True)

    def hide_lines(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        selection = tab.text_edit.selection_range()
        if selection is None:
            line, _ = tab.text_edit.cursor_position()
            start_line = line
            end_line = line
        else:
            l1, c1, l2, c2 = selection
            start_line = min(l1, l2)
            end_line = max(l1, l2)
            # If selection ends at column 0 on the next line, don't hide that line.
            if l2 >= l1 and l2 > l1 and c2 == 0:
                end_line -= 1
            elif l1 > l2 and c1 == 0:
                end_line -= 1
            if end_line < start_line:
                end_line = start_line
        if tab.text_edit.hide_line_range(start_line, end_line):
            self.show_status_message(
                f"Hid line(s) {start_line + 1}-{end_line + 1}. Use Show Hidden Lines to restore.",
                3000,
            )
        else:
            QMessageBox.information(
                self,
                "Hide Lines",
                "Your current editor backend does not support line hiding.",
            )

    def show_hidden_lines(self) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        if tab.text_edit.show_all_lines():
            self.show_status_message("All hidden lines restored.", 2500)
        else:
            QMessageBox.information(
                self,
                "Show Hidden Lines",
                "No hidden-line support available for the current editor backend.",
            )

    def set_text_direction_rtl(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.widget.setLayoutDirection(Qt.RightToLeft)
        tab.markdown_preview.setLayoutDirection(Qt.RightToLeft)

    def set_text_direction_ltr(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.text_edit.widget.setLayoutDirection(Qt.LeftToRight)
        tab.markdown_preview.setLayoutDirection(Qt.LeftToRight)

    def open_document_map(self) -> None:
        if hasattr(self, "minimap_action"):
            self.minimap_action.trigger()

    def open_document_list(self) -> None:
        if hasattr(self, "workspace_files_action"):
            self.workspace_files_action.trigger()

    def open_function_list(self) -> None:
        if hasattr(self, "symbol_outline_action"):
            self.symbol_outline_action.trigger()

    def _disconnect_split_scroll_sync(self, tab: EditorTab) -> None:
        pairs = getattr(tab, "_split_scroll_pairs", [])
        for scrollbar, handler in pairs:
            try:
                scrollbar.valueChanged.disconnect(handler)
            except (TypeError, RuntimeError):
                pass
        tab._split_scroll_pairs = []
        tab._split_scroll_syncing = False

    def _apply_split_scroll_sync(self, tab: EditorTab | None) -> None:
        if tab is None:
            return
        self._disconnect_split_scroll_sync(tab)
        if tab.clone_editor is None or not tab.clone_editor.widget.isVisible():
            return
        if not hasattr(tab.text_edit.widget, "verticalScrollBar") or not hasattr(tab.clone_editor.widget, "verticalScrollBar"):
            return

        tab._split_scroll_pairs = []
        tab._split_scroll_syncing = False

        def _bind_pair(primary_bar, secondary_bar) -> tuple[Any, Any]:
            def _forward(value: int) -> None:
                if getattr(tab, "_split_scroll_syncing", False):
                    return
                tab._split_scroll_syncing = True
                try:
                    secondary_bar.setValue(value)
                finally:
                    tab._split_scroll_syncing = False

            primary_bar.valueChanged.connect(_forward)
            return primary_bar, _forward

        if bool(getattr(self, "sync_vertical_action", None) and self.sync_vertical_action.isChecked()):
            main_v = tab.text_edit.widget.verticalScrollBar()
            clone_v = tab.clone_editor.widget.verticalScrollBar()
            tab._split_scroll_pairs.append(_bind_pair(main_v, clone_v))
            tab._split_scroll_pairs.append(_bind_pair(clone_v, main_v))
            clone_v.setValue(main_v.value())

        if bool(getattr(self, "sync_horizontal_action", None) and self.sync_horizontal_action.isChecked()):
            main_h = tab.text_edit.widget.horizontalScrollBar()
            clone_h = tab.clone_editor.widget.horizontalScrollBar()
            tab._split_scroll_pairs.append(_bind_pair(main_h, clone_h))
            tab._split_scroll_pairs.append(_bind_pair(clone_h, main_h))
            clone_h.setValue(main_h.value())

    def toggle_sync_vertical_scrolling(self, checked: bool) -> None:
        self.settings["sync_vertical_scrolling"] = bool(checked)
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self._apply_split_scroll_sync(self.active_tab())

    def toggle_sync_horizontal_scrolling(self, checked: bool) -> None:
        self.settings["sync_horizontal_scrolling"] = bool(checked)
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self._apply_split_scroll_sync(self.active_tab())

    def _ensure_clone_editor(self, tab: EditorTab) -> None:
        if tab.clone_editor is not None:
            return
        tab.clone_editor = EditorWidget(tab)
        clone_editor = tab.clone_editor
        clone_editor.set_text(tab.text_edit.get_text())
        if hasattr(tab, "_split_syncing"):
            tab._split_syncing = False
        else:
            tab._split_syncing = False

        def _sync(source: EditorWidget, target: EditorWidget | None) -> None:
            if target is None:
                return
            if getattr(tab, "_split_syncing", False):
                return
            tab._split_syncing = True
            target.set_text(source.get_text())
            tab._split_syncing = False

        split_main_handler = lambda: _sync(tab.text_edit, clone_editor)
        split_clone_handler = lambda: _sync(clone_editor, tab.text_edit)
        tab._split_main_handler = split_main_handler
        tab._split_clone_handler = split_clone_handler
        tab.text_edit.textChanged.connect(split_main_handler)  # type: ignore[arg-type]
        clone_editor.textChanged.connect(split_clone_handler)  # type: ignore[arg-type]

    def clone_to_other_view(self) -> None:
        self._enable_split_view(Qt.Horizontal)

    def split_view_vertical(self) -> None:
        self._enable_split_view(Qt.Horizontal)

    def split_view_horizontal(self) -> None:
        self._enable_split_view(Qt.Vertical)

    def _enable_split_view(self, orientation: Qt.Orientation) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        self._ensure_clone_editor(tab)
        tab.split_mode = "split"
        tab.editor_splitter.setOrientation(orientation)
        if tab.clone_editor.widget not in [tab.editor_splitter.widget(i) for i in range(tab.editor_splitter.count())]:
            tab.editor_splitter.insertWidget(1, tab.clone_editor.widget)
        tab.clone_editor.widget.show()
        tab.markdown_preview.hide()
        self._apply_split_scroll_sync(tab)

    def close_split_view(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.clone_editor is None:
            return
        self._disconnect_split_scroll_sync(tab)
        split_main_handler = getattr(tab, "_split_main_handler", None)
        split_clone_handler = getattr(tab, "_split_clone_handler", None)
        if split_main_handler is not None:
            try:
                tab.text_edit.textChanged.disconnect(split_main_handler)
            except (TypeError, RuntimeError):
                pass
            tab._split_main_handler = None
        if split_clone_handler is not None:
            try:
                tab.clone_editor.textChanged.disconnect(split_clone_handler)
            except (TypeError, RuntimeError):
                pass
            tab._split_clone_handler = None
        tab.split_mode = None
        tab.clone_editor.widget.setParent(None)
        tab.clone_editor = None
        if tab.markdown_mode_enabled:
            tab.markdown_preview.show()

    def toggle_column_mode(self, checked: bool) -> None:
        if not self._require_scintilla_feature("Column mode"):
            if hasattr(self, "column_mode_action"):
                self.column_mode_action.blockSignals(True)
                self.column_mode_action.setChecked(False)
                self.column_mode_action.blockSignals(False)
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.column_mode = checked
        tab.text_edit.set_column_mode(checked)
        self.show_status_message("Column mode enabled." if checked else "Column mode disabled.", 1800)

    def toggle_multi_caret(self, checked: bool) -> None:
        if not self._require_scintilla_feature("Multi-caret"):
            if hasattr(self, "multi_caret_action"):
                self.multi_caret_action.blockSignals(True)
                self.multi_caret_action.setChecked(False)
                self.multi_caret_action.blockSignals(False)
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.multi_caret = checked
        tab.text_edit.set_multi_caret(checked)
        self.show_status_message("Multi-caret enabled." if checked else "Multi-caret disabled.", 1800)

    def toggle_code_folding(self, checked: bool) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        tab.code_folding = checked
        tab.text_edit.set_code_folding(checked)

    def set_auto_completion_mode(self, mode: str) -> None:
        if not self._require_scintilla_feature():
            return
        tab = self.active_tab()
        if tab is None:
            return
        normalized = (mode or "all").lower()
        if normalized not in {"none", "off", "all", "document", "doc", "apis", "api", "open_docs"}:
            normalized = "all"
        tab.auto_completion_mode = normalized
        self.settings["auto_completion_mode"] = normalized
        tab.text_edit.set_auto_completion_mode(normalized)
        if normalized == "open_docs":
            tab.text_edit.set_auto_completion_words(self._build_open_docs_word_list())
            label = "open documents"
        elif normalized in {"none", "off"}:
            label = "off"
        elif normalized in {"document", "doc"}:
            label = "document"
        elif normalized in {"apis", "api"}:
            label = "APIs"
        else:
            label = "all"
        self.show_status_message(f"Auto-completion set to {label}.", 1800)

    def _build_open_docs_word_list(self) -> list[str]:
        words: set[str] = set()
        max_words = 4000
        for idx in range(self.tab_widget.count()):
            tab = self._tab_at_index(idx)
            if tab is None:
                continue
            text = tab.text_edit.get_text()
            if not text:
                continue
            for match in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{2,}", text):
                words.add(match.group(0))
                if len(words) >= max_words:
                    break
            if len(words) >= max_words:
                break
        return sorted(words)

    def toggle_word_wrap(self, checked: bool) -> None:
        self.word_wrap_enabled = checked
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.text_edit.set_wrap_enabled(checked)

    def toggle_show_line_numbers(self, checked: bool) -> None:
        self.line_numbers_enabled = bool(checked)
        self.settings["npp_margin_line_numbers_enabled"] = bool(checked)
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.show_line_numbers = bool(checked)
                tab.text_edit.set_line_numbers_visible(bool(checked))
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        self.show_status_message("Line numbers shown." if checked else "Line numbers hidden.", 1800)

    def open_define_language_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("User Defined Language")
        dlg.resize(900, 720)
        root = QVBoxLayout(dlg)
        tokens = build_tokens_from_settings(getattr(self, "settings", {}) if isinstance(getattr(self, "settings", {}), dict) else {})
        dlg.setStyleSheet(build_dialog_theme_qss_from_tokens(tokens) + "\n" + build_tool_dialog_qss(tokens))

        top = QHBoxLayout()
        top.addWidget(QLabel("User language:", dlg))
        lang_combo = QComboBox(dlg)
        lang_combo.addItems(["User Defined Language"])
        top.addWidget(lang_combo, 1)
        create_btn = QPushButton("Create new...", dlg)
        save_as_btn = QPushButton("Save as...", dlg)
        import_btn = QPushButton("Import...", dlg)
        export_btn = QPushButton("Export...", dlg)
        ignore_case = QCheckBox("Ignore case", dlg)
        dock_btn = QPushButton("Dock", dlg)
        transparency = QCheckBox("Transparency", dlg)
        for btn in (create_btn, save_as_btn, import_btn, export_btn, dock_btn):
            top.addWidget(btn)
        top.addWidget(ignore_case)
        top.addStretch(1)
        top.addWidget(transparency)
        root.addLayout(top)

        tabs = QTabWidget(dlg)
        root.addWidget(tabs, 1)

        folder_tab = QWidget(dlg)
        folder_layout = QVBoxLayout(folder_tab)
        docs_group = QGroupBox("Documentation", folder_tab)
        docs_layout = QVBoxLayout(docs_group)
        docs_layout.addWidget(QLabel("User Defined Languages online help", docs_group))
        default_style_group = QGroupBox("Default style", folder_tab)
        default_style_layout = QHBoxLayout(default_style_group)
        styler_btn_1 = QPushButton("Styler", default_style_group)
        default_style_layout.addWidget(styler_btn_1)
        default_style_layout.addStretch(1)
        folder_layout.addWidget(docs_group)
        folder_layout.addWidget(default_style_group)
        fold_compact = QCheckBox("Fold compact (fold empty lines too)", folder_tab)
        folder_layout.addWidget(fold_compact)
        folder_layout.addStretch(1)
        tabs.addTab(folder_tab, "Folder & Default")

        keywords_tab = QWidget(dlg)
        keywords_layout = QVBoxLayout(keywords_tab)
        for idx in range(1, 9):
            group = QGroupBox(f"{idx}th group", keywords_tab)
            gl = QVBoxLayout(group)
            row = QHBoxLayout()
            row.addWidget(QPushButton("Styler", group))
            row.addWidget(QCheckBox("Prefix mode", group))
            row.addStretch(1)
            gl.addLayout(row)
            gl.addWidget(QTextEdit(group))
            keywords_layout.addWidget(group)
        tabs.addTab(keywords_tab, "Keywords Lists")

        comment_tab = QWidget(dlg)
        comment_layout = QVBoxLayout(comment_tab)
        line_comment_group = QGroupBox("Line comment position", comment_tab)
        line_comment_layout = QVBoxLayout(line_comment_group)
        line_comment_layout.addWidget(QCheckBox("Allow anywhere", line_comment_group))
        line_comment_layout.addWidget(QCheckBox("Force at beginning of line", line_comment_group))
        line_comment_layout.addWidget(QCheckBox("Allow preceding whitespace", line_comment_group))
        comment_layout.addWidget(line_comment_group)
        comment_layout.addWidget(QCheckBox("Allow folding of comments", comment_tab))
        comment_layout.addStretch(1)
        tabs.addTab(comment_tab, "Comment & Number")

        operators_tab = QWidget(dlg)
        operators_layout = QVBoxLayout(operators_tab)
        operators_style_group = QGroupBox("Operators style", operators_tab)
        operators_style_layout = QHBoxLayout(operators_style_group)
        operators_style_layout.addWidget(QPushButton("Styler", operators_style_group))
        operators_style_layout.addStretch(1)
        operators_layout.addWidget(operators_style_group)
        for idx in range(1, 9):
            group = QGroupBox(f"Delimiter {idx} style", operators_tab)
            gl = QFormLayout(group)
            gl.addRow("Open:", QLineEdit(group))
            gl.addRow("Escape:", QLineEdit(group))
            gl.addRow("Close:", QLineEdit(group))
            operators_layout.addWidget(group)
        tabs.addTab(operators_tab, "Operators & Delimiters")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, Qt.Orientation.Horizontal, dlg)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        root.addWidget(buttons)

        def _open_styler_dialog() -> None:
            styler = QDialog(dlg)
            styler.setWindowTitle("Styler Dialog")
            styler.resize(520, 460)
            st = QVBoxLayout(styler)
            font_group = QGroupBox("Font options", styler)
            font_form = QFormLayout(font_group)
            font_name = QComboBox(font_group)
            font_name.addItems(["", "Consolas", "Courier New", "Fira Code", "Segoe UI"])
            font_size = QComboBox(font_group)
            font_size.addItems(["", "9", "10", "11", "12", "14", "16"])
            font_form.addRow("Name:", font_name)
            font_form.addRow("Size:", font_size)
            font_form.addRow("Bold", QCheckBox(styler))
            font_form.addRow("Italic", QCheckBox(styler))
            font_form.addRow("Underline", QCheckBox(styler))
            st.addWidget(font_group)
            nesting_group = QGroupBox("Nesting", styler)
            nesting_layout = QVBoxLayout(nesting_group)
            for label in (
                "Delimiter 1",
                "Delimiter 2",
                "Delimiter 3",
                "Delimiter 4",
                "Keyword 1",
                "Keyword 2",
                "Comment",
                "Comment line",
                "Operators 1",
                "Operators 2",
                "Numbers",
            ):
                nesting_layout.addWidget(QCheckBox(label, nesting_group))
            st.addWidget(nesting_group, 1)
            styler_box = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                Qt.Orientation.Horizontal,
                styler,
            )
            styler_box.accepted.connect(styler.accept)
            styler_box.rejected.connect(styler.reject)
            st.addWidget(styler_box)
            styler.exec()

        for btn in folder_tab.findChildren(QPushButton):
            if btn.text() == "Styler":
                btn.clicked.connect(_open_styler_dialog)
        for btn in keywords_tab.findChildren(QPushButton):
            if btn.text() == "Styler":
                btn.clicked.connect(_open_styler_dialog)
        for btn in operators_tab.findChildren(QPushButton):
            if btn.text() == "Styler":
                btn.clicked.connect(_open_styler_dialog)

        dlg.exec()

    def open_monitoring_tail_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Monitoring (tail -f)", "", "All Files (*.*)")
        if not path:
            return
        file_path = Path(path)
        if not file_path.exists():
            QMessageBox.warning(self, "Monitoring (tail -f)", f"File not found:\n{path}")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Monitoring (tail -f): {file_path.name}")
        dlg.resize(860, 560)
        root = QVBoxLayout(dlg)
        viewer = QTextEdit(dlg)
        viewer.setReadOnly(True)
        viewer.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        root.addWidget(viewer, 1)

        controls = QHBoxLayout()
        status_label = QLabel("Stopped", dlg)
        interval_spin = QSpinBox(dlg)
        interval_spin.setRange(200, 5000)
        interval_spin.setSingleStep(100)
        interval_spin.setValue(800)
        start_btn = QPushButton("Start", dlg)
        stop_btn = QPushButton("Stop", dlg)
        close_btn = QPushButton("Close", dlg)
        controls.addWidget(QLabel("Refresh (ms):", dlg))
        controls.addWidget(interval_spin)
        controls.addWidget(start_btn)
        controls.addWidget(stop_btn)
        controls.addStretch(1)
        controls.addWidget(status_label)
        controls.addWidget(close_btn)
        root.addLayout(controls)

        timer = QTimer(dlg)
        timer.setInterval(int(interval_spin.value()))

        def _read_tail() -> None:
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                status_label.setText(f"Read error: {exc}")
                return
            lines = text.splitlines()
            tail_lines = lines[-400:] if lines else []
            viewer.setPlainText("\n".join(tail_lines))
            cursor = viewer.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            viewer.setTextCursor(cursor)
            status_label.setText(f"Updated {datetime.now().strftime('%H:%M:%S')}")

        def _start() -> None:
            timer.setInterval(int(interval_spin.value()))
            _read_tail()
            timer.start()
            status_label.setText("Running")

        def _stop() -> None:
            timer.stop()
            status_label.setText("Stopped")

        interval_spin.valueChanged.connect(lambda value: timer.setInterval(int(value)))
        timer.timeout.connect(_read_tail)
        start_btn.clicked.connect(_start)
        stop_btn.clicked.connect(_stop)
        close_btn.clicked.connect(dlg.accept)
        dlg.finished.connect(lambda _code: timer.stop())
        _read_tail()
        dlg.exec()

    def choose_font(self) -> None:
        current_font: QFont = self.text_edit.current_font()
        font, ok = QFontDialog.getFont(current_font, self, "Choose Font")
        if ok:
            self.text_edit.set_font(font)

    def format_selection_text_size(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        if not tab.text_edit.has_selection():
            QMessageBox.information(
                self,
                "Text Size",
                "Select text first, then run Text Size (Selection).",
            )
            return
        default_size = max(8, min(96, int(self.settings.get("font_size", 11) or 11)))
        size_px, ok = QInputDialog.getInt(
            self,
            "Text Size (Selection)",
            "Size (px):",
            default_size,
            8,
            96,
            1,
        )
        if not ok:
            return
        selected = tab.text_edit.selected_text()
        tab.text_edit.replace_selection(
            f'<span style="font-size: {int(size_px)}px;">{selected}</span>'
        )
        tab.text_edit.set_modified(True)
        if tab.markdown_mode_enabled:
            self.update_markdown_preview()
        self.show_status_message(f"Applied text size: {int(size_px)}px", 2200)

    def _toggle_char_format(self, *, bold: bool | None = None, italic: bool | None = None,
                            underline: bool | None = None, strike: bool | None = None) -> None:
        marker = None
        if bold:
            marker = ("**", "**", "bold")
        elif italic:
            marker = ("*", "*", "italic")
        elif underline:
            marker = ("_", "_", "underline")
        elif strike:
            marker = ("~~", "~~", "strike")
        if marker is None:
            return
        self.insert_markdown_wrapper(*marker)

    def format_bold(self) -> None:
        self._toggle_char_format(bold=True)

    def format_italic(self) -> None:
        self._toggle_char_format(italic=True)

    def format_underline(self) -> None:
        self._toggle_char_format(underline=True)

    def format_strikethrough(self) -> None:
        self._toggle_char_format(strike=True)

    def apply_document_style(self, style_name: str) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        sel = tab.text_edit.selection_range()
        line, _ = tab.text_edit.cursor_position()
        updated = apply_style_to_text(source, style_name, sel, line)
        if updated == source:
            return
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        if tab.markdown_mode_enabled:
            self.update_markdown_preview()
        self.show_status_message(f"Applied style: {style_name}", 2000)

    def _selected_or_placeholder(self, placeholder: str) -> str:
        if self.text_edit.has_selection():
            return self.text_edit.selected_text()
        return placeholder

    def insert_markdown_wrapper(self, prefix: str, suffix: str, placeholder: str) -> None:
        content = self._selected_or_placeholder(placeholder)
        if self.text_edit.has_selection():
            self.text_edit.replace_selection(f"{prefix}{content}{suffix}")
        else:
            self.text_edit.insert_text(f"{prefix}{content}{suffix}")

    def _apply_markdown_prefix(self, prefix: str) -> None:
        text = self.text_edit.get_text()
        lines = text.splitlines(keepends=True)
        sel = self.text_edit.selection_range()
        if sel is None:
            line, _ = self.text_edit.cursor_position()
            if 0 <= line < len(lines):
                lines[line] = prefix + lines[line]
                self.text_edit.set_text("".join(lines))
                self.text_edit.set_cursor_position(line, 0)
            return
        start_line, _, end_line, _ = sel
        for i in range(start_line, end_line + 1):
            if 0 <= i < len(lines):
                lines[i] = prefix + lines[i]
        self.text_edit.set_text("".join(lines))

    def markdown_heading(self, level: int) -> None:
        self._apply_markdown_prefix("#" * max(1, min(level, 6)) + " ")

    def markdown_bullet_list(self) -> None:
        self._apply_markdown_prefix("- ")

    def markdown_task_list(self) -> None:
        self._apply_markdown_prefix("- [ ] ")

    def markdown_blockquote(self) -> None:
        self._apply_markdown_prefix("> ")

    def markdown_numbered_list(self) -> None:
        text = self.text_edit.get_text()
        lines = text.splitlines(keepends=True)
        sel = self.text_edit.selection_range()
        if sel is None:
            line, _ = self.text_edit.cursor_position()
            if 0 <= line < len(lines):
                lines[line] = "1. " + lines[line]
                self.text_edit.set_text("".join(lines))
            return
        start_line, _, end_line, _ = sel
        index = 1
        for i in range(start_line, end_line + 1):
            if 0 <= i < len(lines):
                lines[i] = f"{index}. " + lines[i]
                index += 1
        self.text_edit.set_text("".join(lines))

    def markdown_code_block(self) -> None:
        if self.text_edit.has_selection():
            selected = self.text_edit.selected_text()
            self.text_edit.replace_selection(f"```\n{selected}\n```")
            return
        self.text_edit.insert_text("```\ncode\n```")

    def markdown_link(self) -> None:
        text = self._selected_or_placeholder("link text")
        self.text_edit.insert_text(f"[{text}](https://example.com)")

    def markdown_image(self) -> None:
        text = self._selected_or_placeholder("alt text")
        self.text_edit.insert_text(f"![{text}](https://example.com/image.png)")

    def markdown_horizontal_rule(self) -> None:
        self.text_edit.insert_text("\n---\n")

    def markdown_table(self) -> None:
        self.text_edit.insert_text("| Column 1 | Column 2 |\n| --- | --- |\n| Value 1 | Value 2 |\n")

    def insert_page_break_marker(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        self.text_edit.insert_text("\n[[PAGE_BREAK]]\n")
        tab.text_edit.set_modified(True)
        self.show_status_message("Inserted page break marker.", 2000)

    def configure_page_layout(self) -> None:
        cfg = PageLayoutConfig.from_settings(self.settings)
        dlg = PageLayoutDialog(self, cfg)
        if dlg.exec() != QDialog.Accepted:
            return
        new_cfg = dlg.config
        new_cfg.apply_to_settings(self.settings)
        self.save_settings_to_disk()
        if getattr(self, "_page_layout_view_enabled", False):
            self.toggle_page_layout_view(True)
        self.update_status_bar()
        self.show_status_message("Page layout settings updated.", 2500)

    def toggle_page_layout_view(self, checked: bool) -> None:
        self._page_layout_view_enabled = bool(checked)
        self.settings["page_layout_view_enabled"] = bool(checked)
        self.save_settings_to_disk()
        if checked and getattr(self, "_print_view_enabled", False):
            self.toggle_print_view(False)
        if checked and hasattr(self, "_set_editor_print_view_styles"):
            self._set_editor_print_view_styles(True)
        if not checked and hasattr(self, "_set_editor_print_view_styles"):
            self._set_editor_print_view_styles(False)
        if hasattr(self, "page_layout_view_action"):
            self.page_layout_view_action.blockSignals(True)
            self.page_layout_view_action.setChecked(bool(checked))
            self.page_layout_view_action.blockSignals(False)
        self.update_status_bar()
        self.show_status_message("Page Layout View enabled." if checked else "Page Layout View disabled.", 2500)

    def generate_table_of_contents(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        headings = extract_markdown_headings(tab.text_edit.get_text())
        if not headings:
            QMessageBox.information(self, "Table of Contents", "No markdown headings found.")
            return
        toc_text = build_markdown_toc(headings)
        toc_block = f"<!-- TOC START -->\n{toc_text}\n<!-- TOC END -->\n"
        options = ["Insert at Cursor", "Replace Existing TOC Block", "Copy TOC to Clipboard"]
        choice, ok = QInputDialog.getItem(self, "Generate TOC", "Output:", options, 0, False)
        if not ok or not choice:
            return
        if choice == "Copy TOC to Clipboard":
            QApplication.clipboard().setText(toc_text)
            self.show_status_message("TOC copied to clipboard.", 2500)
            return
        if tab.text_edit.is_read_only():
            QMessageBox.information(self, "Table of Contents", "Current tab is read-only.")
            return
        if choice == "Replace Existing TOC Block":
            source = tab.text_edit.get_text()
            start = source.find("<!-- TOC START -->")
            end = source.find("<!-- TOC END -->")
            if start != -1 and end != -1 and end >= start:
                end += len("<!-- TOC END -->")
                updated = source[:start] + toc_block + source[end:]
                tab.text_edit.set_text(updated)
                tab.text_edit.set_modified(True)
                self.show_status_message("Existing TOC replaced.", 2500)
                return
        tab.text_edit.insert_text(toc_block)
        tab.text_edit.set_modified(True)
        self.show_status_message("TOC inserted.", 2500)

    def _review_author_label(self) -> str:
        return (getpass.getuser() or "").strip() or "author"

    def toggle_track_changes(self, checked: bool) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.track_changes_enabled = bool(checked)
        self.settings["track_changes_enabled"] = bool(checked)
        self.save_settings_to_disk()
        self.update_action_states()
        self.show_status_message(
            "Track changes enabled." if checked else "Track changes disabled.",
            2000,
        )

    def insert_tracked_text(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        if not tab.track_changes_enabled:
            QMessageBox.information(self, "Track Changes", "Enable Track Changes first.")
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Insert Tracked Text",
            "Text to insert:",
            "",
        )
        if not ok or not text:
            return
        source = tab.text_edit.get_text()
        cursor_idx = tab.text_edit.cursor_index()
        updated, change_id = insert_tracked_insertion(source, cursor_idx, text, self._review_author_label())
        tab.text_edit.set_text(updated)
        marker = f"[[INS:{change_id}|"
        pos = updated.find(marker, max(0, cursor_idx - 4))
        if pos >= 0:
            tab.text_edit.set_selection_by_index(pos, pos + len(marker))
        tab.text_edit.set_modified(True)
        self.show_status_message("Tracked insertion added.", 2000)

    def mark_selection_as_deletion(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        if not tab.track_changes_enabled:
            QMessageBox.information(self, "Track Changes", "Enable Track Changes first.")
            return
        sel = tab.text_edit.selection_range()
        if sel is None:
            QMessageBox.information(self, "Track Changes", "Select text to mark as deletion.")
            return
        start = tab.text_edit.index_from_line_col(sel[0], sel[1])
        end = tab.text_edit.index_from_line_col(sel[2], sel[3])
        source = tab.text_edit.get_text()
        result = mark_tracked_deletion(source, start, end, self._review_author_label())
        if result is None:
            return
        updated, change_id = result
        tab.text_edit.set_text(updated)
        marker = f"[[DEL:{change_id}|"
        pos = updated.find(marker, max(0, start - 4))
        if pos >= 0:
            tab.text_edit.set_selection_by_index(pos, pos + len(marker))
        tab.text_edit.set_modified(True)
        self.show_status_message("Tracked deletion added.", 2000)

    def jump_to_next_change(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        source = tab.text_edit.get_text()
        if not has_tracked_changes(source):
            self.show_status_message("No tracked changes in this document.", 2000)
            return
        span = next_change_span(source, tab.text_edit.cursor_index() + 1)
        if span is None:
            self.show_status_message("No tracked changes in this document.", 2000)
            return
        start, end, kind, _change_id = span
        tab.text_edit.set_selection_by_index(start, end)
        self.show_status_message(
            "Moved to tracked insertion." if kind == "ins" else "Moved to tracked deletion.",
            2000,
        )

    def accept_change_at_cursor(self) -> None:
        self._apply_change_decision(accept=True)

    def reject_change_at_cursor(self) -> None:
        self._apply_change_decision(accept=False)

    def _apply_change_decision(self, *, accept: bool) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        updated, changed, kind = accept_or_reject_change_at_cursor(
            source,
            tab.text_edit.cursor_index(),
            accept=accept,
        )
        if not changed:
            self.show_status_message("No tracked change near cursor.", 2000)
            return
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        action = "Accepted" if accept else "Rejected"
        target = "insertion" if kind == "ins" else "deletion"
        self.show_status_message(f"{action} tracked {target}.", 2000)

    def accept_all_tracked_changes(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        updated, count = accept_all_changes(source)
        if count <= 0:
            self.show_status_message("No tracked changes to accept.", 2000)
            return
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Accepted {count} tracked change(s).", 2200)

    def reject_all_tracked_changes(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        updated, count = reject_all_changes(source)
        if count <= 0:
            self.show_status_message("No tracked changes to reject.", 2000)
            return
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Rejected {count} tracked change(s).", 2200)

    def add_review_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        sel = tab.text_edit.selection_range()
        if sel is None:
            QMessageBox.information(self, "Add Comment", "Select text to attach a comment.")
            return
        comment, ok = QInputDialog.getMultiLineText(self, "Add Comment", "Comment:")
        if not ok or not comment.strip():
            return
        start = tab.text_edit.index_from_line_col(sel[0], sel[1])
        end = tab.text_edit.index_from_line_col(sel[2], sel[3])
        source = tab.text_edit.get_text()
        result = add_comment(source, start, end, comment, self._review_author_label())
        if result is None:
            QMessageBox.information(self, "Add Comment", "Could not create comment for this selection.")
            return
        updated, comment_id = result
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Comment {comment_id} added.", 2200)

    def review_comments(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        source = tab.text_edit.get_text()
        entries = list_comments(source)
        if not entries:
            QMessageBox.information(self, "Review Comments", "No comments found in this document.")
            return
        labels = [f"{row.comment_id} - {row.anchor_preview or '(anchor)'}" for row in entries]
        picked, ok = QInputDialog.getItem(self, "Review Comments", "Comment:", labels, 0, False)
        if not ok or not picked:
            return
        index = labels.index(picked)
        chosen = entries[index]
        options = ["Jump to Comment", "Copy Comment Text", "Remove Comment"]
        op, ok = QInputDialog.getItem(self, "Review Comments", "Action:", options, 0, False)
        if not ok or not op:
            return
        if op == "Jump to Comment":
            tab.text_edit.set_selection_by_index(chosen.anchor_start, chosen.anchor_end)
            self.show_status_message(f"Focused comment {chosen.comment_id}.", 2000)
            return
        if op == "Copy Comment Text":
            QApplication.clipboard().setText(chosen.comment)
            self.show_status_message("Comment text copied.", 2000)
            return
        updated, changed = remove_comment(source, chosen.comment_id)
        if not changed:
            self.show_status_message("Comment could not be removed.", 2000)
            return
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Removed comment {chosen.comment_id}.", 2000)

    def insert_footnote(self) -> None:
        self._insert_note_reference(endnote=False)

    def insert_endnote(self) -> None:
        self._insert_note_reference(endnote=True)

    def _insert_note_reference(self, *, endnote: bool) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        title = "Insert Endnote" if endnote else "Insert Footnote"
        prompt = "Endnote text:" if endnote else "Footnote text:"
        note_text, ok = QInputDialog.getMultiLineText(self, title, prompt, "")
        if not ok:
            return
        source = tab.text_edit.get_text()
        updated, marker = insert_note(
            source,
            tab.text_edit.cursor_index(),
            note_text,
            endnote=endnote,
        )
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Inserted {marker}.", 2200)

    def insert_cross_reference(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        source = tab.text_edit.get_text()
        targets = extract_heading_targets(source)
        if not targets:
            QMessageBox.information(self, "Insert Cross-Reference", "No markdown headings found.")
            return
        labels = [f"{title}  ->  #{slug}" for title, slug in targets]
        choice, ok = QInputDialog.getItem(
            self,
            "Insert Cross-Reference",
            "Target heading:",
            labels,
            0,
            False,
        )
        if not ok or not choice:
            return
        index = labels.index(choice)
        title, slug = targets[index]
        updated = insert_cross_reference_link(source, tab.text_edit.cursor_index(), title, slug)
        tab.text_edit.set_text(updated)
        tab.text_edit.set_modified(True)
        self.show_status_message(f"Cross-reference inserted to #{slug}.", 2200)

    @staticmethod
    def _is_markdown_path(path: str | None) -> bool:
        if not path:
            return False
        return Path(path).suffix.lower() in {".md", ".markdown", ".mdown"}

    def set_markdown_mode(self, enabled: bool) -> None:
        self.markdown_mode_enabled = enabled
        self.md_toggle_preview_action.setChecked(enabled)
        self.markdown_preview.setVisible(enabled)
        if enabled:
            self.update_markdown_preview()
        else:
            self.markdown_preview.clear()
        tab = self.active_tab()
        if tab is not None:
            self._apply_syntax_highlighting(tab)

    def toggle_markdown_preview(self, checked: bool) -> None:
        self.set_markdown_mode(checked)
        if checked:
            self.show_status_message("Markdown preview enabled", 2000)
        else:
            self.show_status_message("Markdown preview disabled", 2000)

    def update_markdown_preview(self) -> None:
        if not self.markdown_mode_enabled:
            return
        source_markdown = self.text_edit.get_text()
        self.markdown_preview.setMarkdown(source_markdown)

    def toggle_status_bar(self, checked: bool) -> None:
        self.status.setVisible(checked)

    def view_zoom_in(self) -> None:
        self.text_edit.zoom_in(1)
        self.zoom_steps += 1
        self.zoom_label.setText(f"{max(10, 100 + (self.zoom_steps * 10))}%")
        if hasattr(self, "status_panel_zoom_label"):
            self.status_panel_zoom_label.setText(self.zoom_label.text())

    def view_zoom_out(self) -> None:
        self.text_edit.zoom_in(-1)
        self.zoom_steps -= 1
        self.zoom_label.setText(f"{max(10, 100 + (self.zoom_steps * 10))}%")
        if hasattr(self, "status_panel_zoom_label"):
            self.status_panel_zoom_label.setText(self.zoom_label.text())

    def view_zoom_reset(self) -> None:
        if self.zoom_steps != 0:
            self.text_edit.zoom_in(-self.zoom_steps)
            self.zoom_steps = 0
        self.zoom_label.setText("100%")
        if hasattr(self, "status_panel_zoom_label"):
            self.status_panel_zoom_label.setText(self.zoom_label.text())

    def update_status_bar(self) -> None:
        tab = self.active_tab()
        if tab is None:
            lang_code = getattr(self, "_ui_language_code", "en")
            ln_label = self._translate_text("Ln", lang_code)
            col_label = self._translate_text("Col", lang_code)
            self.position_label.setText(f"{ln_label} -, {col_label} -")
            self.eol_label.setText(self._translate_text("No EOL", lang_code))
            if hasattr(self, "zoom_label"):
                self.zoom_label.setText("100%")
            if hasattr(self, "encoding_label"):
                self.encoding_label.setText("UTF-8")
            if hasattr(self, "ruler_label"):
                self.ruler_label.setVisible(False)
            if hasattr(self, "status_panel_position_label"):
                self.status_panel_position_label.setText(f"{ln_label} -, {col_label} -")
                self.status_panel_zoom_label.setText("100%")
                self.status_panel_eol_label.setText(self._translate_text("No EOL", lang_code))
                self.status_panel_encoding_label.setText("UTF-8")
                self.status_panel_ruler_label.setVisible(False)
            self.update_action_states()
            return

        line, column = tab.text_edit.cursor_position()
        line += 1
        column += 1
        lang_code = getattr(self, "_ui_language_code", "en")
        ln_label = self._translate_text("Ln", lang_code)
        col_label = self._translate_text("Col", lang_code)
        self.position_label.setText(f"{ln_label} {line}, {col_label} {column}")
        self.update_markdown_preview()
        if hasattr(self, "ruler_label"):
            show_ruler = bool(getattr(self, "_page_layout_view_enabled", False) and self.settings.get("page_layout_show_ruler", True))
            self.ruler_label.setVisible(show_ruler)
            if show_ruler:
                self.ruler_label.setText(build_ruler_text(column, width=100))

        eol_mode = tab.eol_mode or "LF"
        if eol_mode == "CRLF":
            eol_text = self._translate_text("Windows (CRLF)", lang_code)
        elif eol_mode == "LF":
            eol_text = self._translate_text("Unix (LF)", lang_code)
        else:
            eol_text = self._translate_text("No EOL", lang_code)
        self.eol_label.setText(eol_text)
        if hasattr(self, "encoding_label"):
            self.encoding_label.setText((tab.encoding or "UTF-8").upper())
        if hasattr(self, "status_panel_position_label"):
            self.status_panel_position_label.setText(f"{ln_label} {line}, {col_label} {column}")
            self.status_panel_eol_label.setText(eol_text)
            self.status_panel_encoding_label.setText((tab.encoding or "UTF-8").upper())
            if hasattr(self, "status_panel_zoom_label"):
                self.status_panel_zoom_label.setText(self.zoom_label.text() if hasattr(self, "zoom_label") else "100%")
            if hasattr(self, "status_panel_ruler_label"):
                show_ruler = bool(getattr(self, "_page_layout_view_enabled", False) and self.settings.get("page_layout_show_ruler", True))
                self.status_panel_ruler_label.setVisible(show_ruler)
                if show_ruler:
                    self.status_panel_ruler_label.setText(build_ruler_text(column, width=100))
            if hasattr(self, "syntax_combo") and hasattr(self, "status_panel_syntax_label"):
                self.status_panel_syntax_label.setText(f"Lang: {self.syntax_combo.currentText()}")
            if hasattr(self, "breadcrumb_label") and hasattr(self, "status_panel_breadcrumb_label"):
                self.status_panel_breadcrumb_label.setText(self.breadcrumb_label.text())
            if hasattr(self, "ai_usage_label") and hasattr(self, "status_panel_ai_usage_label"):
                self.status_panel_ai_usage_label.setText(self.ai_usage_label.text())
        if hasattr(self, "full_screen_action"):
            self.full_screen_action.blockSignals(True)
            self.full_screen_action.setChecked(bool(self.isFullScreen()))
            self.full_screen_action.blockSignals(False)
        if hasattr(self, "advanced_features"):
            self.advanced_features.refresh_views()
        self.update_action_states()


