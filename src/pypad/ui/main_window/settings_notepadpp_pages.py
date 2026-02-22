from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...app_settings.notepadpp_prefs import ENCODING_CHOICES, LANGUAGE_MENU_ITEMS


def _ensure_storage(dialog) -> None:
    if not hasattr(dialog, "_npp_pref_controls"):
        dialog._npp_pref_controls = {}


def _register(dialog, key: str, kind: str, widget: Any, **meta: Any) -> None:
    _ensure_storage(dialog)
    dialog._npp_pref_controls[key] = {"kind": kind, "widget": widget, **meta}


def _add_check(dialog, layout: QVBoxLayout | QFormLayout, idx: int, key: str, label: str) -> QCheckBox:
    cb = QCheckBox(label)
    if isinstance(layout, QFormLayout):
        layout.addRow(cb)
    else:
        layout.addWidget(cb)
    dialog._register_search(idx, label, cb)
    _register(dialog, key, "bool", cb)
    return cb


def _add_spin(dialog, form: QFormLayout, idx: int, key: str, label: str, min_v: int, max_v: int) -> QSpinBox:
    spin = QSpinBox(form.parentWidget())
    spin.setRange(min_v, max_v)
    form.addRow(label, spin)
    dialog._register_search(idx, label, spin)
    _register(dialog, key, "int", spin)
    return spin


def _add_line(dialog, form: QFormLayout, idx: int, key: str, label: str, *, browse_dir: bool = False) -> QLineEdit:
    edit = QLineEdit(form.parentWidget())
    if not browse_dir:
        form.addRow(label, edit)
    else:
        holder = QWidget(form.parentWidget())
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("Browse...", holder)
        row.addWidget(edit, 1)
        row.addWidget(btn)

        def _browse() -> None:
            picked = QFileDialog.getExistingDirectory(dialog, f"Choose {label}", edit.text().strip())
            if picked:
                edit.setText(picked)

        btn.clicked.connect(_browse)
        form.addRow(label, holder)
    dialog._register_search(idx, label, edit)
    _register(dialog, key, "str", edit)
    return edit


def _add_text(dialog, form: QFormLayout, idx: int, key: str, label: str, height: int = 70) -> QTextEdit:
    edit = QTextEdit(form.parentWidget())
    edit.setMinimumHeight(height)
    form.addRow(label, edit)
    dialog._register_search(idx, label, edit)
    _register(dialog, key, "text", edit)
    return edit


def _add_combo(dialog, form: QFormLayout, idx: int, key: str, label: str, options: list[str]) -> QComboBox:
    combo = QComboBox(form.parentWidget())
    combo.addItems(options)
    form.addRow(label, combo)
    dialog._register_search(idx, label, combo)
    _register(dialog, key, "str_combo", combo)
    return combo


def _set_color_label(label: QLabel, value: str) -> None:
    if value:
        label.setText(value)
        label.setStyleSheet(f"background-color: {value}; border: 1px solid #888; padding: 2px;")
    else:
        label.setText("(auto)")
        label.setStyleSheet("")


def _add_color(dialog, form: QFormLayout, idx: int, key: str, label: str) -> QLabel:
    holder = QWidget(form.parentWidget())
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    preview = QLabel("(auto)", holder)
    preview.setMinimumWidth(100)
    pick = QPushButton("Pick...", holder)
    clear = QPushButton("Clear", holder)
    row.addWidget(preview)
    row.addWidget(pick)
    row.addWidget(clear)

    def _pick() -> None:
        base = preview.text() if preview.text() != "(auto)" else "#ffffff"
        color = QColorDialog.getColor(QColor(base), dialog, f"Select {label}")
        if color.isValid():
            _set_color_label(preview, color.name())

    pick.clicked.connect(_pick)
    clear.clicked.connect(lambda: _set_color_label(preview, ""))
    form.addRow(label, holder)
    dialog._register_search(idx, label, preview)
    _register(dialog, key, "color", preview)
    return preview


def _add_radio_group(dialog, root: QVBoxLayout, idx: int, key: str, title: str, options: list[tuple[str, str]]) -> None:
    group_box = QGroupBox(title)
    v = QVBoxLayout(group_box)
    buttons = QButtonGroup(group_box)
    mapping: dict[str, QRadioButton] = {}
    for value, text in options:
        rb = QRadioButton(text, group_box)
        v.addWidget(rb)
        buttons.addButton(rb)
        mapping[value] = rb
        dialog._register_search(idx, text, rb)
    root.addWidget(group_box)
    _register(dialog, key, "radio", buttons, mapping=mapping)


def _sort_list(widget: QListWidget) -> None:
    vals = sorted(widget.item(i).text() for i in range(widget.count()))
    widget.clear()
    for v in vals:
        widget.addItem(v)


def _add_dual_list_editor(dialog, root: QVBoxLayout, idx: int, key: str, title: str, all_items: list[str]) -> None:
    group = QGroupBox(title)
    lay = QHBoxLayout(group)
    avail = QListWidget(group)
    disabled = QListWidget(group)
    for item in all_items:
        avail.addItem(item)
    btn_col = QVBoxLayout()
    to_disabled = QPushButton("->", group)
    to_avail = QPushButton("<-", group)
    btn_col.addStretch(1)
    btn_col.addWidget(to_disabled)
    btn_col.addWidget(to_avail)
    btn_col.addStretch(1)
    lay.addWidget(avail, 1)
    btn_holder = QWidget(group)
    btn_holder.setLayout(btn_col)
    lay.addWidget(btn_holder)
    lay.addWidget(disabled, 1)
    root.addWidget(group)
    dialog._register_search(idx, title, avail)
    _register(dialog, key, "dual_list", (avail, disabled), all_items=all_items)

    def _move(src: QListWidget, dst: QListWidget) -> None:
        rows = sorted({src.row(item) for item in src.selectedItems()}, reverse=True)
        for row in rows:
            item = src.takeItem(row)
            if item is not None:
                dst.addItem(item.text())
        _sort_list(avail)
        _sort_list(disabled)

    to_disabled.clicked.connect(lambda: _move(avail, disabled))
    to_avail.clicked.connect(lambda: _move(disabled, avail))


