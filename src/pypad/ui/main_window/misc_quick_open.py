from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog

from pypad.logging_utils import get_logger
from pypad.ui.editor.command_palette import CommandPaletteDialog, PaletteItem
from pypad.ui.editor.editor_tab import EditorTab
from pypad.ui.editor.quick_open_dialog import QuickOpenDialog, QuickOpenEntry, extract_symbol_rows
from pypad.ui.features.extensibility_ops import discover_window_actions

_LOGGER = get_logger(__name__)


class MiscQuickOpenMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _quick_open_entries(self) -> list[QuickOpenEntry]:
        entries: list[QuickOpenEntry] = []
        seen_paths: set[str] = set()

        for i in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(i)
            if not isinstance(widget, EditorTab):
                continue
            title = self.tab_widget.tabText(i).strip() or f"Tab {i + 1}"
            path = str(widget.current_file or "").strip() or None
            subtitle = path or "Unsaved tab"
            entries.append(
                QuickOpenEntry(
                    kind="open_tab",
                    label=title,
                    subtitle=subtitle,
                    tab_index=i,
                    path=path,
                    source="Open Tab",
                )
            )
            if path:
                seen_paths.add(os.path.normcase(os.path.abspath(path)))

        for raw_path in self.settings.get("recent_files", []):
            path = str(raw_path or "").strip()
            if not path:
                continue
            norm = os.path.normcase(os.path.abspath(path))
            if norm in seen_paths:
                continue
            seen_paths.add(norm)
            entries.append(
                QuickOpenEntry(
                    kind="file",
                    label=Path(path).name or path,
                    subtitle=path,
                    path=path,
                    source="Recent",
                )
            )

        for item in self._quick_open_workspace_entries_cached():
            path = str(item.path or "").strip()
            if path:
                norm = os.path.normcase(os.path.abspath(path))
                if norm in seen_paths:
                    continue
                seen_paths.add(norm)
            entries.append(item)
        return entries

    def _quick_open_workspace_entries_cached(self) -> list[QuickOpenEntry]:
        root = str(self._workspace_root() or "").strip()
        if not root:
            return []
        now = time.time()
        cache_root = str(getattr(self, "_quick_open_cache_root", "") or "")
        cache_items = list(getattr(self, "_quick_open_workspace_cache", []) or [])
        built_at = float(getattr(self, "_quick_open_cache_built_at", 0.0) or 0.0)
        if cache_root != root:
            self._quick_open_cache_root = root
            self._quick_open_workspace_cache = []
            self._quick_open_cache_built_at = 0.0
            self._quick_open_indexing = False
            cache_items = []
            built_at = 0.0
        if not cache_items:
            raw_cache = self.settings.get("quick_open_workspace_index_cache", {})
            if isinstance(raw_cache, dict) and str(raw_cache.get("root", "") or "") == root:
                raw_items = raw_cache.get("items", [])
                if isinstance(raw_items, list):
                    restored: list[QuickOpenEntry] = []
                    for item in raw_items[:5000]:
                        if not isinstance(item, dict):
                            continue
                        path = str(item.get("path", "") or "").strip()
                        label = str(item.get("label", "") or "").strip()
                        subtitle = str(item.get("subtitle", "") or "").strip()
                        if not path or not label:
                            continue
                        restored.append(
                            QuickOpenEntry(
                                kind="file",
                                label=label,
                                subtitle=subtitle or path,
                                path=path,
                                source="Workspace",
                            )
                        )
                    if restored:
                        self._quick_open_workspace_cache = restored
                        self._quick_open_cache_root = root
                        self._quick_open_cache_built_at = float(raw_cache.get("built_at", 0.0) or 0.0)
                        cache_items = restored
                        built_at = self._quick_open_cache_built_at
        self._schedule_quick_open_index_refresh()
        if cache_items and (now - built_at) < 30.0:
            return cache_items
        return cache_items

    def _schedule_quick_open_index_refresh(self) -> None:
        if bool(getattr(self, "_quick_open_indexing", False)):
            return
        root = str(self._workspace_root() or "").strip()
        if not root:
            return
        self._quick_open_indexing = True

        def _build() -> list[QuickOpenEntry]:
            out: list[QuickOpenEntry] = []
            try:
                root_path = Path(root)
                if not root_path.exists():
                    return []
                skip_dirs = {".git", "__pycache__", ".pytest_cache", "dist", "build", "tests_tmp", ".venv", "venv"}
                count = 0
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".mypy")]
                    for name in filenames:
                        full = str(Path(dirpath) / name)
                        try:
                            rel = str(Path(full).relative_to(root_path))
                        except Exception:
                            rel = full
                        out.append(
                            QuickOpenEntry(
                                kind="file",
                                label=name,
                                subtitle=rel,
                                path=full,
                                source="Workspace",
                            )
                        )
                        count += 1
                        if count >= 5000:
                            return out
            except Exception:
                _LOGGER.exception("quick open workspace scan failed root=%s", root)
            return out

        def _worker() -> None:
            items = _build()

            def _apply() -> None:
                self._quick_open_workspace_cache = items
                self._quick_open_cache_root = root
                self._quick_open_cache_built_at = time.time()
                self._quick_open_indexing = False
                self.settings["quick_open_workspace_index_cache"] = {
                    "root": root,
                    "built_at": self._quick_open_cache_built_at,
                    "items": [
                        {
                            "path": str(x.path or ""),
                            "label": x.label,
                            "subtitle": x.subtitle,
                        }
                        for x in items[:5000]
                        if isinstance(x, QuickOpenEntry) and x.path
                    ],
                }
                try:
                    self.save_settings_to_disk()
                except Exception:
                    pass

            try:
                QTimer.singleShot(0, _apply)
            except Exception:
                _apply()

        threading.Thread(target=_worker, name="pypad-quick-open-index", daemon=True).start()

    def _quick_open_current_symbols(self) -> list[QuickOpenEntry]:
        tab = self.active_tab()
        if tab is None:
            return []
        try:
            language = self._detect_language_for_tab(tab)
            text = tab.text_edit.get_text()
        except Exception:
            return []
        rows = extract_symbol_rows(language, text)
        tab_label = self._tab_display_name(tab)
        return [
            QuickOpenEntry(
                kind="symbol",
                label=title,
                subtitle=f"{tab_label} : line {line_no}",
                path=tab.current_file,
                source="Symbol",
                line=line_no,
            )
            for line_no, title in rows
        ]

    def _schedule_workspace_symbol_index_refresh(self) -> None:
        if bool(getattr(self, "_quick_open_workspace_symbol_indexing", False)):
            return
        root = str(self._workspace_root() or "").strip()
        if not root:
            return
        self._quick_open_workspace_symbol_indexing = True

        def _guess_lang(path: str) -> str:
            suffix = Path(path).suffix.lower()
            return {
                ".py": "python",
                ".md": "markdown",
                ".markdown": "markdown",
                ".mdown": "markdown",
            }.get(suffix, "plain")

        def _build() -> list[QuickOpenEntry]:
            out: list[QuickOpenEntry] = []
            file_entries = list(getattr(self, "_quick_open_workspace_cache", []) or [])
            if not file_entries:
                file_entries = self._quick_open_workspace_entries_cached()
            scanned_files = 0
            for entry in file_entries:
                if not isinstance(entry, QuickOpenEntry) or not entry.path:
                    continue
                path = str(entry.path)
                suffix = Path(path).suffix.lower()
                if suffix not in {".py", ".md", ".markdown", ".mdown", ".js", ".ts", ".txt"}:
                    continue
                try:
                    if Path(path).stat().st_size > 512_000:
                        continue
                    text = Path(path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                lang = _guess_lang(path)
                rows = extract_symbol_rows(lang, text)
                rel = entry.subtitle or path
                for line_no, title in rows[:200]:
                    out.append(
                        QuickOpenEntry(
                            kind="symbol_workspace",
                            label=title,
                            subtitle=f"{rel} : line {line_no}",
                            path=path,
                            source="Workspace Symbol",
                            line=line_no,
                        )
                    )
                    if len(out) >= 6000:
                        return out
                scanned_files += 1
                if scanned_files >= 1200:
                    break
            return out

        def _worker() -> None:
            items = _build()

            def _apply() -> None:
                self._quick_open_workspace_symbol_cache = items
                self._quick_open_workspace_symbol_cache_root = root
                self._quick_open_workspace_symbol_cache_built_at = time.time()
                self._quick_open_workspace_symbol_indexing = False
                self.settings["quick_open_workspace_symbol_index_cache"] = {
                    "root": root,
                    "built_at": self._quick_open_workspace_symbol_cache_built_at,
                    "items": [
                        {
                            "path": str(x.path or ""),
                            "label": x.label,
                            "subtitle": x.subtitle,
                            "line": int(x.line or 0),
                        }
                        for x in items[:6000]
                        if isinstance(x, QuickOpenEntry) and x.path and x.line
                    ],
                }
                try:
                    self.save_settings_to_disk()
                except Exception:
                    pass

            try:
                QTimer.singleShot(0, _apply)
            except Exception:
                _apply()

        threading.Thread(target=_worker, name="pypad-quick-open-symbol-index", daemon=True).start()

    def _quick_open_workspace_symbols_cached(self) -> list[QuickOpenEntry]:
        root = str(self._workspace_root() or "").strip()
        if not root:
            return []
        cache_root = str(getattr(self, "_quick_open_workspace_symbol_cache_root", "") or "")
        cache_items = list(getattr(self, "_quick_open_workspace_symbol_cache", []) or [])
        built_at = float(getattr(self, "_quick_open_workspace_symbol_cache_built_at", 0.0) or 0.0)
        if cache_root != root:
            self._quick_open_workspace_symbol_cache_root = root
            self._quick_open_workspace_symbol_cache = []
            self._quick_open_workspace_symbol_cache_built_at = 0.0
            self._quick_open_workspace_symbol_indexing = False
            cache_items = []
            built_at = 0.0
        if not cache_items:
            raw_cache = self.settings.get("quick_open_workspace_symbol_index_cache", {})
            if isinstance(raw_cache, dict) and str(raw_cache.get("root", "") or "") == root:
                raw_items = raw_cache.get("items", [])
                if isinstance(raw_items, list):
                    restored: list[QuickOpenEntry] = []
                    for item in raw_items[:6000]:
                        if not isinstance(item, dict):
                            continue
                        path = str(item.get("path", "") or "").strip()
                        label = str(item.get("label", "") or "").strip()
                        subtitle = str(item.get("subtitle", "") or "").strip()
                        line_no = int(item.get("line", 0) or 0)
                        if not path or not label or line_no <= 0:
                            continue
                        restored.append(
                            QuickOpenEntry(
                                kind="symbol_workspace",
                                label=label,
                                subtitle=subtitle or path,
                                path=path,
                                source="Workspace Symbol",
                                line=line_no,
                            )
                        )
                    if restored:
                        self._quick_open_workspace_symbol_cache = restored
                        self._quick_open_workspace_symbol_cache_root = root
                        self._quick_open_workspace_symbol_cache_built_at = float(raw_cache.get("built_at", 0.0) or 0.0)
                        cache_items = restored
                        built_at = self._quick_open_workspace_symbol_cache_built_at
        self._schedule_workspace_symbol_index_refresh()
        if cache_items and (time.time() - built_at) < 45.0:
            return cache_items
        return cache_items

    def _quick_open_status_text(self) -> str:
        parts: list[str] = []
        if bool(getattr(self, "_quick_open_indexing", False)):
            parts.append("Indexing workspace...")
        if bool(getattr(self, "_quick_open_workspace_symbol_indexing", False)):
            parts.append("Symbols indexing...")
        if not parts:
            return ""
        return " | ".join(parts)

    def _quick_open_apply_selection(self, entry: QuickOpenEntry, *, line: int | None, col: int | None) -> None:
        if entry.kind == "open_tab":
            target_idx = entry.tab_index
            if isinstance(target_idx, int) and 0 <= target_idx < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(target_idx)
            tab = self.active_tab()
            if tab is not None and line is not None:
                tab.text_edit.set_cursor_position(max(0, line - 1), max(0, (col or 1) - 1))
            return
        if entry.kind == "symbol":
            tab = self.active_tab()
            target_line = int(entry.line or 1)
            if tab is not None:
                tab.text_edit.set_cursor_position(max(0, target_line - 1), max(0, (col or 1) - 1))
            return
        if entry.kind == "symbol_workspace" and entry.path:
            if not self._open_file_path(entry.path):
                return
            tab = self.active_tab()
            target_line = int(entry.line or 1)
            if tab is not None:
                tab.text_edit.set_cursor_position(max(0, target_line - 1), max(0, (col or 1) - 1))
            return
        if entry.kind == "file" and entry.path:
            if not self._open_file_path(entry.path):
                return
            tab = self.active_tab()
            if tab is not None and line is not None:
                tab.text_edit.set_cursor_position(max(0, line - 1), max(0, (col or 1) - 1))

    def open_quick_open(self) -> None:
        current_label = ""
        idx = self.tab_widget.currentIndex()
        if idx >= 0:
            current_label = self.tab_widget.tabText(idx).strip()
        dialog = QuickOpenDialog(
            self,
            self._quick_open_entries(),
            current_tab_label=current_label,
            current_symbols=self._quick_open_current_symbols(),
            workspace_symbols=self._quick_open_workspace_symbols_cached(),
            status_provider=self._quick_open_status_text,
            items_provider=self._quick_open_entries,
            current_symbols_provider=self._quick_open_current_symbols,
            workspace_symbols_provider=self._quick_open_workspace_symbols_cached,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        if dialog.command_query is not None:
            self.open_command_palette(initial_query=dialog.command_query)
            return
        entry = dialog.selected_entry
        if entry is None:
            return
        self._quick_open_apply_selection(entry, line=dialog.selected_line, col=dialog.selected_col)

    def open_command_palette(self, initial_query: str = "") -> None:
        actions: list[PaletteItem] = []
        for entry in discover_window_actions(self):
            actions.append(
                PaletteItem(
                    label=entry.label,
                    section=entry.section,
                    action=entry.action,
                    shortcut=entry.shortcut_text,
                    keywords=f"{entry.action_id} {entry.section}",
                )
            )
        dialog = CommandPaletteDialog(self, actions, initial_query=initial_query)
        if dialog.exec() != QDialog.Accepted or dialog.selected_action is None:
            return
        dialog.selected_action.trigger()
