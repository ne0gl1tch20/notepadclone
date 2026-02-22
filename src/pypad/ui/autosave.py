from __future__ import annotations

import json
import uuid
import difflib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from ..logging_utils import get_logger

_LOGGER = get_logger(__name__)


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
        _LOGGER.debug("AutoSaveStore initialized base_dir=%s index=%s", self.base_dir, self.index_path)

    def load(self) -> None:
        _LOGGER.debug("AutoSaveStore.load start index=%s", self.index_path)
        if not self.index_path.exists():
            self.entries = {}
            _LOGGER.debug("AutoSaveStore.load no index file; entries reset")
            return
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            self.entries = {}
            _LOGGER.exception("AutoSaveStore.load failed to parse index=%s", self.index_path)
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
                if entry.autosave_path and not Path(entry.autosave_path).exists():
                    continue
                entries[entry.autosave_id] = entry
            except Exception:
                continue
        self.entries = entries
        _LOGGER.debug("AutoSaveStore.load complete entries=%d", len(self.entries))

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
        _LOGGER.debug("AutoSaveStore.save wrote index=%s entries=%d", self.index_path, len(data))

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
        _LOGGER.debug(
            "AutoSaveStore.upsert id=%s file=%s original=%s title=%s",
            autosave_id,
            autosave_path,
            original_path,
            title,
        )

    def remove(self, autosave_id: str) -> None:
        self.entries.pop(autosave_id, None)
        _LOGGER.debug("AutoSaveStore.remove id=%s remaining=%d", autosave_id, len(self.entries))

    def prune_older_than_days(self, days: int) -> int:
        days = max(1, int(days))
        _LOGGER.debug("AutoSaveStore.prune_older_than_days start days=%d entries=%d", days, len(self.entries))
        now = datetime.now()
        removed = 0
        for autosave_id, entry in list(self.entries.items()):
            stamp = str(entry.saved_at or "").strip()
            if not stamp:
                continue
            try:
                when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if (now - when).days < days:
                continue
            try:
                path = Path(entry.autosave_path)
                if path.exists():
                    path.unlink()
            except Exception:
                pass
            self.entries.pop(autosave_id, None)
            removed += 1
            _LOGGER.debug("AutoSaveStore.pruned id=%s autosave_path=%s", autosave_id, entry.autosave_path)
        _LOGGER.debug("AutoSaveStore.prune_older_than_days complete removed=%d remaining=%d", removed, len(self.entries))
        return removed


class AutoSaveRecoveryDialog(QDialog):
    def __init__(self, parent, entries: list[AutoSaveEntry]) -> None:
        owner = parent
        use_top_level = bool(owner is not None and hasattr(owner, "isVisible") and not owner.isVisible())
        super().__init__(None if use_top_level else owner)
        # During startup recovery (before main window is shown), use a top-level dialog so Windows shows a taskbar button.
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowModality(Qt.ApplicationModal if use_top_level else Qt.WindowModal)
        self.setWindowTitle("Recover Unsaved Notes")
        self.resize(960, 540)
        self._theme_parent = owner
        if owner is not None and hasattr(owner, "windowIcon"):
            try:
                self.setWindowIcon(owner.windowIcon())
            except Exception:
                pass
        self._selected_ids: list[str] = []
        self._selected_action: str = "open"
        self._path_by_id = {entry.autosave_id: entry.autosave_path for entry in entries}
        self._original_by_id = {entry.autosave_id: entry.original_path for entry in entries}

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Recovered items", self))
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        left.addWidget(self.list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Preview", self))
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        right.addWidget(self.preview)
        right.addWidget(QLabel("Diff vs current file", self))
        self.diff_view = QTextEdit(self)
        self.diff_view.setReadOnly(True)
        right.addWidget(self.diff_view)

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
        self._apply_theme_from_parent()

    def _apply_theme_from_parent(self) -> None:
        parent = getattr(self, "_theme_parent", None) or self.parentWidget()
        settings = getattr(parent, "settings", {}) if parent is not None else {}
        dark = bool(settings.get("dark_mode", False))
        accent = str(settings.get("accent_color", "#4a90e2") or "#4a90e2")
        if not accent.startswith("#"):
            accent = f"#{accent}"
        if len(accent) not in (4, 7):
            accent = "#4a90e2"
        window_bg = "#202124" if dark else "#f5f7fb"
        panel_bg = "#25272b" if dark else "#ffffff"
        text_fg = "#e8eaed" if dark else "#111111"
        border = "#3c4043" if dark else "#c7ccd4"
        muted = "#9aa0a6" if dark else "#5f6368"
        selected_bg = accent
        selected_fg = "#ffffff"
        btn_bg = "#303134" if dark else "#eef2f8"
        btn_hover = accent
        btn_border = border
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {window_bg};
                color: {text_fg};
            }}
            QLabel {{
                color: {text_fg};
            }}
            QListWidget, QTextEdit {{
                background: {panel_bg};
                color: {text_fg};
                border: 1px solid {border};
                selection-background-color: {selected_bg};
                selection-color: {selected_fg};
            }}
            QListWidget::item:selected {{
                background: {selected_bg};
                color: {selected_fg};
            }}
            QPushButton {{
                background: {btn_bg};
                color: {text_fg};
                border: 1px solid {btn_border};
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
                color: #ffffff;
                border: 1px solid {accent};
            }}
            QPushButton:disabled {{
                color: {muted};
            }}
            """
        )

    def _populate(self, entries: list[AutoSaveEntry]) -> None:
        for entry in entries:
            title = entry.title or "Untitled"
            label = f"{title} - {entry.saved_at}"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, entry.autosave_id)

    def _update_preview(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            self.diff_view.clear()
            return
        autosave_id = current.data(Qt.UserRole)
        autosave_path = self._path_by_id.get(autosave_id, "")
        if not autosave_path:
            self.preview.clear()
            self.diff_view.clear()
            return
        try:
            text = Path(autosave_path).read_text(encoding="utf-8")
        except Exception:
            text = ""
        self.preview.setPlainText(text)
        original_path = str(self._original_by_id.get(autosave_id, "") or "").strip()
        if original_path and Path(original_path).exists():
            try:
                original = Path(original_path).read_text(encoding="utf-8")
            except Exception:
                original = ""
            diff_lines = difflib.unified_diff(
                original.splitlines(),
                text.splitlines(),
                fromfile=original_path,
                tofile=f"Recovered ({autosave_id})",
                lineterm="",
            )
            self.diff_view.setPlainText("\n".join(diff_lines) or "(No visible diff)")
        else:
            self.diff_view.setPlainText("(No on-disk file to compare)")

    def _accept_open(self) -> None:
        picked = self.list_widget.selectedItems()
        if not picked:
            current = self.list_widget.currentItem()
            if current is not None:
                picked = [current]
        if not picked:
            return
        self._selected_action = "open"
        self._selected_ids = [item.data(Qt.UserRole) for item in picked if item.data(Qt.UserRole)]
        self.accept()

    def _accept_discard(self) -> None:
        picked = self.list_widget.selectedItems()
        if not picked:
            current = self.list_widget.currentItem()
            if current is not None:
                picked = [current]
        if not picked:
            return
        self._selected_action = "discard"
        self._selected_ids = [item.data(Qt.UserRole) for item in picked if item.data(Qt.UserRole)]
        self.accept()

    @property
    def selected_ids(self) -> list[str]:
        return self._selected_ids

    @property
    def selected_action(self) -> str:
        return self._selected_action