def _add_string_list_editor(dialog, root: QVBoxLayout, idx: int, key: str, title: str) -> None:
    group = QGroupBox(title)
    v = QVBoxLayout(group)
    lst = QListWidget(group)
    row = QHBoxLayout()
    edit = QLineEdit(group)
    add_btn = QPushButton("Add", group)
    rm_btn = QPushButton("Remove Selected", group)
    row.addWidget(edit, 1)
    row.addWidget(add_btn)
    v.addWidget(lst)
    v.addLayout(row)
    v.addWidget(rm_btn)
    root.addWidget(group)
    dialog._register_search(idx, title, lst)
    _register(dialog, key, "string_list", (lst, edit))

    def _add() -> None:
        text = edit.text().strip()
        if not text:
            return
        existing = {lst.item(i).text().lower() for i in range(lst.count())}
        if text.lower() not in existing:
            lst.addItem(text)
            _sort_list(lst)
        edit.clear()

    add_btn.clicked.connect(_add)
    edit.returnPressed.connect(_add)
    rm_btn.clicked.connect(lambda: [lst.takeItem(lst.row(it)) for it in list(lst.selectedItems())])


def _add_indent_overrides_table(dialog, root: QVBoxLayout, idx: int, key: str) -> None:
    group = QGroupBox("Per-language indentation overrides")
    v = QVBoxLayout(group)
    table = QTableWidget(group)
    table.setColumnCount(4)
    table.setHorizontalHeaderLabels(["Language", "Size", "Use Tabs", "Auto Indent"])
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    if table.horizontalHeader() is not None:
        table.horizontalHeader().setStretchLastSection(True)
    buttons = QHBoxLayout()
    add_btn = QPushButton("Add Row", group)
    rm_btn = QPushButton("Remove Row", group)
    buttons.addWidget(add_btn)
    buttons.addWidget(rm_btn)
    buttons.addStretch(1)
    v.addWidget(table)
    v.addLayout(buttons)
    root.addWidget(group)
    dialog._register_search(idx, "Per-language indentation overrides", table)
    _register(dialog, key, "indent_overrides_table", table, category_idx=idx)

    language_options = sorted(
        {
            "python",
            "javascript",
            "typescript",
            "json",
            "markdown",
            "html",
            "xml",
            "css",
            "yaml",
            "sql",
            "bash",
            "powershell",
            "go",
            "rust",
            "c",
            "c++",
            "c#",
            "java",
            "php",
            "lua",
            "ini",
        }.union({str(x).strip().lower() for x in LANGUAGE_MENU_ITEMS if str(x).strip()})
    )

    def _set_row(row: int, language: str = "", size: int = 4, use_tabs: bool = False, auto_indent: bool = True) -> None:
        lang_combo = table.cellWidget(row, 0)
        if not isinstance(lang_combo, QComboBox):
            lang_combo = QComboBox(table)
            lang_combo.setEditable(True)
            lang_combo.addItems(language_options)
            lang_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            table.setCellWidget(row, 0, lang_combo)
            lang_combo.currentTextChanged.connect(lambda _text, _t=table: _validate_indent_override_rows(_t))
            line_edit = lang_combo.lineEdit()
            if line_edit is not None:
                line_edit.textChanged.connect(lambda _text, _t=table: _validate_indent_override_rows(_t))
        if language and lang_combo.findText(language) < 0:
            lang_combo.addItem(language)
        lang_combo.setCurrentText(language)

        size_spin = table.cellWidget(row, 1)
        if not isinstance(size_spin, QSpinBox):
            size_spin = QSpinBox(table)
            size_spin.setRange(1, 16)
            table.setCellWidget(row, 1, size_spin)
        size_spin.setValue(int(size))

        use_tabs_cb = table.cellWidget(row, 2)
        if not isinstance(use_tabs_cb, QCheckBox):
            use_tabs_cb = QCheckBox(table)
            use_tabs_cb.setStyleSheet("margin-left:12px;")
            table.setCellWidget(row, 2, use_tabs_cb)
        use_tabs_cb.setChecked(bool(use_tabs))

        auto_indent_cb = table.cellWidget(row, 3)
        if not isinstance(auto_indent_cb, QCheckBox):
            auto_indent_cb = QCheckBox(table)
            auto_indent_cb.setStyleSheet("margin-left:12px;")
            table.setCellWidget(row, 3, auto_indent_cb)
        auto_indent_cb.setChecked(bool(auto_indent))

    def _add_row() -> None:
        row = table.rowCount()
        table.insertRow(row)
        _set_row(row)
        _validate_indent_override_rows(table)

    def _remove_row() -> None:
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)
            _validate_indent_override_rows(table)

    add_btn.clicked.connect(_add_row)
    rm_btn.clicked.connect(_remove_row)
    setattr(table, "_pypad_validate_rows", lambda: _validate_indent_override_rows(table))


