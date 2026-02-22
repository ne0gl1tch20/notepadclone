from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SEARCH_ENGINE_PRESETS: dict[str, str] = {
    "DuckDuckGo": "https://duckduckgo.com/?q=$(CURRENT_WORD)",
    "Google": "https://www.google.com/search?q=$(CURRENT_WORD)",
    "Yahoo!": "https://search.yahoo.com/search?p=$(CURRENT_WORD)",
    "Stack Overflow": "https://stackoverflow.com/search?q=$(CURRENT_WORD)",
    "Bing": "https://www.bing.com/search?q=$(CURRENT_WORD)",
    "Custom": "",
}


ENCODING_CHOICES: list[str] = [
    "ANSI",
    "UTF-8",
    "UTF-8 with BOM",
    "UTF-16 LE",
    "UTF-16 BE",
    "Windows-1252",
    "Windows-1251",
    "ISO-8859-1",
    "OEM 437",
    "OEM 850",
]


LANGUAGE_MENU_ITEMS: list[str] = [
    "ActionScript",
    "Ada",
    "Assembly",
    "AutoIt",
    "Bash",
    "Batch",
    "C",
    "C#",
    "C++",
    "CSS",
    "Go",
    "HTML",
    "INI",
    "Java",
    "JavaScript",
    "JSON",
    "Lua",
    "Markdown",
    "PHP",
    "PowerShell",
    "Python",
    "Rust",
    "SQL",
    "TypeScript",
    "XML",
    "YAML",
]


