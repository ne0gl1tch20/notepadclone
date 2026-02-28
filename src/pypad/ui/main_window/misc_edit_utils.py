from __future__ import annotations

import os
import random
import re
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .notepadpp_pref_runtime import build_search_internet_url
from pypad.ui.theme.dialog_theme import apply_dialog_theme_from_window


class MiscEditUtilsMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    # ---------- Edit extensions ----------
    def edit_insert_datetime_short(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.insert_text(datetime.now().strftime("%Y-%m-%d"))

    def edit_insert_datetime_long(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.insert_text(datetime.now().strftime("%A, %B %d, %Y %H:%M:%S"))

    def edit_insert_datetime_custom(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        fmt, ok = QInputDialog.getText(self, "Date Time (customized)", "strftime format:", text="%Y-%m-%d %H:%M:%S")
        if not ok or not fmt.strip():
            return
        try:
            tab.text_edit.insert_text(datetime.now().strftime(fmt.strip()))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Date Time", f"Invalid format string:\n{exc}")

    def edit_copy_current_full_file_path(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(tab.current_file)

    def edit_copy_current_filename(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(Path(tab.current_file).name)

    def edit_copy_current_dir_path(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.current_file:
            return
        QApplication.clipboard().setText(str(Path(tab.current_file).parent))

    def edit_copy_all_filenames(self) -> None:
        names: list[str] = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            names.append(Path(tab.current_file).name if tab.current_file else "Untitled")
        if names:
            QApplication.clipboard().setText("\n".join(names))

    def edit_copy_all_filepaths(self) -> None:
        paths: list[str] = []
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file:
                paths.append(tab.current_file)
        if paths:
            QApplication.clipboard().setText("\n".join(paths))

    def edit_column_editor(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Column Editor")
        dlg.resize(420, 320)
        apply_dialog_theme_from_window(self, dlg)
        root = QVBoxLayout(dlg)

        text_radio = QRadioButton("Text to Insert")
        text_radio.setChecked(True)
        text_input = QLineEdit(dlg)

        number_radio = QRadioButton("Number to Insert")
        number_group = QGroupBox("Format", dlg)
        number_layout = QHBoxLayout(number_group)
        format_dec = QRadioButton("Dec")
        format_dec.setChecked(True)
        format_hex = QRadioButton("Hex")
        format_oct = QRadioButton("Oct")
        format_bin = QRadioButton("Bin")
        hex_case = QComboBox(dlg)
        hex_case.addItems(["a-f", "A-F"])
        hex_case.setEnabled(False)
        for widget in (format_dec, format_hex, format_oct, format_bin, hex_case):
            number_layout.addWidget(widget)

        form = QFormLayout()
        initial_input = QLineEdit(dlg)
        increment_input = QLineEdit(dlg)
        repeat_input = QLineEdit(dlg)
        leading_combo = QComboBox(dlg)
        leading_combo.addItems(["None", "Zeroes"])
        form.addRow("Initial number:", initial_input)
        form.addRow("Increase by:", increment_input)
        form.addRow("Repeat:", repeat_input)
        form.addRow("Leading:", leading_combo)

        def _toggle_number_widgets(checked: bool) -> None:
            number_group.setEnabled(checked)
            initial_input.setEnabled(checked)
            increment_input.setEnabled(checked)
            repeat_input.setEnabled(checked)
            leading_combo.setEnabled(checked)
            text_input.setEnabled(not checked)

        def _toggle_hex_case() -> None:
            hex_case.setEnabled(format_hex.isChecked())

        format_hex.toggled.connect(lambda _checked: _toggle_hex_case())
        _toggle_number_widgets(False)
        number_radio.toggled.connect(_toggle_number_widgets)

        root.addWidget(text_radio)
        root.addWidget(text_input)
        root.addSpacing(6)
        root.addWidget(number_radio)
        root.addWidget(number_group)
        root.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        root.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.Accepted:
            return

        if text_radio.isChecked():
            insert_values = []
            value = text_input.text()
            if not value:
                return
        else:
            try:
                initial = int(initial_input.text().strip() or "0")
                increment = int(increment_input.text().strip() or "1")
                repeat = max(1, int(repeat_input.text().strip() or "1"))
            except ValueError:
                QMessageBox.warning(self, "Column Editor", "Please enter valid numbers.")
                return

            def _format_num(num: int) -> str:
                if format_hex.isChecked():
                    formatted = f"{num:x}"
                    if hex_case.currentText() == "A-F":
                        formatted = formatted.upper()
                    return formatted
                if format_oct.isChecked():
                    return f"{num:o}"
                if format_bin.isChecked():
                    return f"{num:b}"
                return str(num)

            insert_values = []
            value = initial
            counter = 0
            line_count = 0
            selection = tab.text_edit.selection_range()
            if selection is not None:
                line1, _c1, line2, c2 = selection
                if line2 > line1 and c2 == 0:
                    line2 -= 1
                line_count = max(1, line2 - line1 + 1)
            if line_count <= 0:
                line_count = 1
            for _ in range(line_count):
                insert_values.append(_format_num(value))
                counter += 1
                if counter >= repeat:
                    value += increment
                    counter = 0
            if leading_combo.currentText() == "Zeroes":
                width = max(len(val) for val in insert_values)
                insert_values = [val.zfill(width) for val in insert_values]

        selection = tab.text_edit.selection_range()
        if selection is None:
            line1, col1 = tab.text_edit.cursor_position()
            line2 = line1
            col2 = col1
        else:
            line1, col1, line2, col2 = selection
            if line2 < line1:
                line1, line2 = line2, line1
                col1, col2 = col2, col1
            if line2 > line1 and col2 == 0:
                line2 -= 1
        if line2 < line1:
            return

        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            lines = [""]
        line2 = min(line2, len(lines) - 1)
        targets = list(range(line1, line2 + 1))
        if text_radio.isChecked():
            insert_values = [value for _ in targets]
        if len(insert_values) < len(targets):
            insert_values.extend([insert_values[-1]] * (len(targets) - len(insert_values)))

        for idx, line_no in enumerate(targets):
            line = lines[line_no]
            if col1 > len(line):
                line = line + (" " * (col1 - len(line)))
            insert_text = insert_values[idx]
            lines[line_no] = line[:col1] + insert_text + line[col1:]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_character_panel(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Character Panel")
        dlg.resize(520, 420)
        apply_dialog_theme_from_window(self, dlg)
        layout = QVBoxLayout(dlg)
        table = QTableWidget(dlg)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Value", "Hex", "Character"])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        rows = list(range(32, 127))
        table.setRowCount(len(rows))
        for row_idx, value in enumerate(rows):
            table.setItem(row_idx, 0, QTableWidgetItem(str(value)))
            table.setItem(row_idx, 1, QTableWidgetItem(f"{value:02X}"))
            table.setItem(row_idx, 2, QTableWidgetItem(chr(value)))
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)
        buttons = QDialogButtonBox(dlg)
        insert_btn = buttons.addButton("Insert", QDialogButtonBox.AcceptRole)
        copy_btn = buttons.addButton("Copy", QDialogButtonBox.ActionRole)
        close_btn = buttons.addButton(QDialogButtonBox.Close)
        layout.addWidget(buttons)

        def _selected_char() -> str:
            row = table.currentRow()
            if row < 0:
                return ""
            item = table.item(row, 2)
            return item.text() if item is not None else ""

        def _insert() -> None:
            ch = _selected_char()
            if not ch:
                return
            tab.text_edit.insert_text(ch)
            dlg.accept()

        def _copy() -> None:
            ch = _selected_char()
            if ch:
                QApplication.clipboard().setText(ch)

        insert_btn.clicked.connect(_insert)
        copy_btn.clicked.connect(_copy)
        close_btn.clicked.connect(dlg.reject)
        dlg.exec()

    def _edit_replace_selection_or_all(self, transform) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        if tab.text_edit.has_selection():
            source = tab.text_edit.selected_text()
            tab.text_edit.replace_selection(transform(source))
            return
        source = tab.text_edit.get_text()
        tab.text_edit.set_text(transform(source))
        tab.text_edit.set_modified(True)

    def edit_convert_uppercase(self) -> None:
        self._edit_replace_selection_or_all(lambda s: s.upper())

    def edit_convert_lowercase(self) -> None:
        self._edit_replace_selection_or_all(lambda s: s.lower())

    def edit_convert_proper_case(self) -> None:
        self._edit_replace_selection_or_all(lambda s: " ".join(word.capitalize() for word in s.split(" ")))

    def edit_convert_sentence_case(self) -> None:
        def _sentence(s: str) -> str:
            parts = re.split(r"([.!?]\s+)", s)
            out: list[str] = []
            for idx in range(0, len(parts), 2):
                seg = parts[idx].strip()
                sep = parts[idx + 1] if idx + 1 < len(parts) else ""
                out.append((seg[:1].upper() + seg[1:].lower()) if seg else seg)
                out.append(sep)
            return "".join(out)

        self._edit_replace_selection_or_all(_sentence)

    def edit_convert_invert_case(self) -> None:
        def _invert(s: str) -> str:
            return "".join(ch.lower() if ch.isupper() else ch.upper() if ch.islower() else ch for ch in s)

        self._edit_replace_selection_or_all(_invert)

    def edit_convert_random_case(self) -> None:
        def _random_case(s: str) -> str:
            return "".join(ch.upper() if ch.isalpha() and random.random() > 0.5 else ch.lower() if ch.isalpha() else ch for ch in s)

        self._edit_replace_selection_or_all(_random_case)

    def _edit_line_bounds(self) -> tuple[int, int]:
        tab = self.active_tab()
        if tab is None:
            return 0, 0
        line, _col = tab.text_edit.cursor_position()
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return 0, 0
        line = max(0, min(len(lines) - 1, line))
        return line, len(lines)

    def _edit_selected_line_range(self) -> tuple[int, int]:
        tab = self.active_tab()
        if tab is None:
            return 0, -1
        selection = tab.text_edit.selection_range()
        if selection is None:
            line, _col = tab.text_edit.cursor_position()
            return line, line
        line1, _c1, line2, c2 = selection
        if line2 < line1:
            line1, line2 = line2, line1
        if line2 > line1 and c2 == 0:
            line2 -= 1
        return line1, line2

    def edit_indent_selection(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        line1, line2 = self._edit_selected_line_range()
        if line2 < line1:
            return
        tab_width = int(self.settings.get("tab_width", 4) or 4)
        indent = " " * max(1, tab_width)
        for idx in range(line1, min(line2, len(lines) - 1) + 1):
            lines[idx] = indent + lines[idx]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_unindent_selection(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        line1, line2 = self._edit_selected_line_range()
        if line2 < line1:
            return
        tab_width = int(self.settings.get("tab_width", 4) or 4)
        for idx in range(line1, min(line2, len(lines) - 1) + 1):
            line = lines[idx]
            if line.startswith("\t"):
                lines[idx] = line[1:]
                continue
            if line.startswith(" "):
                trim = min(tab_width, len(line) - len(line.lstrip(" ")))
                lines[idx] = line[trim:]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def _text_eol_mode(self, text: str) -> str:
        if hasattr(self, "_detect_eol_mode"):
            try:
                return self._detect_eol_mode(text)
            except Exception:
                pass
        if "\r\n" in text:
            return "CRLF"
        if "\n" in text:
            return "LF"
        return "LF"

    def edit_trim_trailing_spaces(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        trimmed_lines = [re.sub(r"[ \t]+$", "", line) for line in lines]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        if trimmed != text:
            tab.text_edit.set_text(trimmed)
            tab.text_edit.set_modified(True)
            self.show_status_message("Trimmed trailing spaces.", 2500)

    def edit_trim_leading_spaces(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        trimmed_lines = [re.sub(r"^[ \t]+", "", line) for line in lines]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        if trimmed != text:
            tab.text_edit.set_text(trimmed)
            tab.text_edit.set_modified(True)
            self.show_status_message("Trimmed leading spaces.", 2500)

    def edit_remove_leading_blank_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx <= 0:
            return
        trimmed_lines = lines[idx:]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        tab.text_edit.set_text(trimmed)
        tab.text_edit.set_modified(True)
        self.show_status_message("Removed leading blank lines.", 2500)

    def edit_remove_trailing_blank_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        text = tab.text_edit.get_text()
        if not text:
            return
        lines = text.splitlines()
        idx = len(lines) - 1
        while idx >= 0 and not lines[idx].strip():
            idx -= 1
        if idx >= len(lines) - 1:
            return
        trimmed_lines = lines[: idx + 1]
        had_trailing_newline = text.endswith(("\r\n", "\n", "\r"))
        eol = "\r\n" if self._text_eol_mode(text) == "CRLF" else "\n"
        trimmed = eol.join(trimmed_lines)
        if trimmed_lines and had_trailing_newline:
            trimmed += eol
        tab.text_edit.set_text(trimmed)
        tab.text_edit.set_modified(True)
        self.show_status_message("Removed trailing blank lines.", 2500)

    def edit_begin_end_select(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        anchor = getattr(self, "_begin_select_anchor", None)
        if anchor is None:
            self._begin_select_anchor = (tab.text_edit.cursor_position(), False)
            self.show_status_message("Selection start set.", 1500)
            return
        (line, col), _column = anchor
        cur_line, cur_col = tab.text_edit.cursor_position()
        tab.text_edit.set_selection_by_index(
            tab.text_edit.index_from_line_col(line, col),
            tab.text_edit.index_from_line_col(cur_line, cur_col),
        )
        self._begin_select_anchor = None

    def edit_begin_end_select_column(self) -> None:
        tab = self.active_tab()
        if tab is None or not tab.text_edit.is_scintilla:
            return
        anchor = getattr(self, "_begin_select_anchor", None)
        if anchor is None:
            self._begin_select_anchor = (tab.text_edit.cursor_position(), True)
            self.show_status_message("Column selection start set.", 1500)
            return
        (line, col), is_column = anchor
        cur_line, cur_col = tab.text_edit.cursor_position()
        if is_column and not tab.column_mode:
            tab.column_mode = True
            if hasattr(self, "column_mode_action"):
                self.column_mode_action.blockSignals(True)
                self.column_mode_action.setChecked(True)
                self.column_mode_action.blockSignals(False)
            tab.text_edit.set_column_mode(True)
        if tab.text_edit.is_scintilla and hasattr(tab.text_edit.widget, "setSelection"):
            tab.text_edit.widget.setSelection(line, col, cur_line, cur_col)
            tab.text_edit.widget.setCursorPosition(cur_line, cur_col)
        else:
            tab.text_edit.set_selection_by_index(
                tab.text_edit.index_from_line_col(line, col),
                tab.text_edit.index_from_line_col(cur_line, cur_col),
            )
        self._begin_select_anchor = None

    def edit_line_duplicate_current(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, total = self._edit_line_bounds()
        if total <= 0:
            return
        lines = tab.text_edit.get_text().splitlines()
        lines.insert(line + 1, lines[line])
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_join_selected(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if selected.strip():
            tab.text_edit.replace_selection(" ".join(selected.splitlines()))
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line >= total - 1:
            return
        lines[line] = f"{lines[line].rstrip()} {lines[line + 1].lstrip()}".strip()
        del lines[line + 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_split_selected(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if not selected.strip():
            return
        tab.text_edit.replace_selection("\n".join(selected.split()))

    def edit_line_move_up(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line <= 0:
            return
        lines[line - 1], lines[line] = lines[line], lines[line - 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line - 1, 0)

    def edit_line_move_down(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 1 or line >= total - 1:
            return
        lines[line + 1], lines[line] = lines[line], lines[line + 1]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line + 1, 0)

    def edit_line_remove_duplicate_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        seen = set()
        unique: list[str] = []
        for line in tab.text_edit.get_text().splitlines():
            if line in seen:
                continue
            seen.add(line)
            unique.append(line)
        tab.text_edit.set_text("\n".join(unique))
        tab.text_edit.set_modified(True)

    def edit_line_remove_consecutive_duplicate_lines(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if not lines:
            return
        deduped = [lines[0]]
        for line in lines[1:]:
            if line != deduped[-1]:
                deduped.append(line)
        tab.text_edit.set_text("\n".join(deduped))
        tab.text_edit.set_modified(True)

    def edit_line_insert_blank_above(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 0:
            lines = [""]
            line = 0
        else:
            lines.insert(line, "")
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line, 0)

    def edit_line_insert_blank_below(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        line, total = self._edit_line_bounds()
        if total <= 0:
            lines = [""]
            line = 0
        else:
            lines.insert(line + 1, "")
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)
        tab.text_edit.set_cursor_position(line + 1, 0)

    def edit_line_remove_empty(self, include_whitespace: bool = True) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        if include_whitespace:
            lines = [line for line in lines if line.strip()]
        else:
            lines = [line for line in lines if line != ""]
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_reverse(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        lines.reverse()
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def edit_line_sort(self, ascending: bool = True, ignore_case: bool = False) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        lines = tab.text_edit.get_text().splitlines()
        key = (lambda s: s.lower()) if ignore_case else (lambda s: s)
        lines = sorted(lines, key=key, reverse=not ascending)
        tab.text_edit.set_text("\n".join(lines))
        tab.text_edit.set_modified(True)

    def _line_comment_prefix(self) -> str:
        tab = self.active_tab()
        lang = self._detect_language_for_tab(tab) if tab is not None else "plain"
        if lang in {"python", "markdown", "yaml", "toml"}:
            return "# "
        if lang in {"javascript", "json", "css", "typescript"}:
            return "// "
        return "# "

    def edit_single_line_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        prefix = self._line_comment_prefix()
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line)
        tab.text_edit.replace_line(line, prefix + current)
        tab.text_edit.set_modified(True)

    def edit_single_line_uncomment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line)
        for marker in ("# ", "// ", "#", "//"):
            stripped = current.lstrip()
            if stripped.startswith(marker):
                lead = current[: len(current) - len(stripped)]
                current = lead + stripped[len(marker) :]
                break
        tab.text_edit.replace_line(line, current)
        tab.text_edit.set_modified(True)

    def edit_toggle_single_line_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        line, _ = tab.text_edit.cursor_position()
        current = tab.text_edit.get_line_text(line).lstrip()
        if current.startswith(("#", "//")):
            self.edit_single_line_uncomment()
        else:
            self.edit_single_line_comment()

    def edit_block_comment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only() or not tab.text_edit.has_selection():
            return
        selected = tab.text_edit.selected_text()
        tab.text_edit.replace_selection(f"/* {selected} */")
        tab.text_edit.set_modified(True)

    def edit_block_uncomment(self) -> None:
        tab = self.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        selected = tab.text_edit.selected_text()
        if selected.strip().startswith("/*") and selected.strip().endswith("*/"):
            stripped = selected.strip()[2:-2].strip()
            tab.text_edit.replace_selection(stripped)
            tab.text_edit.set_modified(True)

    def edit_set_eol_mac(self) -> None:
        self.set_tab_eol_mode("CR")

    def edit_open_selection_file(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        candidate = tab.text_edit.selected_text().strip().strip("\"'")
        if not candidate:
            return
        path = Path(candidate)
        if path.exists() and path.is_file():
            self._open_file_path(str(path))

    def edit_open_selection_folder(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        candidate = tab.text_edit.selected_text().strip().strip("\"'")
        if not candidate:
            return
        path = Path(candidate)
        folder = path.parent if path.is_file() else path
        if folder.exists() and folder.is_dir():
            os.startfile(str(folder))  # type: ignore[attr-defined]

    def edit_search_selection_internet(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        query = tab.text_edit.selected_text().strip() or self.last_search_text or ""
        if not query:
            return
        webbrowser.open(build_search_internet_url(self.settings, query))

    def edit_toggle_read_only_current(self) -> None:
        tab = self.active_tab()
        if tab is None:
            return
        next_state = not bool(tab.read_only)
        if tab.current_file and hasattr(self, "_set_file_read_only"):
            self._set_file_read_only(tab.current_file, next_state)
        tab.read_only = next_state
        tab.text_edit.set_read_only(next_state)
        self._refresh_tab_title(tab)
        self.update_action_states()

    def edit_toggle_read_only_all(self) -> None:
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file and hasattr(self, "_set_file_read_only"):
                self._set_file_read_only(tab.current_file, True)
            tab.read_only = True
            tab.text_edit.set_read_only(True)
            self._refresh_tab_title(tab)
        self.update_action_states()

    def edit_clear_read_only_all(self) -> None:
        for i in range(self.tab_widget.count()):
            tab = self._tab_at_index(i)
            if tab is None:
                continue
            if tab.current_file and hasattr(self, "_set_file_read_only"):
                self._set_file_read_only(tab.current_file, False)
            tab.read_only = False
            tab.text_edit.set_read_only(False)
            self._refresh_tab_title(tab)
        self.update_action_states()