def _validate_indent_override_rows(table: QTableWidget) -> None:
    seen: dict[str, list[int]] = {}
    raw_values: list[str] = []
    for row in range(table.rowCount()):
        combo = table.cellWidget(row, 0)
        text = combo.currentText().strip() if isinstance(combo, QComboBox) else ""
        raw_values.append(text)
        key = text.lower()
        if key:
            seen.setdefault(key, []).append(row)
    duplicate_rows = {row for rows in seen.values() if len(rows) > 1 for row in rows}

    for row in range(table.rowCount()):
        combo = table.cellWidget(row, 0)
        if not isinstance(combo, QComboBox):
            continue
        line_edit = combo.lineEdit()
        text = raw_values[row] if row < len(raw_values) else ""
        is_empty = not text
        is_duplicate = row in duplicate_rows
        tooltip = ""
        style = ""
        if is_empty:
            tooltip = "Language is required."
            style = "QComboBox{border:1px solid #d19a00;background:#fff8db;} QLineEdit{background:#fff8db;}"
        elif is_duplicate:
            tooltip = "Duplicate language row. Keep only one row per language."
            style = "QComboBox{border:1px solid #d13438;background:#ffe8ea;} QLineEdit{background:#ffe8ea;}"
        combo.setToolTip(tooltip)
        combo.setStyleSheet(style)
        if line_edit is not None:
            line_edit.setToolTip(tooltip)


def validate_notepadpp_like_page_inputs(dialog) -> list[str]:
    errors: list[str] = []
    controls = getattr(dialog, "_npp_pref_controls", {})
    for key, spec in controls.items():
        if spec.get("kind") != "indent_overrides_table":
            continue
        table = spec.get("widget")
        if not isinstance(table, QTableWidget):
            continue
        seen: dict[str, int] = {}
        duplicate_rows: list[int] = []
        empty_rows: list[int] = []
        for row in range(table.rowCount()):
            combo = table.cellWidget(row, 0)
            lang = combo.currentText().strip().lower() if isinstance(combo, QComboBox) else ""
            if not lang:
                empty_rows.append(row + 1)
                continue
            if lang in seen:
                duplicate_rows.append(row + 1)
                if seen[lang] not in duplicate_rows:
                    duplicate_rows.append(seen[lang])
            else:
                seen[lang] = row + 1
        if empty_rows:
            errors.append("Indentation overrides: Language is required in row(s): " + ", ".join(map(str, sorted(empty_rows))))
        if duplicate_rows:
            errors.append(
                "Indentation overrides: Duplicate language rows found at row(s): "
                + ", ".join(map(str, sorted(set(duplicate_rows))))
            )
        validate_cb = getattr(table, "_pypad_validate_rows", None)
        if callable(validate_cb):
            validate_cb()
    return errors


def focus_first_invalid_notepadpp_like_input(dialog) -> bool:
    controls = getattr(dialog, "_npp_pref_controls", {})
    for _key, spec in controls.items():
        if spec.get("kind") != "indent_overrides_table":
            continue
        table = spec.get("widget")
        if not isinstance(table, QTableWidget):
            continue
        first_invalid_row: int | None = None
        seen: set[str] = set()
        for row in range(table.rowCount()):
            combo = table.cellWidget(row, 0)
            lang = combo.currentText().strip().lower() if isinstance(combo, QComboBox) else ""
            if not lang:
                first_invalid_row = row
                break
            if lang in seen:
                first_invalid_row = row
                break
            seen.add(lang)
        if first_invalid_row is None:
            continue
        category_idx = spec.get("category_idx")
        try:
            if isinstance(category_idx, int):
                dialog.settings_nav_list.setCurrentRow(category_idx)
        except Exception:
            pass
        try:
            table.selectRow(first_invalid_row)
            table.setCurrentCell(first_invalid_row, 0)
            combo = table.cellWidget(first_invalid_row, 0)
            if isinstance(combo, QComboBox):
                combo.setFocus()
                line_edit = combo.lineEdit()
                if line_edit is not None:
                    line_edit.selectAll()
                    line_edit.setFocus()
            else:
                table.setFocus()
        except Exception:
            return False
        return True
    return False


def _build_group_page(dialog, name: str, aliases: list[str], build_fn) -> None:
    page = QWidget(dialog)
    root = QVBoxLayout(page)
    idx = dialog._add_category(name, page)
    if aliases:
        dialog._register_route_aliases(idx, *aliases)
    build_fn(dialog, root, idx)
    root.addStretch(1)


def build_notepadpp_like_pages(dialog) -> None:
    _build_group_page(dialog, "N++ • 🧭 General", ["npp-general"], _build_general_page)
    _build_group_page(dialog, "N++ • 🧰 Toolbar", ["npp-toolbar"], _build_toolbar_page)
    _build_group_page(dialog, "N++ • 🗂️ Tab Bar", ["npp-tab-bar"], _build_tabbar_page)
    _build_group_page(dialog, "N++ • ✍️ Editing 1", ["npp-editing-1"], _build_editing1_page)
    _build_group_page(dialog, "N++ • ✍️ Editing 2", ["npp-editing-2"], _build_editing2_page)
    _build_group_page(dialog, "N++ • 📏 Margins/Border/Edge", ["npp-margins"], _build_margins_page)
    _build_group_page(dialog, "N++ • 📄 New Document", ["npp-new-document"], _build_new_document_page)
    _build_group_page(dialog, "N++ • 📂 Default Directory", ["npp-default-directory"], _build_default_directory_page)
    _build_group_page(dialog, "N++ • 🕘 Recent Files History", ["npp-recent-files"], _build_recent_files_page)
    _build_group_page(dialog, "N++ • 🔗 File Association", ["npp-file-association"], _build_file_association_page)
    _build_group_page(dialog, "N++ • 🈯 Language", ["npp-language"], _build_language_page)
    _build_group_page(dialog, "N++ • ↹ Indentation", ["npp-indentation"], _build_indentation_page)
    _build_group_page(dialog, "N++ • ✨ Highlighting", ["npp-highlighting"], _build_highlighting_page)
    _build_group_page(dialog, "N++ • 🖨️ Print", ["npp-print"], _build_print_page)
    _build_group_page(dialog, "N++ • 🔎 Searching", ["npp-searching"], _build_searching_page)
    _build_group_page(dialog, "N++ • 💾 Backup", ["npp-backup"], _build_backup_page)
    _build_group_page(dialog, "N++ • ⚡ Auto-Completion", ["npp-auto-completion"], _build_autocomplete_page)
    _build_group_page(dialog, "N++ • 🧩 Multi-Instance & Date", ["npp-multi-instance-date"], _build_multi_instance_page)
    _build_group_page(dialog, "N++ • 🔣 Delimiter", ["npp-delimiter"], _build_delimiter_page)
    _build_group_page(dialog, "N++ • 🚀 Performance", ["npp-performance"], _build_performance_page)
    _build_group_page(dialog, "N++ • ☁️ Cloud & Link", ["npp-cloud-link"], _build_cloud_link_page)
    _build_group_page(dialog, "N++ • 🌐 Search Engine", ["npp-search-engine"], _build_search_engine_page)
    _build_group_page(dialog, "N++ • 🧪 MISC.", ["npp-misc"], _build_misc_page)


