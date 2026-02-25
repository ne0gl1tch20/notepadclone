from __future__ import annotations

from dataclasses import dataclass

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
from .theme_tokens import build_dialog_theme_qss_from_tokens, build_tokens_from_settings, build_workspace_dialog_qss


class WorkspaceFilesDialog(QDialog):
    def __init__(self, parent, workspace_root: str, files: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Workspace Files - {workspace_root}")
        self.resize(760, 460)
        self._selected_path: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Files", self))

        self.list_widget = QListWidget(self)
        for path in files:
            item = QListWidgetItem(path, self.list_widget)
            item.setData(Qt.UserRole, path)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.open_btn = QPushButton("Open Selected", self)
        self.close_btn = QPushButton("Close", self)
        button_row.addWidget(self.open_btn)
        button_row.addWidget(self.close_btn)
        layout.addLayout(button_row)

        self.open_btn.clicked.connect(self._open_selected)
        self.close_btn.clicked.connect(self.reject)
        self._apply_theme_from_parent()

    def _apply_theme_from_parent(self) -> None:
        settings = getattr(self.parent(), "settings", {}) if self.parent() is not None else {}
        tokens = build_tokens_from_settings(settings if isinstance(settings, dict) else {})
        self.setStyleSheet(build_dialog_theme_qss_from_tokens(tokens) + "\n" + build_workspace_dialog_qss(tokens))

    def _open_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._selected_path = item.data(Qt.UserRole)
        self.accept()

    @property
    def selected_path(self) -> str | None:
        return self._selected_path


@dataclass
class WorkspaceSearchResult:
    path: str
    line_no: int
    line_text: str


class WorkspaceSearchDialog(QDialog):
    def __init__(self, parent, query: str, results: list[WorkspaceSearchResult]) -> None:
        super().__init__(parent)
        self.setWindowTitle(f'Workspace Search - "{query}"')
        self.resize(900, 520)
        self._selected_path: str | None = None

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Matches", self))
        self.list_widget = QListWidget(self)
        left.addWidget(self.list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        right.addWidget(QLabel("Preview", self))
        self.preview = QTextEdit(self)
        self.preview.setReadOnly(True)
        right.addWidget(self.preview)
        button_row = QHBoxLayout()
        self.open_btn = QPushButton("Open File", self)
        self.close_btn = QPushButton("Close", self)
        button_row.addWidget(self.open_btn)
        button_row.addWidget(self.close_btn)
        right.addLayout(button_row)
        layout.addLayout(right, 3)

        for result in results:
            label = f"{result.path}:{result.line_no} - {result.line_text.strip()}"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, result.path)
            item.setData(Qt.UserRole + 1, result.line_text)

        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.open_btn.clicked.connect(self._open_selected)
        self.close_btn.clicked.connect(self.reject)
        self._apply_theme_from_parent()

    def _apply_theme_from_parent(self) -> None:
        settings = getattr(self.parent(), "settings", {}) if self.parent() is not None else {}
        tokens = build_tokens_from_settings(settings if isinstance(settings, dict) else {})
        self.setStyleSheet(build_dialog_theme_qss_from_tokens(tokens) + "\n" + build_workspace_dialog_qss(tokens))

    def _update_preview(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            self.preview.clear()
            return
        self.preview.setPlainText(current.data(Qt.UserRole + 1) or "")

    def _open_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self._selected_path = item.data(Qt.UserRole)
        self.accept()

    @property
    def selected_path(self) -> str | None:
        return self._selected_path
