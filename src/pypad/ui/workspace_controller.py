from __future__ import annotations

import threading
import time
from pathlib import Path
import re
import difflib
import json
import zipfile
from datetime import datetime
from fnmatch import fnmatch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QDialog

from .editor_tab import EditorTab
from .workspace_search_helpers import collect_workspace_files, search_files_for_query
from .workspace_dialog import WorkspaceFilesDialog, WorkspaceSearchDialog, WorkspaceSearchResult


class WorkspaceController:
    def __init__(self, window) -> None:
        self.window = window
        self._index_lock = threading.Lock()
        self._index_files: list[str] = []
        self._index_key: str = ""
        self._index_ready = False
        self._index_scanning = False
        self._last_index_notice_at = 0.0

    def insert_media_files(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self.window,
            "Insert Media",
            "",
            "Media Files (*.png *.jpg *.jpeg *.gif *.bmp *.svg *.pdf);;All Files (*.*)",
        )
        if not paths:
            return
        self.insert_media_paths(paths)

    def insert_media_paths(self, paths: list[str]) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        for raw in paths:
            path = str(Path(raw))
            suffix = Path(path).suffix.lower()
            name = Path(path).name
            if tab.markdown_mode_enabled:
                if suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg"}:
                    tab.text_edit.insert_text(f"![{name}]({path})\n")
                elif suffix == ".pdf":
                    tab.text_edit.insert_text(f"[{name}]({path})\n")
                else:
                    tab.text_edit.insert_text(f"{path}\n")
            else:
                tab.text_edit.insert_text(f"{path}\n")

    def open_workspace_folder(self) -> None:
        root = QFileDialog.getExistingDirectory(
            self.window,
            "Select Workspace Folder",
            self.window.settings.get("workspace_root", "") or "",
        )
        if not root:
            return
        self.window.settings["workspace_root"] = root
        self.window.show_status_message(f"Workspace: {root}", 3000)
        self._start_background_scan(force=True)
        if hasattr(self.window, "_refresh_workspace_dock"):
            self.window._refresh_workspace_dock()
        self.show_workspace_files()

    def workspace_root(self) -> str | None:
        root = str(self.window.settings.get("workspace_root", "") or "").strip()
        if not root:
            return None
        if not Path(root).exists():
            return None
        return root

    def workspace_files(self) -> list[str]:
        root = self.workspace_root()
        if not root:
            return []
        self._start_background_scan()
        key = self._build_index_key(root)
        with self._index_lock:
            if self._index_ready and self._index_key == key:
                return list(self._index_files)
        # Fallback while background index is warming up.
        return collect_workspace_files(
            root=root,
            allowed_suffixes=self._allowed_suffixes(),
            max_files=800,
            include_hidden=bool(self.window.settings.get("workspace_show_hidden_files", False)),
            follow_symlinks=bool(self.window.settings.get("workspace_follow_symlinks", False)),
        )

    def _allowed_suffixes(self) -> set[str]:
        return {".txt", ".md", ".markdown", ".mdown", ".py", ".json", ".js", ".ts", ".encnote"}

    def _build_index_key(self, root: str) -> str:
        show_hidden = bool(self.window.settings.get("workspace_show_hidden_files", False))
        follow_symlinks = bool(self.window.settings.get("workspace_follow_symlinks", False))
        max_scan = max(1000, int(self.window.settings.get("workspace_max_scan_files", 25000) or 25000))
        return f"{Path(root).resolve()}|hidden={int(show_hidden)}|symlinks={int(follow_symlinks)}|max={max_scan}"

    def _start_background_scan(self, *, force: bool = False) -> None:
        root = self.workspace_root()
        if not root:
            return
        key = self._build_index_key(root)
        with self._index_lock:
            if self._index_scanning:
                return
            if not force and self._index_ready and self._index_key == key:
                return
            self._index_scanning = True
            self._index_ready = False
            self._index_key = key
        self.window.show_status_message("Indexing workspace in background...", 2000)

        def worker() -> None:
            try:
                files = collect_workspace_files(
                    root=root,
                    allowed_suffixes=self._allowed_suffixes(),
                    max_files=max(1000, int(self.window.settings.get("workspace_max_scan_files", 25000) or 25000)),
                    include_hidden=bool(self.window.settings.get("workspace_show_hidden_files", False)),
                    follow_symlinks=bool(self.window.settings.get("workspace_follow_symlinks", False)),
                )
            except Exception:
                files = []
            with self._index_lock:
                self._index_files = files
                self._index_ready = True
                self._index_scanning = False

        threading.Thread(target=worker, name="workspace-indexer", daemon=True).start()

    def show_workspace_files(self) -> None:
        root = self.workspace_root()
        if not root:
            QMessageBox.information(self.window, "Workspace", "Please set a workspace folder first.")
            return
        files = self.workspace_files()
        if self._index_scanning and (time.time() - self._last_index_notice_at) > 1.5:
            self.window.show_status_message("Workspace index is building; showing partial file list.", 2500)
            self._last_index_notice_at = time.time()
        dlg = WorkspaceFilesDialog(self.window, root, files)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.window._open_file_path(dlg.selected_path)

    def search_workspace(self) -> None:
        root = self.workspace_root()
        if not root:
            QMessageBox.information(self.window, "Workspace", "Please set a workspace folder first.")
            return
        query, ok = QInputDialog.getText(self.window, "Search Workspace", "Find text:")
        if not ok or not query.strip():
            return
        query = query.strip()
        hits = search_files_for_query(self.workspace_files(), query=query, max_results=500, case_sensitive=False)
        results = [WorkspaceSearchResult(path=h.path, line_no=h.line_no, line_text=h.line_text) for h in hits]
        if hasattr(self.window, "_set_search_results"):
            self.window._set_search_results(
                query,
                [
                    {
                        "path": r.path,
                        "line_no": int(r.line_no),
                        "line_text": str(r.line_text),
                    }
                    for r in results
                ],
            )
        dlg = WorkspaceSearchDialog(self.window, query, results)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.window._open_file_path(dlg.selected_path)

    def replace_in_files(self) -> None:
        root = self.workspace_root()
        if not root:
            QMessageBox.information(self.window, "Workspace", "Please set a workspace folder first.")
            return

        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QGridLayout,
            QCheckBox,
            QLineEdit,
            QLabel,
            QListWidget,
            QTextEdit,
            QHBoxLayout,
            QVBoxLayout,
            QWidget,
        )

        class ReplaceDialog(QDialog):
            def __init__(self, parent=None) -> None:
                super().__init__(parent)
                self.setWindowTitle("Replace in Files")
                self.find_edit = QLineEdit(self)
                self.replace_edit = QLineEdit(self)
                self.regex_checkbox = QCheckBox("Use regex", self)
                self.case_checkbox = QCheckBox("Case sensitive", self)
                self.skip_modified_open_checkbox = QCheckBox("Skip open files with unsaved changes", self)
                self.skip_modified_open_checkbox.setChecked(True)
                self.include_globs_edit = QLineEdit(self)
                self.include_globs_edit.setPlaceholderText("*.py,*.md,*.txt")
                self.include_globs_edit.setText("*")
                self.exclude_globs_edit = QLineEdit(self)
                self.exclude_globs_edit.setPlaceholderText("*.min.js,node_modules/*")
                self.exclude_globs_edit.setText("")

                layout = QGridLayout(self)
                layout.addWidget(QLabel("Find what:"), 0, 0)
                layout.addWidget(self.find_edit, 0, 1)
                layout.addWidget(QLabel("Replace with:"), 1, 0)
                layout.addWidget(self.replace_edit, 1, 1)
                layout.addWidget(self.regex_checkbox, 2, 0)
                layout.addWidget(self.case_checkbox, 2, 1)
                layout.addWidget(self.skip_modified_open_checkbox, 3, 0, 1, 2)
                layout.addWidget(QLabel("Include file globs:"), 4, 0)
                layout.addWidget(self.include_globs_edit, 4, 1)
                layout.addWidget(QLabel("Exclude file globs:"), 5, 0)
                layout.addWidget(self.exclude_globs_edit, 5, 1)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                    Qt.Horizontal,
                    self,
                )
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons, 6, 0, 1, 2)

            def values(self) -> tuple[str, str, bool, bool, bool, list[str], list[str]]:
                return (
                    self.find_edit.text(),
                    self.replace_edit.text(),
                    self.regex_checkbox.isChecked(),
                    self.case_checkbox.isChecked(),
                    self.skip_modified_open_checkbox.isChecked(),
                    [x.strip() for x in self.include_globs_edit.text().split(",") if x.strip()],
                    [x.strip() for x in self.exclude_globs_edit.text().split(",") if x.strip()],
                )

        class PreviewDialog(QDialog):
            def __init__(self, parent, changes: list[dict]) -> None:
                super().__init__(parent)
                self.setWindowTitle("Replace Preview")
                self.resize(980, 680)
                self._changes = changes
                root_layout = QVBoxLayout(self)
                top = QHBoxLayout()
                self.file_list = QListWidget(self)
                self.diff_view = QTextEdit(self)
                self.diff_view.setReadOnly(True)
                top.addWidget(self.file_list, 1)
                top.addWidget(self.diff_view, 2)
                root_layout.addLayout(top, 1)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
                ok_btn = buttons.button(QDialogButtonBox.Ok)
                if ok_btn is not None:
                    ok_btn.setText("Apply Changes")
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                root_layout.addWidget(buttons)
                for change in changes:
                    self.file_list.addItem(f"{Path(change['path']).name} | {change['count']} replacements")
                self.file_list.currentRowChanged.connect(self._show_diff)
                if changes:
                    self.file_list.setCurrentRow(0)

            def _show_diff(self, row: int) -> None:
                if row < 0 or row >= len(self._changes):
                    self.diff_view.clear()
                    return
                change = self._changes[row]
                before_lines = str(change["before"]).splitlines()
                after_lines = str(change["after"]).splitlines()
                diff = difflib.unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"{change['path']} (before)",
                    tofile=f"{change['path']} (after)",
                    lineterm="",
                    n=2,
                )
                preview = "\n".join(list(diff)[:600])
                self.diff_view.setPlainText(preview or "(No visible diff)")

        dlg = ReplaceDialog(self.window)
        if dlg.exec() != dlg.Accepted:
            return
        (
            find_text,
            replace_text,
            use_regex,
            case_sensitive,
            skip_modified_open,
            include_globs,
            exclude_globs,
        ) = dlg.values()
        if not find_text:
            return

        compiled_pattern: re.Pattern[str] | None = None
        plain_pattern: re.Pattern[str] | None = None
        if use_regex:
            try:
                compiled_pattern = re.compile(find_text, 0 if case_sensitive else re.IGNORECASE)
            except re.error as exc:
                QMessageBox.warning(self.window, "Replace in Files", f"Invalid regular expression:\n{exc}")
                return
        else:
            plain_pattern = re.compile(re.escape(find_text), 0 if case_sensitive else re.IGNORECASE)

        files = self.workspace_files()
        enc_map = self.window.settings.get("file_encodings", {})
        open_tabs: dict[str, EditorTab] = {}
        for index in range(self.window.tab_widget.count()):
            tab = self.window.tab_widget.widget(index)
            if isinstance(tab, EditorTab) and tab.current_file:
                open_tabs[tab.current_file] = tab
        planned_changes: list[dict] = []
        skipped_modified = 0
        skipped_by_filter = 0
        errors = 0
        reloaded_tabs = 0

        for path in files:
            if path.endswith(".encnote"):
                continue
            normalized = path.replace("\\", "/")
            if include_globs and "*" not in include_globs and not any(fnmatch(normalized, pat) for pat in include_globs):
                skipped_by_filter += 1
                continue
            if exclude_globs and any(fnmatch(normalized, pat) for pat in exclude_globs):
                skipped_by_filter += 1
                continue
            tab = open_tabs.get(path)
            if tab is not None and skip_modified_open and tab.text_edit.is_modified():
                skipped_modified += 1
                continue
            encoding = "utf-8"
            if isinstance(enc_map, dict):
                encoding = str(enc_map.get(path, "utf-8") or "utf-8")
            try:
                content = Path(path).read_text(encoding=encoding, errors="replace")
            except Exception:
                errors += 1
                continue
            if use_regex:
                if compiled_pattern is None:
                    continue
                new_content, count = compiled_pattern.subn(replace_text, content)
            else:
                if plain_pattern is None:
                    continue
                new_content, count = plain_pattern.subn(replace_text, content)
            if count:
                planned_changes.append(
                    {
                        "path": path,
                        "encoding": encoding,
                        "before": content,
                        "after": new_content,
                        "count": count,
                        "tab": tab,
                    }
                )

        if not planned_changes:
            QMessageBox.information(
                self.window,
                "Replace in Files",
                (
                    "No replacements found.\n"
                    f"Skipped modified open files: {skipped_modified}\n"
                    f"Skipped by include/exclude filters: {skipped_by_filter}\n"
                    f"Read/write errors: {errors}"
                ),
            )
            return

        preview = PreviewDialog(self.window, planned_changes)
        if preview.exec() != QDialog.Accepted:
            return

        snapshot_path = self._create_replace_snapshot(planned_changes)
        files_changed = 0
        replacements = 0
        for change in planned_changes:
            path = str(change["path"])
            encoding = str(change["encoding"])
            new_content = str(change["after"])
            count = int(change["count"])
            tab = change.get("tab")
            try:
                Path(path).write_text(new_content, encoding=encoding, errors="replace")
            except Exception:
                errors += 1
                continue
            files_changed += 1
            replacements += count
            if tab is not None and not tab.text_edit.is_modified():
                self.window.reload_tab_from_disk(tab)
                reloaded_tabs += 1

        box = QMessageBox(self.window)
        box.setWindowTitle("Replace in Files")
        box.setIcon(QMessageBox.Information)
        box.setText("Replace completed.")
        box.setInformativeText(
            (
                f"Replaced {replacements} occurrence(s) across {files_changed} file(s).\n"
                f"Reloaded open tabs: {reloaded_tabs}\n"
                f"Skipped modified open files: {skipped_modified}\n"
                f"Skipped by include/exclude filters: {skipped_by_filter}\n"
                f"Read/write errors: {errors}\n"
                f"Snapshot: {snapshot_path}"
            )
        )
        rollback_btn = box.addButton("Rollback", QMessageBox.ActionRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == rollback_btn:
            restored = self._restore_replace_snapshot(snapshot_path)
            if restored:
                QMessageBox.information(self.window, "Replace in Files", f"Rollback restored {restored} file(s).")
            else:
                QMessageBox.warning(self.window, "Replace in Files", "Rollback failed or restored no files.")

    def _create_replace_snapshot(self, planned_changes: list[dict]) -> str:
        configured = str(self.window.settings.get("backup_output_dir", "") or "").strip()
        out_dir = Path(configured) if configured else (Path(__file__).resolve().parents[3] / "backups")
        out_dir.mkdir(parents=True, exist_ok=True)
        snapshot = out_dir / f"replace_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        manifest: list[dict] = []
        with zipfile.ZipFile(snapshot, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for idx, change in enumerate(planned_changes):
                payload_name = f"files/{idx}.txt"
                zf.writestr(payload_name, str(change["before"]))
                manifest.append(
                    {
                        "path": str(change["path"]),
                        "encoding": str(change["encoding"]),
                        "payload": payload_name,
                    }
                )
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        return str(snapshot)

    def _restore_replace_snapshot(self, snapshot_path: str) -> int:
        path = Path(snapshot_path)
        if not path.exists():
            return 0
        restored = 0
        try:
            with zipfile.ZipFile(path, "r") as zf:
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                if not isinstance(manifest, list):
                    return 0
                for item in manifest:
                    if not isinstance(item, dict):
                        continue
                    target = str(item.get("path", "") or "")
                    encoding = str(item.get("encoding", "utf-8") or "utf-8")
                    payload = str(item.get("payload", "") or "")
                    if not target or not payload:
                        continue
                    content = zf.read(payload).decode("utf-8", errors="replace")
                    Path(target).write_text(content, encoding=encoding, errors="replace")
                    restored += 1
                    for index in range(self.window.tab_widget.count()):
                        tab = self.window.tab_widget.widget(index)
                        if isinstance(tab, EditorTab) and tab.current_file == target and not tab.text_edit.is_modified():
                            self.window.reload_tab_from_disk(tab)
        except Exception:
            return 0
        return restored

    def handle_dropped_urls(self, local_paths: list[str]) -> bool:
        if not local_paths:
            return False
        media_ext = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".pdf"}
        media_paths = [p for p in local_paths if Path(p).suffix.lower() in media_ext]
        if media_paths:
            self.insert_media_paths(media_paths)
            return True
        if len(local_paths) == 1 and Path(local_paths[0]).is_file():
            return bool(self.window._open_file_path(local_paths[0]))
        return False