NPP_PREF_DEFAULTS: dict[str, Any] = {
    "npp_localization": "English",
    "npp_hide_menu_bar": False,
    "npp_hide_menu_right_shortcuts": False,
    "npp_hide_status_bar": False,
    "npp_toolbar_hidden": False,
    "npp_toolbar_icon_style": "fluent_small",
    "npp_toolbar_colorization": "partial",
    "npp_toolbar_color_choice": "system_accent",
    "npp_toolbar_custom_color": "",
    "npp_tabbar_hidden": False,
    "npp_tabbar_vertical": False,
    "npp_tabbar_multiline": False,
    "npp_tabbar_lock_drag_drop": False,
    "npp_tabbar_double_click_close": False,
    "npp_tabbar_exit_on_last_close": False,
    "npp_tabbar_reduce": True,
    "npp_tabbar_alternate_icons": False,
    "npp_tabbar_change_inactive_color": True,
    "npp_tabbar_active_color_bar": True,
    "npp_tabbar_show_close_button": True,
    "npp_tabbar_enable_pin": True,
    "npp_tabbar_show_only_pinned_close": False,
    "npp_tabbar_show_buttons_on_inactive": False,
    "npp_tabbar_max_title_len": 0,
    "npp_current_line_indicator": "highlight_background",
    "npp_enable_smooth_font": False,
    "npp_enable_virtual_space": False,
    "npp_fold_commands_toggleable": False,
    "npp_keep_selection_on_right_click": True,
    "npp_copy_cut_line_without_selection": True,
    "npp_custom_selected_text_fg_enabled": False,
    "npp_scrolling_beyond_last_line": True,
    "npp_disable_advanced_scrolling_touchpad": False,
    "npp_line_wrap_mode": "default",
    "npp_multi_editing_enabled": True,
    "npp_column_selection_multi_editing": True,
    "npp_eol_display_mode": "default",
    "npp_eol_custom_color_enabled": False,
    "npp_eol_custom_color": "",
    "npp_non_printing_appearance": "abbreviation",
    "npp_non_printing_custom_color_enabled": False,
    "npp_non_printing_custom_color": "",
    "npp_apply_non_printing_appearance_to_eol": False,
    "npp_prevent_c0_input": True,
    "npp_dark_mode_preference": "follow_windows",
    "npp_dark_tone_preset": "black",
    "npp_dark_custom_content_bg": "",
    "npp_dark_custom_hottrack": "",
    "npp_dark_custom_control_bg": "",
    "npp_dark_custom_dialog_bg": "",
    "npp_dark_custom_error": "#c00000",
    "npp_margin_fold_style": "arrow",
    "npp_margin_edge_enabled": False,
    "npp_margin_edge_background_mode": False,
    "npp_margin_line_numbers_enabled": True,
    "npp_margin_line_number_width_mode": "dynamic",
    "npp_margin_border_width": 2,
    "npp_margin_no_edge": False,
    "npp_margin_padding_left": 0,
    "npp_margin_padding_right": 0,
    "npp_margin_distraction_free": 4,
    "npp_margin_display_bookmarks": True,
    "npp_new_doc_eol": "windows",
    "npp_new_doc_encoding": "UTF-8",
    "npp_new_doc_apply_to_opened_ansi": True,
    "npp_new_doc_language": "None (Normal Text)",
    "npp_new_doc_open_extra_on_startup": False,
    "npp_new_doc_first_line_as_tab_name": False,
    "npp_default_dir_mode": "remember_last_used",
    "npp_default_dir_path": "",
    "npp_drop_folder_open_all_files": False,
    "npp_recent_dont_check_exists": False,
    "npp_recent_max_entries": 15,
    "npp_recent_in_submenu": True,
    "npp_recent_display_mode": "full_path",
    "npp_recent_custom_max_len": 0,
    "npp_file_assoc_registered": [],
    "npp_file_assoc_custom_supported": [],
    "npp_language_menu_compact": True,
    "npp_language_menu_disabled_items": [],
    "npp_sql_backslash_as_escape": True,
    "npp_indent_scope": "default",
    "npp_indent_size": 4,
    "npp_indent_using": "space",
    "npp_indent_backspace_unindents": True,
    "npp_indent_language_overrides": {},
    "npp_auto_indent_mode": "advanced",
    "npp_highlight_style_all_match_case": False,
    "npp_highlight_style_all_whole_word": True,
    "npp_highlight_matching_tags": True,
    "npp_highlight_tag_attributes": True,
    "npp_highlight_comment_zones": False,
    "npp_smart_highlighting_enabled": True,
    "npp_smart_highlighting_other_view": False,
    "npp_smart_highlighting_match_case": False,
    "npp_smart_highlighting_whole_word": True,
    "npp_smart_highlighting_use_find_settings": False,
    "npp_print_line_numbers": True,
    "npp_print_color_mode": "wysiwyg",
    "npp_print_margin_top_mm": 0,
    "npp_print_margin_left_mm": 0,
    "npp_print_margin_right_mm": 0,
    "npp_print_margin_bottom_mm": 0,
    "npp_print_header_enabled": False,
    "npp_print_footer_enabled": False,
    "npp_print_header_left": "",
    "npp_print_header_center": "",
    "npp_print_header_right": "",
    "npp_print_footer_left": "",
    "npp_print_footer_center": "",
    "npp_print_footer_right": "",
    "npp_find_min_selection_auto_checking": 1024,
    "npp_find_fill_dir_from_active_doc": False,
    "npp_find_fill_with_selected_text": True,
    "npp_find_max_auto_fill_chars": 1024,
    "npp_find_select_word_under_caret": True,
    "npp_find_use_monospace_dialog_font": False,
    "npp_find_stay_open_after_results": False,
    "npp_find_confirm_replace_all_open_docs": True,
    "npp_find_replace_dont_move_next_occurrence": False,
    "npp_search_results_one_entry_per_found_line": True,
    "npp_backup_remember_session_next_launch": True,
    "npp_backup_enable_session_snapshot": True,
    "npp_backup_trigger_seconds": 7,
    "npp_backup_path": "",
    "npp_backup_remember_inaccessible_files": False,
    "npp_backup_on_save_mode": "simple",
    "npp_backup_custom_dir_enabled": False,
    "npp_backup_custom_dir": "",
    "npp_autocomplete_enabled": True,
    "npp_autocomplete_mode": "function_and_word",
    "npp_autocomplete_from_nth_char": 1,
    "npp_autocomplete_insert_tab": True,
    "npp_autocomplete_insert_enter": True,
    "npp_autocomplete_ignore_numbers": True,
    "npp_autocomplete_brief_hint": False,
    "npp_autocomplete_param_hint": True,
    "npp_autoinsert_paren": False,
    "npp_autoinsert_bracket": False,
    "npp_autoinsert_brace": False,
    "npp_autoinsert_quote": False,
    "npp_autoinsert_apostrophe": False,
    "npp_autoinsert_html_xml_close_tag": False,
    "npp_multi_instance_mode": "default",
    "npp_insert_datetime_reverse_order": False,
    "npp_insert_datetime_custom_format": "yyyy-MM-dd HH:mm:ss",
    "npp_panel_state_clipboard_history": False,
    "npp_panel_state_document_list": False,
    "npp_panel_state_character_panel": False,
    "npp_panel_state_folder_as_workspace": False,
    "npp_panel_state_project_panels": False,
    "npp_panel_state_document_map": False,
    "npp_panel_state_function_list": False,
    "npp_panel_state_plugin_panels": False,
    "npp_delimiter_word_chars_mode": "default",
    "npp_delimiter_extra_word_chars": "",
    "npp_delimiter_open": "",
    "npp_delimiter_close": "",
    "npp_delimiter_allow_several_lines": False,
    "npp_large_file_restriction_enabled": True,
    "npp_large_file_size_mb": 200,
    "npp_large_file_disable_word_wrap": True,
    "npp_large_file_allow_autocomplete": False,
    "npp_large_file_allow_smart_highlighting": False,
    "npp_large_file_allow_brace_match": False,
    "npp_large_file_allow_clickable_link": False,
    "npp_large_file_suppress_warn_gt_2gb": False,
    "npp_cloud_mode": "no_cloud",
    "npp_cloud_settings_path": "",
    "npp_clickable_links_enabled": True,
    "npp_clickable_links_no_underline": False,
    "npp_clickable_links_fullbox_mode": False,
    "npp_clickable_link_schemes": "svn:// cvs:// git:// imap:// irc:// ircs:// ldap:// ldaps:// news:// telnet:// gopher:// ssh:// sftp:// ftps:// smb:// skype:// steam:// sms:// slack:// chrome:// bitcoin:",
    "npp_search_engine_provider": "Bing",
    "npp_search_engine_custom_url": "",
    "npp_misc_notes": "",
}


