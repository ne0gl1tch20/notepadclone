from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from .editor_tab import EditorTab
from .workspace_search_helpers import collect_workspace_files, search_files_for_query
from .workspace_dialog import WorkspaceFilesDialog, WorkspaceSearchDialog, WorkspaceSearchResult


class WorkspaceController:
    def __init__(self, window) -> None:
        self.window = window

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
        allowed = {".txt", ".md", ".markdown", ".mdown", ".py", ".json", ".js", ".ts", ".encnote"}
        return collect_workspace_files(root=root, allowed_suffixes=allowed, max_files=3000)

    def show_workspace_files(self) -> None:
        root = self.workspace_root()
        if not root:
            QMessageBox.information(self.window, "Workspace", "Please set a workspace folder first.")
            return
        files = self.workspace_files()
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
        dlg = WorkspaceSearchDialog(self.window, query, results)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.window._open_file_path(dlg.selected_path)

    def replace_in_files(self) -> None:
        root = self.workspace_root()
        if not root:
            QMessageBox.information(self.window, "Workspace", "Please set a workspace folder first.")
            return

        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QCheckBox, QLineEdit, QLabel

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

                layout = QGridLayout(self)
                layout.addWidget(QLabel("Find what:"), 0, 0)
                layout.addWidget(self.find_edit, 0, 1)
                layout.addWidget(QLabel("Replace with:"), 1, 0)
                layout.addWidget(self.replace_edit, 1, 1)
                layout.addWidget(self.regex_checkbox, 2, 0)
                layout.addWidget(self.case_checkbox, 2, 1)
                layout.addWidget(self.skip_modified_open_checkbox, 3, 0, 1, 2)

                buttons = QDialogButtonBox(
                    QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                    Qt.Horizontal,
                    self,
                )
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons, 4, 0, 1, 2)

            def values(self) -> tuple[str, str, bool, bool, bool]:
                return (
                    self.find_edit.text(),
                    self.replace_edit.text(),
                    self.regex_checkbox.isChecked(),
                    self.case_checkbox.isChecked(),
                    self.skip_modified_open_checkbox.isChecked(),
                )

        dlg = ReplaceDialog(self.window)
        if dlg.exec() != dlg.Accepted:
            return
        find_text, replace_text, use_regex, case_sensitive, skip_modified_open = dlg.values()
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
        files_changed = 0
        replacements = 0
        skipped_modified = 0
        errors = 0
        reloaded_tabs = 0

        for path in files:
            if path.endswith(".encnote"):
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

        QMessageBox.information(
            self.window,
            "Replace in Files",
            (
                f"Replaced {replacements} occurrence(s) across {files_changed} file(s).\n"
                f"Reloaded open tabs: {reloaded_tabs}\n"
                f"Skipped modified open files: {skipped_modified}\n"
                f"Read/write errors: {errors}"
            ),
        )

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
