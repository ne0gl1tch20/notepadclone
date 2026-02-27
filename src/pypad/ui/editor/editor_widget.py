from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QTextCursor
from PySide6.QtWidgets import QTextEdit
from pypad.ui.editor.scintilla_compat import ScintillaCompatEditor

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
        self._native_scintilla = QsciScintilla is not None
        if QsciScintilla is not None:
            self.widget = QsciScintilla(parent)
            self._is_scintilla = True
            self._wire_scintilla_signals()
        else:
            # QScintilla-like compatibility backend for pure PySide6 installs.
            self.widget = ScintillaCompatEditor(parent)
            self._is_scintilla = True
            self._wire_scintilla_signals()

    @property
    def is_scintilla(self) -> bool:
        return self._is_scintilla

    @property
    def is_native_scintilla(self) -> bool:
        return self._native_scintilla

    def _wire_scintilla_signals(self) -> None:
        w = self.widget
        if hasattr(w, "textChanged"):
            w.textChanged.connect(self._emit_text_changed)
        if hasattr(w, "cursorPositionChanged"):
            w.cursorPositionChanged.connect(self._emit_cursor_changed)
        if hasattr(w, "modificationChanged"):
            w.modificationChanged.connect(self.modificationChanged)
        elif hasattr(w, "document"):
            w.document().modificationChanged.connect(self.modificationChanged)
        if hasattr(w, "selectionChanged"):
            w.selectionChanged.connect(self._emit_selection_changed)

    def _send_scintilla(self, command_name: str, *args: int) -> bool:
        if not self._is_scintilla:
            return False
        if QsciScintilla is None and hasattr(self.widget, "send_scintilla_named"):
            return bool(self.widget.send_scintilla_named(command_name, *args))
        if QsciScintilla is None:
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
            wrap_word = getattr(QsciScintilla, "WrapWord", getattr(self.widget, "WrapWord", 1))
            wrap_none = getattr(QsciScintilla, "WrapNone", getattr(self.widget, "WrapNone", 0))
            self.widget.setWrapMode(wrap_word if enabled else wrap_none)
        else:
            self.widget.setLineWrapMode(QTextEdit.WidgetWidth if enabled else QTextEdit.NoWrap)

    def set_margin_padding(self, *, left: int, right: int) -> None:
        if not self._is_scintilla:
            return
        left_px = max(0, int(left))
        right_px = max(0, int(right))
        if not self._send_scintilla("SCI_SETMARGINLEFT", left_px) and hasattr(self.widget, "setMarginLeft"):
            self.widget.setMarginLeft(left_px)
        if not self._send_scintilla("SCI_SETMARGINRIGHT", right_px) and hasattr(self.widget, "setMarginRight"):
            self.widget.setMarginRight(right_px)

    def set_line_numbers_visible(self, visible: bool) -> None:
        if not self._is_scintilla or not hasattr(self.widget, "setMarginWidth"):
            return
        backup_attr = "_pypad_margin_state_backup"
        number_margin_type = getattr(QsciScintilla, "SC_MARGIN_NUMBER", getattr(self.widget, "SC_MARGIN_NUMBER", 1))
        symbol_margin_type = getattr(QsciScintilla, "SC_MARGIN_SYMBOL", getattr(self.widget, "SC_MARGIN_SYMBOL", 0))
        margin_width_getter = getattr(self.widget, "marginWidth", None)
        margin_type_getter = getattr(self.widget, "marginType", None)

        if bool(visible):
            backup = getattr(self.widget, backup_attr, None)
            if isinstance(backup, dict):
                for idx, width in backup.get("widths", {}).items():
                    try:
                        self.widget.setMarginWidth(int(idx), int(width))
                    except Exception:
                        continue
                if hasattr(self.widget, "setMarginLeft"):
                    try:
                        self.widget.setMarginLeft(int(backup.get("left", 0)))
                    except Exception:
                        pass
                if hasattr(self.widget, "setMarginRight"):
                    try:
                        self.widget.setMarginRight(int(backup.get("right", 0)))
                    except Exception:
                        pass
                setattr(self.widget, backup_attr, None)
                return
            # Fallback when no prior hidden-state backup exists.
            try:
                self.widget.setMarginWidth(2, -1)
            except Exception:
                pass
            return

        if getattr(self.widget, backup_attr, None) is None:
            widths: dict[int, int] = {}
            for idx in range(8):
                width_val = None
                if callable(margin_width_getter):
                    try:
                        width_val = int(margin_width_getter(idx))
                    except Exception:
                        width_val = None
                if width_val is None and hasattr(self.widget, "_margin_widths"):
                    try:
                        width_val = int(getattr(self.widget, "_margin_widths", {}).get(idx, 0))
                    except Exception:
                        width_val = None
                if width_val is not None:
                    widths[int(idx)] = int(width_val)
            left = int(getattr(self.widget, "_margin_left_padding", 0))
            right = int(getattr(self.widget, "_margin_right_padding", 0))
            setattr(self.widget, backup_attr, {"widths": widths, "left": left, "right": right})

        gutter_indexes: set[int] = set()
        if callable(margin_type_getter):
            for idx in range(8):
                try:
                    margin_type = int(margin_type_getter(idx))
                except Exception:
                    continue
                if margin_type in {int(number_margin_type), int(symbol_margin_type)}:
                    gutter_indexes.add(int(idx))
        if not gutter_indexes:
            gutter_indexes.update({0, 1, 2})
        for idx in sorted(gutter_indexes):
            try:
                self.widget.setMarginWidth(int(idx), 0)
            except Exception:
                continue
        if hasattr(self.widget, "setMarginLeft"):
            try:
                self.widget.setMarginLeft(0)
            except Exception:
                pass
        if hasattr(self.widget, "setMarginRight"):
            try:
                self.widget.setMarginRight(0)
            except Exception:
                pass

    def configure_indentation(self, *, tab_width: int, use_tabs: bool) -> None:
        width = max(1, int(tab_width))
        if self._is_scintilla:
            if hasattr(self.widget, "setTabWidth"):
                self.widget.setTabWidth(width)
            if hasattr(self.widget, "setIndentationWidth"):
                self.widget.setIndentationWidth(width)
            if hasattr(self.widget, "setIndentationsUseTabs"):
                self.widget.setIndentationsUseTabs(bool(use_tabs))
            return
        metrics = QFontMetricsF(self.widget.font())
        self.widget.setTabStopDistance(max(8.0, metrics.horizontalAdvance(" ") * float(width)))

    def set_line_number_width(self, *, mode: str, width_px: int) -> None:
        if not self._is_scintilla or not hasattr(self.widget, "setMarginWidth"):
            return
        normalized = str(mode or "dynamic").strip().lower()
        if normalized not in {"dynamic", "constant"}:
            normalized = "dynamic"
        target_width = -1 if normalized == "dynamic" else max(24, int(width_px))
        try:
            self.widget.setMarginWidth(2, int(target_width))
        except Exception:
            return

    def set_caret_width(self, width_px: int) -> None:
        width = max(1, int(width_px))
        if self._is_scintilla:
            if not self._send_scintilla("SCI_SETCARETWIDTH", width) and hasattr(self.widget, "setCaretWidth"):
                self.widget.setCaretWidth(width)
            return
        if hasattr(self.widget, "setCursorWidth"):
            self.widget.setCursorWidth(width)

    def set_highlight_current_line(self, enabled: bool) -> None:
        if self._is_scintilla:
            flag = 1 if bool(enabled) else 0
            if not self._send_scintilla("SCI_SETCARETLINEVISIBLE", flag) and hasattr(self.widget, "setCaretLineVisible"):
                self.widget.setCaretLineVisible(bool(enabled))

    @staticmethod
    def _scintilla_rgb_int(color: str) -> int:
        qc = QColor(str(color))
        if not qc.isValid():
            qc = QColor("#000000")
        # Scintilla color integer uses 0x00BBGGRR.
        return int(qc.red()) | (int(qc.green()) << 8) | (int(qc.blue()) << 16)

    def set_theme_colors(
        self,
        *,
        background: str,
        foreground: str,
        selection_bg: str,
        selection_fg: str,
        caret_line_bg: str,
        gutter_bg: str,
        gutter_fg: str,
    ) -> None:
        if not self._is_scintilla:
            self.widget.setStyleSheet(
                "QTextEdit, QPlainTextEdit {"
                f"background: {background}; color: {foreground};"
                f"selection-background-color: {selection_bg}; selection-color: {selection_fg};"
                "}"
            )
            return
        if not self._native_scintilla:
            # Compat backend paints from QTextDocument; stylesheet is the stable path here.
            self.widget.setStyleSheet(
                "QPlainTextEdit {"
                f"background: {background}; color: {foreground};"
                f"selection-background-color: {selection_bg}; selection-color: {selection_fg};"
                "}"
            )
            if hasattr(self.widget, "setCaretLineBackgroundColor"):
                self.widget.setCaretLineBackgroundColor(QColor(caret_line_bg))
            return
        # Drop any stale per-widget stylesheet (e.g. from print/page view) so native Scintilla
        # palette and style calls are not visually overridden.
        self.widget.setStyleSheet("")
        try:
            bg = QColor(background)
            fg = QColor(foreground)
            sel_bg = QColor(selection_bg)
            sel_fg = QColor(selection_fg)
            line_bg = QColor(caret_line_bg)
            gbg = QColor(gutter_bg)
            gfg = QColor(gutter_fg)
            if hasattr(self.widget, "setPaper"):
                self.widget.setPaper(bg)
            if hasattr(self.widget, "setColor"):
                self.widget.setColor(fg)
            if hasattr(self.widget, "setCaretForegroundColor"):
                self.widget.setCaretForegroundColor(fg)
            if hasattr(self.widget, "setSelectionBackgroundColor"):
                self.widget.setSelectionBackgroundColor(sel_bg)
            if hasattr(self.widget, "setSelectionForegroundColor"):
                self.widget.setSelectionForegroundColor(sel_fg)
            if hasattr(self.widget, "setCaretLineBackgroundColor"):
                self.widget.setCaretLineBackgroundColor(line_bg)
            if hasattr(self.widget, "setMarginsBackgroundColor"):
                self.widget.setMarginsBackgroundColor(gbg)
            if hasattr(self.widget, "setMarginsForegroundColor"):
                self.widget.setMarginsForegroundColor(gfg)
            if hasattr(self.widget, "setFoldMarginColors"):
                self.widget.setFoldMarginColors(gfg, gbg)

            style_default = int(getattr(QsciScintilla, "STYLE_DEFAULT", 32)) if QsciScintilla is not None else 32
            style_linenum = int(getattr(QsciScintilla, "STYLE_LINENUMBER", 33)) if QsciScintilla is not None else 33
            bg_i = self._scintilla_rgb_int(background)
            fg_i = self._scintilla_rgb_int(foreground)
            gbg_i = self._scintilla_rgb_int(gutter_bg)
            gfg_i = self._scintilla_rgb_int(gutter_fg)
            sel_bg_i = self._scintilla_rgb_int(selection_bg)
            sel_fg_i = self._scintilla_rgb_int(selection_fg)
            line_bg_i = self._scintilla_rgb_int(caret_line_bg)

            self._send_scintilla("SCI_STYLESETBACK", style_default, bg_i)
            self._send_scintilla("SCI_STYLESETFORE", style_default, fg_i)
            self._send_scintilla("SCI_STYLECLEARALL")
            self._send_scintilla("SCI_STYLESETBACK", style_linenum, gbg_i)
            self._send_scintilla("SCI_STYLESETFORE", style_linenum, gfg_i)
            self._send_scintilla("SCI_SETCARETLINEBACK", line_bg_i)
            self._send_scintilla("SCI_SETSELBACK", 1, sel_bg_i)
            self._send_scintilla("SCI_SETSELFORE", 1, sel_fg_i)
        except Exception:
            pass

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
        if not self._is_scintilla:
            return
        if hasattr(self.widget, "setFolding"):
            fold_on = getattr(QsciScintilla, "BoxedTreeFoldStyle", getattr(self.widget, "BoxedTreeFoldStyle", 1))
            fold_off = getattr(QsciScintilla, "NoFoldStyle", getattr(self.widget, "NoFoldStyle", 0))
            style = fold_on if enabled else fold_off
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
        if not self._is_scintilla:
            return
        mode = (mode or "all").lower()
        source_all = getattr(QsciScintilla, "AcsAll", getattr(self.widget, "AcsAll", 0))
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
        if not self._is_scintilla:
            return
        if QsciAPIs is None:
            if hasattr(self.widget, "set_auto_completion_words"):
                self.widget.set_auto_completion_words(words)
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
        if QsciScintilla is None:
            if hasattr(self.widget, "fold_level"):
                self.widget.fold_level(level=level, expand=expand)
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
        if hasattr(self.widget, "hide_lines"):
            return bool(self.widget.hide_lines(start_line, end_line))
        lo = min(int(start_line), int(end_line))
        hi = max(int(start_line), int(end_line))
        max_index = self._line_count() - 1
        lo = max(0, min(lo, max_index))
        hi = max(0, min(hi, max_index))
        return bool(self._send_scintilla("SCI_HIDELINES", lo, hi))

    def show_all_lines(self) -> bool:
        if not self._is_scintilla:
            return False
        if hasattr(self.widget, "show_all_hidden_lines"):
            return bool(self.widget.show_all_hidden_lines())
        max_index = self._line_count() - 1
        if max_index < 0:
            return False
        return bool(self._send_scintilla("SCI_SHOWLINES", 0, max_index))