def _build_general_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_localization", "Localization", ["English", "Spanish", "French", "German", "Hindi"])
    menu = QGroupBox("Menu")
    menu_v = QVBoxLayout(menu)
    _add_check(dialog, menu_v, idx, "npp_hide_menu_bar", "Hide (use Alt or F10 key to toggle)")
    _add_check(dialog, menu_v, idx, "npp_hide_menu_right_shortcuts", "Hide right shortcuts + glyph hints")
    root.addWidget(menu)
    status = QGroupBox("Status Bar")
    status_v = QVBoxLayout(status)
    _add_check(dialog, status_v, idx, "npp_hide_status_bar", "Hide")
    root.addWidget(status)


def _build_toolbar_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_toolbar_hidden", "Hide")
    _add_combo(
        dialog,
        form,
        idx,
        "npp_toolbar_icon_style",
        "Toolbar icons",
        ["fluent_small", "fluent_large", "filled_fluent_small", "filled_fluent_large", "standard_small"],
    )
    _add_combo(dialog, form, idx, "npp_toolbar_colorization", "Colorization", ["complete", "partial"])
    _add_combo(
        dialog,
        form,
        idx,
        "npp_toolbar_color_choice",
        "Color choice",
        ["default", "system_accent", "custom", "red", "green", "blue", "purple", "cyan", "olive", "yellow"],
    )
    _add_color(dialog, form, idx, "npp_toolbar_custom_color", "Custom color")


def _build_tabbar_page(dialog, root: QVBoxLayout, idx: int) -> None:
    behavior = QGroupBox("Behavior")
    bform = QFormLayout(behavior)
    _add_check(dialog, bform, idx, "npp_tabbar_hidden", "Hide")
    _add_check(dialog, bform, idx, "npp_tabbar_vertical", "Vertical")
    _add_check(dialog, bform, idx, "npp_tabbar_multiline", "Multi-line")
    _add_check(dialog, bform, idx, "npp_tabbar_lock_drag_drop", "Lock (no drag and drop)")
    _add_check(dialog, bform, idx, "npp_tabbar_double_click_close", "Double click to close document")
    _add_check(dialog, bform, idx, "npp_tabbar_exit_on_last_close", "Exit on close the last tab")
    _add_spin(dialog, bform, idx, "npp_tabbar_max_title_len", "Max. tab label length", 0, 300)
    root.addWidget(behavior)

    look = QGroupBox("Look & feel")
    lform = QFormLayout(look)
    _add_check(dialog, lform, idx, "npp_tabbar_reduce", "Reduce")
    _add_check(dialog, lform, idx, "npp_tabbar_alternate_icons", "Alternate icons")
    _add_check(dialog, lform, idx, "npp_tabbar_change_inactive_color", "Change inactive tab color")
    _add_check(dialog, lform, idx, "npp_tabbar_active_color_bar", "Draw a coloured bar on active tab")
    _add_check(dialog, lform, idx, "npp_tabbar_show_close_button", "Show close button")
    _add_check(dialog, lform, idx, "npp_tabbar_enable_pin", "Enable pin tab feature")
    _add_check(dialog, lform, idx, "npp_tabbar_show_only_pinned_close", "Show only pinned tab button")
    _add_check(dialog, lform, idx, "npp_tabbar_show_buttons_on_inactive", "Show buttons on inactive tabs")
    root.addWidget(look)


def _build_editing1_page(dialog, root: QVBoxLayout, idx: int) -> None:
    _add_radio_group(
        dialog,
        root,
        idx,
        "npp_current_line_indicator",
        "Current Line Indicator",
        [("none", "None"), ("highlight_background", "Highlight Background"), ("frame", "Frame")],
    )
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_line_wrap_mode", "Line Wrap", ["default", "aligned", "indent"])
    _add_check(dialog, form, idx, "npp_enable_smooth_font", "Enable smooth font")
    _add_check(dialog, form, idx, "npp_enable_virtual_space", "Enable virtual space")
    _add_check(dialog, form, idx, "npp_fold_commands_toggleable", "Make current level folding/unfolding commands toggleable")
    _add_check(dialog, form, idx, "npp_keep_selection_on_right_click", "Keep selection when right-click outside of selection")
    _add_check(dialog, form, idx, "npp_copy_cut_line_without_selection", "Enable Copy/Cut line without selection")
    _add_check(dialog, form, idx, "npp_custom_selected_text_fg_enabled", "Apply custom color to selected text foreground")
    _add_check(dialog, form, idx, "npp_scrolling_beyond_last_line", "Enable scrolling beyond last line")
    _add_check(dialog, form, idx, "npp_disable_advanced_scrolling_touchpad", "Disable advanced scrolling feature due to touchpad issue")


