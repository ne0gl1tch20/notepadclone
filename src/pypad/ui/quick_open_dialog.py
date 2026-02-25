from __future__ import annotations

from dataclasses import dataclass
import ast
import os
import re
from typing import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
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
from .theme_tokens import build_quick_open_qss, build_tokens_from_settings


@dataclass(frozen=True)
class QuickOpenEntry:
    kind: str  # file | open_tab | symbol
    label: str
    subtitle: str
    path: str | None = None
    tab_index: int | None = None
    source: str = ""
    line: int | None = None  # 1-based for symbol rows


@dataclass(frozen=True)
class QuickOpenQuery:
    needle: str
    line: int | None = None  # 1-based
    col: int | None = None   # 1-based
    current_tab_only: bool = False
    command_query: str | None = None
    symbol_query: str | None = None
    workspace_symbol_query: str | None = None
    workspace_symbol_file_filter: str | None = None
    workspace_symbol_name_query: str | None = None


def parse_quick_open_query(text: str) -> QuickOpenQuery:
    raw = str(text or "").strip()
    if not raw:
        return QuickOpenQuery(needle="")
    if raw.startswith(">"):
        return QuickOpenQuery(needle="", command_query=raw[1:].strip())
    if raw.startswith("@@"):
        q = raw[2:].strip()
        if " " in q:
            first, rest = q.split(None, 1)
            return QuickOpenQuery(
                needle="",
                workspace_symbol_query=q,
                workspace_symbol_file_filter=first.strip() or None,
                workspace_symbol_name_query=rest.strip() or None,
            )
        return QuickOpenQuery(needle="", workspace_symbol_query=q)
    if raw.lower().startswith("@w "):
        q = raw[3:].strip()
        if " " in q:
            first, rest = q.split(None, 1)
            return QuickOpenQuery(
                needle="",
                workspace_symbol_query=q,
                workspace_symbol_file_filter=first.strip() or None,
                workspace_symbol_name_query=rest.strip() or None,
            )
        return QuickOpenQuery(needle="", workspace_symbol_query=q)
    if raw.startswith("@"):
        return QuickOpenQuery(needle="", symbol_query=raw[1:].strip())

    line: int | None = None
    col: int | None = None
    current_tab_only = False
    needle = raw

    if raw.startswith(":"):
        parts = raw[1:].split(":")
        if parts and parts[0].isdigit():
            line = max(1, int(parts[0]))
            if len(parts) >= 2 and parts[1].isdigit():
                col = max(1, int(parts[1]))
            return QuickOpenQuery(needle="", line=line, col=col, current_tab_only=True)

    parts = raw.split(":")
    if len(parts) >= 2 and parts[-1].isdigit():
        if len(parts) >= 3 and parts[-2].isdigit():
            path_part = ":".join(parts[:-2]).strip()
            if path_part:
                needle = path_part
                line = max(1, int(parts[-2]))
                col = max(1, int(parts[-1]))
        else:
            path_part = ":".join(parts[:-1]).strip()
            if path_part:
                needle = path_part
                line = max(1, int(parts[-1]))

    return QuickOpenQuery(needle=needle, line=line, col=col, current_tab_only=current_tab_only)


