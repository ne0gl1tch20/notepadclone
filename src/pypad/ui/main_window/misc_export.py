from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtGui import QPdfWriter, QTextDocument
from PySide6.QtWidgets import QFileDialog, QMessageBox

from pypad.ui.document.document_fidelity import DocumentFidelityError, export_document_text, render_text_to_html
from pypad.ui.editor.editor_tab import EditorTab


class MiscExportMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _export_document_html(self, tab: EditorTab) -> str:
        text = tab.text_edit.get_text()
        return render_text_to_html(
            text,
            markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
        )

    def export_active_as_markdown(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as Markdown",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".md",
            "Markdown Files (*.md);;All Files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(tab.text_edit.get_text(), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export Markdown:\n{e}")
            return
        self.show_status_message(f"Exported Markdown: {path}", 3000)

    def export_active_as_html(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as HTML",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".html",
            "HTML Files (*.html *.htm);;All Files (*.*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self._export_document_html(tab), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export HTML:\n{e}")
            return
        self.show_status_message(f"Exported HTML: {path}", 3000)

    def export_active_as_docx(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as DOCX",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".docx",
            "Word Documents (*.docx);;All Files (*.*)",
        )
        if not path:
            return
        try:
            export_document_text(
                path,
                tab.text_edit.get_text(),
                markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
            )
        except DocumentFidelityError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export DOCX:\n{e}")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export DOCX:\n{e}")
            return
        self.show_status_message(f"Exported DOCX: {path}", 3000)

    def export_active_as_odt(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as ODT",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".odt",
            "OpenDocument Text (*.odt);;All Files (*.*)",
        )
        if not path:
            return
        try:
            export_document_text(
                path,
                tab.text_edit.get_text(),
                markdown_mode=bool(tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file)),
            )
        except DocumentFidelityError as e:
            QMessageBox.critical(self, "Export Failed", f"Could not export ODT:\n{e}")
            return
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export ODT:\n{e}")
            return
        self.show_status_message(f"Exported ODT: {path}", 3000)

    def export_active_as_pdf(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export as PDF",
            (Path(tab.current_file).stem if tab.current_file else "note") + ".pdf",
            "PDF Files (*.pdf);;All Files (*.*)",
        )
        if not path:
            return
        writer = QPdfWriter(path)
        doc = QTextDocument()
        text = tab.text_edit.get_text()
        if tab.markdown_mode_enabled or self._is_markdown_path(tab.current_file):
            doc.setMarkdown(text)
        else:
            doc.setPlainText(text)
        try:
            doc.print_(writer)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export PDF:\n{e}")
            return
        self.show_status_message(f"Exported PDF: {path}", 3000)
