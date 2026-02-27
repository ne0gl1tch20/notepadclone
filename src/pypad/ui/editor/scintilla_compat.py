from __future__ import annotations

from dataclasses import dataclass
import re

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent, QPainter, QPolygon, QTextCharFormat, QTextCursor
from PySide6.QtCore import QStringListModel
from PySide6.QtWidgets import QCompleter, QPlainTextEdit, QTextEdit, QWidget
from PySide6.QtWidgets import QToolTip

# Scintilla Recreated from scratch using QPlainTextEdit, inspired by https://doc.qt.io/qt-6/qtwidgets-widgets-codeeditor-example.html and https://github.com/pyqtgraph/pyqtgraph

@dataclass
class FoldRegion:
    start: int
    end: int
    level: int


@dataclass
class ColumnBlock:
    line_lo: int
    line_hi: int
    col_lo: int
    col_hi: int


@dataclass
class HotspotRange:
    start: int
    end: int
    payload: str = ""


@dataclass
class IndicatorRange:
    start: int
    end: int
    payload: str = ""
    value: int = 0


class _MarginArea(QWidget):
    def __init__(self, editor: "ScintillaCompatEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.margin_width(), 0)

    def paintEvent(self, event) -> None:
        self._editor.paint_margin(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._editor.handle_margin_click(event)


class ScintillaCompatEditor(QPlainTextEdit):
    hotspotClicked = Signal(int, str)
    hotspotHovered = Signal(int, str)
    marginClicked = Signal(int, int)
    indicatorClicked = Signal(int, int, str)
    indicatorHovered = Signal(int, int, str)

    WrapNone = 0
    WrapWord = 1
    # Stable aliases for QPlainTextEdit wrap modes across Qt/PySide enum bindings.
    WidgetWidth = getattr(QPlainTextEdit, "WidgetWidth", QPlainTextEdit.LineWrapMode.WidgetWidth)
    NoWrap = getattr(QPlainTextEdit, "NoWrap", QPlainTextEdit.LineWrapMode.NoWrap)
    RightArrow = 2
    NoFoldStyle = 0
    BoxedTreeFoldStyle = 1
    AcsNone = 0
    AcsAll = 1
    AcsDocument = 2
    AcsAPIs = 3
    SCMOD_ALT = int(Qt.KeyboardModifier.AltModifier.value)
    SC_SEL_STREAM = 0
    SC_SEL_RECTANGLE = 1
    SC_FOLDACTION_CONTRACT = 0
    SC_FOLDACTION_EXPAND = 1
    INDIC_PLAIN = 0
    INDIC_SQUIGGLE = 1
    INDIC_TT = 2
    INDIC_DIAGONAL = 3
    INDIC_STRIKE = 4
    INDIC_HIDDEN = 5
    INDIC_BOX = 6
    INDIC_ROUNDBOX = 7
    SC_MARGIN_SYMBOL = 0
    SC_MARGIN_NUMBER = 1
    SC_MARGIN_BACK = 2
    SC_MARGIN_FORE = 3
    SC_MARGIN_TEXT = 4
    SC_MARGIN_RTEXT = 5
    SC_MARGIN_COLOUR = 6
    Circle = 0
    RoundRect = 1
    RightArrow = 2
    SmallRect = 3
    ShortArrow = 4
    Empty = 5
    Arrow = 6
    Plus = 7
    Minus = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._markers: dict[int, set[int]] = {}
        self._marker_colors: dict[int, QColor] = {}
        self._marker_symbols: dict[int, int] = {}
        self._next_marker_id = 1
        self._hidden_lines: set[int] = set()
        self._fold_hidden_lines: set[int] = set()
        self._collapsed_headers: set[int] = set()
        self._fold_regions: dict[int, FoldRegion] = {}
        self._use_tabs = False
        self._indent_width = 4
        self._folding_enabled = True
        self._lexer = None
        self._apis = None
        self._auto_completion_source = self.AcsAll
        self._auto_completion_threshold = 1
        self._auto_completion_case_sensitive = False
        self._auto_completion_use_single = True
        self._multiple_selection_enabled = False
        self._additional_selection_typing = False
        self._multi_paste = False
        self._rectangular_selection_modifier = self.SCMOD_ALT
        self._column_mode = False
        self._additional_carets: list[int] = []
        self._multi_ranges: list[tuple[int, int]] = []
        self._column_drag_anchor: tuple[int, int] | None = None
        self._column_drag_active = False
        self._column_block: ColumnBlock | None = None
        self._view_whitespace = False
        self._view_eol = False
        self._view_control_chars = False
        self._show_indent_guides = False
        self._show_wrap_symbol = False
        self._completion_words: list[str] = []
        self._completion_model = QStringListModel(self)
        self._completer = QCompleter(self._completion_model, self)
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.activated.connect(self._insert_completion)
        self._annotations: dict[int, str] = {}
        self._brace_match_pair: tuple[int, int] | None = None
        self._margin_sensitive: dict[int, bool] = {}
        self._margin_types: dict[int, int] = {0: self.SC_MARGIN_SYMBOL, 1: self.SC_MARGIN_SYMBOL, 2: self.SC_MARGIN_NUMBER}
        self._margin_widths: dict[int, int] = {0: 14, 1: 14, 2: -1}
        self._indicator_current = 0
        self._indicator_value_current = 0
        self._indicator_styles: dict[int, int] = {}
        self._indicator_colors: dict[int, QColor] = {}
        self._indicator_ranges: dict[int, list[IndicatorRange]] = {}
        self._hotspot_ranges: list[HotspotRange] = []
        self._hotspot_color = QColor("#4fa3ff")
        self._hotspot_underline = True
        self._hotspot_active_color = QColor("#8fd0ff")
        self._active_hotspot_index = -1
        self._active_indicator_hit: tuple[int, int] | None = None
        self._margin_marker_masks: dict[int, int] = {0: -1}
        self._margin_left_padding = 8
        self._margin_right_padding = 4
        self._caret_line_visible = True
        self._caret_line_color = QColor("#2f3640")
        self._style_current_pos = 0
        self._style_formats: dict[int, QTextCharFormat] = {}
        self._style_ranges: list[tuple[int, int, int]] = []
        self._lexer_ranges: list[tuple[int, int, int]] = []

        self._margin = _MarginArea(self)
        self.blockCountChanged.connect(self._update_margin_width)
        self.updateRequest.connect(self._update_margin_area)
        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._on_cursor_changed)
        self._update_margin_width(0)
        self._rebuild_fold_regions()
        self._refresh_extra_selections()

    # Minimal text API parity with QsciScintilla.
    def text(self, line: int | None = None) -> str:
        if line is None:
            return self.toPlainText()
        block = self.document().findBlockByNumber(int(line))
        return block.text() if block.isValid() else ""

    def setText(self, text: str) -> None:
        self.setPlainText(text)

    def insertAt(self, text: str, line: int, index: int) -> None:
        pos = self._index_from_line_col(int(line), int(index))
        cursor = self.textCursor()
        cursor.setPosition(pos)
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def getCursorPosition(self) -> tuple[int, int]:
        cursor = self.textCursor()
        return cursor.blockNumber(), cursor.columnNumber()

    def setCursorPosition(self, line: int, index: int) -> None:
        pos = self._index_from_line_col(int(line), int(index))
        cursor = self.textCursor()
        cursor.setPosition(pos)
        self.setTextCursor(cursor)

    def hasSelectedText(self) -> bool:
        return self.textCursor().hasSelection()

    def selectedText(self) -> str:
        return self.textCursor().selectedText().replace("\u2029", "\n")

    def replaceSelectedText(self, text: str) -> None:
        cursor = self.textCursor()
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def setSelection(self, line1: int, index1: int, line2: int, index2: int) -> None:
        start = self._index_from_line_col(int(line1), int(index1))
        end = self._index_from_line_col(int(line2), int(index2))
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self.setTextCursor(cursor)

    def getSelection(self) -> tuple[int, int, int, int]:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            line, col = self.getCursorPosition()
            return line, col, line, col
        start = min(cursor.selectionStart(), cursor.selectionEnd())
        end = max(cursor.selectionStart(), cursor.selectionEnd())
        start_block = self.document().findBlock(start)
        end_block = self.document().findBlock(max(start, end - 1))
        return (
            start_block.blockNumber(),
            start - start_block.position(),
            end_block.blockNumber(),
            end - end_block.position(),
        )

    def isModified(self) -> bool:
        return bool(self.document().isModified())

    def setModified(self, value: bool) -> None:
        self.document().setModified(bool(value))

    def setWrapMode(self, mode: int) -> None:
        self.setLineWrapMode(self.WidgetWidth if int(mode) == self.WrapWord else self.NoWrap)

    def setTabWidth(self, width: int) -> None:
        self._indent_width = max(1, int(width))

    def setIndentationWidth(self, width: int) -> None:
        self._indent_width = max(1, int(width))

    def setIndentationsUseTabs(self, value: bool) -> None:
        self._use_tabs = bool(value)

    def setRectangularSelectionModifier(self, modifier: int) -> None:
        self._rectangular_selection_modifier = int(modifier)
        if self._rectangular_selection_modifier == self.SCMOD_ALT:
            self._column_mode = True
        if self._rectangular_selection_modifier == 0:
            self._column_mode = False

    def setMultipleSelectionEnabled(self, value: bool) -> None:
        self._multiple_selection_enabled = bool(value)
        if not self._multiple_selection_enabled:
            self._additional_carets = []
            self.viewport().update()

    def setAdditionalSelectionTyping(self, value: bool) -> None:
        self._additional_selection_typing = bool(value)

    def setMultiPaste(self, value: bool) -> None:
        self._multi_paste = bool(value)

    def setFolding(self, style: int) -> None:
        self._folding_enabled = int(style) != self.NoFoldStyle
        if not self._folding_enabled:
            self._collapsed_headers.clear()
            self._fold_hidden_lines.clear()
            self._refresh_visibility()
        self._margin.update()

    def setAutoCompletionSource(self, source: int) -> None:
        self._auto_completion_source = int(source)
        self._refresh_completion_words()

    def setAutoCompletionThreshold(self, threshold: int) -> None:
        self._auto_completion_threshold = int(threshold)

    def setAutoCompletionCaseSensitivity(self, value: bool) -> None:
        self._auto_completion_case_sensitive = bool(value)
        self._completer.setCaseSensitivity(Qt.CaseSensitive if self._auto_completion_case_sensitive else Qt.CaseInsensitive)

    def setAutoCompletionUseSingle(self, value: bool) -> None:
        self._auto_completion_use_single = bool(value)

    def setAPIs(self, apis) -> None:
        self._apis = apis

    def set_auto_completion_words(self, words: list[str]) -> None:
        self._completion_words = sorted({str(word).strip() for word in words if str(word).strip()})
        self._refresh_completion_words()

    def isUndoAvailable(self) -> bool:
        return bool(self.document().isUndoAvailable())

    def isRedoAvailable(self) -> bool:
        return bool(self.document().isRedoAvailable())

    def deleteBack(self) -> None:
        if self._multiple_selection_enabled and self._additional_selection_typing and self._additional_carets:
            self._delete_at_all_carets(backward=True)
            return
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deletePreviousChar()
        self.setTextCursor(cursor)

    def deleteChar(self) -> None:
        if self._multiple_selection_enabled and self._additional_selection_typing and self._additional_carets:
            self._delete_at_all_carets(backward=False)
            return
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        self.setTextCursor(cursor)

    def annotationSetText(self, line: int, text: str) -> None:
        ln = max(0, int(line))
        self._annotations[ln] = str(text)
        self.viewport().update()

    def annotationClearAll(self) -> None:
        self._annotations.clear()
        self.viewport().update()

    def callTipShow(self, pos: int, text: str) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(max(0, min(int(pos), len(self.toPlainText()))))
        rect = self.cursorRect(cursor)
        point = self.viewport().mapToGlobal(rect.bottomRight())
        QToolTip.showText(point, str(text), self)

    def callTipCancel(self) -> None:
        QToolTip.hideText()

    def setMarginSensitivity(self, margin: int, sensitive: bool) -> None:
        self._margin_sensitive[int(margin)] = bool(sensitive)

    def setMarginType(self, margin: int, margin_type: int) -> None:
        self._margin_types[int(margin)] = int(margin_type)
        self._update_margin_width(0)
        self._margin.update()

    def setMarginWidth(self, margin: int, width: int) -> None:
        self._margin_widths[int(margin)] = int(width)
        self._update_margin_width(0)
        self._margin.update()

    def setMarginLeft(self, width: int) -> None:
        self._margin_left_padding = max(0, int(width))
        self._update_margin_width(0)
        self._margin.update()

    def setMarginRight(self, width: int) -> None:
        self._margin_right_padding = max(0, int(width))
        self._update_margin_width(0)
        self._margin.update()

    def setMarginMarkerMask(self, margin: int, mask: int) -> None:
        self._margin_marker_masks[int(margin)] = int(mask)
        self._margin.update()

    def setCaretWidth(self, width: int) -> None:
        self.setCursorWidth(max(1, int(width)))

    def setCaretLineVisible(self, visible: bool) -> None:
        self._caret_line_visible = bool(visible)
        self._refresh_extra_selections()

    def setCaretLineBackgroundColor(self, color) -> None:
        if isinstance(color, QColor):
            self._caret_line_color = QColor(color)
        else:
            self._caret_line_color = QColor(str(color))
        self._refresh_extra_selections()

    def indicatorDefine(self, style: int, indicator: int) -> int:
        idx = max(0, int(indicator))
        self._indicator_styles[idx] = int(style)
        if idx not in self._indicator_colors:
            self._indicator_colors[idx] = QColor("#f4d03f")
        return idx

    def setIndicatorForegroundColor(self, color, indicator: int) -> None:
        idx = max(0, int(indicator))
        if isinstance(color, QColor):
            self._indicator_colors[idx] = color
        else:
            self._indicator_colors[idx] = QColor(str(color))
        self._refresh_extra_selections()

    def setIndicatorCurrent(self, indicator: int) -> None:
        self._indicator_current = max(0, int(indicator))

    def setIndicatorValue(self, value: int) -> None:
        self._indicator_value_current = int(value)

    def indicatorFillRange(self, position: int, length: int) -> None:
        pos = max(0, int(position))
        end = max(pos, pos + max(0, int(length)))
        ranges = self._indicator_ranges.setdefault(self._indicator_current, [])
        ranges.append(
            IndicatorRange(
                start=pos,
                end=end,
                payload=str(self._indicator_value_current),
                value=int(self._indicator_value_current),
            )
        )
        self._refresh_extra_selections()

    def indicatorClearRange(self, position: int, length: int) -> None:
        pos = max(0, int(position))
        end = max(pos, pos + max(0, int(length)))
        for key in list(self._indicator_ranges.keys()):
            kept: list[IndicatorRange] = []
            for seg in self._indicator_ranges.get(key, []):
                lo = int(seg.start)
                hi = int(seg.end)
                if hi <= pos or lo >= end:
                    kept.append(seg)
                    continue
                if lo < pos:
                    kept.append(IndicatorRange(start=lo, end=pos, payload=seg.payload, value=seg.value))
                if hi > end:
                    kept.append(IndicatorRange(start=end, end=hi, payload=seg.payload, value=seg.value))
            self._indicator_ranges[key] = kept
        if self._active_indicator_hit is not None:
            aid, aidx = self._active_indicator_hit
            current = self._indicator_ranges.get(aid, [])
            if aidx >= len(current):
                self._active_indicator_hit = None
        self._refresh_extra_selections()

    def addIndicatorRange(self, start: int, end: int, *, indicator: int | None = None, payload: str = "", value: int = 0) -> None:
        idx = self._indicator_current if indicator is None else max(0, int(indicator))
        lo = max(0, min(int(start), int(end)))
        hi = max(0, max(int(start), int(end)))
        if hi <= lo:
            return
        self._indicator_ranges.setdefault(idx, []).append(
            IndicatorRange(start=lo, end=hi, payload=str(payload), value=int(value))
        )
        self._refresh_extra_selections()

    def clearHotspots(self) -> None:
        self._hotspot_ranges = []
        self._active_hotspot_index = -1
        self._refresh_extra_selections()

    def addHotspotRange(self, start: int, end: int, payload: str = "") -> None:
        lo = max(0, min(int(start), int(end)))
        hi = max(0, max(int(start), int(end)))
        if hi <= lo:
            return
        self._hotspot_ranges.append(HotspotRange(start=lo, end=hi, payload=str(payload)))
        self._refresh_extra_selections()

    def setHotspotStyle(self, *, color: QColor | str | None = None, underline: bool | None = None) -> None:
        if color is not None:
            self._hotspot_color = color if isinstance(color, QColor) else QColor(str(color))
        if underline is not None:
            self._hotspot_underline = bool(underline)
        self._refresh_extra_selections()

    def _hotspot_index_at_pos(self, pos: int) -> int:
        for idx, hs in enumerate(self._hotspot_ranges):
            if hs.start <= pos < hs.end:
                return idx
        return -1

    def _indicator_hit_at_pos(self, pos: int) -> tuple[int, int] | None:
        for indic_id, ranges in self._indicator_ranges.items():
            for idx, seg in enumerate(ranges):
                if int(seg.start) <= pos < int(seg.end):
                    return int(indic_id), int(idx)
        return None

    def styleSetFore(self, style_id: int, color: QColor | str) -> None:
        fmt = self._style_formats.get(int(style_id), QTextCharFormat())
        fmt.setForeground(color if isinstance(color, QColor) else QColor(str(color)))
        self._style_formats[int(style_id)] = fmt
        self._refresh_extra_selections()

    def styleSetBold(self, style_id: int, bold: bool) -> None:
        fmt = self._style_formats.get(int(style_id), QTextCharFormat())
        fmt.setFontWeight(75 if bool(bold) else 50)
        self._style_formats[int(style_id)] = fmt
        self._refresh_extra_selections()

    def styleSetItalic(self, style_id: int, italic: bool) -> None:
        fmt = self._style_formats.get(int(style_id), QTextCharFormat())
        fmt.setFontItalic(bool(italic))
        self._style_formats[int(style_id)] = fmt
        self._refresh_extra_selections()

    def styleSetUnderline(self, style_id: int, underline: bool) -> None:
        fmt = self._style_formats.get(int(style_id), QTextCharFormat())
        fmt.setFontUnderline(bool(underline))
        self._style_formats[int(style_id)] = fmt
        self._refresh_extra_selections()

    def startStyling(self, position: int) -> None:
        self._style_current_pos = max(0, int(position))

    def setStyling(self, length: int, style_id: int) -> None:
        if int(length) <= 0:
            return
        lo = self._style_current_pos
        hi = lo + int(length)
        self._style_ranges.append((lo, hi, int(style_id)))
        self._style_current_pos = hi
        self._refresh_extra_selections()

    def lexer(self):
        return self._lexer

    def setLexer(self, lexer) -> None:
        self._lexer = lexer
        self._rebuild_lexer_ranges()
        self._refresh_extra_selections()

    def set_column_mode(self, value: bool) -> None:
        self._column_mode = bool(value)
        if not self._column_mode:
            self._clear_multi_ranges()

    def foldAll(self, expand: bool) -> None:
        if not self._folding_enabled:
            return
        self._rebuild_fold_regions()
        if expand:
            self._collapsed_headers.clear()
            self._fold_hidden_lines.clear()
            self._refresh_visibility()
            return
        self._collapsed_headers = set(self._fold_regions.keys())
        self._rebuild_fold_hidden_lines()
        self._refresh_visibility()

    def fold_level(self, level: int, expand: bool) -> None:
        if not self._folding_enabled:
            return
        self._rebuild_fold_regions()
        target = max(0, int(level) - 1)
        for header, region in self._fold_regions.items():
            if region.level != target:
                continue
            if expand:
                self._collapsed_headers.discard(header)
            else:
                self._collapsed_headers.add(header)
        self._rebuild_fold_hidden_lines()
        self._refresh_visibility()

    def fold_line(self, line: int, expand: bool) -> None:
        if not self._folding_enabled:
            return
        self._rebuild_fold_regions()
        region = self._fold_regions.get(int(line))
        if region is None:
            return
        if expand:
            self._collapsed_headers.discard(region.start)
        else:
            self._collapsed_headers.add(region.start)
        self._rebuild_fold_hidden_lines()
        self._refresh_visibility()

    def lines(self) -> int:
        return max(1, self.document().blockCount())

    def markerDefine(self, symbol: int) -> int:
        marker_id = self._next_marker_id
        self._next_marker_id += 1
        self._markers.setdefault(marker_id, set())
        self._marker_symbols[marker_id] = int(symbol)
        return marker_id

    def setMarkerBackgroundColor(self, color, marker_id: int) -> None:
        if isinstance(color, QColor):
            self._marker_colors[int(marker_id)] = color
        else:
            self._marker_colors[int(marker_id)] = QColor(str(color))
        self._margin.update()

    def markerDeleteAll(self, marker_id: int) -> None:
        self._markers[int(marker_id)] = set()
        self._margin.update()

    def markerAdd(self, line: int, marker_id: int) -> None:
        self._markers.setdefault(int(marker_id), set()).add(max(0, int(line)))
        self._margin.update()

    def markerDelete(self, line: int, marker_id: int) -> None:
        self._markers.setdefault(int(marker_id), set()).discard(max(0, int(line)))
        self._margin.update()

    def hide_lines(self, start_line: int, end_line: int) -> bool:
        lo = min(int(start_line), int(end_line))
        hi = max(int(start_line), int(end_line))
        for line in range(lo, hi + 1):
            self._hidden_lines.add(line)
        self._refresh_visibility()
        return True

    def show_all_hidden_lines(self) -> bool:
        had_hidden = bool(self._hidden_lines or self._fold_hidden_lines or self._collapsed_headers)
        self._hidden_lines.clear()
        self._fold_hidden_lines.clear()
        self._collapsed_headers.clear()
        self._refresh_visibility()
        return had_hidden

    def send_scintilla_named(self, command_name: str, *args: int) -> bool:
        command = str(command_name).strip().upper()
        if command == "SCI_HIDELINES" and len(args) >= 2:
            return self.hide_lines(int(args[0]), int(args[1]))
        if command == "SCI_SHOWLINES" and len(args) >= 2:
            return self.show_all_hidden_lines()
        if command == "SCI_SETSELECTIONMODE" and len(args) >= 1:
            self.set_column_mode(int(args[0]) == self.SC_SEL_RECTANGLE)
            return True
        if command == "SCI_SETMULTIPLESELECTION" and len(args) >= 1:
            self.setMultipleSelectionEnabled(bool(args[0]))
            return True
        if command == "SCI_SETADDITIONALSELECTIONTYPING" and len(args) >= 1:
            self.setAdditionalSelectionTyping(bool(args[0]))
            return True
        if command == "SCI_SETMULTIPASTE" and len(args) >= 1:
            self.setMultiPaste(bool(args[0]))
            return True
        if command == "SCI_SETVIEWWS" and len(args) >= 1:
            self._view_whitespace = bool(int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_SETVIEWEOL" and len(args) >= 1:
            self._view_eol = bool(int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_SETCONTROLCHARSYMBOL" and len(args) >= 1:
            self._view_control_chars = bool(int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_SETMARGINSENSITIVEN" and len(args) >= 2:
            self.setMarginSensitivity(int(args[0]), bool(int(args[1])))
            return True
        if command == "SCI_SETMARGINTYPEN" and len(args) >= 2:
            self.setMarginType(int(args[0]), int(args[1]))
            return True
        if command == "SCI_SETMARGINWIDTHN" and len(args) >= 2:
            self.setMarginWidth(int(args[0]), int(args[1]))
            return True
        if command == "SCI_SETMARGINLEFT" and len(args) >= 1:
            self.setMarginLeft(int(args[0]))
            return True
        if command == "SCI_SETMARGINRIGHT" and len(args) >= 1:
            self.setMarginRight(int(args[0]))
            return True
        if command == "SCI_SETMARGINMASKN" and len(args) >= 2:
            self.setMarginMarkerMask(int(args[0]), int(args[1]))
            return True
        if command == "SCI_SETCARETWIDTH" and len(args) >= 1:
            self.setCaretWidth(int(args[0]))
            return True
        if command == "SCI_SETCARETLINEVISIBLE" and len(args) >= 1:
            self.setCaretLineVisible(bool(int(args[0])))
            return True
        if command == "SCI_SETINDICATORCURRENT" and len(args) >= 1:
            self.setIndicatorCurrent(int(args[0]))
            return True
        if command == "SCI_SETINDICATORVALUE" and len(args) >= 1:
            self.setIndicatorValue(int(args[0]))
            return True
        if command == "SCI_INDICSETSTYLE" and len(args) >= 2:
            self.indicatorDefine(int(args[1]), int(args[0]))
            return True
        if command == "SCI_INDICSETFORE" and len(args) >= 2:
            self.setIndicatorForegroundColor(self._qcolor_from_scintilla_rgb(int(args[1])), int(args[0]))
            return True
        if command == "SCI_INDICATORFILLRANGE" and len(args) >= 2:
            self.indicatorFillRange(int(args[0]), int(args[1]))
            return True
        if command == "SCI_INDICATORCLEARRANGE" and len(args) >= 2:
            self.indicatorClearRange(int(args[0]), int(args[1]))
            return True
        if command == "SCI_SETHOTSPOTACTIVEFORE" and len(args) >= 2:
            color = self._qcolor_from_scintilla_rgb(int(args[1]))
            self.setHotspotStyle(color=color)
            self._hotspot_active_color = color.lighter(130)
            return True
        if command == "SCI_SETHOTSPOTACTIVEUNDERLINE" and len(args) >= 1:
            self.setHotspotStyle(underline=bool(int(args[0])))
            return True
        if command == "SCI_STYLESETFORE" and len(args) >= 2:
            self.styleSetFore(int(args[0]), self._qcolor_from_scintilla_rgb(int(args[1])))
            return True
        if command == "SCI_STYLESETBOLD" and len(args) >= 2:
            self.styleSetBold(int(args[0]), bool(int(args[1])))
            return True
        if command == "SCI_STYLESETITALIC" and len(args) >= 2:
            self.styleSetItalic(int(args[0]), bool(int(args[1])))
            return True
        if command == "SCI_STYLESETUNDERLINE" and len(args) >= 2:
            self.styleSetUnderline(int(args[0]), bool(int(args[1])))
            return True
        if command == "SCI_STARTSTYLING" and len(args) >= 1:
            self.startStyling(int(args[0]))
            return True
        if command == "SCI_SETSTYLING" and len(args) >= 2:
            self.setStyling(int(args[0]), int(args[1]))
            return True
        if command == "SCI_SETINDENTATIONGUIDES" and len(args) >= 1:
            self._show_indent_guides = bool(int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_SETWRAPVISUALFLAGS" and len(args) >= 1:
            self._show_wrap_symbol = bool(int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_BRACEHIGHLIGHT" and len(args) >= 2:
            self._brace_match_pair = (int(args[0]), int(args[1]))
            self.viewport().update()
            return True
        if command == "SCI_BRACEBADLIGHT" and len(args) >= 1:
            self._brace_match_pair = (int(args[0]), int(args[0]))
            self.viewport().update()
            return True
        if command == "SCI_FOLDALL" and len(args) >= 1:
            self.foldAll(bool(int(args[0])))
            return True
        if command == "SCI_FOLDLINE" and len(args) >= 2:
            self.fold_line(int(args[0]), bool(int(args[1])))
            return True
        return False

    def margin_width(self) -> int:
        return sum(width for _idx, _kind, _x, width in self._margin_segments()) + self._margin_left_padding + self._margin_right_padding

    def _margin_segments(self) -> list[tuple[int, str, int, int]]:
        digits = max(2, len(str(self.blockCount())))
        dynamic_number_width = 8 + self.fontMetrics().horizontalAdvance("9" * digits)
        x = self._margin_left_padding
        segments: list[tuple[int, str, int, int]] = []
        for idx in (0, 1, 2):
            raw = int(self._margin_widths.get(idx, 0))
            width = dynamic_number_width if raw < 0 else max(0, raw)
            if width <= 0:
                continue
            margin_type = int(self._margin_types.get(idx, self.SC_MARGIN_SYMBOL))
            kind = "symbol"
            if idx == 0:
                kind = "fold"
            elif margin_type == self.SC_MARGIN_NUMBER:
                kind = "number"
            elif margin_type in {self.SC_MARGIN_TEXT, self.SC_MARGIN_RTEXT}:
                kind = "text"
            segments.append((idx, kind, x, width))
            x += width
        return segments

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        width = self.margin_width()
        self._margin.setGeometry(QRect(cr.left(), cr.top(), width, cr.height()))

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_multi_ranges()
        self._paint_annotations()
        self._paint_symbol_overlays()
        self._paint_brace_match()
        if not self._additional_carets:
            return
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing, False)
        color = self.palette().color(self.palette().Text)
        color.setAlpha(210)
        painter.setPen(color)
        for pos in self._additional_carets:
            cursor = QTextCursor(self.document())
            cursor.setPosition(max(0, min(pos, len(self.toPlainText()))))
            rect = self.cursorRect(cursor)
            if not rect.isValid():
                continue
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        painter.end()

    def _paint_annotations(self) -> None:
        if not self._annotations:
            return
        painter = QPainter(self.viewport())
        color = QColor("#6f7684")
        painter.setPen(color)
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= self.viewport().height():
            if block.isVisible() and bottom >= 0:
                line = block.blockNumber()
                note = self._annotations.get(line, "")
                if note:
                    x = int(self.contentOffset().x() + 4)
                    y = int(top + self.fontMetrics().height() - 2)
                    painter.drawText(x, y, note)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()

    def _paint_brace_match(self) -> None:
        pair = self._brace_match_pair
        if pair is None:
            return
        painter = QPainter(self.viewport())
        color = QColor("#5da9ff")
        color.setAlpha(150)
        painter.setPen(color)
        for pos in pair:
            if pos < 0:
                continue
            cursor = QTextCursor(self.document())
            cursor.setPosition(max(0, min(pos, len(self.toPlainText()))))
            rect = self.cursorRect(cursor)
            if rect.isValid():
                painter.drawRect(rect.adjusted(0, 0, max(1, self.fontMetrics().horizontalAdvance(" ")), 0))
        painter.end()

    def _paint_multi_ranges(self) -> None:
        ranges = [(s, e) for s, e in self._multi_ranges if e > s]
        if not ranges:
            return
        painter = QPainter(self.viewport())
        color = self.palette().color(self.palette().Highlight)
        color.setAlpha(90)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        for start, end in ranges:
            c1 = QTextCursor(self.document())
            c2 = QTextCursor(self.document())
            c1.setPosition(max(0, min(start, len(self.toPlainText()))))
            c2.setPosition(max(0, min(end, len(self.toPlainText()))))
            r1 = self.cursorRect(c1)
            r2 = self.cursorRect(c2)
            if not r1.isValid() or not r2.isValid():
                continue
            x1 = min(r1.left(), r2.left())
            x2 = max(r1.left(), r2.left())
            if x1 == x2:
                x2 = x1 + max(2, self.fontMetrics().horizontalAdvance(" "))
            rect = QRect(x1, r1.top(), x2 - x1, r1.height())
            painter.drawRect(rect)
        painter.end()

    def _paint_symbol_overlays(self) -> None:
        if not (
            self._view_whitespace
            or self._view_eol
            or self._view_control_chars
            or self._show_indent_guides
            or self._show_wrap_symbol
        ):
            return
        painter = QPainter(self.viewport())
        overlay = QColor("#8d939f")
        overlay.setAlpha(120)
        painter.setPen(overlay)
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        char_w = max(1, self.fontMetrics().horizontalAdvance(" "))
        while block.isValid() and top <= self.viewport().height():
            if block.isVisible() and bottom >= 0:
                text = block.text()
                base_x = self.contentOffset().x()
                if self._view_whitespace:
                    for idx, ch in enumerate(text):
                        if ch == " ":
                            x = int(base_x + idx * char_w + (char_w // 2))
                            y = int(top + self.fontMetrics().ascent())
                            painter.drawPoint(x, y)
                if self._show_indent_guides:
                    indent = self._indent_of_line(text)
                    for col in range(self._indent_width, indent + 1, max(1, self._indent_width)):
                        x = int(base_x + col * char_w)
                        painter.drawLine(x, top + 1, x, bottom - 1)
                if self._view_control_chars:
                    for idx, ch in enumerate(text):
                        if ord(ch) < 32 and ch != "\t":
                            x = int(base_x + idx * char_w)
                            y = int(top + self.fontMetrics().ascent())
                            painter.drawText(x, y, ".")
                if self._view_eol:
                    x = int(base_x + len(text) * char_w + 2)
                    y = int(top + self.fontMetrics().ascent())
                    painter.drawText(x, y, "$")
                if self._show_wrap_symbol and self.lineWrapMode() == self.WidgetWidth and len(text) * char_w > self.viewport().width():
                    x = max(2, self.viewport().width() - 14)
                    y = int(top + self.fontMetrics().ascent())
                    painter.drawText(x, y, "\\")
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()
    def paint_margin(self, event) -> None:
        painter = QPainter(self._margin)
        painter.fillRect(event.rect(), QColor("#202228"))
        segments = self._margin_segments()

        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                line = block.blockNumber()
                text_color = QColor("#8f95a1")
                if line == self.textCursor().blockNumber():
                    text_color = QColor("#c8ced9")
                for idx, kind, x, width in segments:
                    if kind == "number":
                        painter.setPen(text_color)
                        painter.drawText(
                            x,
                            top,
                            width,
                            self.fontMetrics().height(),
                            int(Qt.AlignRight | Qt.AlignVCenter),
                            str(line + 1),
                        )
                    elif kind == "fold":
                        self._paint_fold_glyph(painter, line, x, top)
                    else:
                        self._paint_marker_glyph(painter, line, x, top, margin=idx)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()

    def handle_margin_click(self, event: QMouseEvent) -> None:
        line = self._line_from_y(int(event.position().y()))
        if line < 0:
            return
        x = int(event.position().x())
        margin_idx = -1
        margin_kind = ""
        for idx, kind, seg_x, width in self._margin_segments():
            if seg_x <= x < (seg_x + width):
                margin_idx = idx
                margin_kind = kind
                break
        if margin_kind == "fold" and line in self._fold_regions:
            if line in self._collapsed_headers:
                self.fold_line(line, expand=True)
            else:
                self.fold_line(line, expand=False)
            return
        if margin_idx >= 0 and self._margin_sensitive.get(margin_idx, False):
            self.marginClicked.emit(margin_idx, line)
        self.setCursorPosition(line, 0)
        self.setFocus()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        mods = event.modifiers()
        add_multi_caret = bool(mods & Qt.ControlModifier) and bool(mods & Qt.AltModifier)
        if self._multiple_selection_enabled and add_multi_caret:
            self._clear_multi_ranges()
            cursor = self.cursorForPosition(event.position().toPoint())
            pos = int(cursor.position())
            if pos in self._additional_carets:
                self._additional_carets = [p for p in self._additional_carets if p != pos]
            else:
                self._additional_carets.append(pos)
                self._additional_carets = sorted(set(self._additional_carets))
            self.viewport().update()
            return
        if event.button() == Qt.LeftButton and self._column_mode:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._column_drag_anchor = (cursor.blockNumber(), cursor.columnNumber())
            self._column_drag_active = True
            self._apply_column_drag(cursor.blockNumber(), cursor.columnNumber())
            self.viewport().update()
            return
        if self._additional_carets:
            self._additional_carets = []
            self._clear_multi_ranges()
            self.viewport().update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._column_drag_active and self._column_drag_anchor is not None:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._apply_column_drag(cursor.blockNumber(), cursor.columnNumber())
            self.viewport().update()
            return
        pos = int(self.cursorForPosition(event.position().toPoint()).position())
        active_idx = self._hotspot_index_at_pos(pos)
        indic_hit = self._indicator_hit_at_pos(pos)
        if active_idx != self._active_hotspot_index:
            self._active_hotspot_index = active_idx
            self._refresh_extra_selections()
        if indic_hit != self._active_indicator_hit:
            self._active_indicator_hit = indic_hit
            self._refresh_extra_selections()
        if active_idx >= 0:
            payload = self._hotspot_ranges[active_idx].payload
            self.hotspotHovered.emit(pos, payload)
            self.viewport().setCursor(Qt.PointingHandCursor)
        elif indic_hit is not None:
            indic_id, _hit_idx = indic_hit
            payload = self._indicator_ranges.get(indic_id, [])[ _hit_idx ].payload if _hit_idx < len(self._indicator_ranges.get(indic_id, [])) else ""
            self.indicatorHovered.emit(indic_id, pos, payload)
            self.viewport().setCursor(Qt.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._column_drag_active and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.position().toPoint())
            self._apply_column_drag(cursor.blockNumber(), cursor.columnNumber())
            self._column_drag_active = False
            self.viewport().update()
            return
        if event.button() == Qt.LeftButton:
            pos = int(self.cursorForPosition(event.position().toPoint()).position())
            idx = self._hotspot_index_at_pos(pos)
            if idx >= 0:
                self.hotspotClicked.emit(pos, self._hotspot_ranges[idx].payload)
            else:
                indic_hit = self._indicator_hit_at_pos(pos)
                if indic_hit is not None:
                    indic_id, hit_idx = indic_hit
                    payload = ""
                    ranges = self._indicator_ranges.get(indic_id, [])
                    if 0 <= hit_idx < len(ranges):
                        payload = ranges[hit_idx].payload
                    self.indicatorClicked.emit(indic_id, pos, payload)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape:
            if self._completer.popup().isVisible():
                self._completer.popup().hide()
                return
            self._clear_multi_ranges()
            self._additional_carets = []
            self.viewport().update()
            return
        if self._multi_ranges and (self._column_mode or self._additional_selection_typing):
            if event.key() in {Qt.Key_Backspace, Qt.Key_Delete}:
                self._delete_multi_ranges(backward=event.key() == Qt.Key_Backspace)
                return
            if event.matches(QKeySequence.Paste):
                text = self._clipboard_text()
                if text:
                    if self._multi_paste:
                        lines = text.splitlines()
                        if len(lines) == len(self._multi_ranges):
                            self._replace_ranges_with_text_rows(self._multi_ranges, lines)
                            return
                    self._replace_ranges_with_text(self._multi_ranges, text)
                return
            if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                self._replace_ranges_with_text(self._multi_ranges, self._block_newline_text())
                return
            if event.key() == Qt.Key_Tab:
                text = "\t" if self._use_tabs else (" " * self._indent_width)
                self._replace_ranges_with_text(self._multi_ranges, text)
                return
            text = event.text()
            if text and not (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
                self._replace_ranges_with_text(self._multi_ranges, text)
                return
        if not (self._multiple_selection_enabled and self._additional_selection_typing and self._additional_carets):
            super().keyPressEvent(event)
            return
        if self.textCursor().hasSelection():
            super().keyPressEvent(event)
            return
        if event.key() in {Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End}:
            self._move_all_carets(event.key(), keep_anchor=bool(event.modifiers() & Qt.ShiftModifier))
            return
        if event.key() in {Qt.Key_Backspace, Qt.Key_Delete}:
            self._delete_at_all_carets(backward=event.key() == Qt.Key_Backspace)
            return
        if event.matches(QKeySequence.Paste):
            text = self._clipboard_text()
            if text:
                if self._multi_paste:
                    positions = sorted(set([self.textCursor().position(), *self._additional_carets]))
                    lines = text.splitlines()
                    if len(lines) == len(positions):
                        self._insert_rows_at_all_carets(lines)
                        return
                self._insert_text_at_all_carets(text)
                return
        if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
            self._insert_text_at_all_carets(self._block_newline_text())
            return
        if event.key() == Qt.Key_Tab:
            self._insert_text_at_all_carets("\t" if self._use_tabs else (" " * self._indent_width))
            return
        text = event.text()
        if text and not (event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier)):
            self._insert_text_at_all_carets(text)
            return
        force_completion = event.key() == Qt.Key_Space and bool(event.modifiers() & Qt.ControlModifier)
        super().keyPressEvent(event)
        if force_completion:
            self._invoke_completion(force=True)
            return
        if text and self._auto_completion_source != self.AcsNone:
            self._invoke_completion(force=False)

    def _insert_text_at_all_carets(self, text: str) -> None:
        positions = sorted(set([self.textCursor().position(), *self._additional_carets]))
        if not positions:
            return
        primary = self.textCursor().position()
        delta = 0
        new_positions: list[int] = []
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for pos in positions:
            adjusted = pos + delta
            cursor.setPosition(adjusted)
            cursor.insertText(text)
            new_positions.append(adjusted + len(text))
            delta += len(text)
        cursor.endEditBlock()
        if primary in positions:
            idx = positions.index(primary)
            new_primary = new_positions[idx]
        else:
            new_primary = new_positions[-1]
        caret = self.textCursor()
        caret.setPosition(new_primary)
        self.setTextCursor(caret)
        self._additional_carets = [p for p in new_positions if p != new_primary]
        self.viewport().update()

    def _insert_rows_at_all_carets(self, rows: list[str]) -> None:
        positions = sorted(set([self.textCursor().position(), *self._additional_carets]))
        if not positions or len(rows) != len(positions):
            return
        primary = self.textCursor().position()
        shift = 0
        new_positions: list[int] = []
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for pos, row in zip(positions, rows):
            adjusted = pos + shift
            cursor.setPosition(adjusted)
            cursor.insertText(row)
            new_positions.append(adjusted + len(row))
            shift += len(row)
        cursor.endEditBlock()
        if primary in positions:
            idx = positions.index(primary)
            new_primary = new_positions[idx]
        else:
            new_primary = new_positions[-1]
        caret = self.textCursor()
        caret.setPosition(new_primary)
        self.setTextCursor(caret)
        self._additional_carets = [p for p in new_positions if p != new_primary]
        self.viewport().update()

    def _move_all_carets(self, key: int, *, keep_anchor: bool) -> None:
        positions = sorted(set([self.textCursor().position(), *self._additional_carets]))
        if not positions:
            return
        source = self.toPlainText()
        new_positions: list[int] = []
        for pos in positions:
            if key == Qt.Key_Left:
                new_pos = max(0, pos - 1)
            elif key == Qt.Key_Right:
                new_pos = min(len(source), pos + 1)
            elif key == Qt.Key_Home:
                line, _col = self._line_col_from_pos(pos)
                new_pos = self._index_from_line_col(line, 0)
            elif key == Qt.Key_End:
                line, _col = self._line_col_from_pos(pos)
                block = self.document().findBlockByNumber(line)
                new_pos = block.position() + (len(block.text()) if block.isValid() else 0)
            else:
                new_pos = pos
            new_positions.append(new_pos)
        primary_new = new_positions[-1]
        tc = self.textCursor()
        if keep_anchor:
            tc.setPosition(tc.position())
            tc.setPosition(primary_new, QTextCursor.KeepAnchor)
        else:
            tc.setPosition(primary_new)
        self.setTextCursor(tc)
        self._additional_carets = new_positions[:-1]
        self.viewport().update()

    def _delete_at_all_carets(self, *, backward: bool) -> None:
        positions = sorted(set([self.textCursor().position(), *self._additional_carets]))
        if not positions:
            return
        primary = self.textCursor().position()
        shift = 0
        new_positions: list[int] = []
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for pos in positions:
            adjusted = max(0, min(len(self.toPlainText()), pos + shift))
            if backward:
                if adjusted <= 0:
                    new_positions.append(0)
                    continue
                cursor.setPosition(adjusted - 1)
                cursor.setPosition(adjusted, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                shift -= 1
                new_positions.append(adjusted - 1)
            else:
                if adjusted >= len(self.toPlainText()):
                    new_positions.append(adjusted)
                    continue
                cursor.setPosition(adjusted)
                cursor.setPosition(adjusted + 1, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                shift -= 1
                new_positions.append(adjusted)
        cursor.endEditBlock()
        if primary in positions:
            idx = positions.index(primary)
            new_primary = new_positions[idx]
        else:
            new_primary = new_positions[-1]
        caret = self.textCursor()
        caret.setPosition(max(0, new_primary))
        self.setTextCursor(caret)
        self._additional_carets = [p for p in new_positions if p != new_primary]
        self.viewport().update()

    def _replace_ranges_with_text(self, ranges: list[tuple[int, int]], text: str) -> None:
        ordered = sorted((min(s, e), max(s, e)) for s, e in ranges)
        if not ordered:
            return
        primary = self.textCursor().position()
        shift = 0
        new_positions: list[int] = []
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for start, end in ordered:
            start_adj = max(0, min(len(self.toPlainText()), start + shift))
            end_adj = max(start_adj, min(len(self.toPlainText()), end + shift))
            cursor.setPosition(start_adj)
            cursor.setPosition(end_adj, QTextCursor.KeepAnchor)
            cursor.insertText(text)
            delta = len(text) - (end_adj - start_adj)
            shift += delta
            new_positions.append(start_adj + len(text))
        cursor.endEditBlock()
        candidate_old = [start for start, _ in ordered]
        if candidate_old:
            primary_idx = min(range(len(candidate_old)), key=lambda i: abs(candidate_old[i] - primary))
            new_primary = new_positions[primary_idx]
        else:
            new_primary = self.textCursor().position()
        caret = self.textCursor()
        caret.setPosition(max(0, new_primary))
        self.setTextCursor(caret)
        self._additional_carets = [p for p in new_positions if p != new_primary]
        if self._column_mode and self._column_block is not None and "\n" not in text and "\r" not in text:
            width = len(text)
            self._column_block.col_hi = self._column_block.col_lo + max(0, width)
            self._reapply_column_block()
        else:
            self._clear_multi_ranges()
        self.viewport().update()

    def _replace_ranges_with_text_rows(self, ranges: list[tuple[int, int]], rows: list[str]) -> None:
        ordered = sorted((min(s, e), max(s, e), idx) for idx, (s, e) in enumerate(ranges))
        if not ordered or len(rows) != len(ordered):
            return
        primary = self.textCursor().position()
        shift = 0
        new_positions: list[int] = [0] * len(rows)
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for start, end, idx in ordered:
            text = rows[idx]
            start_adj = max(0, min(len(self.toPlainText()), start + shift))
            end_adj = max(start_adj, min(len(self.toPlainText()), end + shift))
            cursor.setPosition(start_adj)
            cursor.setPosition(end_adj, QTextCursor.KeepAnchor)
            cursor.insertText(text)
            delta = len(text) - (end_adj - start_adj)
            shift += delta
            new_positions[idx] = start_adj + len(text)
        cursor.endEditBlock()
        candidate_old = [min(s, e) for s, e in ranges]
        if candidate_old:
            primary_idx = min(range(len(candidate_old)), key=lambda i: abs(candidate_old[i] - primary))
            new_primary = new_positions[primary_idx]
        else:
            new_primary = self.textCursor().position()
        caret = self.textCursor()
        caret.setPosition(max(0, new_primary))
        self.setTextCursor(caret)
        self._additional_carets = [p for p in new_positions if p != new_primary]
        if self._column_mode and self._column_block is not None:
            width = max((len(row) for row in rows), default=0)
            self._column_block.col_hi = self._column_block.col_lo + max(0, width)
            self._reapply_column_block()
        else:
            self._clear_multi_ranges()
        self.viewport().update()

    def _delete_multi_ranges(self, *, backward: bool) -> None:
        ranges = [(s, e) for s, e in self._multi_ranges if s != e]
        if ranges:
            self._replace_ranges_with_text(ranges, "")
            return
        self._delete_at_all_carets(backward=backward)

    def _clipboard_text(self) -> str:
        try:
            from PySide6.QtGui import QGuiApplication

            clip = QGuiApplication.clipboard()
            return clip.text() if clip is not None else ""
        except Exception:
            return ""

    def _on_text_changed(self) -> None:
        self._rebuild_fold_regions()
        self._rebuild_lexer_ranges()
        self._refresh_visibility()
        self._refresh_extra_selections()
        self._margin.update()

    def _on_cursor_changed(self) -> None:
        self._auto_brace_match()
        self._margin.update()
        self.viewport().update()

    def _update_margin_width(self, _new_count: int) -> None:
        self.setViewportMargins(self.margin_width(), 0, 0, 0)
        self._margin.setFixedWidth(self.margin_width())

    def _update_margin_area(self, rect, dy: int) -> None:
        if dy:
            self._margin.scroll(0, dy)
        else:
            self._margin.update(0, rect.y(), self._margin.width(), rect.height())

    def _paint_marker_glyph(self, painter: QPainter, line: int, x: int, top: int, *, margin: int) -> None:
        marker_id = self._first_masked_marker_for_line(line, margin=margin)
        if marker_id is None:
            return
        color = self._marker_colors.get(marker_id, QColor("#ffcc00"))
        symbol = int(self._marker_symbols.get(marker_id, self.Circle))
        h = self.fontMetrics().height()
        size = max(6, min(10, h - 2))
        left = int(x + 2)
        top_y = int(top + max(1, (h - size) // 2))
        rect = QRect(left, top_y, size, size)
        painter.setBrush(color)
        painter.setPen(color.darker(130))
        if symbol == self.Empty:
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(rect)
        elif symbol in {self.Circle, self.RoundRect}:
            if symbol == self.RoundRect:
                painter.drawRoundedRect(rect, 2, 2)
            else:
                painter.drawEllipse(rect)
        elif symbol in {self.RightArrow, self.Arrow, self.ShortArrow}:
            cy = rect.center().y()
            tip = rect.right()
            tail = rect.left()
            half = max(2, rect.height() // 3)
            poly = QPolygon([QPoint(tail, cy - half), QPoint(tip, cy), QPoint(tail, cy + half)])
            painter.drawPolygon(poly)
        elif symbol == self.Plus:
            painter.drawRect(rect)
            painter.drawLine(rect.left() + 2, rect.center().y(), rect.right() - 2, rect.center().y())
            painter.drawLine(rect.center().x(), rect.top() + 2, rect.center().x(), rect.bottom() - 2)
        elif symbol == self.Minus:
            painter.drawRect(rect)
            painter.drawLine(rect.left() + 2, rect.center().y(), rect.right() - 2, rect.center().y())
        elif symbol == self.SmallRect:
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        else:
            painter.drawEllipse(rect)

    def _first_masked_marker_for_line(self, line: int, *, margin: int) -> int | None:
        mask = int(self._margin_marker_masks.get(int(margin), -1))
        for mid, lines in self._markers.items():
            if line not in lines:
                continue
            if mask == -1:
                return mid
            if 0 <= int(mid) < 63 and (mask & (1 << int(mid))):
                return mid
        return None

    def _paint_fold_glyph(self, painter: QPainter, line: int, x: int, top: int) -> None:
        if not self._folding_enabled or line not in self._fold_regions:
            return
        h = self.fontMetrics().height()
        y = top + max(1, (h - 10) // 2)
        box = QRect(x + 2, y, 10, 10)
        painter.setPen(QColor("#8f95a1"))
        painter.setBrush(QColor("#2c2f36"))
        painter.drawRect(box)
        painter.drawLine(box.left() + 2, box.center().y(), box.right() - 2, box.center().y())
        if line in self._collapsed_headers:
            painter.drawLine(box.center().x(), box.top() + 2, box.center().x(), box.bottom() - 2)

    def _line_from_y(self, y: int) -> int:
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid():
            if block.isVisible() and top <= y <= bottom:
                return block.blockNumber()
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        return -1

    def _rebuild_fold_regions(self) -> None:
        lines = self.toPlainText().splitlines()
        if not lines:
            self._fold_regions = {}
            self._collapsed_headers.clear()
            self._fold_hidden_lines.clear()
            return
        non_blank: list[tuple[int, int]] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            non_blank.append((idx, self._indent_of_line(line)))
        if len(non_blank) < 2:
            self._fold_regions = {}
            self._collapsed_headers.clear()
            self._fold_hidden_lines.clear()
            return
        regions: dict[int, FoldRegion] = {}
        stack: list[tuple[int, int]] = []
        prev_line, prev_indent = non_blank[0]
        for current_line, current_indent in non_blank[1:]:
            while stack and current_indent <= stack[-1][1]:
                header_line, header_indent = stack.pop()
                regions[header_line] = FoldRegion(
                    start=header_line,
                    end=prev_line,
                    level=max(0, header_indent // max(1, self._indent_width)),
                )
            if current_indent > prev_indent:
                stack.append((prev_line, prev_indent))
            prev_line, prev_indent = current_line, current_indent
        while stack:
            header_line, header_indent = stack.pop()
            regions[header_line] = FoldRegion(
                start=header_line,
                end=prev_line,
                level=max(0, header_indent // max(1, self._indent_width)),
            )
        indent_regions = {k: v for k, v in regions.items() if v.end > v.start}
        bracket_regions = self._build_bracket_fold_regions(lines)
        merged: dict[int, FoldRegion] = {}
        for start, region in indent_regions.items():
            merged[start] = region
        for start, region in bracket_regions.items():
            current = merged.get(start)
            if current is None:
                merged[start] = region
                continue
            if region.end > current.end:
                merged[start] = FoldRegion(start=start, end=region.end, level=min(current.level, region.level))
        self._fold_regions = merged
        self._collapsed_headers = {line for line in self._collapsed_headers if line in self._fold_regions}
        self._rebuild_fold_hidden_lines()

    def _build_bracket_fold_regions(self, lines: list[str]) -> dict[int, FoldRegion]:
        regions: dict[int, FoldRegion] = {}
        stack: list[tuple[int, int]] = []
        in_block_comment = False
        in_string: str | None = None
        escape = False
        for line_no, line in enumerate(lines):
            i = 0
            while i < len(line):
                ch = line[i]
                nxt = line[i + 1] if i + 1 < len(line) else ""
                if in_string is not None:
                    if escape:
                        escape = False
                        i += 1
                        continue
                    if ch == "\\":
                        escape = True
                        i += 1
                        continue
                    if ch == in_string:
                        in_string = None
                    i += 1
                    continue
                if in_block_comment:
                    if ch == "*" and nxt == "/":
                        in_block_comment = False
                        i += 2
                        continue
                    i += 1
                    continue
                if ch == "/" and nxt == "/":
                    break
                if ch == "/" and nxt == "*":
                    in_block_comment = True
                    i += 2
                    continue
                if ch in {"'", '"', "`"}:
                    in_string = ch
                    i += 1
                    continue
                if ch == "{":
                    stack.append((line_no, len(stack)))
                elif ch == "}":
                    if stack:
                        start_line, depth = stack.pop()
                        if line_no > start_line:
                            current = regions.get(start_line)
                            candidate = FoldRegion(start=start_line, end=line_no, level=depth)
                            if current is None or candidate.end > current.end:
                                regions[start_line] = candidate
                i += 1
        return regions

    def _rebuild_fold_hidden_lines(self) -> None:
        hidden: set[int] = set()
        for header in self._collapsed_headers:
            region = self._fold_regions.get(header)
            if region is None:
                continue
            for line in range(region.start + 1, region.end + 1):
                hidden.add(line)
        self._fold_hidden_lines = hidden

    def _refresh_visibility(self) -> None:
        hidden_union = self._hidden_lines | self._fold_hidden_lines
        block = self.document().firstBlock()
        while block.isValid():
            line = block.blockNumber()
            should_show = line not in hidden_union
            if block.isVisible() != should_show:
                block.setVisible(should_show)
            block = block.next()
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()
        self._margin.update()

    def _indent_of_line(self, line: str) -> int:
        total = 0
        for ch in line:
            if ch == " ":
                total += 1
            elif ch == "\t":
                total += max(1, self._indent_width)
            else:
                break
        return total

    def _index_from_line_col(self, line: int, col: int) -> int:
        line = max(0, int(line))
        col = max(0, int(col))
        block = self.document().findBlockByNumber(line)
        if not block.isValid():
            return max(0, len(self.toPlainText()))
        return min(block.position() + col, block.position() + len(block.text()))

    def _line_col_from_pos(self, pos: int) -> tuple[int, int]:
        block = self.document().findBlock(max(0, min(pos, len(self.toPlainText()))))
        return block.blockNumber(), max(0, min(pos - block.position(), len(block.text())))

    def _clear_multi_ranges(self) -> None:
        self._multi_ranges = []
        self._column_block = None

    def _apply_column_drag(self, line: int, col: int) -> None:
        if self._column_drag_anchor is None:
            return
        a_line, a_col = self._column_drag_anchor
        line_lo = min(a_line, line)
        line_hi = max(a_line, line)
        col_lo = min(a_col, col)
        col_hi = max(a_col, col)
        ranges: list[tuple[int, int]] = []
        carets: list[int] = []
        for ln in range(line_lo, line_hi + 1):
            start = self._index_from_line_col(ln, col_lo)
            end = self._index_from_line_col(ln, col_hi)
            ranges.append((start, end))
            carets.append(end)
        if not carets:
            return
        primary = carets[-1]
        tc = self.textCursor()
        tc.setPosition(primary)
        self.setTextCursor(tc)
        self._additional_carets = [p for p in carets[:-1] if p != primary]
        self._multi_ranges = ranges
        self._column_block = ColumnBlock(
            line_lo=line_lo,
            line_hi=line_hi,
            col_lo=col_lo,
            col_hi=col_hi,
        )

    def _reapply_column_block(self) -> None:
        block = self._column_block
        if block is None:
            return
        ranges: list[tuple[int, int]] = []
        carets: list[int] = []
        for ln in range(block.line_lo, block.line_hi + 1):
            start = self._index_from_line_col(ln, block.col_lo)
            end = self._index_from_line_col(ln, block.col_hi)
            ranges.append((start, end))
            carets.append(end)
        if not carets:
            self._clear_multi_ranges()
            return
        primary = carets[-1]
        tc = self.textCursor()
        tc.setPosition(primary)
        self.setTextCursor(tc)
        self._additional_carets = [p for p in carets[:-1] if p != primary]
        self._multi_ranges = ranges

    def _block_newline_text(self) -> str:
        cursor = self.textCursor()
        block = cursor.block()
        line = block.text() if block.isValid() else ""
        indent_chars: list[str] = []
        for ch in line:
            if ch in {" ", "\t"}:
                indent_chars.append(ch)
            else:
                break
        return "\n" + "".join(indent_chars)

    def _refresh_completion_words(self) -> None:
        if self._auto_completion_source == self.AcsNone:
            self._completion_model.setStringList([])
            return
        words = set(self._completion_words)
        if self._auto_completion_source in {self.AcsDocument, self.AcsAll}:
            words.update(self._document_words())
        if self._auto_completion_source in {self.AcsAPIs, self.AcsAll} and self._completion_words:
            words.update(self._completion_words)
        self._completion_model.setStringList(sorted(words))

    def _document_words(self) -> set[str]:
        return {m.group(0) for m in re.finditer(r"[A-Za-z_][A-Za-z0-9_]{1,}", self.toPlainText())}

    def _current_word_span(self) -> tuple[int, int]:
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()
        if not text:
            return pos, pos
        start = pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        end = pos
        while end < len(text) and (text[end].isalnum() or text[end] == "_"):
            end += 1
        return start, end

    def _invoke_completion(self, *, force: bool) -> None:
        self._refresh_completion_words()
        start, end = self._current_word_span()
        prefix = self.toPlainText()[start:end]
        threshold = max(1, int(self._auto_completion_threshold))
        if not force and len(prefix) < threshold:
            self._completer.popup().hide()
            return
        self._completer.setCompletionPrefix(prefix)
        popup = self._completer.popup()
        if popup is None:
            return
        cr = self.cursorRect()
        cr.setWidth(max(220, popup.sizeHintForColumn(0) + 24))
        self._completer.complete(cr)

    def _insert_completion(self, completion: str) -> None:
        text = str(completion or "")
        if not text:
            return
        start, end = self._current_word_span()
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(text)
        self.setTextCursor(cursor)

    def _rebuild_lexer_ranges(self) -> None:
        if self._lexer is None:
            self._lexer_ranges = []
            return
        language = self._detect_lexer_language(self._lexer)
        source = self.toPlainText()
        if not source:
            self._lexer_ranges = []
            return
        ranges: list[tuple[int, int, int]] = []
        if language == "python":
            kw = r"\b(?:and|as|assert|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)\b"
            ranges.extend(self._find_style_ranges(source, kw, 1))
            ranges.extend(self._find_style_ranges(source, r"#.*", 2))
            ranges.extend(self._find_style_ranges(source, r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\")", 3))
            ranges.extend(self._find_style_ranges(source, r"\b\d+(\.\d+)?\b", 4))
        elif language in {"javascript", "typescript", "json"}:
            kw = r"\b(?:break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|false|finally|for|function|if|import|in|instanceof|let|new|null|return|super|switch|this|throw|true|try|typeof|var|void|while|with|yield)\b"
            ranges.extend(self._find_style_ranges(source, kw, 1))
            ranges.extend(self._find_style_ranges(source, r"//.*", 2))
            ranges.extend(self._find_style_ranges(source, r"/\*[\s\S]*?\*/", 2))
            ranges.extend(self._find_style_ranges(source, r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"|`([^`\\]|\\.)*`)", 3))
            ranges.extend(self._find_style_ranges(source, r"\b\d+(\.\d+)?\b", 4))
        elif language == "markdown":
            ranges.extend(self._find_style_ranges(source, r"^#{1,6} .*$", 5, flags=re.MULTILINE))
            ranges.extend(self._find_style_ranges(source, r"`{1,3}[^`]+`{1,3}", 3))
            ranges.extend(self._find_style_ranges(source, r"\*\*[^*]+\*\*", 1))
        self._lexer_ranges = ranges
        self._ensure_default_styles()

    def _detect_lexer_language(self, lexer) -> str:
        label = ""
        for attr in ("language", "name"):
            value = getattr(lexer, attr, None)
            if callable(value):
                try:
                    label = str(value()).strip().lower()
                except Exception:
                    label = ""
            else:
                label = str(value or "").strip().lower()
            if label:
                break
        if not label:
            label = lexer.__class__.__name__.lower()
        if "python" in label:
            return "python"
        if "json" in label:
            return "json"
        if "typescript" in label:
            return "typescript"
        if "javascript" in label or "js" in label:
            return "javascript"
        if "markdown" in label or "md" in label:
            return "markdown"
        return "plain"

    def _find_style_ranges(self, source: str, pattern: str, style_id: int, *, flags: int = 0) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for match in re.finditer(pattern, source, flags):
            lo, hi = match.span()
            if hi > lo:
                out.append((lo, hi, int(style_id)))
        return out

    def _ensure_default_styles(self) -> None:
        defaults: dict[int, tuple[str, bool, bool, bool]] = {
            1: ("#b96ad9", True, False, False),
            2: ("#7a828f", False, True, False),
            3: ("#6fb1ff", False, False, False),
            4: ("#f2c879", False, False, False),
            5: ("#cfd8e3", True, False, False),
        }
        for style_id, (color, bold, italic, under) in defaults.items():
            if style_id in self._style_formats:
                continue
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            fmt.setFontWeight(75 if bold else 50)
            fmt.setFontItalic(italic)
            fmt.setFontUnderline(under)
            self._style_formats[style_id] = fmt

    def _refresh_extra_selections(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        if self._caret_line_visible:
            current_line = QTextEdit.ExtraSelection()
            current_line.cursor = self.textCursor()
            current_line.cursor.clearSelection()
            line_fmt = QTextCharFormat()
            bg = QColor(self._caret_line_color)
            if not bg.isValid():
                bg = self.palette().alternateBase().color()
            line_fmt.setBackground(bg)
            line_fmt.setProperty(QTextCharFormat.FullWidthSelection, True)
            current_line.format = line_fmt
            selections.append(current_line)
        doc_len = len(self.toPlainText())
        for lo, hi, style_id in [*self._lexer_ranges, *self._style_ranges]:
            fmt = self._style_formats.get(style_id)
            if fmt is None:
                continue
            sel = QTextEdit.ExtraSelection()
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(max(0, min(lo, doc_len)))
            sel.cursor.setPosition(max(0, min(hi, doc_len)), QTextCursor.KeepAnchor)
            sel.format = QTextCharFormat(fmt)
            selections.append(sel)
        for indic_id, ranges in self._indicator_ranges.items():
            color = self._indicator_colors.get(indic_id, QColor("#f4d03f"))
            style = int(self._indicator_styles.get(indic_id, 0))
            for idx, seg in enumerate(ranges):
                lo = int(seg.start)
                hi = int(seg.end)
                sel = QTextEdit.ExtraSelection()
                sel.cursor = self.textCursor()
                sel.cursor.setPosition(max(0, min(lo, doc_len)))
                sel.cursor.setPosition(max(0, min(hi, doc_len)), QTextCursor.KeepAnchor)
                fmt = QTextCharFormat()
                hit = self._active_indicator_hit == (int(indic_id), int(idx))
                active_color = color.lighter(130) if hit else color
                if style == self.INDIC_HIDDEN:
                    continue
                if style == self.INDIC_PLAIN:
                    fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)
                    fmt.setUnderlineColor(active_color)
                elif style == self.INDIC_SQUIGGLE:
                    fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
                    fmt.setUnderlineColor(active_color)
                elif style == self.INDIC_TT:
                    fmt.setUnderlineStyle(QTextCharFormat.DotLine)
                    fmt.setUnderlineColor(active_color)
                elif style == self.INDIC_DIAGONAL:
                    fmt.setUnderlineStyle(QTextCharFormat.DashUnderline)
                    fmt.setUnderlineColor(active_color)
                elif style == self.INDIC_STRIKE:
                    fmt.setFontStrikeOut(True)
                    fmt.setForeground(active_color)
                else:
                    shade = QColor(active_color)
                    shade.setAlpha(90 if style == self.INDIC_BOX else 70)
                    fmt.setBackground(shade)
                    if style == self.INDIC_ROUNDBOX:
                        fmt.setUnderlineStyle(QTextCharFormat.SingleUnderline)
                        fmt.setUnderlineColor(active_color.darker(120))
                sel.format = fmt
                selections.append(sel)
        for idx, hs in enumerate(self._hotspot_ranges):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(max(0, min(hs.start, doc_len)))
            sel.cursor.setPosition(max(0, min(hs.end, doc_len)), QTextCursor.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setForeground(self._hotspot_active_color if idx == self._active_hotspot_index else self._hotspot_color)
            fmt.setFontUnderline(self._hotspot_underline)
            sel.format = fmt
            selections.append(sel)
        self.setExtraSelections(selections)

    @staticmethod
    def _qcolor_from_scintilla_rgb(value: int) -> QColor:
        iv = int(value)
        r = iv & 0xFF
        g = (iv >> 8) & 0xFF
        b = (iv >> 16) & 0xFF
        return QColor(r, g, b)

    def _auto_brace_match(self) -> None:
        text = self.toPlainText()
        if not text:
            self._brace_match_pair = None
            return
        pos = self.textCursor().position()
        pair = self._find_nearby_brace_pair(text, pos)
        self._brace_match_pair = pair

    def _find_nearby_brace_pair(self, text: str, pos: int) -> tuple[int, int] | None:
        if pos > 0 and pos - 1 < len(text):
            pair = self._find_brace_pair_at(text, pos - 1)
            if pair is not None:
                return pair
        if pos < len(text):
            pair = self._find_brace_pair_at(text, pos)
            if pair is not None:
                return pair
        return None

    def _find_brace_pair_at(self, text: str, index: int) -> tuple[int, int] | None:
        if index < 0 or index >= len(text):
            return None
        ch = text[index]
        opens = {"(": ")", "[": "]", "{": "}"}
        closes = {")": "(", "]": "[", "}": "{"}
        if ch in opens:
            target = opens[ch]
            depth = 0
            for i in range(index + 1, len(text)):
                c = text[i]
                if c == ch:
                    depth += 1
                elif c == target:
                    if depth == 0:
                        return index, i
                    depth -= 1
            return index, -1
        if ch in closes:
            target = closes[ch]
            depth = 0
            for i in range(index - 1, -1, -1):
                c = text[i]
                if c == ch:
                    depth += 1
                elif c == target:
                    if depth == 0:
                        return i, index
                    depth -= 1
            return -1, index
        return None
