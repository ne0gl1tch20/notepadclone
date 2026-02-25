from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


@dataclass(frozen=True)
class PaletteItem:
    label: str
    section: str
    action: QAction
    shortcut: str = ""
    keywords: str = ""


def _score(query: str, candidate: str) -> int:
    if not query:
        return 0
    q = query.lower().strip()
    c = candidate.lower()
    if q == c:
        return 100
    if c.startswith(q):
        return 80
    if q in c:
        return 60
    parts = [p for p in q.split() if p]
    if parts and all(p in c for p in parts):
        return 40
    return -1


class CommandPaletteDialog(QDialog):
    def __init__(self, parent, items: list[PaletteItem], *, initial_query: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.resize(560, 440)
        self._items = items
        self.selected_action: QAction | None = None

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Search:", self))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Type a command...")
        top.addWidget(self.search_edit, 1)
        layout.addLayout(top)

        self.list_widget = QListWidget(self)
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.run_btn = QPushButton("Run", self)
        self.cancel_btn = QPushButton("Cancel", self)
        buttons.addWidget(self.run_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.search_edit.textChanged.connect(self._refresh_list)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        self.run_btn.clicked.connect(self._accept_selected)
        self.cancel_btn.clicked.connect(self.reject)

        self._refresh_list()
        if initial_query:
            self.search_edit.setText(initial_query)
        self.search_edit.setFocus()

    def _refresh_list(self) -> None:
        query = self.search_edit.text().strip()
        self.list_widget.clear()
        scored: list[tuple[int, PaletteItem]] = []
        for item in self._items:
            corpus = f"{item.section} {item.label} {item.shortcut} {item.keywords}".strip()
            s = _score(query, corpus)
            if query and s < 0:
                continue
            scored.append((s, item))
        scored.sort(key=lambda row: (-row[0], row[1].section.lower(), row[1].label.lower()))
        for _score_value, item in scored[:300]:
            suffix = f" [{item.shortcut}]" if item.shortcut else ""
            row = QListWidgetItem(f"{item.label}{suffix}    [{item.section}]")
            row.setData(Qt.ItemDataRole.UserRole, item.action)
            self.list_widget.addItem(row)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _accept_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            self.reject()
            return
        action = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(action, QAction):
            self.selected_action = action
            self.accept()
            return
        self.reject()
