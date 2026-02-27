from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from pypad.ui.main_window.window import Notepad


PRESET_SHORTCUTS: dict[str, dict[str, str]] = {
    "default": {},
    "vscode": {
        "new_action": "Ctrl+N",
        "open_action": "Ctrl+O",
        "save_action": "Ctrl+S",
        "find_action": "Ctrl+F",
        "replace_action": "Ctrl+H",
        "close_tab_action": "Ctrl+W",
        "zoom_in_action": "Ctrl+=",
        "zoom_out_action": "Ctrl+-",
        "zoom_reset_action": "Ctrl+0",
        "full_screen_action": "F11",
    },
    "notepad++": {
        "new_action": "Ctrl+N",
        "open_action": "Ctrl+O",
        "save_action": "Ctrl+S",
        "find_action": "Ctrl+F",
        "replace_action": "Ctrl+H",
        "find_next_action": "F3",
        "find_prev_action": "Shift+F3",
        "close_tab_action": "Ctrl+W",
        "toggle_bookmark_action": "Ctrl+F2",
        "next_bookmark_action": "F2",
        "prev_bookmark_action": "Shift+F2",
    },
    "sublime": {
        "new_action": "Ctrl+N",
        "open_action": "Ctrl+O",
        "save_action": "Ctrl+S",
        "find_action": "Ctrl+F",
        "replace_action": "Ctrl+H",
        "find_next_action": "F3",
        "close_tab_action": "Ctrl+W",
        "pin_tab_action": "Ctrl+Shift+P",
    },
}


@dataclass
class ShortcutActionRow:
    action_id: str
    label: str
    action: QAction


def sequence_to_string(seq: QKeySequence) -> str:
    return seq.toString(QKeySequence.SequenceFormat.NativeText)


def _read_action_shortcuts(action: QAction) -> list[str]:
    seqs = [sequence_to_string(seq).strip() for seq in action.shortcuts() if not seq.isEmpty()]
    if not seqs:
        fallback = action.shortcut()
        if not fallback.isEmpty():
            seqs = [sequence_to_string(fallback).strip()]
    return [s for s in seqs if s]


def parse_shortcut_value(value: str | list[str]) -> list[QKeySequence]:
    if isinstance(value, list):
        texts = [str(v).strip() for v in value if str(v).strip()]
    else:
        texts = [str(value or "").strip()]
    return [QKeySequence(text) for text in texts if text]


class KeyCaptureDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Press Shortcut")
        self.resize(320, 120)
        self.captured: QKeySequence | None = None
        layout = QVBoxLayout(self)
        self.info = QLabel("Press key combination now...", self)
        layout.addWidget(self.info)
        buttons = QDialogButtonBox(self)
        self.clear_btn = QPushButton("Clear", self)
        self.cancel_btn = QPushButton("Cancel", self)
        buttons.addButton(self.clear_btn, QDialogButtonBox.ButtonRole.DestructiveRole)
        buttons.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        self.clear_btn.clicked.connect(self._clear)
        self.cancel_btn.clicked.connect(self.reject)

    def _clear(self) -> None:
        self.captured = QKeySequence()
        self.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = int(event.key())
        mod = int(event.modifiers())
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            event.accept()
            return
        seq = QKeySequence(mod | key)
        self.captured = seq
        self.accept()


