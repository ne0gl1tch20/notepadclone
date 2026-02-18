from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QTextEdit, QVBoxLayout, QWidget
from typing import Any

from .editor_widget import EditorWidget

from .version_history import VersionHistory

class EditorTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.text_edit = EditorWidget(self)
        if hasattr(self.text_edit.widget, "setVerticalScrollBarPolicy"):
            self.text_edit.widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        if hasattr(self.text_edit.widget, "setHorizontalScrollBarPolicy"):
            self.text_edit.widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.markdown_preview = QTextEdit(self)
        self.markdown_preview.setReadOnly(True)
        self.markdown_preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.markdown_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.markdown_preview.hide()

        self.editor_splitter = QSplitter(Qt.Horizontal, self)
        self.editor_splitter.addWidget(self.text_edit.widget)
        self.editor_splitter.addWidget(self.markdown_preview)
        self.editor_splitter.setStretchFactor(0, 3)
        self.editor_splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor_splitter)

        self.current_file: str | None = None
        self.zoom_steps = 0
        self.markdown_mode_enabled = False
        self.version_history = VersionHistory()
        self.last_snapshot_time: float | None = None
        self.syntax_highlighter: Any = None
        self.syntax_language_override: str | None = None
        self.autosave_id: str | None = None
        self.autosave_path: str | None = None
        self.pinned = False
        self.favorite = False
        self.read_only = False
        self.tab_color: str | None = None
        self.bookmarks: set[int] = set()
        self.bookmark_marker_id: int | None = None
        self.encoding: str | None = None
        self.eol_mode: str | None = None
        self.large_file = False
        self.large_file_notice_shown = False
        self.clone_editor: EditorWidget | None = None
        self.split_mode: str | None = None
        self.column_mode = False
        self.multi_caret = False
        self.code_folding = True
        self.show_space_tab = False
        self.show_eol = False
        self.show_non_printing = False
        self.show_control_chars = False
        self.show_all_chars = False
        self.show_indent_guides = True
        self.show_wrap_symbol = False
        self.tags: list[str] = []
        self.encryption_enabled = False
        self.encryption_password: str | None = None

