from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTextEdit

try:
    from PySide6.Qsci import QsciScintilla, QsciAPIs, QsciLexerCustom
except Exception:  # noqa: BLE001
    QsciScintilla = None
    QsciAPIs = None
    QsciLexerCustom = None


class EditorWidget(QObject):
    textChanged = Signal()
    cursorPositionChanged = Signal()
    modificationChanged = Signal(bool)
    copyAvailable = Signal(bool)
    undoAvailable = Signal(bool)
    redoAvailable = Signal(bool)
    selectionChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        if QsciScintilla is not None:
            self.widget = QsciScintilla(parent)
            self._is_scintilla = True
            self._wire_scintilla_signals()
        else:
            self.widget = QTextEdit(parent)
            self._is_scintilla = False
            self._wire_qtextedit_signals()

    @property
    def is_scintilla(self) -> bool:
        return self._is_scintilla

    def _wire_scintilla_signals(self) -> None:
        w = self.widget
        if hasattr(w, "textChanged"):
            w.textChanged.connect(self._emit_text_changed)
        if hasattr(w, "cursorPositionChanged"):
            w.cursorPositionChanged.connect(self._emit_cursor_changed)
        if hasattr(w, "modificationChanged"):
            w.modificationChanged.connect(self.modificationChanged)
        if hasattr(w, "selectionChanged"):
            w.selectionChanged.connect(self._emit_selection_changed)

    def _send_scintilla(self, command_name: str, *args: int) -> bool:
        if not self._is_scintilla or QsciScintilla is None:
            return False
        if not hasattr(self.widget, "SendScintilla"):
            return False
        command = getattr(QsciScintilla, command_name, None)
        if command is None:
            return False
        self.widget.SendScintilla(command, *args)
        return True

    def _wire_qtextedit_signals(self) -> None:
        w = self.widget
        w.textChanged.connect(self._emit_text_changed)
        w.cursorPositionChanged.connect(self._emit_cursor_changed)
        if hasattr(w, "selectionChanged"):
            w.selectionChanged.connect(self._emit_selection_changed)
        w.copyAvailable.connect(self.copyAvailable)
        w.undoAvailable.connect(self.undoAvailable)
        w.redoAvailable.connect(self.redoAvailable)
        w.document().modificationChanged.connect(self.modificationChanged)

    def _emit_text_changed(self) -> None:
        self.textChanged.emit()
        self._emit_selection_changed()

    def _emit_cursor_changed(self) -> None:
        self.cursorPositionChanged.emit()
        self._emit_selection_changed()

    def _emit_selection_changed(self) -> None:
        has_sel = self.has_selection()
        self.copyAvailable.emit(has_sel)
        self.selectionChanged.emit()

    # ---- text access ----
    def get_text(self) -> str:
        if self._is_scintilla:
            return self.widget.text()
        return self.widget.toPlainText()

    def set_text(self, text: str) -> None:
        if self._is_scintilla:
            self.widget.setText(text)
        else:
            self.widget.setPlainText(text)

    def insert_text(self, text: str) -> None:
        if self._is_scintilla:
            line, index = self.widget.getCursorPosition()
            self.widget.insertAt(text, line, index)
            self.widget.setCursorPosition(line, index + len(text))
        else:
            cursor = self.widget.textCursor()
            cursor.insertText(text)

    # ---- selection ----
    def has_selection(self) -> bool:
        if self._is_scintilla:
            return self.widget.hasSelectedText()
        return self.widget.textCursor().hasSelection()

    def selected_text(self) -> str:
        if self._is_scintilla:
            return self.widget.selectedText()
        return self.widget.textCursor().selectedText().replace("\u2029", "\n")

    def replace_selection(self, text: str) -> None:
        if self._is_scintilla:
            self.widget.replaceSelectedText(text)
        else:
            cursor = self.widget.textCursor()
            cursor.insertText(text)

    def clear_selection(self) -> None:
        if self._is_scintilla:
            line, index = self.widget.getCursorPosition()
            self.widget.setSelection(line, index, line, index)
        else:
            cursor = self.widget.textCursor()
            cursor.clearSelection()
            self.widget.setTextCursor(cursor)

    # ---- cursor ----
    def cursor_position(self) -> tuple[int, int]:
        if self._is_scintilla:
            line, index = self.widget.getCursorPosition()
            return line, index
        cursor = self.widget.textCursor()
        return cursor.blockNumber(), cursor.columnNumber()

    def set_cursor_position(self, line: int, index: int) -> None:
        if self._is_scintilla:
            self.widget.setCursorPosition(line, index)
            return
        cursor = self.widget.textCursor()
        cursor.setPosition(self.widget.document().findBlockByNumber(line).position() + index)
        self.widget.setTextCursor(cursor)

    def get_line_text(self, line: int) -> str:
        if self._is_scintilla:
            return self.widget.text(line)
        block = self.widget.document().findBlockByNumber(line)
        return block.text() if block.isValid() else ""

    def current_line_text(self) -> str:
        line, _ = self.cursor_position()
        return self.get_line_text(line)

    def replace_line(self, line: int, text: str) -> None:
        if self._is_scintilla:
            current = self.widget.text(line)
            self.widget.setSelection(line, 0, line, len(current))
            self.widget.replaceSelectedText(text)
            return
        block = self.widget.document().findBlockByNumber(line)
        if not block.isValid():
            return
        cursor = self.widget.textCursor()
        cursor.setPosition(block.position())
        cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        cursor.insertText(text)

    def selection_range(self) -> tuple[int, int, int, int] | None:
        if self._is_scintilla:
            if not self.widget.hasSelectedText():
                return None
            return self.widget.getSelection()
        cursor = self.widget.textCursor()
        if not cursor.hasSelection():
            return None
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        start_block = self.widget.document().findBlock(start)
        end_block = self.widget.document().findBlock(max(start, end - 1))
        return (
            start_block.blockNumber(),
            start - start_block.position(),
            end_block.blockNumber(),
            end - end_block.position(),
        )

    def index_from_line_col(self, line: int, col: int) -> int:
        lines = self.get_text().splitlines(keepends=True)
        if line <= 0:
            return max(0, col)
        return sum(len(lines[i]) for i in range(min(line, len(lines)))) + col

    def line_col_from_index(self, index: int) -> tuple[int, int]:
        if index <= 0:
            return 0, 0
        lines = self.get_text().splitlines(keepends=True)
        total = 0
        for i, line in enumerate(lines):
            next_total = total + len(line)
            if index < next_total:
                return i, index - total
            total = next_total
        return max(0, len(lines) - 1), max(0, index - total)

    def cursor_index(self) -> int:
        line, col = self.cursor_position()
        return self.index_from_line_col(line, col)

    def set_selection_by_index(self, start: int, end: int) -> None:
        if end < start:
            start, end = end, start
        line1, col1 = self.line_col_from_index(start)
        line2, col2 = self.line_col_from_index(end)
        if self._is_scintilla:
            self.widget.setSelection(line1, col1, line2, col2)
            self.widget.setCursorPosition(line2, col2)
            return
        cursor = self.widget.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, cursor.KeepAnchor)
        self.widget.setTextCursor(cursor)

    # ---- editing ----
    def undo(self) -> None:
        self.widget.undo()

    def redo(self) -> None:
        self.widget.redo()

    def cut(self) -> None:
        self.widget.cut()

    def copy(self) -> None:
        self.widget.copy()

    def paste(self) -> None:
        self.widget.paste()

    def select_all(self) -> None:
        self.widget.selectAll()

    def is_modified(self) -> bool:
        if self._is_scintilla:
            return bool(self.widget.isModified())
        return bool(self.widget.document().isModified())

    def set_modified(self, value: bool) -> None:
        if self._is_scintilla:
            self.widget.setModified(value)
        else:
            self.widget.document().setModified(value)

    def is_undo_available(self) -> bool:
        if self._is_scintilla and hasattr(self.widget, "isUndoAvailable"):
            return bool(self.widget.isUndoAvailable())
        if not self._is_scintilla:
            return bool(self.widget.document().isUndoAvailable())
        return False

    def is_redo_available(self) -> bool:
        if self._is_scintilla and hasattr(self.widget, "isRedoAvailable"):
            return bool(self.widget.isRedoAvailable())
        if not self._is_scintilla:
            return bool(self.widget.document().isRedoAvailable())
        return False

    def set_read_only(self, read_only: bool) -> None:
        self.widget.setReadOnly(read_only)

    def is_read_only(self) -> bool:
        return bool(self.widget.isReadOnly())

    def set_font(self, font: QFont) -> None:
        self.widget.setFont(font)

    def current_font(self) -> QFont:
        if self._is_scintilla:
            return self.widget.font()
        return self.widget.currentFont()

    def set_wrap_enabled(self, enabled: bool) -> None:
        if self._is_scintilla:
            self.widget.setWrapMode(QsciScintilla.WrapWord if enabled else QsciScintilla.WrapNone)
        else:
            self.widget.setLineWrapMode(QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap)

    def zoom_in(self, steps: int) -> None:
        if self._is_scintilla:
            for _ in range(abs(steps)):
                self.widget.zoomIn(1 if steps > 0 else -1)
        else:
            self.widget.zoomIn(steps)

    def delete_backspace(self) -> None:
        if self._is_scintilla:
            if hasattr(self.widget, "deleteBack"):
                self.widget.deleteBack()
            elif hasattr(self.widget, "deleteBackNotLine"):
                self.widget.deleteBackNotLine()
            return
        cursor = self.widget.textCursor()
        cursor.deletePreviousChar()

    def delete_delete(self) -> None:
        if self._is_scintilla:
            if hasattr(self.widget, "deleteChar"):
                self.widget.deleteChar()
            return
        cursor = self.widget.textCursor()
        cursor.deleteChar()

    def set_column_mode(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        mode = getattr(QsciScintilla, "SC_SEL_RECTANGLE", 1) if enabled else getattr(QsciScintilla, "SC_SEL_STREAM", 0)
        if self._send_scintilla("SCI_SETSELECTIONMODE", mode):
            return
        if hasattr(self.widget, "setRectangularSelectionModifier"):
            modifier = self.widget.SCMOD_ALT if enabled and hasattr(self.widget, "SCMOD_ALT") else 0
            self.widget.setRectangularSelectionModifier(modifier)

    def set_multi_caret(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        if self._send_scintilla("SCI_SETMULTIPLESELECTION", int(enabled)):
            self._send_scintilla("SCI_SETADDITIONALSELECTIONTYPING", int(enabled))
            self._send_scintilla("SCI_SETMULTIPASTE", 1 if enabled else 0)
            return
        if hasattr(self.widget, "setMultipleSelectionEnabled"):
            self.widget.setMultipleSelectionEnabled(enabled)
        if hasattr(self.widget, "setAdditionalSelectionTyping"):
            self.widget.setAdditionalSelectionTyping(enabled)
        if hasattr(self.widget, "setMultiPaste"):
            self.widget.setMultiPaste(enabled)

    def set_code_folding(self, enabled: bool) -> None:
        if not self._is_scintilla or QsciScintilla is None:
            return
        if hasattr(self.widget, "setFolding"):
            style = QsciScintilla.BoxedTreeFoldStyle if enabled else QsciScintilla.NoFoldStyle
            self.widget.setFolding(style)

    def set_show_space_tab(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        mode_visible = getattr(QsciScintilla, "SCWS_VISIBLEALWAYS", 1)
        mode_hidden = getattr(QsciScintilla, "SCWS_INVISIBLE", 0)
        self._send_scintilla("SCI_SETVIEWWS", mode_visible if enabled else mode_hidden)

    def set_show_eol(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        self._send_scintilla("SCI_SETVIEWEOL", int(enabled))

    def set_show_control_chars(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        self._send_scintilla("SCI_SETCONTROLCHARSYMBOL", 183 if enabled else 0)

    def set_show_indent_guides(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        mode = 1 if enabled else 0
        if not self._send_scintilla("SCI_SETINDENTATIONGUIDES", mode) and hasattr(self.widget, "setIndentationGuides"):
            self.widget.setIndentationGuides(enabled)

    def set_show_wrap_symbol(self, enabled: bool) -> None:
        if not self._is_scintilla:
            return
        end_flag = getattr(QsciScintilla, "SC_WRAPVISUALFLAG_END", 1)
        self._send_scintilla("SCI_SETWRAPVISUALFLAGS", end_flag if enabled else 0)

    def set_auto_completion_mode(self, mode: str, threshold: int = 1) -> None:
        if not self._is_scintilla or QsciScintilla is None:
            return
        mode = (mode or "all").lower()
        source_all = getattr(QsciScintilla, "AcsAll", 0)
        source_doc = getattr(QsciScintilla, "AcsDocument", source_all)
        source_api = getattr(QsciScintilla, "AcsAPIs", source_doc)
        source_none = getattr(QsciScintilla, "AcsNone", 0)
        source = source_all
        if mode in {"none", "off"}:
            source = source_none
        elif mode in {"document", "doc"}:
            source = source_doc
        elif mode in {"apis", "api"}:
            source = source_api
        if hasattr(self.widget, "setAutoCompletionSource"):
            self.widget.setAutoCompletionSource(source)
        if hasattr(self.widget, "setAutoCompletionThreshold"):
            self.widget.setAutoCompletionThreshold(max(1, int(threshold)) if source != source_none else 0)
        if hasattr(self.widget, "setAutoCompletionCaseSensitivity"):
            self.widget.setAutoCompletionCaseSensitivity(False)
        if hasattr(self.widget, "setAutoCompletionUseSingle"):
            self.widget.setAutoCompletionUseSingle(True)

    def set_auto_completion_words(self, words: list[str]) -> None:
        if not self._is_scintilla or QsciAPIs is None:
            return
        if not hasattr(self.widget, "setAPIs"):
            return
        lexer = None
        if hasattr(self.widget, "lexer"):
            try:
                lexer = self.widget.lexer()
            except Exception:
                lexer = None
        if lexer is None and QsciLexerCustom is not None and hasattr(self.widget, "setLexer"):
            try:
                lexer = getattr(self.widget, "_pypad_api_lexer", None)
                if lexer is None:
                    lexer = QsciLexerCustom(self.widget)
                    self.widget.setLexer(lexer)
                    setattr(self.widget, "_pypad_api_lexer", lexer)
            except Exception:
                lexer = None
        if lexer is None:
            return
        try:
            api = QsciAPIs(lexer)
            for word in words:
                api.add(word)
            api.prepare()
            self.widget.setAPIs(api)
        except Exception:
            return

    def fold_all(self, expand: bool) -> None:
        if not self._is_scintilla:
            return
        if hasattr(self.widget, "foldAll"):
            try:
                self.widget.foldAll(expand)
                return
            except Exception:
                pass
        action = getattr(QsciScintilla, "SC_FOLDACTION_EXPAND", 1) if expand else getattr(QsciScintilla, "SC_FOLDACTION_CONTRACT", 0)
        self._send_scintilla("SCI_FOLDALL", action)

    def fold_current(self, expand: bool) -> None:
        if not self._is_scintilla:
            return
        line, _ = self.cursor_position()
        action = getattr(QsciScintilla, "SC_FOLDACTION_EXPAND", 1) if expand else getattr(QsciScintilla, "SC_FOLDACTION_CONTRACT", 0)
        self._send_scintilla("SCI_FOLDLINE", line, action)

    def fold_level(self, level: int, expand: bool) -> None:
        if not self._is_scintilla:
            return
        action = getattr(QsciScintilla, "SC_FOLDACTION_EXPAND", 1) if expand else getattr(QsciScintilla, "SC_FOLDACTION_CONTRACT", 0)
        max_lines = len(self.get_text().splitlines())
        get_fold_level = getattr(QsciScintilla, "SCI_GETFOLDLEVEL", None)
        number_mask = getattr(QsciScintilla, "SC_FOLDLEVELNUMBERMASK", 0x0FFF)
        if get_fold_level is None or not hasattr(self.widget, "SendScintilla"):
            return
        for line in range(max_lines):
            try:
                fold_level = int(self.widget.SendScintilla(get_fold_level, line)) & number_mask
            except Exception:
                continue
            if fold_level == max(0, level - 1):
                self._send_scintilla("SCI_FOLDLINE", line, action)

    def _line_count(self) -> int:
        if self._is_scintilla and hasattr(self.widget, "lines"):
            try:
                return max(1, int(self.widget.lines()))
            except Exception:
                pass
        return max(1, len(self.get_text().splitlines()) or 1)

    def hide_line_range(self, start_line: int, end_line: int) -> bool:
        if not self._is_scintilla:
            return False
        lo = min(int(start_line), int(end_line))
        hi = max(int(start_line), int(end_line))
        max_index = self._line_count() - 1
        lo = max(0, min(lo, max_index))
        hi = max(0, min(hi, max_index))
        return bool(self._send_scintilla("SCI_HIDELINES", lo, hi))

    def show_all_lines(self) -> bool:
        if not self._is_scintilla:
            return False
        max_index = self._line_count() - 1
        if max_index < 0:
            return False
        return bool(self._send_scintilla("SCI_SHOWLINES", 0, max_index))