def extract_symbol_rows(language: str, text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    lang = str(language or "").lower().strip()
    src = str(text or "")
    if not src:
        return rows
    if lang == "python":
        try:
            tree = ast.parse(src)
            for n in ast.walk(tree):
                if isinstance(n, ast.ClassDef):
                    rows.append((max(1, int(n.lineno)), f"class {n.name}"))
                if isinstance(n, ast.FunctionDef):
                    rows.append((max(1, int(n.lineno)), f"def {n.name}"))
                if hasattr(ast, "AsyncFunctionDef") and isinstance(n, ast.AsyncFunctionDef):  # py311/312 safe
                    rows.append((max(1, int(n.lineno)), f"async def {n.name}"))
        except Exception:
            pass
    if lang == "markdown":
        for i, ln in enumerate(src.splitlines(), start=1):
            if ln.strip().startswith("#"):
                rows.append((i, ln.strip()))
    if not rows:
        for i, ln in enumerate(src.splitlines(), start=1):
            s = ln.strip()
            if re.match(r"^(class|def|function)\s+\w+", s):
                rows.append((i, s))
    rows.sort(key=lambda row: (row[0], row[1].lower()))
    return rows[:500]


def score_quick_open_match(query: str, candidate: str) -> int:
    q = str(query or "").strip().lower()
    c = str(candidate or "").lower()
    if not q:
        return 0
    if q == c:
        return 120
    if c.startswith(q):
        return 95
    base = os.path.basename(c)
    if base.startswith(q):
        return 88
    if q in c:
        return 70
    tokens = [t for t in q.replace("\\", "/").split() if t]
    if tokens and all(t in c for t in tokens):
        return 45
    # simple ordered fuzzy subsequence
    idx = 0
    for ch in q:
        idx = c.find(ch, idx)
        if idx < 0:
            return -1
        idx += 1
    return 25


def split_workspace_symbol_scope(raw_query: str) -> tuple[str | None, str]:
    q = str(raw_query or "").strip()
    if not q:
        return None, ""
    if " " not in q:
        return None, q
    first, rest = q.split(None, 1)
    return (first.strip() or None), (rest.strip() or "")


class QuickOpenDialog(QDialog):
    def __init__(
        self,
        parent,
        items: list[QuickOpenEntry],
        *,
        current_tab_label: str = "",
        current_symbols: list[QuickOpenEntry] | None = None,
        workspace_symbols: list[QuickOpenEntry] | None = None,
        status_provider: Callable[[], str] | None = None,
        items_provider: Callable[[], list[QuickOpenEntry]] | None = None,
        current_symbols_provider: Callable[[], list[QuickOpenEntry]] | None = None,
        workspace_symbols_provider: Callable[[], list[QuickOpenEntry]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Open / Go to Anything")
        self.resize(760, 560)
        self._items = list(items)
        self._current_tab_label = str(current_tab_label or "").strip()
        self._current_symbols = list(current_symbols or [])
        self._workspace_symbols = list(workspace_symbols or [])
        self._status_provider = status_provider
        self._items_provider = items_provider
        self._current_symbols_provider = current_symbols_provider
        self._workspace_symbols_provider = workspace_symbols_provider
        self.selected_entry: QuickOpenEntry | None = None
        self.selected_line: int | None = None
        self.selected_col: int | None = None
        self.command_query: str | None = None
        self._mode_cycle = ["file", "symbol", "workspace_symbol", "command"]
        self._items_signature = 0
        self._current_symbols_signature = 0
        self._workspace_symbols_signature = 0

        self.setObjectName("quickOpenDialog")
        parent_settings = getattr(parent, "settings", {}) if parent is not None else {}
        self.setStyleSheet(build_quick_open_qss(build_tokens_from_settings(parent_settings if isinstance(parent_settings, dict) else {})))
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        header = QLabel("Quick Open / Go to Anything", self)
        header.setObjectName("quickOpenHeader")
        root.addWidget(header)
        top = QHBoxLayout()
        top.addWidget(QLabel("Open:", self))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(
            "file/path, :line[:col], @symbol, @@filepattern symbol, file.py:42, or >command"
        )
        top.addWidget(self.search_edit, 1)
        root.addLayout(top)

        self.list_widget = QListWidget(self)
        self.list_widget.setAlternatingRowColors(True)
        root.addWidget(self.list_widget, 1)

        help_label = QLabel(
            "Examples: report.txt, src/app.py:120, :55, @render, @@models save, >bookmark  |  Tab: file/symbol/workspace-symbol/command",
            self,
        )
        help_label.setObjectName("quickOpenHint")
        root.addWidget(help_label)
        self.status_label = QLabel("", self)
        self.status_label.setObjectName("quickOpenStatus")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        btns = QHBoxLayout()
        btns.addStretch(1)
        self.open_btn = QPushButton("Open", self)
        self.cancel_btn = QPushButton("Cancel", self)
        btns.addWidget(self.open_btn)
        btns.addWidget(self.cancel_btn)
        root.addLayout(btns)

        self.search_edit.textChanged.connect(self._refresh_list)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_current())
        self.open_btn.clicked.connect(self._accept_current)
        self.cancel_btn.clicked.connect(self.reject)
        self.search_edit.installEventFilter(self)
        self.list_widget.installEventFilter(self)

        self._refresh_list()
        self._items_signature = self._entries_signature(self._items)
        self._current_symbols_signature = self._entries_signature(self._current_symbols)
        self._workspace_symbols_signature = self._entries_signature(self._workspace_symbols)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(450)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start()
        self._refresh_status()
        self.search_edit.setFocus()

    def _refresh_status(self) -> None:
        self._poll_providers_and_refresh()
        if not callable(self._status_provider):
            self.status_label.setVisible(False)
            return
        text = str(self._status_provider() or "").strip()
        self.status_label.setVisible(bool(text))
        self.status_label.setText(text)

    @staticmethod
    def _entries_signature(entries: list[QuickOpenEntry]) -> int:
        # Lightweight content hash to detect updates even when counts are unchanged.
        acc = 1469598103934665603  # FNV offset basis (64-bit)
        for i, e in enumerate(entries[:5120]):
            token = (
                str(e.kind),
                str(e.label),
                str(e.subtitle),
                str(e.path or ""),
                int(e.tab_index or -1),
                str(e.source or ""),
                int(e.line or 0),
                i,
            )
            for part in token:
                text = str(part)
                for ch in text:
                    acc ^= ord(ch)
                    acc *= 1099511628211
                    acc &= 0xFFFFFFFFFFFFFFFF
        acc ^= len(entries)
        acc *= 1099511628211
        return acc & 0xFFFFFFFFFFFFFFFF

    def _poll_providers_and_refresh(self) -> None:
        changed = False
        if callable(self._items_provider):
            try:
                latest = list(self._items_provider() or [])
            except Exception:
                latest = self._items
            sig = self._entries_signature(latest)
            if sig != self._items_signature:
                self._items = latest
                self._items_signature = sig
                changed = True
        if callable(self._current_symbols_provider):
            try:
                latest = list(self._current_symbols_provider() or [])
            except Exception:
                latest = self._current_symbols
            sig = self._entries_signature(latest)
            if sig != self._current_symbols_signature:
                self._current_symbols = latest
                self._current_symbols_signature = sig
                changed = True
        if callable(self._workspace_symbols_provider):
            try:
                latest = list(self._workspace_symbols_provider() or [])
            except Exception:
                latest = self._workspace_symbols
            sig = self._entries_signature(latest)
            if sig != self._workspace_symbols_signature:
                self._workspace_symbols = latest
                self._workspace_symbols_signature = sig
                changed = True
        if changed:
            self._refresh_list()

    def _add_header_row(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setData(Qt.ItemDataRole.UserRole, ("header",))
        item.setForeground(Qt.GlobalColor.lightGray)
        self.list_widget.addItem(item)

    def _entry_row_text(self, entry: QuickOpenEntry, *, line_suffix: str = "") -> str:
        prefix = f"[{entry.source}] " if entry.source else ""
        text = f"{prefix}{entry.label}"
        if entry.subtitle:
            text += f" - {entry.subtitle}"
        if line_suffix:
            text += line_suffix
        return text

    def _set_mode_prefix(self, mode: str) -> None:
        text = self.search_edit.text()
        # Remove existing explicit mode prefixes first.
        stripped = text
        if stripped.startswith(">"):
            stripped = stripped[1:].lstrip()
        elif stripped.startswith("@@"):
            stripped = stripped[2:].lstrip()
        elif stripped.lower().startswith("@w "):
            stripped = stripped[3:].lstrip()
        elif stripped.startswith("@"):
            stripped = stripped[1:].lstrip()
        prefixes = {
            "file": "",
            "symbol": "@",
            "workspace_symbol": "@@",
            "command": ">",
        }
        new_text = f"{prefixes.get(mode, '')}{stripped}".strip() if prefixes.get(mode, "") else stripped
        self.search_edit.setText(new_text)
        self.search_edit.setFocus()

    def _current_mode(self) -> str:
        parsed = parse_quick_open_query(self.search_edit.text())
        if parsed.command_query is not None:
            return "command"
        if parsed.workspace_symbol_query is not None:
            return "workspace_symbol"
        if parsed.symbol_query is not None:
            return "symbol"
        return "file"

    def _toggle_mode(self, *, reverse: bool = False) -> bool:
        cur = self._current_mode()
        try:
            idx = self._mode_cycle.index(cur)
        except ValueError:
            idx = 0
        nxt = (idx - 1) % len(self._mode_cycle) if reverse else (idx + 1) % len(self._mode_cycle)
        self._set_mode_prefix(self._mode_cycle[nxt])
        return True

    def eventFilter(self, obj, event):  # type: ignore[override]
        if event.type() == QEvent.Type.KeyPress and obj in {self.search_edit, self.list_widget}:
            key = event.key()
            if key == Qt.Key.Key_Tab:
                return self._toggle_mode(reverse=False)
            if key == Qt.Key.Key_Backtab:
                return self._toggle_mode(reverse=True)
        return super().eventFilter(obj, event)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        parsed = parse_quick_open_query(self.search_edit.text())

        if parsed.command_query is not None:
            self._add_header_row("Command")
            label = parsed.command_query or "(all commands)"
            row = QListWidgetItem(f"Command Palette: {label}")
            row.setData(Qt.ItemDataRole.UserRole, ("command", parsed.command_query))
            self.list_widget.addItem(row)
            self.list_widget.setCurrentRow(0)
            return
        if parsed.symbol_query is not None:
            scored_symbols: list[tuple[int, QuickOpenEntry]] = []
            for entry in self._current_symbols:
                corpus = f"{entry.label} {entry.subtitle}".strip()
                score = score_quick_open_match(parsed.symbol_query or "", corpus)
                if parsed.symbol_query and score < 0:
                    continue
                scored_symbols.append((score, entry))
            scored_symbols.sort(key=lambda row: (-row[0], (row[1].line or 0), row[1].label.lower()))
            if scored_symbols:
                self._add_header_row("Symbols")
            for _, entry in scored_symbols[:300]:
                row = QListWidgetItem(f"[Symbol] {entry.label} - {entry.subtitle}")
                row.setData(Qt.ItemDataRole.UserRole, ("entry", entry, None, None))
                self.list_widget.addItem(row)
            if self.list_widget.count():
                self.list_widget.setCurrentRow(0)
            return
        if parsed.workspace_symbol_query is not None:
            file_scope = parsed.workspace_symbol_file_filter
            symbol_scope = parsed.workspace_symbol_name_query
            if symbol_scope is None:
                file_scope, symbol_scope = split_workspace_symbol_scope(parsed.workspace_symbol_query or "")
            scored_symbols: list[tuple[int, QuickOpenEntry]] = []
            for entry in self._workspace_symbols:
                if file_scope and score_quick_open_match(file_scope, entry.subtitle) < 0:
                    continue
                corpus = f"{entry.label} {entry.subtitle}".strip()
                score = score_quick_open_match(symbol_scope or "", corpus)
                if symbol_scope and score < 0:
                    continue
                if file_scope:
                    score += max(0, min(35, score_quick_open_match(file_scope, entry.subtitle)))
                scored_symbols.append((score, entry))
            scored_symbols.sort(key=lambda row: (-row[0], row[1].label.lower(), row[1].subtitle.lower()))
            if scored_symbols:
                self._add_header_row("Workspace Symbols")
            for _, entry in scored_symbols[:400]:
                row = QListWidgetItem(f"[Workspace Symbol] {entry.label} - {entry.subtitle}")
                row.setData(Qt.ItemDataRole.UserRole, ("entry", entry, None, None))
                self.list_widget.addItem(row)
            if self.list_widget.count():
                self.list_widget.setCurrentRow(0)
            return

        line_suffix = ""
        if parsed.line is not None:
            line_suffix = f"  (line {parsed.line}"
            if parsed.col is not None:
                line_suffix += f", col {parsed.col}"
            line_suffix += ")"

        if parsed.current_tab_only and self._current_tab_label:
            self._add_header_row("Current Tab")
            row = QListWidgetItem(f"Current Tab: {self._current_tab_label}{line_suffix}")
            row.setData(Qt.ItemDataRole.UserRole, ("current_tab", parsed.line, parsed.col))
            self.list_widget.addItem(row)
            self.list_widget.setCurrentRow(0)
            return

        scored: list[tuple[int, QuickOpenEntry]] = []
        for entry in self._items:
            corpus = f"{entry.label} {entry.subtitle} {entry.source}".strip()
            score = score_quick_open_match(parsed.needle, corpus)
            if parsed.needle and score < 0:
                continue
            scored.append((score, entry))
        scored.sort(key=lambda row: (-row[0], row[1].label.lower(), row[1].subtitle.lower()))

        grouped_order = ["Open Tab", "Recent", "Workspace"]
        grouped: dict[str, list[QuickOpenEntry]] = {k: [] for k in grouped_order}
        other: list[QuickOpenEntry] = []
        for _, entry in scored[:400]:
            if entry.source in grouped:
                grouped[entry.source].append(entry)
            else:
                other.append(entry)
        for source in grouped_order:
            bucket = grouped[source]
            if not bucket:
                continue
            header = "Open Tabs" if source == "Open Tab" else source
            self._add_header_row(header)
            for entry in bucket:
                row = QListWidgetItem(self._entry_row_text(entry, line_suffix=line_suffix))
                row.setData(Qt.ItemDataRole.UserRole, ("entry", entry, parsed.line, parsed.col))
                self.list_widget.addItem(row)
        if other:
            self._add_header_row("Results")
        for entry in other:
            row = QListWidgetItem(self._entry_row_text(entry, line_suffix=line_suffix))
            row.setData(Qt.ItemDataRole.UserRole, ("entry", entry, parsed.line, parsed.col))
            self.list_widget.addItem(row)

        if self.list_widget.count():
            for i in range(self.list_widget.count()):
                it = self.list_widget.item(i)
                data = it.data(Qt.ItemDataRole.UserRole)
                if isinstance(data, tuple) and data and data[0] != "header":
                    self.list_widget.setCurrentRow(i)
                    break

    def _accept_current(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            self.reject()
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, tuple) or not payload:
            self.reject()
            return
        mode = payload[0]
        if mode == "header":
            return
        if mode == "command":
            self.command_query = str(payload[1] or "")
            self.accept()
            return
        if mode == "current_tab":
            self.selected_entry = QuickOpenEntry(kind="open_tab", label=self._current_tab_label, subtitle="", source="Current")
            self.selected_line = payload[1]
            self.selected_col = payload[2]
            self.accept()
            return
        if mode == "entry":
            self.selected_entry = payload[1]
            self.selected_line = payload[2]
            self.selected_col = payload[3]
            self.accept()
            return
        self.reject()
