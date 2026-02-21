from __future__ import annotations

import difflib
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class _Hunk:
    start_a: int
    end_a: int
    start_b: int
    end_b: int
    old_lines: list[str]
    new_lines: list[str]


class AIEditPreviewDialog(QDialog):
    def __init__(self, parent, original_text: str, proposed_text: str, title: str = "AI Edit Preview") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1000, 620)
        self._original_lines = original_text.splitlines(keepends=True)
        self._proposed_lines = proposed_text.splitlines(keepends=True)
        self._hunks = self._build_hunks(self._original_lines, self._proposed_lines)
        self.final_text = original_text

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Review changes. Uncheck hunks you want to reject.", self))

        split = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(split, 1)

        left = QWidget(split)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Hunks", left))
        self.hunk_list = QListWidget(left)
        left_layout.addWidget(self.hunk_list, 1)

        right = QWidget(split)
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Diff Preview", right))
        self.diff_preview = QTextEdit(right)
        self.diff_preview.setReadOnly(True)
        right_layout.addWidget(self.diff_preview, 1)

        compare = QWidget(split)
        compare_layout = QVBoxLayout(compare)
        compare_layout.addWidget(QLabel("Proposed Result", compare))
        self.result_preview = QTextEdit(compare)
        self.result_preview.setReadOnly(True)
        compare_layout.addWidget(self.result_preview, 1)

        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setStretchFactor(2, 2)

        self.buttons = QDialogButtonBox(self)
        self.apply_button = self.buttons.addButton("Apply Selected Hunks", QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = self.buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(self.buttons)

        self.apply_button.clicked.connect(self._accept_with_merge)
        self.cancel_button.clicked.connect(self.reject)
        self.hunk_list.currentItemChanged.connect(self._refresh_hunk_diff)
        self.hunk_list.itemChanged.connect(lambda _item: self._refresh_result_preview())

        self._populate_hunks()
        self._refresh_result_preview()

    @staticmethod
    def _build_hunks(old_lines: list[str], new_lines: list[str]) -> list[_Hunk]:
        sm = difflib.SequenceMatcher(a=old_lines, b=new_lines)
        hunks: list[_Hunk] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            hunks.append(
                _Hunk(
                    start_a=i1,
                    end_a=i2,
                    start_b=j1,
                    end_b=j2,
                    old_lines=old_lines[i1:i2],
                    new_lines=new_lines[j1:j2],
                )
            )
        return hunks

    def _populate_hunks(self) -> None:
        self.hunk_list.clear()
        if not self._hunks:
            item = QListWidgetItem("No textual changes detected")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.hunk_list.addItem(item)
            self.apply_button.setEnabled(False)
            return
        for idx, hunk in enumerate(self._hunks, start=1):
            old_span = f"{hunk.start_a + 1}-{max(hunk.start_a + 1, hunk.end_a)}"
            new_span = f"{hunk.start_b + 1}-{max(hunk.start_b + 1, hunk.end_b)}"
            text = f"Hunk {idx}  old:{old_span}  new:{new_span}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, idx - 1)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.hunk_list.addItem(item)
        self.hunk_list.setCurrentRow(0)

    def _refresh_hunk_diff(self) -> None:
        item = self.hunk_list.currentItem()
        if item is None:
            self.diff_preview.clear()
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(index, int) or not (0 <= index < len(self._hunks)):
            self.diff_preview.clear()
            return
        hunk = self._hunks[index]
        diff_lines = list(
            difflib.unified_diff(
                hunk.old_lines,
                hunk.new_lines,
                fromfile="original",
                tofile="ai",
                lineterm="",
            )
        )
        self.diff_preview.setPlainText("\n".join(diff_lines))

    def _is_hunk_enabled(self, index: int) -> bool:
        for row in range(self.hunk_list.count()):
            item = self.hunk_list.item(row)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data == index:
                return item.checkState() == Qt.CheckState.Checked
        return False

    def _merged_text(self) -> str:
        sm = difflib.SequenceMatcher(a=self._original_lines, b=self._proposed_lines)
        merged: list[str] = []
        hunk_idx = 0
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                merged.extend(self._original_lines[i1:i2])
                continue
            if self._is_hunk_enabled(hunk_idx):
                merged.extend(self._proposed_lines[j1:j2])
            else:
                merged.extend(self._original_lines[i1:i2])
            hunk_idx += 1
        return "".join(merged)

    def _refresh_result_preview(self) -> None:
        self.result_preview.setPlainText(self._merged_text())

    def _accept_with_merge(self) -> None:
        self.final_text = self._merged_text()
        self.accept()
