from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QApplication, QColorDialog, QInputDialog, QMenu, QMessageBox

from pypad.ui.editor.editor_tab import EditorTab


class MiscTabActionsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _move_to_recycle_bin(self, path: str) -> bool:
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return False

        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004
        FOF_NOERRORUI = 0x0400

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        op = SHFILEOPSTRUCTW()
        op.wFunc = FO_DELETE
        op.pFrom = path + "\0\0"
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return result == 0 and not bool(op.fAnyOperationsAborted)

    def show_tab_context_menu(self, index: int, global_pos: QPoint) -> None:
        tab = self._tab_at_index(index)
        if tab is None:
            return
        self.tab_widget.setCurrentIndex(index)

        menu = QMenu(self)
        pin_action = menu.addAction("Unpin Tab" if tab.pinned else "Pin Tab")
        close_action = menu.addAction("Close")
        close_all_but_action = menu.addAction("Close All But This")
        close_all_but_pinned_action = menu.addAction("Close All But Pinned")
        close_all_left_action = menu.addAction("Close All to the Left")
        close_all_right_action = menu.addAction("Close All to the Right")
        close_all_unchanged_action = menu.addAction("Close Unchanged")
        menu.addSeparator()
        save_action = menu.addAction("Save")
        save_as_action = menu.addAction("Save As...")
        reload_action = menu.addAction("Reload from Disk")
        print_action = menu.addAction("Print...")
        menu.addSeparator()
        open_explorer_action = menu.addAction("Open Containing Folder")
        open_cmd_action = menu.addAction("Open CMD Here")
        open_workspace_action = menu.addAction("Set Folder as Workspace")
        open_default_action = menu.addAction("Open with Default App")
        menu.addSeparator()
        rename_action = menu.addAction("Rename File...")
        move_recycle_action = menu.addAction("Move to Recycle Bin")
        read_only_action = menu.addAction("Toggle Read-only")
        copy_path_action = menu.addAction("Copy Full Path")
        copy_name_action = menu.addAction("Copy File Name")
        menu.addSeparator()
        color_menu = menu.addMenu("Tab Color")
        clear_color_action = color_menu.addAction("Default")
        preset_colors = [
            ("#d32f2f", "Red"),
            ("#f57c00", "Orange"),
            ("#fbc02d", "Yellow"),
            ("#388e3c", "Green"),
            ("#0288d1", "Blue"),
            ("#512da8", "Purple"),
            ("#c2185b", "Magenta"),
            ("#5d4037", "Brown"),
            ("#455a64", "Slate"),
            ("#00897b", "Teal"),
            ("#7cb342", "Lime"),
            ("#afb42b", "Olive"),
            ("#ff7043", "Coral"),
            ("#8d6e63", "Taupe"),
            ("#607d8b", "Steel"),
            ("#1e88e5", "Sky"),
            ("#3949ab", "Indigo"),
            ("#6a1b9a", "Violet"),
            ("#c239b3", "Pink"),
            ("#6b6b6b", "Gray"),
        ]
        color_actions: dict[QAction, str] = {}
        for hex_color, label in preset_colors:
            preset_action = color_menu.addAction(label)
            preset_action.setIcon(self._color_swatch_icon(hex_color))
            color_actions[preset_action] = hex_color
        color_menu.addSeparator()
        custom_color_action = color_menu.addAction("Custom...")

        has_file = bool(tab.current_file and Path(tab.current_file).exists())
        for action in (
            open_explorer_action,
            open_cmd_action,
            open_workspace_action,
            open_default_action,
            move_recycle_action,
            reload_action,
            read_only_action,
            copy_path_action,
            copy_name_action,
        ):
            action.setEnabled(has_file)
        rename_action.setEnabled(True)

        chosen = menu.exec(global_pos)
        if chosen is None:
            return

        if chosen == pin_action:
            self.toggle_pin_active_tab()
        elif chosen == close_action:
            self.close_tab(index)
        elif chosen == close_all_but_action:
            self.close_all_but(index)
        elif chosen == close_all_but_pinned_action:
            self.close_all_but_pinned()
        elif chosen == close_all_left_action:
            self.close_all_left_of(index)
        elif chosen == close_all_right_action:
            self.close_all_right_of(index)
        elif chosen == close_all_unchanged_action:
            self.close_all_unchanged()
        elif chosen == save_action:
            self.file_save_tab(tab)
        elif chosen == save_as_action:
            self.file_save_as_tab(tab)
        elif chosen == open_explorer_action and tab.current_file:
            os.startfile(os.path.dirname(tab.current_file))
        elif chosen == open_cmd_action and tab.current_file:
            folder = os.path.dirname(tab.current_file)
            try:
                subprocess.Popen(f'cmd.exe /K cd /d "{folder}"', shell=True)
            except Exception as e:
                print(f"Failed to open CMD: {e}")
        elif chosen == open_workspace_action and tab.current_file:
            folder = os.path.dirname(tab.current_file)
            self.settings["workspace_root"] = folder
            self.show_status_message(f"Workspace: {folder}", 3000)
            self.show_workspace_files()
        elif chosen == open_default_action and tab.current_file:
            os.startfile(tab.current_file)
        elif chosen == rename_action:
            self.rename_tab_file(tab)
        elif chosen == move_recycle_action and tab.current_file:
            if self._move_to_recycle_bin(tab.current_file):
                self.close_tab(index)
            else:
                QMessageBox.warning(self, "Recycle Bin", "Could not move file to Recycle Bin.")
        elif chosen == reload_action:
            self.reload_tab_from_disk(tab)
        elif chosen == print_action:
            self.file_print()
        elif chosen == read_only_action:
            self.toggle_tab_read_only(tab)
        elif chosen == copy_path_action and tab.current_file:
            QApplication.clipboard().setText(tab.current_file)
        elif chosen == copy_name_action and tab.current_file:
            QApplication.clipboard().setText(Path(tab.current_file).name)
        elif chosen == clear_color_action:
            self.set_tab_color(tab, None)
        elif chosen in color_actions:
            self.set_tab_color(tab, color_actions[chosen])
        elif chosen == custom_color_action:
            current = QColor(tab.tab_color) if tab.tab_color else QColor()
            color = QColorDialog.getColor(current, self, "Tab Color")
            if color.isValid():
                self.set_tab_color(tab, color.name())

    def _open_recent_file(self, path: str) -> None:
        if not Path(path).exists():
            QMessageBox.warning(self, "Recent Files", f"File not found:\n{path}")
            self.settings["recent_files"] = [p for p in self.settings.get("recent_files", []) if p != path]
            self._refresh_recent_files_menu()
            return
        self._open_file_path(path)

    def toggle_pin_active_tab(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.pinned = not tab.pinned
        pinned_files = [p for p in self.settings.get("pinned_files", []) if isinstance(p, str)]
        if tab.current_file:
            if tab.pinned and tab.current_file not in pinned_files:
                pinned_files.append(tab.current_file)
            if not tab.pinned:
                pinned_files = [p for p in pinned_files if p != tab.current_file]
        self.settings["pinned_files"] = pinned_files
        self._refresh_tab_title(tab)
        self._sort_tabs_by_pinned()
        self.pin_tab_action.setText("&Unpin Tab" if tab.pinned else "&Pin Tab")

    def toggle_favorite_active_tab(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        tab.favorite = not tab.favorite
        if tab.current_file:
            self._persist_file_metadata_for_tab(tab)
            self._refresh_recent_files_menu()
            if hasattr(self, "save_settings_to_disk"):
                self.save_settings_to_disk()
        else:
            self._refresh_favorite_files_menu()
        self._refresh_tab_title(tab)
        self.favorite_tab_action.setText("&Unfavorite Tab" if tab.favorite else "&Favorite Tab")

    def edit_active_tab_tags(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        current = ", ".join(tab.tags)
        text, ok = QInputDialog.getText(self, "Edit Tags", "Comma-separated tags:", text=current)
        if not ok:
            return
        tab.tags = self._normalize_tags(text)
        self._persist_file_metadata_for_tab(tab)
        self._refresh_tab_title(tab)

    def rename_active_tab_file(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        self.rename_tab_file(tab)

    def move_active_tab_to_recycle_bin(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        if not tab.current_file or not Path(tab.current_file).exists():
            QMessageBox.information(self, "Move to Recycle Bin", "Current tab is not a saved file.")
            return
        name = Path(tab.current_file).name
        answer = QMessageBox.question(
            self,
            "Move to Recycle Bin",
            f'Move "{name}" to Recycle Bin?',
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        index = self.tab_widget.indexOf(tab)
        if self._move_to_recycle_bin(tab.current_file):
            if index >= 0:
                self.close_tab(index)
            self.show_status_message(f'Moved "{name}" to Recycle Bin.', 3000)
        else:
            QMessageBox.warning(self, "Move to Recycle Bin", "Could not move file to Recycle Bin.")

    def rename_tab_file(self, tab: EditorTab) -> None:
        if not tab.current_file:
            QMessageBox.information(
                self,
                "Rename",
                "This tab has no file yet. Use Save As to choose a file name.",
            )
            self.file_save_as_tab(tab)
            return
        current_path = Path(tab.current_file)
        if not current_path.exists():
            QMessageBox.warning(self, "Rename", "Current file does not exist on disk.")
            return

        new_name, ok = QInputDialog.getText(self, "Rename File", "New file name:", text=current_path.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if any(sep in new_name for sep in ("/", "\\")):
            QMessageBox.warning(self, "Rename Failed", "Please provide only a file name, not a path.")
            return

        new_path = current_path.with_name(new_name)
        if new_path == current_path:
            return
        if new_path.exists():
            QMessageBox.warning(self, "Rename Failed", "A file with that name already exists.")
            return
        try:
            current_path.rename(new_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rename Failed", f"Could not rename file:\n{exc}")
            return

        old_path = str(current_path)
        tab.current_file = str(new_path)
        self._update_path_references(old_path, str(new_path))
        self._refresh_tab_title(tab)
        self.update_window_title()
        self.show_status_message(f'Renamed to "{new_path.name}"', 3000)

    def new_tab_from_template(self, template_name: str) -> None:
        template = self.templates.get(template_name)
        if template is None:
            return
        tab = self.add_new_tab(text=template, file_path=None, make_current=True)
        tab.text_edit.set_modified(True)
        self.update_window_title()

    def insert_template_into_active_tab(self, template_name: str) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        template = self.templates.get(template_name)
        if template is None:
            return
        tab.text_edit.insert_text(template)