def _build_editing2_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_multi_editing_enabled", "Enable Multi-Editing (Ctrl+Mouse click/selection)")
    _add_check(dialog, form, idx, "npp_column_selection_multi_editing", "Enable Column Selection to Multi-Editing")
    _add_combo(dialog, form, idx, "npp_eol_display_mode", "EOL display", ["default", "plain_text"])
    _add_check(dialog, form, idx, "npp_eol_custom_color_enabled", "EOL custom color")
    _add_color(dialog, form, idx, "npp_eol_custom_color", "EOL custom color value")
    _add_combo(dialog, form, idx, "npp_non_printing_appearance", "Non-printing appearance", ["abbreviation", "codepoint"])
    _add_check(dialog, form, idx, "npp_non_printing_custom_color_enabled", "Non-printing custom color")
    _add_color(dialog, form, idx, "npp_non_printing_custom_color", "Non-printing custom color value")
    _add_check(dialog, form, idx, "npp_apply_non_printing_appearance_to_eol", "Apply appearance settings to C0, C1 & Unicode EOL")
    _add_check(dialog, form, idx, "npp_prevent_c0_input", "Prevent control character (C0 code) typing into document")


def _build_dark_mode_controls(dialog, root: QVBoxLayout, idx: int) -> None:
    _add_radio_group(
        dialog,
        root,
        idx,
        "npp_dark_mode_preference",
        "Dark mode",
        [("light", "Light mode"), ("dark", "Dark mode"), ("follow_windows", "Follow Windows")],
    )
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_dark_tone_preset", "Tones", ["black", "red", "green", "blue", "purple", "cyan", "olive", "custom"])
    _add_color(dialog, form, idx, "npp_dark_custom_content_bg", "Content background")
    _add_color(dialog, form, idx, "npp_dark_custom_hottrack", "Hot track item")
    _add_color(dialog, form, idx, "npp_dark_custom_control_bg", "Control background")
    _add_color(dialog, form, idx, "npp_dark_custom_dialog_bg", "Dialog background")
    _add_color(dialog, form, idx, "npp_dark_custom_error", "Error")


def _build_dark_mode_page(dialog, root: QVBoxLayout, idx: int) -> None:
    _build_dark_mode_controls(dialog, root, idx)


def build_npp_dark_mode_embedded_group(dialog, parent_layout: QVBoxLayout, idx: int) -> None:
    group = QGroupBox("N++ Compatibility: Dark Mode")
    group_layout = QVBoxLayout(group)
    note = QLabel("Advanced compatibility dark-mode preferences that extend PyPad Appearance.")
    note.setWordWrap(True)
    note.setStyleSheet("color: #888;")
    group_layout.addWidget(note)
    _build_dark_mode_controls(dialog, group_layout, idx)
    parent_layout.addWidget(group)


def _build_margins_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_margin_fold_style", "Fold margin style", ["simple", "arrow", "circle_tree", "box_tree", "none"])
    _add_check(dialog, form, idx, "npp_margin_edge_enabled", "Vertical edge settings enabled")
    _add_check(dialog, form, idx, "npp_margin_edge_background_mode", "Vertical edge background mode")
    _add_spin(dialog, form, idx, "npp_margin_border_width", "Border width", 0, 20)
    _add_check(dialog, form, idx, "npp_margin_no_edge", "No edge")
    _add_check(dialog, form, idx, "npp_margin_line_numbers_enabled", "Display line number")
    _add_combo(dialog, form, idx, "npp_margin_line_number_width_mode", "Line number width", ["dynamic", "constant"])
    _add_spin(dialog, form, idx, "npp_margin_padding_left", "Padding left", 0, 50)
    _add_spin(dialog, form, idx, "npp_margin_padding_right", "Padding right", 0, 50)
    _add_spin(dialog, form, idx, "npp_margin_distraction_free", "Distraction Free", 0, 50)
    _add_check(dialog, form, idx, "npp_margin_display_bookmarks", "Display bookmark")


def _build_new_document_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_new_doc_eol", "Format (line ending)", ["windows", "unix", "mac"])
    _add_combo(dialog, form, idx, "npp_new_doc_encoding", "Encoding", ENCODING_CHOICES)
    _add_check(dialog, form, idx, "npp_new_doc_apply_to_opened_ansi", "Apply to opened ANSI files")
    _add_line(dialog, form, idx, "npp_new_doc_language", "Default language")
    _add_check(dialog, form, idx, "npp_new_doc_open_extra_on_startup", "Always open a new document in addition at startup")
    _add_check(dialog, form, idx, "npp_new_doc_first_line_as_tab_name", "Use the first line of document as untitled tab name")


def _build_default_directory_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_default_dir_mode", "Default Open/Save file Directory", ["follow_current_document", "remember_last_used", "custom"])
    _add_line(dialog, form, idx, "npp_default_dir_path", "Custom path", browse_dir=True)
    _add_check(dialog, form, idx, "npp_drop_folder_open_all_files", "Open all files of folder instead of Folder as Workspace when dropping")


def _build_recent_files_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_recent_dont_check_exists", "Don't check at launch time")
    _add_spin(dialog, form, idx, "npp_recent_max_entries", "Max. number of entries", 0, 30)
    _add_check(dialog, form, idx, "npp_recent_in_submenu", "In Submenu")
    _add_combo(dialog, form, idx, "npp_recent_display_mode", "Display", ["only_file_name", "full_path", "custom_max"])
    _add_spin(dialog, form, idx, "npp_recent_custom_max_len", "Customize Maximum Length", 0, 259)


def _build_file_association_page(dialog, root: QVBoxLayout, idx: int) -> None:
    info = QLabel("Profile-based extension lists. OS registration may require Administrator mode.")
    info.setWordWrap(True)
    root.addWidget(info)
    _add_string_list_editor(dialog, root, idx, "npp_file_assoc_custom_supported", "Supported extensions (custom)")
    _add_string_list_editor(dialog, root, idx, "npp_file_assoc_registered", "Registered extensions")


def _build_language_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_language_menu_compact", "Make language menu compact")
    _add_check(dialog, form, idx, "npp_sql_backslash_as_escape", "Treat backslash as escape character for SQL")
    _add_dual_list_editor(dialog, root, idx, "npp_language_menu_disabled_items", "Language Menu", LANGUAGE_MENU_ITEMS)


