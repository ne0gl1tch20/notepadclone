from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from pypad.app_settings.defaults import DEFAULT_UPDATE_FEED_URL


def _normalize_hex_color(value: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        return "#" + "".join(ch * 2 for ch in text[1:])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.lower()
    return None


class SettingsDialog(QDialog):
    def __init__(self, parent: Notepad, settings: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 500)
        self._settings = dict(settings)
        self.reset_to_defaults_requested = False

        main_layout = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        container = QWidget(scroll)
        scroll.setWidget(container)

        vbox = QVBoxLayout(container)

        # Dark Mode
        dark_group = QGroupBox("Dark Mode \U0001F319", container)
        dark_layout = QVBoxLayout(dark_group)
        self.dark_checkbox = QCheckBox("Enable dark mode (night theme)", dark_group)
        self.dark_checkbox.setChecked(self._settings.get("dark_mode", False))
        self.app_style_combo = QComboBox(dark_group)
        available_styles = sorted(QStyleFactory.keys())
        self.app_style_combo.addItem("System Default")
        self.app_style_combo.addItems(available_styles)
        current_style = str(self._settings.get("app_style", "System Default") or "System Default")
        style_index = self.app_style_combo.findText(current_style)
        if style_index >= 0:
            self.app_style_combo.setCurrentIndex(style_index)
        dark_layout.addWidget(self.dark_checkbox)
        dark_layout.addWidget(QLabel("Widget style engine:", dark_group))
        dark_layout.addWidget(self.app_style_combo)
        vbox.addWidget(dark_group)

        # Theme Customization
        theme_group = QGroupBox("Theme Customization \U0001F3A8", container)
        theme_form = QFormLayout(theme_group)
        self.theme_combo = QComboBox(theme_group)
        self.theme_combo.addItems(["Default", "Soft Light", "High Contrast", "Solarized Light", "Ocean Blue"])
        current_theme = self._settings.get("theme", "Default")
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self.accent_color_value = self._normalized_or_default(self._settings.get("accent_color", "#4a90e2"), "#4a90e2")
        self.custom_editor_bg_value = self._normalized_or_default(self._settings.get("custom_editor_bg", ""), "")
        self.custom_editor_fg_value = self._normalized_or_default(self._settings.get("custom_editor_fg", ""), "")
        self.custom_chrome_bg_value = self._normalized_or_default(self._settings.get("custom_chrome_bg", ""), "")

        self.accent_color_label, accent_color_row = self._build_color_picker_row(
            "Pick accent...", self.accent_color_value, allow_empty=False
        )
        self.use_custom_colors_checkbox = QCheckBox("Use custom colors", theme_group)
        self.use_custom_colors_checkbox.setChecked(self._settings.get("use_custom_colors", False))
        self.custom_editor_bg_label, custom_editor_bg_row = self._build_color_picker_row(
            "Pick editor bg...", self.custom_editor_bg_value, allow_empty=True
        )
        self.custom_editor_fg_label, custom_editor_fg_row = self._build_color_picker_row(
            "Pick editor text...", self.custom_editor_fg_value, allow_empty=True
        )
        self.custom_chrome_bg_label, custom_chrome_bg_row = self._build_color_picker_row(
            "Pick chrome bg...", self.custom_chrome_bg_value, allow_empty=True
        )
        self.background_input = QLineEdit(theme_group)
        self.background_input.setPlaceholderText("Background hint (e.g. 'paper', 'code', 'midnight')")
        theme_form.addRow("Theme preset:", self.theme_combo)
        theme_form.addRow("Accent color:", accent_color_row)
        theme_form.addRow(self.use_custom_colors_checkbox)
        theme_form.addRow("Editor bg:", custom_editor_bg_row)
        theme_form.addRow("Editor text:", custom_editor_fg_row)
        theme_form.addRow("Chrome bg:", custom_chrome_bg_row)
        theme_form.addRow("Background style hint:", self.background_input)
        vbox.addWidget(theme_group)

        # Font Size & Style
        font_group = QGroupBox("Font Size & Style \u270F\uFE0F", container)
        font_layout = QFormLayout(font_group)
        self.font_family_edit = QLineEdit(font_group)
        self.font_family_edit.setText(self._settings.get("font_family", ""))
        self.font_size_slider = QSlider(Qt.Horizontal, font_group)
        self.font_size_slider.setMinimum(8)
        self.font_size_slider.setMaximum(32)
        self.font_size_slider.setValue(self._settings.get("font_size", 11))
        self.font_size_label = QLabel(str(self.font_size_slider.value()), font_group)

        size_row = QHBoxLayout()
        size_row.addWidget(self.font_size_slider)
        size_row.addWidget(self.font_size_label)

        font_layout.addRow("Font family:", self.font_family_edit)
        font_layout.addRow("Font size:", QWidget())
        font_layout.itemAt(font_layout.rowCount() - 1, QFormLayout.FieldRole).widget().setLayout(size_row)

        self.font_size_slider.valueChanged.connect(
            lambda v: self.font_size_label.setText(str(v))
        )
        vbox.addWidget(font_group)

        # Sound Settings
        sound_group = QGroupBox("Sound Settings \U0001F50A", container)
        sound_layout = QVBoxLayout(sound_group)
        self.sound_checkbox = QCheckBox("Enable sound effects / notifications", sound_group)
        self.sound_checkbox.setChecked(self._settings.get("sound_enabled", True))
        self.music_checkbox = QCheckBox("Allow background music (where supported)", sound_group)
        self.music_checkbox.setChecked(self._settings.get("background_music", False))
        sound_layout.addWidget(self.sound_checkbox)
        sound_layout.addWidget(self.music_checkbox)
        vbox.addWidget(sound_group)

        # Language
        lang_group = QGroupBox("Language \U0001F310", container)
        lang_layout = QFormLayout(lang_group)
        self.lang_combo = QComboBox(lang_group)
        self.lang_combo.addItems(["English", "EspaÃ±ol", "Deutsch", "FranÃ§ais"])
        current_lang = self._settings.get("language", "English")
        idx = self.lang_combo.findText(current_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        lang_layout.addRow("App language:", self.lang_combo)
        vbox.addWidget(lang_group)

        # Notifications
        notif_group = QGroupBox("Notifications \U0001F6CE\uFE0F", container)
        notif_layout = QVBoxLayout(notif_group)
        self.notifications_checkbox = QCheckBox("Show pop-up notifications and alerts", notif_group)
        self.notifications_checkbox.setChecked(self._settings.get("notifications_enabled", True))
        notif_layout.addWidget(self.notifications_checkbox)
        vbox.addWidget(notif_group)

        # Productivity & Focus
        productivity_group = QGroupBox("Productivity & Focus \U0001F9E0", container)
        productivity_form = QFormLayout(productivity_group)

        self.version_history_checkbox = QCheckBox("Enable version history", productivity_group)
        self.version_history_checkbox.setChecked(self._settings.get("version_history_enabled", True))
        self.version_history_interval_spin = QSpinBox(productivity_group)
        self.version_history_interval_spin.setRange(5, 600)
        self.version_history_interval_spin.setValue(int(self._settings.get("version_history_interval_sec", 30)))
        self.version_history_max_spin = QSpinBox(productivity_group)
        self.version_history_max_spin.setRange(5, 500)
        self.version_history_max_spin.setValue(int(self._settings.get("version_history_max_entries", 50)))

        self.autosave_checkbox = QCheckBox("Enable autosave", productivity_group)
        self.autosave_checkbox.setChecked(self._settings.get("autosave_enabled", True))
        self.autosave_interval_spin = QSpinBox(productivity_group)
        self.autosave_interval_spin.setRange(10, 600)
        self.autosave_interval_spin.setValue(int(self._settings.get("autosave_interval_sec", 30)))

        self.reminders_checkbox = QCheckBox("Enable reminders & alarms", productivity_group)
        self.reminders_checkbox.setChecked(self._settings.get("reminders_enabled", True))
        self.reminder_interval_spin = QSpinBox(productivity_group)
        self.reminder_interval_spin.setRange(10, 600)
        self.reminder_interval_spin.setValue(int(self._settings.get("reminder_check_interval_sec", 30)))

        self.syntax_highlight_checkbox = QCheckBox("Enable code syntax highlighting", productivity_group)
        self.syntax_highlight_checkbox.setChecked(self._settings.get("syntax_highlighting_enabled", True))
        self.syntax_mode_combo = QComboBox(productivity_group)
        self.syntax_mode_combo.addItems(["Auto", "Python", "JavaScript", "JSON", "Markdown", "Plain"])
        current_mode = str(self._settings.get("syntax_highlighting_mode", "Auto"))
        idx = self.syntax_mode_combo.findText(current_mode, Qt.MatchFixedString)
        if idx >= 0:
            self.syntax_mode_combo.setCurrentIndex(idx)

        self.checklist_toggle_checkbox = QCheckBox("Enable checklist toggle action", productivity_group)
        self.checklist_toggle_checkbox.setChecked(self._settings.get("checklist_toggle_enabled", True))

        self.focus_hide_menu_checkbox = QCheckBox("Hide menu bar in focus mode", productivity_group)
        self.focus_hide_menu_checkbox.setChecked(self._settings.get("focus_hide_menu", True))
        self.focus_hide_toolbar_checkbox = QCheckBox("Hide toolbars in focus mode", productivity_group)
        self.focus_hide_toolbar_checkbox.setChecked(self._settings.get("focus_hide_toolbar", True))
        self.focus_hide_status_checkbox = QCheckBox("Hide status bar in focus mode", productivity_group)
        self.focus_hide_status_checkbox.setChecked(self._settings.get("focus_hide_status", False))
        self.focus_hide_tabs_checkbox = QCheckBox("Hide tabs in focus mode", productivity_group)
        self.focus_hide_tabs_checkbox.setChecked(self._settings.get("focus_hide_tabs", False))
        self.focus_escape_exit_checkbox = QCheckBox("Allow Esc to disable focus mode", productivity_group)
        self.focus_escape_exit_checkbox.setChecked(self._settings.get("focus_allow_escape_exit", True))

        productivity_form.addRow(self.version_history_checkbox)
        productivity_form.addRow("Version snapshot interval (sec):", self.version_history_interval_spin)
        productivity_form.addRow("Max history entries:", self.version_history_max_spin)
        productivity_form.addRow(self.autosave_checkbox)
        productivity_form.addRow("Autosave interval (sec):", self.autosave_interval_spin)
        productivity_form.addRow(self.reminders_checkbox)
        productivity_form.addRow("Reminder check interval (sec):", self.reminder_interval_spin)
        productivity_form.addRow(self.syntax_highlight_checkbox)
        productivity_form.addRow("Syntax mode:", self.syntax_mode_combo)
        productivity_form.addRow(self.checklist_toggle_checkbox)
        productivity_form.addRow(self.focus_hide_menu_checkbox)
        productivity_form.addRow(self.focus_hide_toolbar_checkbox)
        productivity_form.addRow(self.focus_hide_status_checkbox)
        productivity_form.addRow(self.focus_hide_tabs_checkbox)
        productivity_form.addRow(self.focus_escape_exit_checkbox)
        vbox.addWidget(productivity_group)

        # Privacy & Security
        privacy_group = QGroupBox("Privacy & Security \U0001F512", container)
        privacy_layout = QFormLayout(privacy_group)
        self.privacy_lock_checkbox = QCheckBox("Enable lock screen on open", privacy_group)
        self.privacy_lock_checkbox.setChecked(self._settings.get("privacy_lock", False))
        self.lock_password_edit = QLineEdit(privacy_group)
        self.lock_password_edit.setEchoMode(QLineEdit.Password)
        self.lock_password_edit.setPlaceholderText("Optional password")
        self.lock_password_edit.setText(self._settings.get("lock_password", ""))
        self.lock_pin_edit = QLineEdit(privacy_group)
        self.lock_pin_edit.setMaxLength(10)
        self.lock_pin_edit.setPlaceholderText("Optional PIN (digits)")
        self.lock_pin_edit.setText(self._settings.get("lock_pin", ""))

        privacy_layout.addRow(self.privacy_lock_checkbox)
        privacy_layout.addRow("Password:", self.lock_password_edit)
        privacy_layout.addRow("PIN:", self.lock_pin_edit)
        vbox.addWidget(privacy_group)

        # AI & Updates
        ai_group = QGroupBox("AI & Updates", container)
        ai_form = QFormLayout(ai_group)
        self.gemini_api_key_edit = QLineEdit(ai_group)
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("Gemini API key")
        self.gemini_api_key_edit.setText(self._settings.get("gemini_api_key", ""))
        self.ai_model_edit = QLineEdit(ai_group)
        self.ai_model_edit.setPlaceholderText("gemini-3-flash-preview")
        self.ai_model_edit.setText(self._settings.get("ai_model", "gemini-3-flash-preview"))
        self.update_feed_url_edit = QLineEdit(ai_group)
        self.update_feed_url_edit.setPlaceholderText(DEFAULT_UPDATE_FEED_URL)
        self.update_feed_url_edit.setReadOnly(True)
        self.update_feed_url_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.update_feed_url_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update_feed_url_edit.setToolTip("Update feed URL is managed by the app and is read-only.")
        self.update_feed_url_edit.setText(
            self._settings.get("update_feed_url", DEFAULT_UPDATE_FEED_URL)
        )
        self.auto_check_updates_checkbox = QCheckBox("Check for updates on startup", ai_group)
        self.auto_check_updates_checkbox.setChecked(self._settings.get("auto_check_updates", True))

        ai_form.addRow("Gemini API key:", self.gemini_api_key_edit)
        ai_form.addRow("Model:", self.ai_model_edit)
        ai_form.addRow("Update feed URL:", self.update_feed_url_edit)
        ai_form.addRow(self.auto_check_updates_checkbox)
        vbox.addWidget(ai_group)

        # Backup & Restore
        backup_group = QGroupBox("Backup & Restore \U0001F4BE", container)
        backup_layout = QHBoxLayout(backup_group)
        self.backup_btn = QPushButton("Backup Settings...", backup_group)
        self.restore_btn = QPushButton("Restore Settings...", backup_group)
        self.reset_defaults_btn = QPushButton("Reset to Default (Close App)", backup_group)
        backup_layout.addWidget(self.backup_btn)
        backup_layout.addWidget(self.restore_btn)
        backup_layout.addWidget(self.reset_defaults_btn)
        vbox.addWidget(backup_group)

        # Advanced Options
        adv_group = QGroupBox("Advanced Options \u2699\uFE0F", container)
        adv_layout = QVBoxLayout(adv_group)
        self.experimental_checkbox = QCheckBox("Enable experimental features", adv_group)
        adv_layout.addWidget(self.experimental_checkbox)
        vbox.addWidget(adv_group)

        vbox.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal,
            self,
        )
        main_layout.addWidget(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.backup_btn.clicked.connect(self.backup_settings)
        self.restore_btn.clicked.connect(self.restore_settings)
        self.reset_defaults_btn.clicked.connect(self.reset_to_defaults_and_close)

    @staticmethod
    def _normalized_or_default(value: str, fallback: str) -> str:
        normalized = _normalize_hex_color(value)
        if normalized is not None:
            return normalized
        return fallback

    def _build_color_picker_row(self, button_text: str, initial_hex: str, allow_empty: bool) -> tuple[QLabel, QWidget]:
        holder = QWidget(self)
        row_layout = QHBoxLayout(holder)
        row_layout.setContentsMargins(0, 0, 0, 0)
        value_label = QLabel(initial_hex if initial_hex else "(auto)", holder)
        value_label.setMinimumWidth(90)
        pick_button = QPushButton(button_text, holder)
        clear_button = QPushButton("Clear", holder)
        clear_button.setVisible(allow_empty)

        def apply_value(hex_value: str) -> None:
            if hex_value:
                value_label.setText(hex_value)
                value_label.setStyleSheet(f"background-color: {hex_value}; border: 1px solid #888; padding: 2px;")
            else:
                value_label.setText("(auto)")
                value_label.setStyleSheet("")

        def pick_color() -> None:
            initial = value_label.text() if value_label.text() != "(auto)" else "#ffffff"
            color = QColorDialog.getColor(QColor(initial), self, "Select Color")
            if color.isValid():
                apply_value(color.name())

        pick_button.clicked.connect(pick_color)
        clear_button.clicked.connect(lambda: apply_value(""))
        apply_value(initial_hex)

        row_layout.addWidget(value_label)
        row_layout.addWidget(pick_button)
        row_layout.addWidget(clear_button)
        return value_label, holder

    @staticmethod
    def _label_color_value(label: QLabel) -> str:
        value = label.text().strip()
        if value == "(auto)":
            return ""
        return value

    def get_settings(self) -> dict:
        s = dict(self._settings)
        s["app_style"] = self.app_style_combo.currentText()
        s["dark_mode"] = self.dark_checkbox.isChecked()
        s["theme"] = self.theme_combo.currentText()
        s["accent_color"] = self._normalized_or_default(self._label_color_value(self.accent_color_label), "#4a90e2")
        s["use_custom_colors"] = self.use_custom_colors_checkbox.isChecked()
        s["custom_editor_bg"] = self._normalized_or_default(self._label_color_value(self.custom_editor_bg_label), "")
        s["custom_editor_fg"] = self._normalized_or_default(self._label_color_value(self.custom_editor_fg_label), "")
        s["custom_chrome_bg"] = self._normalized_or_default(self._label_color_value(self.custom_chrome_bg_label), "")
        s["font_family"] = self.font_family_edit.text().strip() or s.get("font_family")
        s["font_size"] = int(self.font_size_slider.value())
        s["sound_enabled"] = self.sound_checkbox.isChecked()
        s["background_music"] = self.music_checkbox.isChecked()
        s["language"] = self.lang_combo.currentText()
        s["notifications_enabled"] = self.notifications_checkbox.isChecked()
        s["version_history_enabled"] = self.version_history_checkbox.isChecked()
        s["version_history_interval_sec"] = int(self.version_history_interval_spin.value())
        s["version_history_max_entries"] = int(self.version_history_max_spin.value())
        s["autosave_enabled"] = self.autosave_checkbox.isChecked()
        s["autosave_interval_sec"] = int(self.autosave_interval_spin.value())
        s["reminders_enabled"] = self.reminders_checkbox.isChecked()
        s["reminder_check_interval_sec"] = int(self.reminder_interval_spin.value())
        s["syntax_highlighting_enabled"] = self.syntax_highlight_checkbox.isChecked()
        s["syntax_highlighting_mode"] = self.syntax_mode_combo.currentText()
        s["checklist_toggle_enabled"] = self.checklist_toggle_checkbox.isChecked()
        s["focus_hide_menu"] = self.focus_hide_menu_checkbox.isChecked()
        s["focus_hide_toolbar"] = self.focus_hide_toolbar_checkbox.isChecked()
        s["focus_hide_status"] = self.focus_hide_status_checkbox.isChecked()
        s["focus_hide_tabs"] = self.focus_hide_tabs_checkbox.isChecked()
        s["focus_allow_escape_exit"] = self.focus_escape_exit_checkbox.isChecked()
        s["privacy_lock"] = self.privacy_lock_checkbox.isChecked()
        s["lock_password"] = self.lock_password_edit.text()
        s["lock_pin"] = self.lock_pin_edit.text()
        s["gemini_api_key"] = self.gemini_api_key_edit.text().strip()
        s["ai_model"] = self.ai_model_edit.text().strip() or "gemini-3-flash-preview"
        s["update_feed_url"] = self.update_feed_url_edit.text().strip() or DEFAULT_UPDATE_FEED_URL
        s["auto_check_updates"] = self.auto_check_updates_checkbox.isChecked()
        return s

    def backup_settings(self) -> None:
        import json

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Backup Settings",
            "",
            "Settings Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.get_settings(), f, indent=2)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Backup Failed", f"Could not save settings:\n{e}")

    def restore_settings(self) -> None:
        import json

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Restore Settings",
            "",
            "Settings Files (*.json);;All Files (*.*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Restore Failed", f"Could not load settings:\n{e}")
            return

        # Update UI from loaded settings (best-effort)
        self._settings.update(loaded)
        style_idx = self.app_style_combo.findText(str(self._settings.get("app_style", "System Default")))
        if style_idx >= 0:
            self.app_style_combo.setCurrentIndex(style_idx)
        else:
            self.app_style_combo.setCurrentIndex(0)
        self.dark_checkbox.setChecked(self._settings.get("dark_mode", False))
        idx = self.theme_combo.findText(self._settings.get("theme", "Default"))
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        restored_accent = self._normalized_or_default(self._settings.get("accent_color", "#4a90e2"), "#4a90e2")
        self.accent_color_label.setText(restored_accent)
        self.accent_color_label.setStyleSheet(
            f"background-color: {restored_accent}; border: 1px solid #888; padding: 2px;"
        )
        self.use_custom_colors_checkbox.setChecked(self._settings.get("use_custom_colors", False))
        restored_editor_bg = self._normalized_or_default(self._settings.get("custom_editor_bg", ""), "")
        restored_editor_fg = self._normalized_or_default(self._settings.get("custom_editor_fg", ""), "")
        restored_chrome_bg = self._normalized_or_default(self._settings.get("custom_chrome_bg", ""), "")
        self.custom_editor_bg_label.setText(restored_editor_bg if restored_editor_bg else "(auto)")
        self.custom_editor_bg_label.setStyleSheet(
            f"background-color: {restored_editor_bg}; border: 1px solid #888; padding: 2px;"
            if restored_editor_bg else ""
        )
        self.custom_editor_fg_label.setText(restored_editor_fg if restored_editor_fg else "(auto)")
        self.custom_editor_fg_label.setStyleSheet(
            f"background-color: {restored_editor_fg}; border: 1px solid #888; padding: 2px;"
            if restored_editor_fg else ""
        )
        self.custom_chrome_bg_label.setText(restored_chrome_bg if restored_chrome_bg else "(auto)")
        self.custom_chrome_bg_label.setStyleSheet(
            f"background-color: {restored_chrome_bg}; border: 1px solid #888; padding: 2px;"
            if restored_chrome_bg else ""
        )
        self.font_family_edit.setText(self._settings.get("font_family", ""))
        self.font_size_slider.setValue(self._settings.get("font_size", 11))
        self.sound_checkbox.setChecked(self._settings.get("sound_enabled", True))
        self.music_checkbox.setChecked(self._settings.get("background_music", False))
        lang_idx = self.lang_combo.findText(self._settings.get("language", "English"))
        if lang_idx >= 0:
            self.lang_combo.setCurrentIndex(lang_idx)
        self.notifications_checkbox.setChecked(self._settings.get("notifications_enabled", True))
        self.version_history_checkbox.setChecked(self._settings.get("version_history_enabled", True))
        self.version_history_interval_spin.setValue(int(self._settings.get("version_history_interval_sec", 30)))
        self.version_history_max_spin.setValue(int(self._settings.get("version_history_max_entries", 50)))
        self.autosave_checkbox.setChecked(self._settings.get("autosave_enabled", True))
        self.autosave_interval_spin.setValue(int(self._settings.get("autosave_interval_sec", 30)))
        self.reminders_checkbox.setChecked(self._settings.get("reminders_enabled", True))
        self.reminder_interval_spin.setValue(int(self._settings.get("reminder_check_interval_sec", 30)))
        self.syntax_highlight_checkbox.setChecked(self._settings.get("syntax_highlighting_enabled", True))
        syntax_mode = str(self._settings.get("syntax_highlighting_mode", "Auto"))
        syntax_idx = self.syntax_mode_combo.findText(syntax_mode, Qt.MatchFixedString)
        if syntax_idx >= 0:
            self.syntax_mode_combo.setCurrentIndex(syntax_idx)
        self.checklist_toggle_checkbox.setChecked(self._settings.get("checklist_toggle_enabled", True))
        self.focus_hide_menu_checkbox.setChecked(self._settings.get("focus_hide_menu", True))
        self.focus_hide_toolbar_checkbox.setChecked(self._settings.get("focus_hide_toolbar", True))
        self.focus_hide_status_checkbox.setChecked(self._settings.get("focus_hide_status", False))
        self.focus_hide_tabs_checkbox.setChecked(self._settings.get("focus_hide_tabs", False))
        self.focus_escape_exit_checkbox.setChecked(self._settings.get("focus_allow_escape_exit", True))
        self.privacy_lock_checkbox.setChecked(self._settings.get("privacy_lock", False))
        self.lock_password_edit.setText(self._settings.get("lock_password", ""))
        self.lock_pin_edit.setText(self._settings.get("lock_pin", ""))
        self.gemini_api_key_edit.setText(self._settings.get("gemini_api_key", ""))
        self.ai_model_edit.setText(self._settings.get("ai_model", "gemini-3-flash-preview"))
        self.update_feed_url_edit.setText(
            self._settings.get("update_feed_url", DEFAULT_UPDATE_FEED_URL)
        )
        self.auto_check_updates_checkbox.setChecked(self._settings.get("auto_check_updates", True))

    def reset_to_defaults_and_close(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Reset Settings",
            "Reset all settings to default and close the app?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.reset_to_defaults_requested = True
        self.accept()




