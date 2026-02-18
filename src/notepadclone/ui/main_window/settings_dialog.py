from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QColorDialog,
    QStyleFactory,
)

from ...app_settings import migrate_settings
from ...app_settings.defaults import DEFAULT_UPDATE_FEED_URL
from ...i18n.translator import get_language_display_options

if TYPE_CHECKING:
    from .window import Notepad


class SettingsDialog(QDialog):
    def __init__(self, parent: "Notepad", settings: dict) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(980, 680)
        self._parent_window = parent
        self._settings = migrate_settings(dict(settings))
        self._search_entries: list[tuple[int, str, QWidget]] = []
        self._nav_base_labels: list[str] = []
        self._highlighted_widgets: list[QWidget] = []
        self.reset_to_defaults_requested = False

        root = QVBoxLayout(self)
        self.settings_search_input = QLineEdit(self)
        self.settings_search_input.setPlaceholderText("Search settings... (theme, tab, AI, autosave)")
        root.addWidget(self.settings_search_input)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        self.settings_nav_list = QListWidget(splitter)
        self.settings_nav_list.setFixedWidth(220)
        self.settings_pages = QStackedWidget(splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self._build_pages()

        buttons_row = QHBoxLayout()
        self.restore_defaults_btn = QPushButton("Restore Defaults ♻️", self)
        self.restore_defaults_btn.clicked.connect(self._reset_controls_to_defaults)
        buttons_row.addWidget(self.restore_defaults_btn)
        buttons_row.addStretch(1)

        self.apply_btn = QPushButton("Apply", self)
        self.apply_btn.clicked.connect(self._apply_to_memory)
        buttons_row.addWidget(self.apply_btn)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.button_box.accepted.connect(self._accept_with_apply)
        self.button_box.rejected.connect(self.reject)
        buttons_row.addWidget(self.button_box)
        root.addLayout(buttons_row)

        self.settings_nav_list.currentRowChanged.connect(self.settings_pages.setCurrentIndex)
        self.settings_search_input.textChanged.connect(self._apply_search_filter)
        self.settings_nav_list.setCurrentRow(0)
        self._load_controls_from_settings(self._settings)
        self._apply_dialog_theme()
        self.dark_checkbox.toggled.connect(lambda _checked: self._apply_dialog_theme())

    @staticmethod
    def _normalize_hex(value: str, fallback: str) -> str:
        text = (value or "").strip()
        if not text:
            return fallback
        if not text.startswith("#"):
            text = f"#{text}"
        if len(text) not in (4, 7):
            return fallback
        if not all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
            return fallback
        return text

    def _add_category(self, name: str, page: QWidget) -> int:
        idx = self.settings_pages.addWidget(page)
        self.settings_nav_list.addItem(name)
        self._nav_base_labels.append(name)
        return idx

    def _register_search(self, category_idx: int, label: str, widget: QWidget) -> None:
        self._search_entries.append((category_idx, label.lower(), widget))

    def _add_combo(self, form: QFormLayout, category_idx: int, label: str, options: list[str]) -> QComboBox:
        combo = QComboBox(form.parentWidget())
        combo.addItems(options)
        form.addRow(label, combo)
        self._register_search(category_idx, label, combo)
        return combo

    def _add_check(self, layout: QVBoxLayout | QFormLayout, category_idx: int, label: str) -> QCheckBox:
        cb = QCheckBox(label, layout.parentWidget())
        if isinstance(layout, QFormLayout):
            layout.addRow(cb)
        else:
            layout.addWidget(cb)
        self._register_search(category_idx, label, cb)
        return cb

    def _add_spin(self, form: QFormLayout, category_idx: int, label: str, min_v: int, max_v: int) -> QSpinBox:
        spin = QSpinBox(form.parentWidget())
        spin.setRange(min_v, max_v)
        form.addRow(label, spin)
        self._register_search(category_idx, label, spin)
        return spin

    def _build_color_row(self, parent: QWidget, category_idx: int, label: str) -> tuple[QLabel, QWidget]:
        holder = QWidget(parent)
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        preview = QLabel("(auto)", holder)
        preview.setMinimumWidth(95)
        pick = QPushButton("Pick...", holder)
        clear = QPushButton("Clear", holder)
        row.addWidget(preview)
        row.addWidget(pick)
        row.addWidget(clear)
        self._register_search(category_idx, label, preview)

        def apply_value(hex_value: str) -> None:
            if hex_value:
                preview.setText(hex_value)
                preview.setStyleSheet(f"background-color: {hex_value}; border: 1px solid #888; padding: 2px;")
            else:
                preview.setText("(auto)")
                preview.setStyleSheet("")
            if label == "Accent color":
                self._apply_dialog_theme()

        def pick_color() -> None:
            current = preview.text() if preview.text() != "(auto)" else "#ffffff"
            color = QColorDialog.getColor(QColor(current), self, "Select Color")
            if color.isValid():
                apply_value(color.name())

        pick.clicked.connect(pick_color)
        clear.clicked.connect(lambda: apply_value(""))
        return preview, holder

    def _build_pages(self) -> None:
        # Appearance
        appearance = QWidget(self)
        appearance_layout = QVBoxLayout(appearance)
        appearance_form = QFormLayout()
        appearance_layout.addLayout(appearance_form)
        idx = self._add_category("🎨 Appearance", appearance)

        self.dark_checkbox = self._add_check(appearance_form, idx, "Enable dark mode")
        styles = sorted(QStyleFactory.keys())
        self.app_style_combo = self._add_combo(appearance_form, idx, "Widget style engine", ["System Default"] + styles)
        self.theme_combo = self._add_combo(
            appearance_form, idx, "Theme preset", ["Default", "Soft Light", "High Contrast", "Solarized Light", "Ocean Blue"]
        )
        self.accent_color_label, accent_row = self._build_color_row(appearance, idx, "Accent color")
        appearance_form.addRow("Accent color", accent_row)
        self.use_custom_colors_checkbox = self._add_check(appearance_form, idx, "Use custom colors")
        self.custom_editor_bg_label, editor_bg_row = self._build_color_row(appearance, idx, "Editor background")
        self.custom_editor_fg_label, editor_fg_row = self._build_color_row(appearance, idx, "Editor foreground")
        self.custom_chrome_bg_label, chrome_bg_row = self._build_color_row(appearance, idx, "Chrome background")
        appearance_form.addRow("Editor bg", editor_bg_row)
        appearance_form.addRow("Editor text", editor_fg_row)
        appearance_form.addRow("Chrome bg", chrome_bg_row)
        self.font_family_edit = QLineEdit(appearance)
        appearance_form.addRow("Font family", self.font_family_edit)
        self.font_size_slider = QSlider(Qt.Orientation.Horizontal, appearance)
        self.font_size_slider.setRange(8, 32)
        self.font_size_label = QLabel("11", appearance)
        font_row = QWidget(appearance)
        font_layout = QHBoxLayout(font_row)
        font_layout.setContentsMargins(0, 0, 0, 0)
        font_layout.addWidget(self.font_size_slider)
        font_layout.addWidget(self.font_size_label)
        appearance_form.addRow("Font size", font_row)
        self.ui_density_combo = self._add_combo(appearance_form, idx, "UI density", ["compact", "comfortable"])
        self.icon_size_combo = self._add_combo(appearance_form, idx, "Icon size", ["16", "18", "20", "24"])
        self.toolbar_label_mode_combo = self._add_combo(
            appearance_form, idx, "Toolbar labels", ["icons_only", "text_only", "icons_text"]
        )
        self.show_main_toolbar_checkbox = self._add_check(appearance_form, idx, "Show main toolbar")
        self.show_markdown_toolbar_checkbox = self._add_check(appearance_form, idx, "Show markdown toolbar")
        self.show_find_panel_checkbox = self._add_check(appearance_form, idx, "Show find panel")
        self.simple_mode_checkbox = self._add_check(appearance_form, idx, "Enable simple mode")
        appearance_layout.addStretch(1)
        self.font_size_slider.valueChanged.connect(lambda v: self.font_size_label.setText(str(v)))

        # Editor
        editor = QWidget(self)
        editor_layout = QFormLayout(editor)
        idx = self._add_category("✍️ Editor", editor)
        self.syntax_highlight_checkbox = self._add_check(editor_layout, idx, "Enable code syntax highlighting")
        self.syntax_mode_combo = self._add_combo(editor_layout, idx, "Syntax mode", ["Auto", "Python", "JavaScript", "JSON", "Markdown", "Plain"])
        self.checklist_toggle_checkbox = self._add_check(editor_layout, idx, "Enable checklist toggle action")
        self.tab_width_spin = self._add_spin(editor_layout, idx, "Tab width", 2, 8)
        self.insert_spaces_checkbox = self._add_check(editor_layout, idx, "Insert spaces")
        self.auto_indent_checkbox = self._add_check(editor_layout, idx, "Auto indent")
        self.trim_trailing_checkbox = self._add_check(editor_layout, idx, "Trim trailing whitespace on save")
        self.caret_width_spin = self._add_spin(editor_layout, idx, "Caret width", 1, 4)
        self.highlight_current_line_checkbox = self._add_check(editor_layout, idx, "Highlight current line")

        # Language
        language = QWidget(self)
        language_layout = QFormLayout(language)
        idx = self._add_category("Language", language)
        self.language_combo = self._add_combo(language_layout, idx, "App language", get_language_display_options())
        self.clear_translation_cache_btn = QPushButton("Clear translation cache", language)
        language_layout.addRow("", self.clear_translation_cache_btn)
        self._register_search(idx, "Clear translation cache", self.clear_translation_cache_btn)
        self.clear_translation_cache_btn.clicked.connect(self._clear_translation_cache)

        # Tabs
        tabs = QWidget(self)
        tabs_layout = QFormLayout(tabs)
        idx = self._add_category("🗂️ Tabs", tabs)
        self.tab_close_mode_combo = self._add_combo(tabs_layout, idx, "Close button mode", ["always", "hover"])
        self.tab_elide_combo = self._add_combo(tabs_layout, idx, "Tab elide mode", ["right", "middle", "none"])
        self.tab_min_width_spin = self._add_spin(tabs_layout, idx, "Tab min width", 80, 220)
        self.tab_max_width_spin = self._add_spin(tabs_layout, idx, "Tab max width", 120, 420)
        self.tab_double_click_combo = self._add_combo(tabs_layout, idx, "Double-click action", ["new_tab", "rename", "none"])

        # Workspace
        workspace = QWidget(self)
        workspace_layout = QFormLayout(workspace)
        idx = self._add_category("📁 Workspace", workspace)
        self.workspace_root_edit = QLineEdit(workspace)
        workspace_layout.addRow("Workspace root", self.workspace_root_edit)
        self._register_search(idx, "Workspace root", self.workspace_root_edit)
        self.workspace_show_hidden_checkbox = self._add_check(workspace_layout, idx, "Show hidden files")
        self.workspace_follow_symlinks_checkbox = self._add_check(workspace_layout, idx, "Follow symlinks")
        self.workspace_max_scan_spin = self._add_spin(workspace_layout, idx, "Max scan files", 1000, 200000)

        # Search
        search = QWidget(self)
        search_layout = QFormLayout(search)
        idx = self._add_category("🔎 Search", search)
        self.search_default_match_case_checkbox = self._add_check(search_layout, idx, "Default match case")
        self.search_default_whole_word_checkbox = self._add_check(search_layout, idx, "Default whole word")
        self.search_default_regex_checkbox = self._add_check(search_layout, idx, "Default regex")
        self.search_highlight_color_label, search_color_row = self._build_color_row(search, idx, "Search highlight color")
        search_layout.addRow("Highlight color", search_color_row)
        self.search_max_highlights_spin = self._add_spin(search_layout, idx, "Max highlights", 100, 10000)

        # Shortcuts
        shortcuts = QWidget(self)
        shortcuts_layout = QVBoxLayout(shortcuts)
        idx = self._add_category("⌨️ Shortcuts", shortcuts)
        shortcuts_form = QFormLayout()
        shortcuts_layout.addLayout(shortcuts_form)
        self.shortcut_profile_combo = self._add_combo(shortcuts_form, idx, "Shortcut profile", ["default", "vscode"])
        self.shortcut_conflict_combo = self._add_combo(shortcuts_form, idx, "Conflict policy", ["warn", "block", "allow"])
        self.shortcut_show_unassigned_checkbox = self._add_check(shortcuts_form, idx, "Show unassigned")
        profile_row = QHBoxLayout()
        self.export_profile_btn = QPushButton("Export Profile...", shortcuts)
        self.import_profile_btn = QPushButton("Import Profile...", shortcuts)
        self.open_mapper_btn = QPushButton("Open Shortcut Mapper...", shortcuts)
        profile_row.addWidget(self.export_profile_btn)
        profile_row.addWidget(self.import_profile_btn)
        profile_row.addWidget(self.open_mapper_btn)
        shortcuts_layout.addLayout(profile_row)
        shortcuts_layout.addStretch(1)
        self.export_profile_btn.clicked.connect(self._export_profile)
        self.import_profile_btn.clicked.connect(self._import_profile)
        self.open_mapper_btn.clicked.connect(self._open_mapper_from_settings)

        # AI & Updates
        ai = QWidget(self)
        ai_layout = QFormLayout(ai)
        idx = self._add_category("🤖 AI & Updates", ai)
        self.gemini_api_key_edit = QLineEdit(ai)
        self.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ai_layout.addRow("Gemini API key", self.gemini_api_key_edit)
        self._register_search(idx, "Gemini API key", self.gemini_api_key_edit)
        self.ai_model_edit = QLineEdit(ai)
        ai_layout.addRow("Model", self.ai_model_edit)
        self._register_search(idx, "Model", self.ai_model_edit)
        self.update_feed_url_edit = QLineEdit(ai)
        self.update_feed_url_edit.setPlaceholderText(DEFAULT_UPDATE_FEED_URL)
        ai_layout.addRow("Update feed URL", self.update_feed_url_edit)
        self._register_search(idx, "Update feed URL", self.update_feed_url_edit)
        self.auto_check_updates_checkbox = self._add_check(ai_layout, idx, "Check updates on startup")
        self.ai_send_redact_emails_checkbox = self._add_check(ai_layout, idx, "Redact emails before AI send")
        self.ai_send_redact_paths_checkbox = self._add_check(ai_layout, idx, "Redact file paths before AI send")
        self.ai_send_redact_tokens_checkbox = self._add_check(ai_layout, idx, "Redact tokens before AI send")
        self.ai_key_storage_mode_combo = self._add_combo(ai_layout, idx, "AI key storage mode", ["settings", "env_only"])
        self.ai_private_mode_checkbox = self._add_check(ai_layout, idx, "Enable AI private mode (disable AI calls)")
        self.ai_cost_rate_spin = QDoubleSpinBox(ai)
        self.ai_cost_rate_spin.setDecimals(6)
        self.ai_cost_rate_spin.setRange(0.0, 10.0)
        self.ai_cost_rate_spin.setSingleStep(0.0001)
        ai_layout.addRow("Estimated USD per 1k tokens", self.ai_cost_rate_spin)
        self._register_search(idx, "Estimated USD per 1k tokens", self.ai_cost_rate_spin)

        # Privacy
        privacy = QWidget(self)
        privacy_layout = QFormLayout(privacy)
        idx = self._add_category("🔐 Privacy & Security", privacy)
        self.privacy_lock_checkbox = self._add_check(privacy_layout, idx, "Enable lock screen on open")
        self.lock_password_edit = QLineEdit(privacy)
        self.lock_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        privacy_layout.addRow("Password", self.lock_password_edit)
        self._register_search(idx, "Password", self.lock_password_edit)
        self.lock_pin_edit = QLineEdit(privacy)
        self.lock_pin_edit.setMaxLength(10)
        privacy_layout.addRow("PIN", self.lock_pin_edit)
        self._register_search(idx, "PIN", self.lock_pin_edit)
        self.recovery_mode_combo = self._add_combo(privacy_layout, idx, "Recovery mode", ["ask", "auto_restore", "auto_discard"])
        self.recovery_discard_days_spin = self._add_spin(privacy_layout, idx, "Discard recovery after days", 1, 90)

        # Backup
        backup = QWidget(self)
        backup_layout = QVBoxLayout(backup)
        idx = self._add_category("💾 Backup & Restore", backup)
        backup_buttons = QHBoxLayout()
        self.backup_btn = QPushButton("Backup Settings...", backup)
        self.restore_btn = QPushButton("Restore Settings...", backup)
        backup_buttons.addWidget(self.backup_btn)
        backup_buttons.addWidget(self.restore_btn)
        backup_layout.addLayout(backup_buttons)
        self.export_settings_profile_btn = QPushButton("Export Profile...", backup)
        self.import_settings_profile_btn = QPushButton("Import Profile...", backup)
        self.edit_settings_json_btn = QPushButton("Edit with settings.json 📝", backup)
        backup_output_row = QWidget(backup)
        backup_output_layout = QHBoxLayout(backup_output_row)
        backup_output_layout.setContentsMargins(0, 0, 0, 0)
        self.backup_output_dir_edit = QLineEdit(backup_output_row)
        self.backup_output_dir_browse_btn = QPushButton("Browse...", backup_output_row)
        backup_output_layout.addWidget(self.backup_output_dir_edit, 1)
        backup_output_layout.addWidget(self.backup_output_dir_browse_btn)
        backup_layout.addWidget(QLabel("Backup output folder (optional):", backup))
        backup_layout.addWidget(backup_output_row)
        backup_layout.addWidget(self.export_settings_profile_btn)
        backup_layout.addWidget(self.import_settings_profile_btn)
        backup_layout.addWidget(self.edit_settings_json_btn)
        self._register_search(idx, "Backup Settings", self.backup_btn)
        self._register_search(idx, "Restore Settings", self.restore_btn)
        self._register_search(idx, "Backup output folder", self.backup_output_dir_edit)
        backup_layout.addStretch(1)
        self.backup_btn.clicked.connect(self.backup_settings)
        self.restore_btn.clicked.connect(self.restore_settings)
        self.export_settings_profile_btn.clicked.connect(self._export_profile)
        self.import_settings_profile_btn.clicked.connect(self._import_profile)
        self.edit_settings_json_btn.clicked.connect(self._edit_with_settings_json)
        self.backup_output_dir_browse_btn.clicked.connect(self._pick_backup_output_dir)

        # Advanced
        advanced = QWidget(self)
        advanced_layout = QFormLayout(advanced)
        idx = self._add_category("🧪 Advanced", advanced)
        self.experimental_checkbox = self._add_check(advanced_layout, idx, "Enable experimental features")
        self.debug_telemetry_checkbox = self._add_check(advanced_layout, idx, "Enable debug telemetry")
        self.save_debug_logs_checkbox = self._add_check(
            advanced_layout,
            idx,
            "Save debug logs to app data and write crash traceback logs",
        )
        self.settings_schema_version_label = QLabel("2", advanced)
        advanced_layout.addRow("Settings schema version", self.settings_schema_version_label)
        self._register_search(idx, "Settings schema version", self.settings_schema_version_label)

    def _apply_search_filter(self, text: str) -> None:
        query = text.strip().lower()
        for widget in self._highlighted_widgets:
            widget.setStyleSheet("")
        self._highlighted_widgets.clear()
        counts = [0] * len(self._nav_base_labels)
        if query:
            for idx, label, widget in self._search_entries:
                if query in label:
                    counts[idx] += 1
                    widget.setStyleSheet("border: 1px solid #4a90e2;")
                    self._highlighted_widgets.append(widget)
            matching = [i for i, c in enumerate(counts) if c > 0]
            if len(matching) == 1:
                self.settings_nav_list.setCurrentRow(matching[0])
        for idx, base in enumerate(self._nav_base_labels):
            suffix = f" ({counts[idx]})" if query and counts[idx] else ""
            self.settings_nav_list.item(idx).setText(f"{base}{suffix}")

    def _set_color_label(self, label: QLabel, value: str) -> None:
        if value:
            label.setText(value)
            label.setStyleSheet(f"background-color: {value}; border: 1px solid #888; padding: 2px;")
        else:
            label.setText("(auto)")
            label.setStyleSheet("")

    def _apply_dialog_theme(self) -> None:
        dark_mode = bool(self.dark_checkbox.isChecked())
        accent_color = self._normalize_hex(self._label_color_value(self.accent_color_label), "#4a90e2")
        bg = "#1f2023" if dark_mode else "#f5f7fb"
        panel = "#25272b" if dark_mode else "#ffffff"
        text = "#e8eaed" if dark_mode else "#111111"
        border = "#3c4043" if dark_mode else "#c9cdd3"
        hover = "#353942" if dark_mode else "#eef3fb"
        input_bg = "#2b2e33" if dark_mode else "#ffffff"
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {bg};
                color: {text};
            }}
            QListWidget, QStackedWidget, QGroupBox {{
                background: {panel};
                color: {text};
                border: 1px solid {border};
            }}
            QListWidget::item {{
                padding: 4px 6px;
                border: 1px solid transparent;
            }}
            QListWidget::item:hover {{
                background: {hover};
            }}
            QListWidget::item:selected {{
                background: {accent_color};
                color: #ffffff;
            }}
            QGroupBox {{
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }}
            QLabel, QCheckBox {{
                color: {text};
                background: transparent;
            }}
            QLineEdit, QComboBox, QSpinBox, QSlider {{
                background: {input_bg};
                color: {text};
                border: 1px solid {border};
            }}
            QComboBox QAbstractItemView {{
                background: {panel};
                color: {text};
                selection-background-color: {accent_color};
                selection-color: #ffffff;
            }}
            QPushButton {{
                background: {panel};
                color: {text};
                border: 1px solid {border};
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: {hover};
                border: 1px solid {accent_color};
            }}
            QPushButton:pressed {{
                background: {accent_color};
                color: #ffffff;
                border: 1px solid {accent_color};
            }}
            QSplitter::handle {{
                background: {border};
            }}
            """
        )

    def _label_color_value(self, label: QLabel) -> str:
        text = label.text().strip()
        return "" if text == "(auto)" else text

    def _load_controls_from_settings(self, s: dict) -> None:
        self.dark_checkbox.setChecked(bool(s.get("dark_mode", False)))
        self.app_style_combo.setCurrentText(str(s.get("app_style", "System Default")))
        self.theme_combo.setCurrentText(str(s.get("theme", "Default")))
        self._set_color_label(self.accent_color_label, self._normalize_hex(str(s.get("accent_color", "#4a90e2")), "#4a90e2"))
        self.use_custom_colors_checkbox.setChecked(bool(s.get("use_custom_colors", False)))
        self._set_color_label(self.custom_editor_bg_label, self._normalize_hex(str(s.get("custom_editor_bg", "")), ""))
        self._set_color_label(self.custom_editor_fg_label, self._normalize_hex(str(s.get("custom_editor_fg", "")), ""))
        self._set_color_label(self.custom_chrome_bg_label, self._normalize_hex(str(s.get("custom_chrome_bg", "")), ""))
        self.font_family_edit.setText(str(s.get("font_family", "")))
        self.font_size_slider.setValue(int(s.get("font_size", 11)))
        self.ui_density_combo.setCurrentText(str(s.get("ui_density", "comfortable")))
        self.icon_size_combo.setCurrentText(str(int(s.get("icon_size_px", 18))))
        self.toolbar_label_mode_combo.setCurrentText(str(s.get("toolbar_label_mode", "icons_only")))
        self.show_main_toolbar_checkbox.setChecked(bool(s.get("show_main_toolbar", True)))
        self.show_markdown_toolbar_checkbox.setChecked(bool(s.get("show_markdown_toolbar", False)))
        self.show_find_panel_checkbox.setChecked(bool(s.get("show_find_panel", False)))
        self.simple_mode_checkbox.setChecked(bool(s.get("simple_mode", False)))

        self.syntax_highlight_checkbox.setChecked(bool(s.get("syntax_highlighting_enabled", True)))
        self.syntax_mode_combo.setCurrentText(str(s.get("syntax_highlighting_mode", "Auto")))
        self.checklist_toggle_checkbox.setChecked(bool(s.get("checklist_toggle_enabled", True)))
        self.tab_width_spin.setValue(int(s.get("tab_width", 4)))
        self.insert_spaces_checkbox.setChecked(bool(s.get("insert_spaces", True)))
        self.auto_indent_checkbox.setChecked(bool(s.get("auto_indent", True)))
        self.trim_trailing_checkbox.setChecked(bool(s.get("trim_trailing_whitespace_on_save", False)))
        self.caret_width_spin.setValue(int(s.get("caret_width_px", 1)))
        self.highlight_current_line_checkbox.setChecked(bool(s.get("highlight_current_line", True)))

        self.language_combo.setCurrentText(str(s.get("language", "English")))

        self.tab_close_mode_combo.setCurrentText(str(s.get("tab_close_button_mode", "always")))
        self.tab_elide_combo.setCurrentText(str(s.get("tab_elide_mode", "right")))
        self.tab_min_width_spin.setValue(int(s.get("tab_min_width_px", 120)))
        self.tab_max_width_spin.setValue(int(s.get("tab_max_width_px", 240)))
        self.tab_double_click_combo.setCurrentText(str(s.get("tab_double_click_action", "new_tab")))

        self.workspace_root_edit.setText(str(s.get("workspace_root", "")))
        self.workspace_show_hidden_checkbox.setChecked(bool(s.get("workspace_show_hidden_files", False)))
        self.workspace_follow_symlinks_checkbox.setChecked(bool(s.get("workspace_follow_symlinks", False)))
        self.workspace_max_scan_spin.setValue(int(s.get("workspace_max_scan_files", 25000)))

        self.search_default_match_case_checkbox.setChecked(bool(s.get("search_default_match_case", False)))
        self.search_default_whole_word_checkbox.setChecked(bool(s.get("search_default_whole_word", False)))
        self.search_default_regex_checkbox.setChecked(bool(s.get("search_default_regex", False)))
        self._set_color_label(self.search_highlight_color_label, self._normalize_hex(str(s.get("search_highlight_color", "#4a90e2")), "#4a90e2"))
        self.search_max_highlights_spin.setValue(int(s.get("search_max_highlights", 2000)))

        self.shortcut_profile_combo.setCurrentText(str(s.get("shortcut_profile", "vscode")))
        self.shortcut_conflict_combo.setCurrentText(str(s.get("shortcut_conflict_policy", "warn")))
        self.shortcut_show_unassigned_checkbox.setChecked(bool(s.get("shortcut_show_unassigned", True)))

        self.gemini_api_key_edit.setText(str(s.get("gemini_api_key", "")))
        self.ai_model_edit.setText(str(s.get("ai_model", "gemini-3-flash-preview")))
        self.update_feed_url_edit.setText(str(s.get("update_feed_url", DEFAULT_UPDATE_FEED_URL)))
        self.auto_check_updates_checkbox.setChecked(bool(s.get("auto_check_updates", True)))
        self.ai_send_redact_emails_checkbox.setChecked(bool(s.get("ai_send_redact_emails", False)))
        self.ai_send_redact_paths_checkbox.setChecked(bool(s.get("ai_send_redact_paths", False)))
        self.ai_send_redact_tokens_checkbox.setChecked(bool(s.get("ai_send_redact_tokens", True)))
        self.ai_key_storage_mode_combo.setCurrentText(str(s.get("ai_key_storage_mode", "settings")))
        self.ai_private_mode_checkbox.setChecked(bool(s.get("ai_private_mode", False)))
        self.ai_cost_rate_spin.setValue(float(s.get("ai_estimated_cost_per_1k_tokens", 0.0005) or 0.0005))

        self.privacy_lock_checkbox.setChecked(bool(s.get("privacy_lock", False)))
        self.lock_password_edit.setText(str(s.get("lock_password", "")))
        self.lock_pin_edit.setText(str(s.get("lock_pin", "")))
        self.recovery_mode_combo.setCurrentText(str(s.get("recovery_mode", "ask")))
        self.recovery_discard_days_spin.setValue(int(s.get("recovery_discard_after_days", 14)))
        self.backup_output_dir_edit.setText(str(s.get("backup_output_dir", "")))

        self.experimental_checkbox.setChecked(bool(s.get("experimental_features", False)))
        self.debug_telemetry_checkbox.setChecked(bool(s.get("debug_telemetry_enabled", False)))
        self.save_debug_logs_checkbox.setChecked(bool(s.get("save_debug_logs_to_appdata", False)))
        self.settings_schema_version_label.setText(str(int(s.get("settings_schema_version", 2))))

    def _collect_settings(self) -> dict:
        s = dict(self._settings)
        s["app_style"] = self.app_style_combo.currentText()
        s["dark_mode"] = self.dark_checkbox.isChecked()
        s["theme"] = self.theme_combo.currentText()
        s["accent_color"] = self._normalize_hex(self._label_color_value(self.accent_color_label), "#4a90e2")
        s["use_custom_colors"] = self.use_custom_colors_checkbox.isChecked()
        s["custom_editor_bg"] = self._normalize_hex(self._label_color_value(self.custom_editor_bg_label), "")
        s["custom_editor_fg"] = self._normalize_hex(self._label_color_value(self.custom_editor_fg_label), "")
        s["custom_chrome_bg"] = self._normalize_hex(self._label_color_value(self.custom_chrome_bg_label), "")
        s["font_family"] = self.font_family_edit.text().strip() or s.get("font_family", "")
        s["font_size"] = int(self.font_size_slider.value())
        s["ui_density"] = self.ui_density_combo.currentText()
        s["icon_size_px"] = int(self.icon_size_combo.currentText())
        s["toolbar_label_mode"] = self.toolbar_label_mode_combo.currentText()
        s["show_main_toolbar"] = self.show_main_toolbar_checkbox.isChecked()
        s["show_markdown_toolbar"] = self.show_markdown_toolbar_checkbox.isChecked()
        s["show_find_panel"] = self.show_find_panel_checkbox.isChecked()
        s["simple_mode"] = self.simple_mode_checkbox.isChecked()

        s["syntax_highlighting_enabled"] = self.syntax_highlight_checkbox.isChecked()
        s["syntax_highlighting_mode"] = self.syntax_mode_combo.currentText()
        s["checklist_toggle_enabled"] = self.checklist_toggle_checkbox.isChecked()
        s["tab_width"] = int(self.tab_width_spin.value())
        s["insert_spaces"] = self.insert_spaces_checkbox.isChecked()
        s["auto_indent"] = self.auto_indent_checkbox.isChecked()
        s["trim_trailing_whitespace_on_save"] = self.trim_trailing_checkbox.isChecked()
        s["caret_width_px"] = int(self.caret_width_spin.value())
        s["highlight_current_line"] = self.highlight_current_line_checkbox.isChecked()

        s["language"] = self.language_combo.currentText()

        s["tab_close_button_mode"] = self.tab_close_mode_combo.currentText()
        s["tab_elide_mode"] = self.tab_elide_combo.currentText()
        s["tab_min_width_px"] = int(self.tab_min_width_spin.value())
        s["tab_max_width_px"] = int(self.tab_max_width_spin.value())
        s["tab_double_click_action"] = self.tab_double_click_combo.currentText()

        s["workspace_root"] = self.workspace_root_edit.text().strip()
        s["workspace_show_hidden_files"] = self.workspace_show_hidden_checkbox.isChecked()
        s["workspace_follow_symlinks"] = self.workspace_follow_symlinks_checkbox.isChecked()
        s["workspace_max_scan_files"] = int(self.workspace_max_scan_spin.value())

        s["search_default_match_case"] = self.search_default_match_case_checkbox.isChecked()
        s["search_default_whole_word"] = self.search_default_whole_word_checkbox.isChecked()
        s["search_default_regex"] = self.search_default_regex_checkbox.isChecked()
        s["search_highlight_color"] = self._normalize_hex(self._label_color_value(self.search_highlight_color_label), "#4a90e2")
        s["search_max_highlights"] = int(self.search_max_highlights_spin.value())

        s["shortcut_profile"] = self.shortcut_profile_combo.currentText()
        s["shortcut_conflict_policy"] = self.shortcut_conflict_combo.currentText()
        s["shortcut_show_unassigned"] = self.shortcut_show_unassigned_checkbox.isChecked()

        s["gemini_api_key"] = self.gemini_api_key_edit.text().strip()
        s["ai_model"] = self.ai_model_edit.text().strip() or "gemini-3-flash-preview"
        s["update_feed_url"] = self.update_feed_url_edit.text().strip() or DEFAULT_UPDATE_FEED_URL
        s["auto_check_updates"] = self.auto_check_updates_checkbox.isChecked()
        s["ai_send_redact_emails"] = self.ai_send_redact_emails_checkbox.isChecked()
        s["ai_send_redact_paths"] = self.ai_send_redact_paths_checkbox.isChecked()
        s["ai_send_redact_tokens"] = self.ai_send_redact_tokens_checkbox.isChecked()
        s["ai_key_storage_mode"] = self.ai_key_storage_mode_combo.currentText()
        s["ai_private_mode"] = self.ai_private_mode_checkbox.isChecked()
        s["ai_estimated_cost_per_1k_tokens"] = float(self.ai_cost_rate_spin.value())

        s["privacy_lock"] = self.privacy_lock_checkbox.isChecked()
        s["lock_password"] = self.lock_password_edit.text()
        s["lock_pin"] = self.lock_pin_edit.text()
        s["recovery_mode"] = self.recovery_mode_combo.currentText()
        s["recovery_discard_after_days"] = int(self.recovery_discard_days_spin.value())
        s["backup_output_dir"] = self.backup_output_dir_edit.text().strip()

        s["experimental_features"] = self.experimental_checkbox.isChecked()
        s["debug_telemetry_enabled"] = self.debug_telemetry_checkbox.isChecked()
        s["save_debug_logs_to_appdata"] = self.save_debug_logs_checkbox.isChecked()
        s["settings_schema_version"] = 2
        return migrate_settings(s)

    def _apply_to_memory(self) -> None:
        self._settings = self._collect_settings()

    def _accept_with_apply(self) -> None:
        self._apply_to_memory()
        self.accept()

    def _reset_controls_to_defaults(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Restore Defaults",
            "Reset settings in this dialog to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        defaults = self._parent_window._build_default_settings()
        self._load_controls_from_settings(defaults)

    def get_settings(self) -> dict:
        return dict(self._settings)

    def _export_profile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Profile", "", "Settings Files (*.json);;All Files (*.*)")
        if not path:
            return
        payload = self._collect_settings()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export Profile Failed", f"Could not export profile:\n{exc}")

    def _import_profile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Profile", "", "Settings Files (*.json);;All Files (*.*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("Profile must be a JSON object.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import Profile Failed", f"Could not import profile:\n{exc}")
            return
        self._settings = migrate_settings(loaded)
        self._load_controls_from_settings(self._settings)

    def backup_settings(self) -> None:
        self._export_profile()

    def restore_settings(self) -> None:
        self._import_profile()

    def _edit_with_settings_json(self) -> None:
        self._apply_to_memory()
        self._parent_window.settings = self.get_settings()
        self._parent_window.save_settings_to_disk()
        self.accept()
        QTimer.singleShot(0, self._parent_window.edit_settings_json_in_app)

    def _open_mapper_from_settings(self) -> None:
        self._apply_to_memory()
        self._parent_window.settings = self.get_settings()
        self._parent_window.open_shortcut_mapper()
        self._settings = dict(self._parent_window.settings)
        self._load_controls_from_settings(self._settings)

    def _pick_backup_output_dir(self) -> None:
        start_dir = self.backup_output_dir_edit.text().strip() or ""
        picked = QFileDialog.getExistingDirectory(self, "Choose Backup Output Folder", start_dir)
        if picked:
            self.backup_output_dir_edit.setText(picked)

    def _clear_translation_cache(self) -> None:
        if hasattr(self._parent_window, "clear_translation_cache"):
            self._parent_window.clear_translation_cache()
            QMessageBox.information(self, "Translation Cache", "Translation cache cleared.")

