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
from ..advanced_text_tools import compute_regex_filtered_replacement
from ..document_fidelity import clipboard_paste_special_options, convert_clipboard_for_paste



class EditOpsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    # ---------- Edit helpers ----------
    def toggle_search_panel(self, checked: bool) -> None:
        if checked:
            self.show_search_panel()
        else:
            self.hide_search_panel()

    def edit_undo(self) -> None:
        self.text_edit.undo()

    def edit_redo(self) -> None:
        self.text_edit.redo()

    def edit_cut(self) -> None:
        self.text_edit.cut()

    def edit_copy(self) -> None:
        self.text_edit.copy()

    def edit_paste(self) -> None:
        self.text_edit.paste()

    def edit_paste_special(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData() if clipboard is not None else None
        if mime is None:
            return
        options = clipboard_paste_special_options(mime)
        choice, ok = QInputDialog.getItem(self, "Paste Special", "Paste as:", options, 0, False)
        if not ok or not choice:
            return

        if choice == "Keep Formatting":
            self.edit_paste()
            return

        converted = convert_clipboard_for_paste(mime, choice)
        if converted:
            self.text_edit.insert_text(converted)

    def edit_select_all(self) -> None:
        self.text_edit.select_all()

    def edit_delete(self) -> None:
        if self.text_edit.has_selection():
            self.text_edit.replace_selection("")
            return
        text = self.text_edit.get_text()
        idx = self.text_edit.cursor_index()
        if 0 <= idx < len(text):
            text = text[:idx] + text[idx + 1 :]
            self.text_edit.set_text(text)
            self.text_edit.set_selection_by_index(idx, idx)

    def edit_time_date(self) -> None:
        self.text_edit.insert_text(datetime.now().strftime("%H:%M %d/%m/%Y"))

    def _do_find(self, text: str, backward: bool = False) -> bool:
        if not text:
            return False
        source = self.text_edit.get_text()
        case_sensitive = bool(getattr(self, "search_case_checkbox", None) and self.search_case_checkbox.isChecked())
        haystack = source if case_sensitive else source.lower()
        needle = text if case_sensitive else text.lower()
        sel_range = self.text_edit.selection_range()
        if sel_range:
            start_index = self.text_edit.index_from_line_col(sel_range[2], sel_range[3])
        else:
            start_index = self.text_edit.cursor_index()
        if backward:
            found = haystack.rfind(needle, 0, start_index)
        else:
            found = haystack.find(needle, start_index)
        if found == -1:
            found = haystack.rfind(needle) if backward else haystack.find(needle)
        if found == -1:
            return False
        self.text_edit.set_selection_by_index(found, found + len(text))
        return True

    def edit_find(self) -> None:
        self.show_search_panel()

    def edit_find_next(self) -> None:
        if hasattr(self, "search_toolbar") and self.search_toolbar.isVisible():
            text = self.search_input.text().strip()
            if text:
                self.last_search_text = text
        if not self.last_search_text:
            self.edit_find()
            return
        if not self._do_find(self.last_search_text, backward=False):
            QMessageBox.information(self, "Pypad", f'Cannot find "{self.last_search_text}".')

    def edit_find_previous(self) -> None:
        if hasattr(self, "search_toolbar") and self.search_toolbar.isVisible():
            text = self.search_input.text().strip()
            if text:
                self.last_search_text = text
        if not self.last_search_text:
            self.edit_find()
            return
        if not self._do_find(self.last_search_text, backward=True):
            QMessageBox.information(self, "Pypad", f'Cannot find "{self.last_search_text}".')

    def edit_replace(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QGridLayout

        class ReplaceDialog(QDialog):
            def __init__(self, parent=None, last_search: str | None = None) -> None:
                super().__init__(parent)
                self.setWindowTitle("Replace")
                self.find_edit = QLineEdit(self)
                self.replace_edit = QLineEdit(self)

                if last_search:
                    self.find_edit.setText(last_search)

                layout = QGridLayout(self)
                layout.addWidget(QLabel("Find what:"), 0, 0)
                layout.addWidget(self.find_edit, 0, 1)
                layout.addWidget(QLabel("Replace with:"), 1, 0)
                layout.addWidget(self.replace_edit, 1, 1)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                    Qt.Horizontal,
                    self,
                )
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons, 2, 0, 1, 2)

            def get_values(self) -> tuple[str, str]:
                return self.find_edit.text(), self.replace_edit.text()

        dlg = ReplaceDialog(self, self.last_search_text)
        if dlg.exec() != QDialog.Accepted:
            return

        find_text, replace_text = dlg.get_values()
        if not find_text:
            return

        self.last_search_text = find_text
        self.update_action_states()

        if self.text_edit.has_selection() and self.text_edit.selected_text() == find_text:
            self.text_edit.replace_selection(replace_text)

        replaced_any = False
        while self._do_find(find_text, backward=False):
            if self.text_edit.has_selection():
                self.text_edit.replace_selection(replace_text)
                replaced_any = True

        if not replaced_any:
            QMessageBox.information(self, "Pypad", f'Cannot find "{find_text}".')

    def edit_regex_replace_preview(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QGridLayout

        class RegexReplaceDialog(QDialog):
            def __init__(self, parent=None, seed: str | None = None, has_selection: bool = False) -> None:
                super().__init__(parent)
                self.setWindowTitle("Regex Replace Preview")
                self.resize(780, 520)
                self.find_edit = QLineEdit(self)
                self.replace_edit = QLineEdit(self)
                self.case_checkbox = QCheckBox("Match case", self)
                self.multiline_checkbox = QCheckBox("Multiline (^ and $ per line)", self)
                self.selection_only_checkbox = QCheckBox("Selection only", self)
                self.selection_only_checkbox.setEnabled(has_selection)
                self.selection_only_checkbox.setChecked(has_selection)
                self.preview = QTextEdit(self)
                self.preview.setReadOnly(True)
                self.preview.setPlaceholderText("Preview will appear here.")
                self.preview_btn = QPushButton("Preview", self)
                self.apply_btn = QPushButton("Apply", self)
                self.apply_btn.setEnabled(False)

                if seed:
                    self.find_edit.setText(seed)

                layout = QGridLayout(self)
                layout.addWidget(QLabel("Find regex:"), 0, 0)
                layout.addWidget(self.find_edit, 0, 1)
                layout.addWidget(QLabel("Replace with:"), 1, 0)
                layout.addWidget(self.replace_edit, 1, 1)
                layout.addWidget(self.case_checkbox, 2, 0, 1, 2)
                layout.addWidget(self.multiline_checkbox, 3, 0, 1, 2)
                layout.addWidget(self.selection_only_checkbox, 4, 0, 1, 2)
                layout.addWidget(self.preview, 5, 0, 1, 2)
                button_row = QDialogButtonBox(self)
                button_row.addButton(self.preview_btn, QDialogButtonBox.ActionRole)
                button_row.addButton(self.apply_btn, QDialogButtonBox.AcceptRole)
                button_row.addButton(QDialogButtonBox.Cancel)
                layout.addWidget(button_row, 6, 0, 1, 2)
                self.preview_btn.clicked.connect(self.preview_requested)
                self.apply_btn.clicked.connect(self.accept)
                button_row.rejected.connect(self.reject)
                self._last_regex: re.Pattern[str] | None = None

            def _build_flags(self) -> int:
                flags = 0 if self.case_checkbox.isChecked() else re.IGNORECASE
                if self.multiline_checkbox.isChecked():
                    flags |= re.MULTILINE
                return flags

            def preview_requested(self) -> None:
                pattern = self.find_edit.text()
                repl = self.replace_edit.text()
                source = self._source_text_for_preview()
                if not pattern:
                    self.preview.setPlainText("Enter a regex pattern.")
                    self.apply_btn.setEnabled(False)
                    return
                try:
                    rx = re.compile(pattern, self._build_flags())
                except re.error as exc:
                    self.preview.setPlainText(f"Regex error:\n{exc}")
                    self.apply_btn.setEnabled(False)
                    return
                matches = list(rx.finditer(source))
                if not matches:
                    self.preview.setPlainText("No matches.")
                    self.apply_btn.setEnabled(False)
                    self._last_regex = rx
                    return
                lines: list[str] = [f"Matches: {len(matches)}", ""]
                for idx, match in enumerate(matches[:150], start=1):
                    start = match.start()
                    line_no = source.count("\n", 0, start) + 1
                    line_start = source.rfind("\n", 0, start)
                    col_no = (start - line_start) if line_start >= 0 else start + 1
                    original = match.group(0)
                    try:
                        replaced = match.expand(repl)
                    except re.error as exc:
                        self.preview.setPlainText(f"Replacement expression error:\n{exc}")
                        self.apply_btn.setEnabled(False)
                        return
                    lines.append(f"{idx}. Ln {line_no}, Col {col_no}")
                    lines.append(f"   - {original!r}")
                    lines.append(f"   + {replaced!r}")
                if len(matches) > 150:
                    lines.append("")
                    lines.append(f"... {len(matches) - 150} more matches")
                self.preview.setPlainText("\n".join(lines))
                self.apply_btn.setEnabled(True)
                self._last_regex = rx

            def _source_text_for_preview(self) -> str:
                if self.selection_only_checkbox.isChecked():
                    return self.parent().text_edit.selected_text()  # type: ignore[union-attr]
                return self.parent().text_edit.get_text()  # type: ignore[union-attr]

        has_selection = self.text_edit.has_selection()
        dlg = RegexReplaceDialog(self, self.last_search_text, has_selection=has_selection)
        if dlg.exec() != QDialog.Accepted:
            return

        pattern = dlg.find_edit.text()
        replacement = dlg.replace_edit.text()
        if not pattern:
            return
        try:
            rx = re.compile(pattern, dlg._build_flags())
        except re.error as exc:
            QMessageBox.warning(self, "Regex Replace Preview", f"Regex error:\n{exc}")
            return

        selection_only = dlg.selection_only_checkbox.isChecked()
        if selection_only and self.text_edit.has_selection():
            source = self.text_edit.selected_text()
            replaced, count = rx.subn(replacement, source)
            if count:
                self.text_edit.replace_selection(replaced)
                self.show_status_message(f"Regex replaced {count} match(es) in selection.", 3000)
            else:
                QMessageBox.information(self, "Regex Replace Preview", "No matches in selection.")
            return

        source = self.text_edit.get_text()
        replaced, count = rx.subn(replacement, source)
        if count:
            self.text_edit.set_text(replaced)
            self.text_edit.set_modified(True)
            self.show_status_message(f"Regex replaced {count} match(es) in document.", 3000)
        else:
            QMessageBox.information(self, "Regex Replace Preview", "No matches in document.")

    def edit_regex_filter_preview(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QGridLayout

        class RegexFilterDialog(QDialog):
            def __init__(self, parent=None, seed: str | None = None, has_selection: bool = False) -> None:
                super().__init__(parent)
                self.setWindowTitle("Regex Include/Exclude Preview")
                self.resize(820, 560)
                self.find_edit = QLineEdit(self)
                self.replace_edit = QLineEdit(self)
                self.include_edit = QLineEdit(self)
                self.exclude_edit = QLineEdit(self)
                self.case_checkbox = QCheckBox("Match case", self)
                self.multiline_checkbox = QCheckBox("Multiline (^ and $ per line)", self)
                self.selection_only_checkbox = QCheckBox("Selection only", self)
                self.selection_only_checkbox.setEnabled(has_selection)
                self.selection_only_checkbox.setChecked(has_selection)
                self.preview = QTextEdit(self)
                self.preview.setReadOnly(True)
                self.preview_btn = QPushButton("Preview", self)
                self.apply_btn = QPushButton("Apply", self)
                self.apply_btn.setEnabled(False)

                if seed:
                    self.find_edit.setText(seed)
                self.include_edit.setPlaceholderText("Optional: only process matches on lines matching this regex")
                self.exclude_edit.setPlaceholderText("Optional: skip matches on lines matching this regex")

                layout = QGridLayout(self)
                layout.addWidget(QLabel("Find regex:"), 0, 0)
                layout.addWidget(self.find_edit, 0, 1)
                layout.addWidget(QLabel("Replace with:"), 1, 0)
                layout.addWidget(self.replace_edit, 1, 1)
                layout.addWidget(QLabel("Include line regex:"), 2, 0)
                layout.addWidget(self.include_edit, 2, 1)
                layout.addWidget(QLabel("Exclude line regex:"), 3, 0)
                layout.addWidget(self.exclude_edit, 3, 1)
                layout.addWidget(self.case_checkbox, 4, 0, 1, 2)
                layout.addWidget(self.multiline_checkbox, 5, 0, 1, 2)
                layout.addWidget(self.selection_only_checkbox, 6, 0, 1, 2)
                layout.addWidget(self.preview, 7, 0, 1, 2)
                buttons = QDialogButtonBox(self)
                buttons.addButton(self.preview_btn, QDialogButtonBox.ActionRole)
                buttons.addButton(self.apply_btn, QDialogButtonBox.AcceptRole)
                buttons.addButton(QDialogButtonBox.Cancel)
                layout.addWidget(buttons, 8, 0, 1, 2)
                self.preview_btn.clicked.connect(self.preview_requested)
                self.apply_btn.clicked.connect(self.accept)
                buttons.rejected.connect(self.reject)

            def _flags(self) -> int:
                flags = 0 if self.case_checkbox.isChecked() else re.IGNORECASE
                if self.multiline_checkbox.isChecked():
                    flags |= re.MULTILINE
                return flags

            def _source_text(self) -> str:
                if self.selection_only_checkbox.isChecked():
                    return self.parent().text_edit.selected_text()  # type: ignore[union-attr]
                return self.parent().text_edit.get_text()  # type: ignore[union-attr]

            def preview_requested(self) -> None:
                pattern = self.find_edit.text()
                source = self._source_text()
                if not pattern:
                    self.preview.setPlainText("Enter a regex pattern.")
                    self.apply_btn.setEnabled(False)
                    return
                try:
                    result = compute_regex_filtered_replacement(
                        source,
                        pattern,
                        self.replace_edit.text(),
                        flags=self._flags(),
                        include_pattern=self.include_edit.text(),
                        exclude_pattern=self.exclude_edit.text(),
                        max_preview_rows=180,
                    )
                except re.error as exc:
                    self.preview.setPlainText(f"Regex error:\n{exc}")
                    self.apply_btn.setEnabled(False)
                    return
                if result.total_matches <= 0:
                    self.preview.setPlainText("No matches.")
                    self.apply_btn.setEnabled(False)
                    return
                lines: list[str] = [
                    f"Matches: {result.total_matches}",
                    f"After include/exclude filters: {result.filtered_matches}",
                    "",
                ]
                lines.extend(result.preview_lines)
                if result.filtered_matches > 180:
                    lines.append("")
                    lines.append(f"... {result.filtered_matches - 180} more filtered match(es)")
                self.preview.setPlainText("\n".join(lines))
                self.apply_btn.setEnabled(result.filtered_matches > 0)

        has_selection = self.text_edit.has_selection()
        dlg = RegexFilterDialog(self, self.last_search_text, has_selection=has_selection)
        if dlg.exec() != QDialog.Accepted:
            return
        pattern = dlg.find_edit.text()
        if not pattern:
            return
        selection_only = dlg.selection_only_checkbox.isChecked()
        source = self.text_edit.selected_text() if selection_only and self.text_edit.has_selection() else self.text_edit.get_text()
        try:
            result = compute_regex_filtered_replacement(
                source,
                pattern,
                dlg.replace_edit.text(),
                flags=dlg._flags(),
                include_pattern=dlg.include_edit.text(),
                exclude_pattern=dlg.exclude_edit.text(),
            )
        except re.error as exc:
            QMessageBox.warning(self, "Regex Include/Exclude Preview", f"Regex error:\n{exc}")
            return
        if result.filtered_matches <= 0:
            QMessageBox.information(self, "Regex Include/Exclude Preview", "No filtered matches to apply.")
            return
        if selection_only and self.text_edit.has_selection():
            self.text_edit.replace_selection(result.replaced_text)
            self.text_edit.set_modified(True)
            self.show_status_message(
                f"Regex replaced {result.filtered_matches} filtered match(es) in selection.",
                3000,
            )
            return
        self.text_edit.set_text(result.replaced_text)
        self.text_edit.set_modified(True)
        self.show_status_message(
            f"Regex replaced {result.filtered_matches} filtered match(es) in document.",
            3000,
        )

    def edit_search_bing(self) -> None:
        text = self.text_edit.selected_text() or (self.last_search_text or "")
        if not text:
            QMessageBox.information(self, "Pypad", "Please select some text or use Find first.")
            return
        url = f"https://www.bing.com/search?q={quote_plus(text)}"
        webbrowser.open(url)

    def show_search_panel(self) -> None:
        if not hasattr(self, "search_toolbar"):
            return
        self.settings["show_find_panel"] = True
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        if hasattr(self, "_layout_top_toolbars"):
            self._layout_top_toolbars()
        self.search_toolbar.show()
        if hasattr(self, "search_panel_action"):
            self.search_panel_action.blockSignals(True)
            self.search_panel_action.setChecked(True)
            self.search_panel_action.blockSignals(False)
        current = self.text_edit.selected_text() or (self.last_search_text or "")
        if current and not self.search_input.text():
            self.search_input.setText(current)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._on_search_text_changed()

    def hide_search_panel(self) -> None:
        if not hasattr(self, "search_toolbar"):
            return
        self.settings["show_find_panel"] = False
        if hasattr(self, "save_settings_to_disk"):
            self.save_settings_to_disk()
        if hasattr(self, "_layout_top_toolbars"):
            self._layout_top_toolbars()
        self.search_toolbar.hide()
        if hasattr(self, "search_panel_action"):
            self.search_panel_action.blockSignals(True)
            self.search_panel_action.setChecked(False)
            self.search_panel_action.blockSignals(False)
        self._clear_search_highlights()

    def _on_search_text_changed(self) -> None:
        tab = self.active_tab()
        if tab is not None and tab.large_file:
            self._clear_search_highlights()
            self.update_action_states()
            return
        text = self.search_input.text().strip()
        if text:
            self.last_search_text = text
        if not text or not self.search_highlight_checkbox.isChecked():
            self._clear_search_highlights()
            self.update_action_states()
            return
        self._apply_search_highlights(text)
        self.update_action_states()

    def _clear_search_highlights(self) -> None:
        tab = self.active_tab()
        if tab is not None:
            if not tab.text_edit.is_scintilla:
                tab.text_edit.widget.setExtraSelections([])

    def _apply_search_highlights(self, query: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if tab.text_edit.is_scintilla:
            return
        flags = QTextDocument.FindFlag()
        if self.search_case_checkbox.isChecked():
            flags |= QTextDocument.FindCaseSensitively

        selections: list[QTextEdit.ExtraSelection] = []
        doc = tab.text_edit.widget.document()
        cursor = QTextCursor(doc)
        cursor = doc.find(query, cursor, flags)
        while not cursor.isNull():
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor("#f7e36d"))
            selections.append(selection)
            cursor = doc.find(query, cursor, flags)
        tab.text_edit.widget.setExtraSelections(selections)

