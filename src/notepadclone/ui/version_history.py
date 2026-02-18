from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import difflib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


@dataclass
class VersionEntry:
    timestamp: str
    text: str
    label: str


class VersionHistory:
    def __init__(self, max_entries: int = 50) -> None:
        self.max_entries = max(1, int(max_entries))
        self.entries: list[VersionEntry] = []

    def add_snapshot(self, text: str, label: str = "Snapshot") -> None:
        if self.entries and self.entries[-1].text == text:
            return
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.entries.append(VersionEntry(timestamp=stamp, text=text, label=label))
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]


class VersionHistoryDialog(QDialog):
    def __init__(self, parent, history: VersionHistory, current_text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Version History")
        self.resize(820, 500)
        self._selected_text: str | None = None

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Snapshots", self))
        self.list_widget = QListWidget(self)
        left.addWidget(self.list_widget)

        right = QVBoxLayout()
        right.addWidget(QLabel("Preview", self))
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        right.addWidget(self.preview)

        right.addWidget(QLabel("Diff (selected vs current)", self))
        self.diff_view = QTextEdit(self)
        self.diff_view.setReadOnly(True)
        right.addWidget(self.diff_view)

        layout.addLayout(left, 1)
        layout.addLayout(right, 2)

        button_row = QHBoxLayout()
        self.restore_btn = QPushButton("Restore Selected", self)
        self.restore_btn.setEnabled(False)
        self.cancel_btn = QPushButton("Cancel", self)
        button_row.addWidget(self.restore_btn)
        button_row.addWidget(self.cancel_btn)
        right.addLayout(button_row)

        self._current_text = current_text
        self._populate(history, current_text)
        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.restore_btn.clicked.connect(self._accept_restore)
        self.cancel_btn.clicked.connect(self.reject)

    def _populate(self, history: VersionHistory, current_text: str) -> None:
        current_item = QListWidgetItem("Current (unsaved)", self.list_widget)
        current_item.setData(Qt.UserRole, current_text)
        self.list_widget.addItem(current_item)
        for entry in reversed(history.entries):
            label = f"{entry.timestamp} - {entry.label}"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, entry.text)
            self.list_widget.addItem(item)

    def _update_preview(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            self.restore_btn.setEnabled(False)
            return
        text = current.data(Qt.UserRole) or ""
        self.preview.setPlainText(text)
        diff_lines = difflib.unified_diff(
            self._current_text.splitlines(),
            text.splitlines(),
            fromfile="Current",
            tofile="Selected",
            lineterm="",
        )
        self.diff_view.setPlainText("\n".join(diff_lines))
        self.restore_btn.setEnabled(True)

    def _accept_restore(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._selected_text = item.data(Qt.UserRole) or ""
        self.accept()

    @property
    def selected_text(self) -> str | None:
        return self._selected_text