def _build_indentation_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_indent_scope", "Indent settings", ["default", "language_specific"])
    _add_spin(dialog, form, idx, "npp_indent_size", "Indent size", 1, 16)
    _add_combo(dialog, form, idx, "npp_indent_using", "Indent using", ["tab", "space"])
    _add_check(dialog, form, idx, "npp_indent_backspace_unindents", "Backspace key unindents instead of removing single space")
    _add_combo(dialog, form, idx, "npp_auto_indent_mode", "Auto-indent", ["none", "basic", "advanced"])
    _add_indent_overrides_table(dialog, root, idx, "npp_indent_language_overrides")


def _build_highlighting_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    for key, label in [
        ("npp_highlight_style_all_match_case", "Style all occurrences: Match case"),
        ("npp_highlight_style_all_whole_word", "Style all occurrences: Match whole word only"),
        ("npp_highlight_matching_tags", "Highlight Matching Tags: Enable"),
        ("npp_highlight_tag_attributes", "Highlight tag attributes"),
        ("npp_highlight_comment_zones", "Highlight comment/php/asp zone"),
        ("npp_smart_highlighting_enabled", "Smart Highlighting: Enable"),
        ("npp_smart_highlighting_other_view", "Smart Highlighting: Highlight another view"),
        ("npp_smart_highlighting_match_case", "Smart Highlighting: Match case"),
        ("npp_smart_highlighting_whole_word", "Smart Highlighting: Match whole word only"),
        ("npp_smart_highlighting_use_find_settings", "Smart Highlighting: Use Find dialog settings"),
    ]:
        _add_check(dialog, form, idx, key, label)


def _build_print_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_print_line_numbers", "Print line number")
    _add_combo(dialog, form, idx, "npp_print_color_mode", "Color mode", ["wysiwyg", "invert", "black_on_white", "no_background"])
    for key, label in [
        ("npp_print_margin_top_mm", "Top margin (mm)"),
        ("npp_print_margin_left_mm", "Left margin (mm)"),
        ("npp_print_margin_right_mm", "Right margin (mm)"),
        ("npp_print_margin_bottom_mm", "Bottom margin (mm)"),
    ]:
        _add_spin(dialog, form, idx, key, label, 0, 100)
    _add_check(dialog, form, idx, "npp_print_header_enabled", "Enable header")
    _add_check(dialog, form, idx, "npp_print_footer_enabled", "Enable footer")
    for key, label in [
        ("npp_print_header_left", "Header left"),
        ("npp_print_header_center", "Header middle"),
        ("npp_print_header_right", "Header right"),
        ("npp_print_footer_left", "Footer left"),
        ("npp_print_footer_center", "Footer middle"),
        ("npp_print_footer_right", "Footer right"),
    ]:
        _add_line(dialog, form, idx, key, label)


def _build_searching_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_spin(dialog, form, idx, "npp_find_min_selection_auto_checking", 'Minimum Size for Auto-Checking "In selection"', 32, 100000)
    _add_check(dialog, form, idx, "npp_find_fill_dir_from_active_doc", "Fill Find in Files Directory Field Based On Active Document")
    _add_check(dialog, form, idx, "npp_find_fill_with_selected_text", "Fill Find Field with Selected Text")
    _add_spin(dialog, form, idx, "npp_find_max_auto_fill_chars", "Max Characters to Auto-Fill Find Field from Selection", 32, 100000)
    _add_check(dialog, form, idx, "npp_find_select_word_under_caret", "Select Word Under Caret when Nothing Selected")
    _add_check(dialog, form, idx, "npp_find_use_monospace_dialog_font", "Use Monospaced font in Find dialog")
    _add_check(dialog, form, idx, "npp_find_stay_open_after_results", "Find dialog remains open after results")
    _add_check(dialog, form, idx, "npp_find_confirm_replace_all_open_docs", "Confirm Replace All in All Opened Documents")
    _add_check(dialog, form, idx, "npp_find_replace_dont_move_next_occurrence", "Replace: Don't move to the following occurrence")
    _add_check(dialog, form, idx, "npp_search_results_one_entry_per_found_line", "Search Result: one entry per found line")


def _build_backup_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_backup_remember_session_next_launch", "Remember current session for next launch")
    _add_check(dialog, form, idx, "npp_backup_enable_session_snapshot", "Enable session snapshot and periodic backup")
    _add_spin(dialog, form, idx, "npp_backup_trigger_seconds", "Trigger backup on modification (sec)", 1, 300)
    _add_line(dialog, form, idx, "npp_backup_path", "Backup path", browse_dir=True)
    _add_check(dialog, form, idx, "npp_backup_remember_inaccessible_files", "Remember inaccessible files from past session")
    _add_combo(dialog, form, idx, "npp_backup_on_save_mode", "Backup on save", ["none", "simple", "verbose"])
    _add_check(dialog, form, idx, "npp_backup_custom_dir_enabled", "Custom Backup Directory")
    _add_line(dialog, form, idx, "npp_backup_custom_dir", "Custom backup directory", browse_dir=True)


def _build_autocomplete_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_autocomplete_enabled", "Enable auto-completion on each input")
    _add_combo(dialog, form, idx, "npp_autocomplete_mode", "Completion mode", ["function", "word", "function_and_word"])
    _add_spin(dialog, form, idx, "npp_autocomplete_from_nth_char", "From nth character", 1, 9)
    _add_check(dialog, form, idx, "npp_autocomplete_insert_tab", "Insert selection with TAB")
    _add_check(dialog, form, idx, "npp_autocomplete_insert_enter", "Insert selection with ENTER")
    _add_check(dialog, form, idx, "npp_autocomplete_ignore_numbers", "Ignore numbers")
    _add_check(dialog, form, idx, "npp_autocomplete_brief_hint", "Make auto-completion list brief")
    _add_check(dialog, form, idx, "npp_autocomplete_param_hint", "Function parameters hint on input")
    for key, label in [
        ("npp_autoinsert_paren", "Auto-insert ( )"),
        ("npp_autoinsert_bracket", "Auto-insert [ ]"),
        ("npp_autoinsert_brace", "Auto-insert { }"),
        ("npp_autoinsert_quote", 'Auto-insert "'),
        ("npp_autoinsert_apostrophe", "Auto-insert '"),
        ("npp_autoinsert_html_xml_close_tag", "Auto-insert html/xml close tag"),
    ]:
        _add_check(dialog, form, idx, key, label)


