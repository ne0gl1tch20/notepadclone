from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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
class AutoSaveEntry:
    autosave_id: str
    autosave_path: str
    original_path: str
    title: str
    saved_at: str


class AutoSaveStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.base_dir / "autosave_index.json"
        self.entries: dict[str, AutoSaveEntry] = {}

    def load(self) -> None:
        if not self.index_path.exists():
            self.entries = {}
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            self.entries = {}
            return
        entries = {}
        for item in data:
            try:
                entry = AutoSaveEntry(
                    autosave_id=item["autosave_id"],
                    autosave_path=item["autosave_path"],
                    original_path=item.get("original_path", ""),
                    title=item.get("title", "Untitled"),
                    saved_at=item.get("saved_at", ""),
                )
                entries[entry.autosave_id] = entry
            except Exception:
                continue
        self.entries = entries

    def save(self) -> None:
        data = [
            {
                "autosave_id": e.autosave_id,
                "autosave_path": e.autosave_path,
                "original_path": e.original_path,
                "title": e.title,
                "saved_at": e.saved_at,
            }
            for e in self.entries.values()
        ]
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def new_id(self) -> str:
        return str(uuid.uuid4())

    def autosave_file(self, autosave_id: str) -> Path:
        return self.base_dir / f"{autosave_id}.autosave.txt"

    def upsert(self, autosave_id: str, autosave_path: str, original_path: str, title: str) -> None:
        saved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.entries[autosave_id] = AutoSaveEntry(
            autosave_id=autosave_id,
            autosave_path=autosave_path,
            original_path=original_path,
            title=title,
            saved_at=saved_at,
        )

    def remove(self, autosave_id: str) -> None:
        self.entries.pop(autosave_id, None)


class AutoSaveRecoveryDialog(QDialog):
    def __init__(self, parent, entries: list[AutoSaveEntry]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recover Unsaved Notes")
        self.resize(820, 480)
        self._selected_ids: list[str] = []
        self._selected_action: str = "open"
        self._path_by_id = {entry.autosave_id: entry.autosave_path for entry in entries}

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Recovered items", self))
        self.list_widget = QListWidget(self)
        left.addWidget(self.list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Preview", self))
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        right.addWidget(self.preview)

        button_row = QHBoxLayout()
        self.open_btn = QPushButton("Open Selected", self)
        self.discard_btn = QPushButton("Discard Selected", self)
        self.cancel_btn = QPushButton("Close", self)
        button_row.addWidget(self.open_btn)
        button_row.addWidget(self.discard_btn)
        button_row.addWidget(self.cancel_btn)
        right.addLayout(button_row)

        layout.addLayout(right, 3)

        self._populate(entries)
        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.open_btn.clicked.connect(self._accept_open)
        self.discard_btn.clicked.connect(self._accept_discard)
        self.cancel_btn.clicked.connect(self.reject)

    def _populate(self, entries: list[AutoSaveEntry]) -> None:
        for entry in entries:
            title = entry.title or "Untitled"
            label = f"{title} - {entry.saved_at}"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, entry.autosave_id)

    def _update_preview(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            return
        autosave_id = current.data(Qt.UserRole)
        autosave_path = self._path_by_id.get(autosave_id, "")
        if not autosave_path:
            self.preview.clear()
            return
        try:
            text = Path(autosave_path).read_text(encoding="utf-8")
        except Exception:
            text = ""
        self.preview.setPlainText(text)

    def _accept_open(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._selected_action = "open"
        self._selected_ids = [item.data(Qt.UserRole)]
        self.accept()

    def _accept_discard(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._selected_action = "discard"
        self._selected_ids = [item.data(Qt.UserRole)]
        self.accept()

    @property
    def selected_ids(self) -> list[str]:
        return self._selected_ids

    @property
    def selected_action(self) -> str:
        return self._selected_action
