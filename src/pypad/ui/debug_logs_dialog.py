from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout
from .theme_tokens import build_debug_logs_dialog_qss, build_dialog_theme_qss_from_tokens, build_tokens_from_settings

class DebugLogsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Debug Logs")
        self.resize(860, 520)

        layout = QVBoxLayout(self)
        self.logs_view = QTextEdit(self)
        self.logs_view.setReadOnly(True)
        self.logs_view.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.logs_view)

        buttons_row = QHBoxLayout()
        self.copy_button = QPushButton("Copy All", self)
        self.clear_button = QPushButton("Clear", self)
        self.close_button = QPushButton("Close", self)
        buttons_row.addWidget(self.copy_button)
        buttons_row.addWidget(self.clear_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.close_button)
        layout.addLayout(buttons_row)

        self.copy_button.clicked.connect(self._copy_all)
        self.clear_button.clicked.connect(self._clear_all)
        self.close_button.clicked.connect(self.close)
        self._apply_theme_from_parent()

    def _apply_theme_from_parent(self) -> None:
        settings = getattr(self.parent(), "settings", {}) if self.parent() is not None else {}
        tokens = build_tokens_from_settings(settings if isinstance(settings, dict) else {})
        self.setStyleSheet(build_dialog_theme_qss_from_tokens(tokens) + "\n" + build_debug_logs_dialog_qss(tokens))

    def set_lines(self, lines: list[str]) -> None:
        self.logs_view.setPlainText("\n".join(lines))
        cursor = self.logs_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.logs_view.setTextCursor(cursor)

    def append_line(self, line: str) -> None:
        if not self.logs_view.toPlainText():
            self.logs_view.setPlainText(line)
        else:
            self.logs_view.append(line)
        cursor = self.logs_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.logs_view.setTextCursor(cursor)

    def _copy_all(self) -> None:
        QApplication.clipboard().setText(self.logs_view.toPlainText())

    def _clear_all(self) -> None:
        self.logs_view.clear()