def _build_multi_instance_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_multi_instance_mode", "Multi-instance settings", ["default", "always_multi", "new_instance_and_save_session"])
    _add_check(dialog, form, idx, "npp_insert_datetime_reverse_order", "Reverse default date time order")
    _add_line(dialog, form, idx, "npp_insert_datetime_custom_format", "Custom format")
    for key, label in [
        ("npp_panel_state_clipboard_history", "Clipboard History"),
        ("npp_panel_state_document_list", "Document List"),
        ("npp_panel_state_character_panel", "Character Panel"),
        ("npp_panel_state_folder_as_workspace", "Folder as Workspace"),
        ("npp_panel_state_project_panels", "Project Panels"),
        ("npp_panel_state_document_map", "Document Map"),
        ("npp_panel_state_function_list", "Function List"),
        ("npp_panel_state_plugin_panels", "Plugin Panels"),
    ]:
        _add_check(dialog, form, idx, key, f"Remember panel state: {label}")


def _build_delimiter_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_delimiter_word_chars_mode", "Word character list", ["default", "custom"])
    _add_line(dialog, form, idx, "npp_delimiter_extra_word_chars", "Custom word chars")
    _add_line(dialog, form, idx, "npp_delimiter_open", "Open delimiter")
    _add_line(dialog, form, idx, "npp_delimiter_close", "Close delimiter")
    _add_check(dialog, form, idx, "npp_delimiter_allow_several_lines", "Allow on several lines")


def _build_performance_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_check(dialog, form, idx, "npp_large_file_restriction_enabled", "Enable Large File Restriction (no syntax highlighting)")
    _add_spin(dialog, form, idx, "npp_large_file_size_mb", "Define Large File Size (MB)", 1, 2046)
    _add_check(dialog, form, idx, "npp_large_file_disable_word_wrap", "Deactivate Word Wrap globally")
    _add_check(dialog, form, idx, "npp_large_file_allow_autocomplete", "Allow Auto-Completion")
    _add_check(dialog, form, idx, "npp_large_file_allow_smart_highlighting", "Allow Smart Highlighting")
    _add_check(dialog, form, idx, "npp_large_file_allow_brace_match", "Allow Brace match")
    _add_check(dialog, form, idx, "npp_large_file_allow_clickable_link", "Allow URL Clickable Link")
    _add_check(dialog, form, idx, "npp_large_file_suppress_warn_gt_2gb", "Suppress warning when opening >2GB files")


def _build_cloud_link_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_cloud_mode", "Settings on cloud", ["no_cloud", "custom_path"])
    _add_line(dialog, form, idx, "npp_cloud_settings_path", "Cloud location path", browse_dir=True)
    _add_check(dialog, form, idx, "npp_clickable_links_enabled", "Clickable links: Enable")
    _add_check(dialog, form, idx, "npp_clickable_links_no_underline", "Clickable links: No underline")
    _add_check(dialog, form, idx, "npp_clickable_links_fullbox_mode", "Clickable links: Enable fullbox mode")
    _add_text(dialog, form, idx, "npp_clickable_link_schemes", "URI customized schemes", 90)


def _build_search_engine_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    _add_combo(dialog, form, idx, "npp_search_engine_provider", "Search Engine", ["DuckDuckGo", "Google", "Yahoo!", "Stack Overflow", "Bing", "Custom"])
    _add_line(dialog, form, idx, "npp_search_engine_custom_url", "Custom search engine URL")
    note = QLabel("Use $(CURRENT_WORD) in custom URLs.")
    form.addRow("", note)
    dialog._register_search(idx, "CURRENT_WORD", note)


def _build_misc_page(dialog, root: QVBoxLayout, idx: int) -> None:
    form = QFormLayout()
    root.addLayout(form)
    notes = _add_text(dialog, form, idx, "npp_misc_notes", "Misc notes", 120)
    notes.setPlaceholderText("Store preferences notes, team conventions, or future tweaks.")


