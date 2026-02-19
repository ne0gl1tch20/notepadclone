from __future__ import annotations

from urllib.parse import urlsplit

from .defaults import build_default_settings

def coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


def normalize_ui_visibility_settings(settings: dict) -> dict:
    settings["show_markdown_toolbar"] = coerce_bool(
        settings.get("show_markdown_toolbar", False),
        default=False,
    )
    settings["show_find_panel"] = coerce_bool(
        settings.get("show_find_panel", False),
        default=False,
    )
    return settings


def _coerce_enum(value: object, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def _coerce_int_clamped(value: object, default: int, min_value: int, max_value: int) -> int:
    try:
        num = int(value)  # type: ignore[arg-type]
    except Exception:
        num = default
    return max(min_value, min(max_value, num))


def _coerce_hex(value: object, default: str) -> str:
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


def _sanitize_update_feed_url(value: object, default: str) -> str:
    raw = str(value or "").strip() or default
    if "neogl1tch20server" in raw or raw.endswith("/updates/notepad.xml"):
        raw = default
    try:
        parts = urlsplit(raw)
    except Exception:
        return default
    if not parts.scheme or not parts.netloc:
        return default
    return raw


def migrate_settings(settings: dict) -> dict:
    current = dict(settings)
    defaults = build_default_settings(default_style="Windows", font_family="Segoe UI", font_size=11)
    schema = _coerce_int_clamped(current.get("settings_schema_version", 1), 1, 1, 999)
    if schema >= 2:
        current["save_debug_logs_to_appdata"] = coerce_bool(current.get("save_debug_logs_to_appdata", False), False)
        current["backup_output_dir"] = str(current.get("backup_output_dir", "") or "").strip()
        current["update_feed_url"] = _sanitize_update_feed_url(current.get("update_feed_url"), defaults.get("update_feed_url", ""))
        normalize_ui_visibility_settings(current)
        return current

    for key, value in defaults.items():
        current.setdefault(key, value)

    current["show_main_toolbar"] = coerce_bool(current.get("show_main_toolbar", True), True)
    current["show_markdown_toolbar"] = coerce_bool(current.get("show_markdown_toolbar", False), False)
    current["show_find_panel"] = coerce_bool(current.get("show_find_panel", False), False)
    current["ui_density"] = _coerce_enum(current.get("ui_density"), {"compact", "comfortable"}, "comfortable")
    current["icon_size_px"] = _coerce_int_clamped(current.get("icon_size_px", 18), 18, 16, 24)
    current["toolbar_label_mode"] = _coerce_enum(
        current.get("toolbar_label_mode"),
        {"icons_only", "text_only", "icons_text"},
        "icons_only",
    )

    current["tab_width"] = _coerce_int_clamped(current.get("tab_width", 4), 4, 2, 8)
    current["insert_spaces"] = coerce_bool(current.get("insert_spaces", True), True)
    current["auto_indent"] = coerce_bool(current.get("auto_indent", True), True)
    current["trim_trailing_whitespace_on_save"] = coerce_bool(
        current.get("trim_trailing_whitespace_on_save", False), False
    )
    current["caret_width_px"] = _coerce_int_clamped(current.get("caret_width_px", 1), 1, 1, 4)
    current["highlight_current_line"] = coerce_bool(current.get("highlight_current_line", True), True)

    current["tab_close_button_mode"] = _coerce_enum(current.get("tab_close_button_mode"), {"always", "hover"}, "always")
    current["tab_elide_mode"] = _coerce_enum(current.get("tab_elide_mode"), {"right", "middle", "none"}, "right")
    current["tab_min_width_px"] = _coerce_int_clamped(current.get("tab_min_width_px", 120), 120, 80, 220)
    current["tab_max_width_px"] = _coerce_int_clamped(current.get("tab_max_width_px", 240), 240, 120, 420)
    current["tab_double_click_action"] = _coerce_enum(
        current.get("tab_double_click_action"),
        {"new_tab", "rename", "none"},
        "new_tab",
    )

    current["workspace_show_hidden_files"] = coerce_bool(current.get("workspace_show_hidden_files", False), False)
    current["workspace_follow_symlinks"] = coerce_bool(current.get("workspace_follow_symlinks", False), False)
    current["workspace_max_scan_files"] = _coerce_int_clamped(
        current.get("workspace_max_scan_files", 25000), 25000, 1000, 200000
    )

    current["search_default_match_case"] = coerce_bool(current.get("search_default_match_case", False), False)
    current["search_default_whole_word"] = coerce_bool(current.get("search_default_whole_word", False), False)
    current["search_default_regex"] = coerce_bool(current.get("search_default_regex", False), False)
    current["search_highlight_color"] = _coerce_hex(current.get("search_highlight_color", "#4a90e2"), "#4a90e2")
    current["search_max_highlights"] = _coerce_int_clamped(current.get("search_max_highlights", 2000), 2000, 100, 10000)

    current["shortcut_profile"] = _coerce_enum(current.get("shortcut_profile"), {"default", "vscode"}, "vscode")
    current["shortcut_conflict_policy"] = _coerce_enum(
        current.get("shortcut_conflict_policy"),
        {"warn", "block", "allow"},
        "warn",
    )
    current["shortcut_show_unassigned"] = coerce_bool(current.get("shortcut_show_unassigned", True), True)
    raw_map = current.get("shortcut_map", {})
    cleaned_map: dict[str, str | list[str]] = {}
    if isinstance(raw_map, dict):
        for key, value in raw_map.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if isinstance(value, str):
                cleaned_map[key] = value.strip()
            elif isinstance(value, list):
                seqs = [str(v).strip() for v in value if str(v).strip()]
                cleaned_map[key] = seqs
    current["shortcut_map"] = cleaned_map

    current["ai_send_redact_emails"] = coerce_bool(current.get("ai_send_redact_emails", False), False)
    current["ai_send_redact_paths"] = coerce_bool(current.get("ai_send_redact_paths", False), False)
    current["ai_send_redact_tokens"] = coerce_bool(current.get("ai_send_redact_tokens", True), True)
    current["ai_key_storage_mode"] = _coerce_enum(current.get("ai_key_storage_mode"), {"settings", "env_only"}, "settings")
    current["update_feed_url"] = _sanitize_update_feed_url(current.get("update_feed_url"), defaults.get("update_feed_url", ""))

    current["recovery_mode"] = _coerce_enum(
        current.get("recovery_mode"),
        {"ask", "auto_restore", "auto_discard"},
        "ask",
    )
    current["recovery_discard_after_days"] = _coerce_int_clamped(
        current.get("recovery_discard_after_days", 14),
        14,
        1,
        90,
    )
    current["debug_telemetry_enabled"] = coerce_bool(current.get("debug_telemetry_enabled", False), False)
    current["save_debug_logs_to_appdata"] = coerce_bool(current.get("save_debug_logs_to_appdata", False), False)
    current["backup_output_dir"] = str(current.get("backup_output_dir", "") or "").strip()
    current["settings_schema_version"] = 2

    normalize_ui_visibility_settings(current)
    return current