@dataclass(frozen=True)
class _BoolKey:
    key: str
    default: bool


@dataclass(frozen=True)
class _IntKey:
    key: str
    default: int
    min_value: int
    max_value: int


@dataclass(frozen=True)
class _EnumKey:
    key: str
    default: str
    allowed: set[str]


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off", ""}:
            return False
    return default


def _coerce_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        num = int(value)
    except Exception:
        num = default
    return max(min_value, min(max_value, num))


def _coerce_enum(value: Any, default: str, allowed: set[str]) -> str:
    text = str(value or "").strip()
    return text if text in allowed else default


def _coerce_hex(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) not in (4, 7):
        return default
    if not all(ch in "0123456789abcdefABCDEF" for ch in text[1:]):
        return default
    return text


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        out.append(text)
    return out


def _coerce_indent_overrides(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for raw_lang, raw_cfg in value.items():
        lang = str(raw_lang or "").strip().lower()
        if not lang or not isinstance(raw_cfg, dict):
            continue
        size = _coerce_int(raw_cfg.get("size", 4), 4, 1, 16)
        use_tabs = _coerce_bool(raw_cfg.get("use_tabs", False), False)
        auto_indent = _coerce_bool(raw_cfg.get("auto_indent", True), True)
        cleaned[lang] = {
            "size": size,
            "use_tabs": use_tabs,
            "auto_indent": auto_indent,
        }
    return cleaned


_BOOL_KEYS = [
    _BoolKey(k, v)
    for k, v in NPP_PREF_DEFAULTS.items()
    if isinstance(v, bool)
]
_INT_KEYS = [
    _IntKey("npp_tabbar_max_title_len", 0, 0, 300),
    _IntKey("npp_recent_max_entries", 15, 0, 30),
    _IntKey("npp_recent_custom_max_len", 0, 0, 259),
    _IntKey("npp_indent_size", 4, 1, 16),
    _IntKey("npp_find_min_selection_auto_checking", 1024, 32, 100000),
    _IntKey("npp_find_max_auto_fill_chars", 1024, 32, 100000),
    _IntKey("npp_backup_trigger_seconds", 7, 1, 300),
    _IntKey("npp_autocomplete_from_nth_char", 1, 1, 9),
    _IntKey("npp_large_file_size_mb", 200, 1, 2046),
    _IntKey("npp_margin_border_width", 2, 0, 20),
    _IntKey("npp_margin_padding_left", 0, 0, 50),
    _IntKey("npp_margin_padding_right", 0, 0, 50),
    _IntKey("npp_margin_distraction_free", 4, 0, 50),
    _IntKey("npp_print_margin_top_mm", 0, 0, 100),
    _IntKey("npp_print_margin_left_mm", 0, 0, 100),
    _IntKey("npp_print_margin_right_mm", 0, 0, 100),
    _IntKey("npp_print_margin_bottom_mm", 0, 0, 100),
]
_ENUM_KEYS = [
    _EnumKey("npp_toolbar_icon_style", "fluent_small", {"fluent_small", "fluent_large", "filled_fluent_small", "filled_fluent_large", "standard_small"}),
    _EnumKey("npp_toolbar_colorization", "partial", {"complete", "partial"}),
    _EnumKey("npp_toolbar_color_choice", "system_accent", {"default", "system_accent", "custom", "red", "green", "blue", "purple", "cyan", "olive", "yellow"}),
    _EnumKey("npp_current_line_indicator", "highlight_background", {"none", "highlight_background", "frame"}),
    _EnumKey("npp_line_wrap_mode", "default", {"default", "aligned", "indent"}),
    _EnumKey("npp_eol_display_mode", "default", {"default", "plain_text"}),
    _EnumKey("npp_non_printing_appearance", "abbreviation", {"abbreviation", "codepoint"}),
    _EnumKey("npp_dark_mode_preference", "follow_windows", {"light", "dark", "follow_windows"}),
    _EnumKey("npp_dark_tone_preset", "black", {"black", "red", "green", "blue", "purple", "cyan", "olive", "custom"}),
    _EnumKey("npp_margin_fold_style", "arrow", {"simple", "arrow", "circle_tree", "box_tree", "none"}),
    _EnumKey("npp_margin_line_number_width_mode", "dynamic", {"dynamic", "constant"}),
    _EnumKey("npp_new_doc_eol", "windows", {"windows", "unix", "mac"}),
    _EnumKey("npp_new_doc_encoding", "UTF-8", set(ENCODING_CHOICES)),
    _EnumKey("npp_default_dir_mode", "remember_last_used", {"follow_current_document", "remember_last_used", "custom"}),
    _EnumKey("npp_recent_display_mode", "full_path", {"only_file_name", "full_path", "custom_max"}),
    _EnumKey("npp_indent_scope", "default", {"default", "language_specific"}),
    _EnumKey("npp_indent_using", "space", {"tab", "space"}),
    _EnumKey("npp_auto_indent_mode", "advanced", {"none", "basic", "advanced"}),
    _EnumKey("npp_print_color_mode", "wysiwyg", {"wysiwyg", "invert", "black_on_white", "no_background"}),
    _EnumKey("npp_backup_on_save_mode", "simple", {"none", "simple", "verbose"}),
    _EnumKey("npp_autocomplete_mode", "function_and_word", {"function", "word", "function_and_word"}),
    _EnumKey("npp_multi_instance_mode", "default", {"default", "always_multi", "new_instance_and_save_session"}),
    _EnumKey("npp_delimiter_word_chars_mode", "default", {"default", "custom"}),
    _EnumKey("npp_cloud_mode", "no_cloud", {"no_cloud", "custom_path"}),
    _EnumKey("npp_search_engine_provider", "Bing", set(SEARCH_ENGINE_PRESETS.keys())),
]


def coerce_notepadpp_prefs(settings: dict) -> dict:
    current = dict(settings)
    for key, default in NPP_PREF_DEFAULTS.items():
        current.setdefault(key, default)

    for spec in _BOOL_KEYS:
        current[spec.key] = _coerce_bool(current.get(spec.key, spec.default), spec.default)

    for spec in _INT_KEYS:
        current[spec.key] = _coerce_int(current.get(spec.key, spec.default), spec.default, spec.min_value, spec.max_value)

    for spec in _ENUM_KEYS:
        current[spec.key] = _coerce_enum(current.get(spec.key, spec.default), spec.default, spec.allowed)

    for key in (
        "npp_toolbar_custom_color",
        "npp_eol_custom_color",
        "npp_non_printing_custom_color",
        "npp_dark_custom_content_bg",
        "npp_dark_custom_hottrack",
        "npp_dark_custom_control_bg",
        "npp_dark_custom_dialog_bg",
        "npp_dark_custom_error",
    ):
        current[key] = _coerce_hex(current.get(key, ""), "")

    for key in (
        "npp_localization",
        "npp_new_doc_language",
        "npp_default_dir_path",
        "npp_backup_path",
        "npp_backup_custom_dir",
        "npp_cloud_settings_path",
        "npp_search_engine_custom_url",
        "npp_clickable_link_schemes",
        "npp_insert_datetime_custom_format",
        "npp_delimiter_extra_word_chars",
        "npp_delimiter_open",
        "npp_delimiter_close",
        "npp_misc_notes",
    ):
        current[key] = str(current.get(key, "") or "").strip()

    current["npp_language_menu_disabled_items"] = _coerce_string_list(current.get("npp_language_menu_disabled_items", []))
    current["npp_file_assoc_registered"] = _coerce_string_list(current.get("npp_file_assoc_registered", []))
    current["npp_file_assoc_custom_supported"] = _coerce_string_list(current.get("npp_file_assoc_custom_supported", []))
    current["npp_indent_language_overrides"] = _coerce_indent_overrides(current.get("npp_indent_language_overrides", {}))

    return current