def load_notepadpp_like_page_settings(dialog, settings: dict) -> None:
    if "language" in settings and "npp_localization" in getattr(dialog, "_npp_pref_controls", {}):
        settings = dict(settings)
        settings["npp_localization"] = str(settings.get("language", settings.get("npp_localization", "English")))
    for key, spec in getattr(dialog, "_npp_pref_controls", {}).items():
        kind = spec["kind"]
        widget = spec["widget"]
        value = settings.get(key)
        if kind == "bool":
            widget.setChecked(bool(value))
        elif kind == "int":
            try:
                widget.setValue(int(value))
            except Exception:
                pass
        elif kind == "str":
            widget.setText(str(value or ""))
        elif kind == "str_combo":
            text = str(value or "")
            if widget.findText(text) < 0 and text:
                widget.addItem(text)
            widget.setCurrentText(text)
        elif kind == "text":
            widget.setPlainText(str(value or ""))
        elif kind == "color":
            _set_color_label(widget, str(value or ""))
        elif kind == "radio":
            mapping = spec.get("mapping", {})
            btn = mapping.get(str(value or ""))
            if btn is None and mapping:
                btn = next(iter(mapping.values()))
            if btn is not None:
                btn.setChecked(True)
        elif kind == "dual_list":
            avail, disabled = widget
            all_items = list(spec.get("all_items", []))
            disabled_set = {str(x) for x in (value or []) if str(x)}
            avail.clear()
            disabled.clear()
            for item in all_items:
                (disabled if item in disabled_set else avail).addItem(item)
            _sort_list(avail)
            _sort_list(disabled)
        elif kind == "string_list":
            lst, _edit = widget
            lst.clear()
            for item in (value or []):
                text = str(item or "").strip()
                if text:
                    lst.addItem(QListWidgetItem(text))
            _sort_list(lst)
        elif kind == "indent_overrides_table":
            table: QTableWidget = widget
            table.setRowCount(0)
            raw = value if isinstance(value, dict) else {}
            for lang in sorted(raw.keys()):
                cfg = raw.get(lang, {}) if isinstance(raw.get(lang), dict) else {}
                row = table.rowCount()
                table.insertRow(row)
                lang_combo = QComboBox(table)
                lang_combo.setEditable(True)
                lang_combo.addItems(
                    sorted(
                        {
                            "python",
                            "javascript",
                            "typescript",
                            "json",
                            "markdown",
                            "html",
                            "xml",
                            "css",
                            "yaml",
                            "sql",
                            "bash",
                            "powershell",
                            "go",
                            "rust",
                            "c",
                            "c++",
                            "c#",
                            "java",
                            "php",
                            "lua",
                            "ini",
                        }.union({str(x).strip().lower() for x in LANGUAGE_MENU_ITEMS if str(x).strip()})
                    )
                )
                lang_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                if lang_combo.findText(str(lang)) < 0:
                    lang_combo.addItem(str(lang))
                lang_combo.setCurrentText(str(lang))
                table.setCellWidget(row, 0, lang_combo)
                size_spin = QSpinBox(table)
                size_spin.setRange(1, 16)
                size_spin.setValue(int(cfg.get("size", 4) or 4))
                table.setCellWidget(row, 1, size_spin)
                use_tabs_cb = QCheckBox(table)
                use_tabs_cb.setStyleSheet("margin-left:12px;")
                use_tabs_cb.setChecked(bool(cfg.get("use_tabs", False)))
                table.setCellWidget(row, 2, use_tabs_cb)
                auto_indent_cb = QCheckBox(table)
                auto_indent_cb.setStyleSheet("margin-left:12px;")
                auto_indent_cb.setChecked(bool(cfg.get("auto_indent", True)))
                table.setCellWidget(row, 3, auto_indent_cb)
            validate_cb = getattr(table, "_pypad_validate_rows", None)
            if callable(validate_cb):
                validate_cb()


def collect_notepadpp_like_page_settings(dialog, settings: dict) -> dict:
    for key, spec in getattr(dialog, "_npp_pref_controls", {}).items():
        kind = spec["kind"]
        widget = spec["widget"]
        if kind == "bool":
            settings[key] = bool(widget.isChecked())
        elif kind == "int":
            settings[key] = int(widget.value())
        elif kind == "str":
            settings[key] = widget.text().strip()
        elif kind == "str_combo":
            settings[key] = widget.currentText().strip()
        elif kind == "text":
            settings[key] = widget.toPlainText().strip()
        elif kind == "color":
            settings[key] = "" if widget.text() == "(auto)" else widget.text().strip()
        elif kind == "radio":
            mapping = spec.get("mapping", {})
            for value, btn in mapping.items():
                if btn.isChecked():
                    settings[key] = value
                    break
        elif kind == "dual_list":
            _avail, disabled = widget
            settings[key] = [disabled.item(i).text() for i in range(disabled.count())]
        elif kind == "string_list":
            lst, _edit = widget
            settings[key] = [lst.item(i).text() for i in range(lst.count())]
        elif kind == "indent_overrides_table":
            table: QTableWidget = widget
            overrides: dict[str, dict[str, Any]] = {}
            for row in range(table.rowCount()):
                lang_widget = table.cellWidget(row, 0)
                lang = (lang_widget.currentText() if isinstance(lang_widget, QComboBox) else "").strip().lower()
                if not lang:
                    continue
                size_widget = table.cellWidget(row, 1)
                use_tabs_widget = table.cellWidget(row, 2)
                auto_indent_widget = table.cellWidget(row, 3)
                size = int(size_widget.value()) if isinstance(size_widget, QSpinBox) else 4
                use_tabs = bool(use_tabs_widget.isChecked()) if isinstance(use_tabs_widget, QCheckBox) else False
                auto_indent = (
                    bool(auto_indent_widget.isChecked()) if isinstance(auto_indent_widget, QCheckBox) else True
                )
                overrides[lang] = {
                    "size": max(1, min(16, size)),
                    "use_tabs": use_tabs,
                    "auto_indent": auto_indent,
                }
            settings[key] = overrides
    # Bridge a few extended pages to existing canonical runtime settings.
    settings["language"] = str(settings.get("npp_localization", settings.get("language", "English")) or "English")
    dark_pref = str(settings.get("npp_dark_mode_preference", "follow_windows") or "follow_windows")
    if dark_pref == "dark":
        settings["dark_mode"] = True
    elif dark_pref == "light":
        settings["dark_mode"] = False
    settings["restore_last_session"] = bool(settings.get("npp_backup_remember_session_next_launch", settings.get("restore_last_session", True)))
    settings["autosave_enabled"] = bool(settings.get("npp_backup_enable_session_snapshot", settings.get("autosave_enabled", True)))
    settings["autosave_interval_sec"] = int(settings.get("npp_backup_trigger_seconds", settings.get("autosave_interval_sec", 30)))
    settings["large_file_threshold_kb"] = int(settings.get("npp_large_file_size_mb", 200)) * 1024
    if bool(settings.get("npp_toolbar_hidden", False)):
        settings["show_main_toolbar"] = False
    return settings
