from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)


@dataclass
class Reminder:
    reminder_id: str
    title: str
    note_ref: str
    due_iso: str
    notes: str = ""
    recurrence: str = "none"  # none, daily, weekly, monthly
    fired: bool = False

    @property
    def due_datetime(self) -> datetime:
        return datetime.fromisoformat(self.due_iso)

    def set_due(self, due_dt: datetime) -> None:
        self.due_iso = due_dt.isoformat()


def _add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + ((dt.month - 1 + months) // 12)
    month = ((dt.month - 1 + months) % 12) + 1
    day = min(dt.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return dt.replace(year=year, month=month, day=day)


class ReminderStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.reminders: list[Reminder] = []

    def load(self) -> None:
        if not self.path.exists():
            self.reminders = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.reminders = [
                Reminder(
                    reminder_id=item["reminder_id"],
                    title=item.get("title", ""),
                    note_ref=item.get("note_ref", ""),
                    due_iso=item["due_iso"],
                    notes=item.get("notes", ""),
                    recurrence=item.get("recurrence", "none"),
                    fired=bool(item.get("fired", False)),
                )
                for item in data
            ]
        except Exception:
            self.reminders = []

    def save(self) -> None:
        data = [
            {
                "reminder_id": r.reminder_id,
                "title": r.title,
                "note_ref": r.note_ref,
                "due_iso": r.due_iso,
                "notes": r.notes,
                "recurrence": r.recurrence,
                "fired": r.fired,
            }
            for r in self.reminders
        ]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add(self, title: str, note_ref: str, due_dt: datetime, notes: str, recurrence: str) -> Reminder:
        reminder = Reminder(
            reminder_id=str(uuid.uuid4()),
            title=title,
            note_ref=note_ref,
            due_iso=due_dt.isoformat(),
            notes=notes,
            recurrence=recurrence,
        )
        self.reminders.append(reminder)
        return reminder

    def remove(self, reminder_id: str) -> None:
        self.reminders = [r for r in self.reminders if r.reminder_id != reminder_id]

    def by_id(self, reminder_id: str) -> Reminder | None:
        for reminder in self.reminders:
            if reminder.reminder_id == reminder_id:
                return reminder
        return None

    def snooze(self, reminder: Reminder, delta: timedelta) -> None:
        reminder.set_due(datetime.now() + delta)
        reminder.fired = False

    def reschedule_recurring(self, reminder: Reminder) -> None:
        due = reminder.due_datetime
        if reminder.recurrence == "daily":
            reminder.set_due(due + timedelta(days=1))
        elif reminder.recurrence == "weekly":
            reminder.set_due(due + timedelta(days=7))
        elif reminder.recurrence == "monthly":
            reminder.set_due(_add_months(due, 1))


class RemindersDialog(QDialog):
    def __init__(self, parent, store: ReminderStore, note_ref: str, note_title: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reminders")
        self.resize(760, 460)
        self.store = store
        self.note_ref = note_ref
        self.note_title = note_title

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        left.addWidget(QLabel("Upcoming reminders", self))
        self.list_widget = QListWidget(self)
        left.addWidget(self.list_widget)
        layout.addLayout(left, 2)

        right = QVBoxLayout()
        details_group = QGroupBox("Details", self)
        details_form = QFormLayout(details_group)
        self.title_input = QLineEdit(details_group)
        self.title_input.setPlaceholderText("Reminder title")
        self.notes_input = QTextEdit(details_group)
        self.notes_input.setPlaceholderText("Notes")
        self.notes_input.setFixedHeight(90)
        self.due_input = QDateTimeEdit(details_group)
        self.due_input.setCalendarPopup(True)
        self.due_input.setDateTime(QDateTime.currentDateTime().addSecs(3600))
        self.recurrence_combo = QComboBox(details_group)
        self.recurrence_combo.addItems(["none", "daily", "weekly", "monthly"])

        details_form.addRow("Title:", self.title_input)
        details_form.addRow("Due at:", self.due_input)
        details_form.addRow("Recurrence:", self.recurrence_combo)
        details_form.addRow(QLabel("Notes:", details_group))
        details_form.addRow(self.notes_input)
        right.addWidget(details_group)

        button_row = QHBoxLayout()
        self.add_btn = QPushButton("Add", self)
        self.update_btn = QPushButton("Update Selected", self)
        self.delete_btn = QPushButton("Delete Selected", self)
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.update_btn)
        button_row.addWidget(self.delete_btn)
        right.addLayout(button_row)

        snooze_group = QGroupBox("Snooze", self)
        snooze_row = QHBoxLayout(snooze_group)
        self.snooze_5 = QPushButton("5 min", snooze_group)
        self.snooze_15 = QPushButton("15 min", snooze_group)
        self.snooze_60 = QPushButton("1 hour", snooze_group)
        self.snooze_1440 = QPushButton("1 day", snooze_group)
        for btn in (self.snooze_5, self.snooze_15, self.snooze_60, self.snooze_1440):
            snooze_row.addWidget(btn)
        right.addWidget(snooze_group)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.close_btn = QPushButton("Close", self)
        close_row.addWidget(self.close_btn)
        right.addLayout(close_row)

        layout.addLayout(right, 3)

        self.add_btn.clicked.connect(self._add_reminder)
        self.update_btn.clicked.connect(self._update_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.close_btn.clicked.connect(self.accept)
        self.list_widget.currentItemChanged.connect(self._load_selected)
        self.snooze_5.clicked.connect(lambda: self._snooze_selected(timedelta(minutes=5)))
        self.snooze_15.clicked.connect(lambda: self._snooze_selected(timedelta(minutes=15)))
        self.snooze_60.clicked.connect(lambda: self._snooze_selected(timedelta(hours=1)))
        self.snooze_1440.clicked.connect(lambda: self._snooze_selected(timedelta(days=1)))

        self._refresh()

    def _refresh(self) -> None:
        self.list_widget.clear()
        for reminder in sorted(self.store.reminders, key=lambda r: r.due_iso):
            status = "done" if reminder.fired else "pending"
            label = f"{reminder.due_iso.replace('T', ' ')} - {reminder.title} ({reminder.recurrence}, {status})"
            item = QListWidgetItem(label, self.list_widget)
            item.setData(Qt.UserRole, reminder.reminder_id)

    def _selected_reminder(self) -> Reminder | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        reminder_id = item.data(Qt.UserRole)
        return self.store.by_id(reminder_id)

    def _load_selected(self, _current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            return
        self.title_input.setText(reminder.title)
        self.notes_input.setPlainText(reminder.notes)
        self.due_input.setDateTime(QDateTime.fromString(reminder.due_iso, Qt.ISODate))
        idx = self.recurrence_combo.findText(reminder.recurrence)
        if idx >= 0:
            self.recurrence_combo.setCurrentIndex(idx)

    def _add_reminder(self) -> None:
        due_dt = self.due_input.dateTime().toPython()
        if due_dt <= datetime.now():
            QMessageBox.warning(self, "Reminder", "Pick a time in the future.")
            return
        title = self.title_input.text().strip() or (self.note_title or "Untitled")
        notes = self.notes_input.toPlainText().strip()
        recurrence = self.recurrence_combo.currentText()
        self.store.add(title=title, note_ref=self.note_ref, due_dt=due_dt, notes=notes, recurrence=recurrence)
        self.store.save()
        self._refresh()

    def _update_selected(self) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            return
        due_dt = self.due_input.dateTime().toPython()
        if due_dt <= datetime.now():
            QMessageBox.warning(self, "Reminder", "Pick a time in the future.")
            return
        reminder.title = self.title_input.text().strip() or (self.note_title or "Untitled")
        reminder.notes = self.notes_input.toPlainText().strip()
        reminder.recurrence = self.recurrence_combo.currentText()
        reminder.set_due(due_dt)
        reminder.fired = False
        self.store.save()
        self._refresh()

    def _delete_selected(self) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            return
        self.store.remove(reminder.reminder_id)
        self.store.save()
        self._refresh()

    def _snooze_selected(self, delta: timedelta) -> None:
        reminder = self._selected_reminder()
        if reminder is None:
            return
        self.store.snooze(reminder, delta)
        self.store.save()
        self._refresh()
