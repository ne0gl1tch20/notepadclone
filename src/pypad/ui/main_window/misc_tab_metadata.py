from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap

from pypad.ui.editor.editor_tab import EditorTab


class MiscTabMetadataMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    @staticmethod
    def _is_path_read_only(path: str) -> bool:
        try:
            return not os.access(path, os.W_OK)
        except OSError:
            return False

    def _apply_tab_color(self, tab: EditorTab) -> None:
        index = self.tab_widget.indexOf(tab)
        if index < 0:
            return
        bar = self.tab_widget.tabBar()
        if tab.tab_color:
            color = QColor(tab.tab_color)
            if color.isValid():
                bar.setTabData(index, tab.tab_color)
                bar.setTabTextColor(index, color)
                return
        bar.setTabData(index, None)
        bar.setTabTextColor(index, self.palette().color(QPalette.Text))

    def _color_swatch_icon(self, color_hex: str, size: int = 12) -> QIcon:
        color = QColor(color_hex)
        if not color.isValid():
            return QIcon()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QColor("#666666"))
        painter.setBrush(color)
        painter.drawRoundedRect(1, 1, size - 2, size - 2, 2, 2)
        painter.end()
        return QIcon(pixmap)

    def _apply_file_metadata_to_tab(self, tab: EditorTab) -> None:
        if not tab.current_file:
            tab.favorite = False
            tab.tags = []
            tab.tab_color = None
            tab.read_only = False
            tab.text_edit.set_read_only(False)
            return
        favorites = set(self.settings.get("favorite_files", []))
        tags_map = self.settings.get("file_tags", {})
        colors_map = self.settings.get("file_colors", {})
        tags = []
        if isinstance(tags_map, dict):
            raw = tags_map.get(tab.current_file, [])
            tags = self._normalize_tags(raw if isinstance(raw, (list, tuple, str)) else [])
        tab.favorite = tab.current_file in favorites
        tab.tags = tags
        if isinstance(colors_map, dict):
            color = colors_map.get(tab.current_file)
            if color:
                tab.tab_color = str(color)
            else:
                tab.tab_color = tab.tab_color or None
        else:
            tab.tab_color = tab.tab_color or None
        tab.read_only = self._is_path_read_only(tab.current_file)
        tab.text_edit.set_read_only(tab.read_only)
        self._apply_tab_color(tab)
        self._refresh_tab_title(tab)

    def _persist_file_metadata_for_tab(self, tab: EditorTab) -> None:
        if not tab.current_file:
            return
        favorites = [p for p in self.settings.get("favorite_files", []) if isinstance(p, str)]
        if tab.favorite and tab.current_file not in favorites:
            favorites.append(tab.current_file)
        if not tab.favorite:
            favorites = [p for p in favorites if p != tab.current_file]
        self.settings["favorite_files"] = favorites

        tags_map = self.settings.get("file_tags", {})
        if not isinstance(tags_map, dict):
            tags_map = {}
        cleaned = self._normalize_tags(tab.tags)
        if cleaned:
            tags_map[tab.current_file] = cleaned
        else:
            tags_map.pop(tab.current_file, None)
        self.settings["file_tags"] = tags_map
        colors_map = self.settings.get("file_colors", {})
        if not isinstance(colors_map, dict):
            colors_map = {}
        if tab.tab_color:
            colors_map[tab.current_file] = tab.tab_color
        else:
            colors_map.pop(tab.current_file, None)
        self.settings["file_colors"] = colors_map
        self._refresh_favorite_files_menu()
