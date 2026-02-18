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
            QMessageBox.information(self, "Notepad", f'Cannot find "{self.last_search_text}".')

    def edit_find_previous(self) -> None:
        if hasattr(self, "search_toolbar") and self.search_toolbar.isVisible():
            text = self.search_input.text().strip()
            if text:
                self.last_search_text = text
        if not self.last_search_text:
            self.edit_find()
            return
        if not self._do_find(self.last_search_text, backward=True):
            QMessageBox.information(self, "Notepad", f'Cannot find "{self.last_search_text}".')

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
            QMessageBox.information(self, "Notepad", f'Cannot find "{find_text}".')

    def edit_search_bing(self) -> None:
        text = self.text_edit.selected_text() or (self.last_search_text or "")
        if not text:
            QMessageBox.information(self, "Notepad", "Please select some text or use Find first.")
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