class ShortcutMapperDialog(QDialog):
    def __init__(
        self,
        parent: "Notepad",
        actions: list[ShortcutActionRow],
        default_shortcuts: dict[str, list[str]],
        settings: dict,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Shortcut Mapper")
        self.resize(860, 620)
        self._window = parent
        self._actions = actions
        self._defaults = default_shortcuts
        self._settings = settings
        self._action_by_id = {row.action_id: row for row in actions}
        self._working_map: dict[str, str | list[str]] = dict(settings.get("shortcut_map", {}))

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Preset:", self))
        self.preset_combo = QComboBox(self)
        self.preset_combo.addItems(["default", "vscode", "notepad++", "sublime"])
        self.preset_combo.setCurrentText(str(settings.get("shortcut_profile", "vscode")))
        top.addWidget(self.preset_combo)
        top.addSpacing(12)
        top.addWidget(QLabel("Conflict policy:", self))
        self.conflict_combo = QComboBox(self)
        self.conflict_combo.addItems(["warn", "block", "allow"])
        self.conflict_combo.setCurrentText(str(settings.get("shortcut_conflict_policy", "warn")))
        top.addWidget(self.conflict_combo)
        top.addStretch(1)

        self.import_btn = QPushButton("Import JSON...", self)
        self.export_btn = QPushButton("Export JSON...", self)
        top.addWidget(self.import_btn)
        top.addWidget(self.export_btn)
        root.addLayout(top)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut", "Set", "Reset"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, self.table.horizontalHeader().ResizeMode.Stretch)
        self.table.setRowCount(len(actions))
        root.addWidget(self.table, 1)

        for row_idx, row in enumerate(actions):
            self.table.setItem(row_idx, 0, QTableWidgetItem(row.label))
            self.table.setItem(row_idx, 1, QTableWidgetItem(""))
            set_btn = QPushButton("Set...", self.table)
            reset_btn = QPushButton("Reset", self.table)
            set_btn.clicked.connect(lambda _=False, aid=row.action_id: self._set_shortcut_for(aid))
            reset_btn.clicked.connect(lambda _=False, aid=row.action_id: self._reset_shortcut_for(aid))
            self.table.setCellWidget(row_idx, 2, set_btn)
            self.table.setCellWidget(row_idx, 3, reset_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.apply_btn = QPushButton("Apply", self)
        buttons.addButton(self.apply_btn, QDialogButtonBox.ButtonRole.ApplyRole)
        root.addWidget(buttons)
        buttons.accepted.connect(self._accept_with_apply)
        buttons.rejected.connect(self.reject)
        self.apply_btn.clicked.connect(self.apply_live)

        self.import_btn.clicked.connect(self._import_json)
        self.export_btn.clicked.connect(self._export_json)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)

        self._refresh_table()

    def _effective_map(self) -> dict[str, list[str]]:
        profile = self.preset_combo.currentText()
        combined: dict[str, list[str]] = dict(self._defaults)
        preset = PRESET_SHORTCUTS.get(profile, {})
        for aid, seq in preset.items():
            combined[aid] = [seq]
        for aid, value in self._working_map.items():
            seqs = parse_shortcut_value(value)
            combined[aid] = [sequence_to_string(s) for s in seqs if not s.isEmpty()]
        return combined

    def _refresh_table(self) -> None:
        mapping = self._effective_map()
        for row_idx, row in enumerate(self._actions):
            current = mapping.get(row.action_id, [])
            self.table.item(row_idx, 1).setText(", ".join(current))

    def _find_conflict(self, target_id: str, text: str) -> str | None:
        mapping = self._effective_map()
        for aid, seqs in mapping.items():
            if aid == target_id:
                continue
            if text in seqs:
                return aid
        return None

    def _set_shortcut_for(self, action_id: str) -> None:
        dlg = KeyCaptureDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        seq = dlg.captured or QKeySequence()
        text = sequence_to_string(seq).strip()
        policy = self.conflict_combo.currentText()
        if text:
            conflict_id = self._find_conflict(action_id, text)
            if conflict_id is not None:
                conflict_label = self._action_by_id[conflict_id].label
                if policy == "block":
                    QMessageBox.warning(self, "Conflict Blocked", f"Shortcut already used by: {conflict_label}")
                    return
                if policy == "warn":
                    btn = QMessageBox.question(
                        self,
                        "Shortcut Conflict",
                        f"{text} is already used by {conflict_label}. Continue?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No,
                    )
                    if btn != QMessageBox.StandardButton.Yes:
                        return
        self._working_map[action_id] = text
        self._refresh_table()

    def _reset_shortcut_for(self, action_id: str) -> None:
        self._working_map.pop(action_id, None)
        self._refresh_table()

    def _apply_preset(self) -> None:
        self._refresh_table()

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Shortcut Map", "", "JSON (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Shortcut map must be an object.")
            raw = data.get("shortcut_map", data)
            if not isinstance(raw, dict):
                raise ValueError("Invalid shortcut_map shape.")
            cleaned: dict[str, str | list[str]] = {}
            for key, value in raw.items():
                if isinstance(key, str):
                    if isinstance(value, (str, list)):
                        cleaned[key] = value
            self._working_map = cleaned
            if isinstance(data.get("shortcut_profile"), str):
                self.preset_combo.setCurrentText(data["shortcut_profile"])
            if isinstance(data.get("shortcut_conflict_policy"), str):
                self.conflict_combo.setCurrentText(data["shortcut_conflict_policy"])
            self._refresh_table()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import Failed", f"Could not import shortcut map:\n{exc}")

    def _export_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Shortcut Map", "", "JSON (*.json);;All Files (*.*)")
        if not path:
            return
        payload = {
            "shortcut_profile": self.preset_combo.currentText(),
            "shortcut_conflict_policy": self.conflict_combo.currentText(),
            "shortcut_map": self._working_map,
        }
        try:
            Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Failed", f"Could not export shortcut map:\n{exc}")

    def apply_live(self) -> None:
        self._settings["shortcut_profile"] = self.preset_combo.currentText()
        self._settings["shortcut_conflict_policy"] = self.conflict_combo.currentText()
        self._settings["shortcut_map"] = dict(self._working_map)
        self._window.settings.update(self._settings)
        self._window.apply_shortcut_settings()
        self._window.save_settings_to_disk()

    def _accept_with_apply(self) -> None:
        self.apply_live()
        self.accept()

