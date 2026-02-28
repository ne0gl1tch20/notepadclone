from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from pypad.ui.editor.editor_tab import EditorTab
from pypad.ui.theme.dialog_theme import apply_dialog_theme_from_window


class MiscWindowTabsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

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
        apply_dialog_theme_from_window(self, dialog)

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
