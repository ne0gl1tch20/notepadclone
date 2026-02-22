from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget

from ...app_settings.notepadpp_prefs import SEARCH_ENGINE_PRESETS


def _shorten_middle(text: str, max_len: int) -> str:
    if max_len <= 0 or len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    if max_len <= 4:
        return text[: max_len - 3] + "..."
    left = (max_len - 3) // 2
    right = max_len - 3 - left
    return f"{text[:left]}...{text[-right:]}"


def recent_file_menu_label(settings: dict, path: str) -> str:
    display_mode = str(settings.get("npp_recent_display_mode", "full_path") or "full_path")
    if display_mode == "only_file_name":
        label = Path(path).name or path
    else:
        label = path
    if display_mode == "custom_max":
        max_len = int(settings.get("npp_recent_custom_max_len", 0) or 0)
        label = _shorten_middle(label, max_len)
    return label


def recent_file_max_entries(settings: dict) -> int:
    try:
        value = int(settings.get("npp_recent_max_entries", 15))
    except Exception:
        value = 15
    return max(0, min(30, value))


def build_search_internet_url(settings: dict, query: str) -> str:
    provider = str(settings.get("npp_search_engine_provider", "Bing") or "Bing")
    template = ""
    if provider == "Custom":
        template = str(settings.get("npp_search_engine_custom_url", "") or "").strip()
    else:
        template = str(SEARCH_ENGINE_PRESETS.get(provider, SEARCH_ENGINE_PRESETS["Bing"]))
    if not template:
        template = SEARCH_ENGINE_PRESETS["Bing"]
    if "$(CURRENT_WORD)" not in template:
        sep = "&" if "?" in template else "?"
        template = f"{template}{sep}q=$(CURRENT_WORD)"
    return template.replace("$(CURRENT_WORD)", quote_plus(query))


def allowed_clickable_schemes(settings: dict) -> set[str]:
    if not bool(settings.get("npp_clickable_links_enabled", True)):
        return set()
    raw = str(settings.get("npp_clickable_link_schemes", "") or "")
    schemes: set[str] = set()
    for token in raw.replace("\n", " ").split():
        item = token.strip().rstrip("/")
        if "://" in item:
            item = item.split("://", 1)[0]
        item = item.rstrip(":").strip().lower()
        if item:
            schemes.add(item)
    schemes.update({"http", "https", "file", "mailto"})
    return schemes


def is_clickable_scheme_allowed(settings: dict, url: str) -> bool:
    text = str(url or "").strip()
    if not text:
        return False
    if text.startswith("pypad://"):
        return True
    if "://" not in text and not text.lower().startswith("mailto:"):
        return True
    scheme = text.split(":", 1)[0].strip().lower()
    return scheme in allowed_clickable_schemes(settings)


def apply_notepadpp_runtime_settings(window) -> None:
    settings = getattr(window, "settings", {}) or {}

    toolbar_hidden = bool(settings.get("npp_toolbar_hidden", False))
    if hasattr(window, "main_toolbar") and window.main_toolbar is not None:
        window.main_toolbar.setVisible(not toolbar_hidden and bool(settings.get("show_main_toolbar", True)))

    try:
        menu_bar = window.menuBar()
    except Exception:
        menu_bar = None
    if menu_bar is not None:
        focus_active = bool(getattr(window, "focus_mode_action", None) and window.focus_mode_action.isChecked())
        if not focus_active:
            menu_bar.setVisible(not bool(settings.get("npp_hide_menu_bar", False)))

    status_bar = None
    if hasattr(window, "statusBar"):
        try:
            status_bar = window.statusBar()
        except Exception:
            status_bar = None
    if status_bar is None and hasattr(window, "status"):
        status_bar = getattr(window, "status", None)
    if status_bar is not None:
        status_bar.setVisible(not bool(settings.get("npp_hide_status_bar", False)))

    tab_widget = getattr(window, "tab_widget", None)
    if tab_widget is not None:
        tab_bar = tab_widget.tabBar()
        tab_bar.setVisible(not bool(settings.get("npp_tabbar_hidden", False)))
        tab_bar.setMovable(not bool(settings.get("npp_tabbar_lock_drag_drop", False)))
        tab_widget.setMovable(not bool(settings.get("npp_tabbar_lock_drag_drop", False)))
        tab_widget.setTabsClosable(bool(settings.get("npp_tabbar_show_close_button", True)))
        tab_bar.setUsesScrollButtons(not bool(settings.get("npp_tabbar_multiline", False)))
        if hasattr(tab_bar, "setExpanding"):
            tab_bar.setExpanding(not bool(settings.get("npp_tabbar_reduce", True)))
        vertical = bool(settings.get("npp_tabbar_vertical", False))
        tab_widget.setTabPosition(QTabWidget.TabPosition.West if vertical else QTabWidget.TabPosition.North)
        max_title_len = int(settings.get("npp_tabbar_max_title_len", 0) or 0)
        if max_title_len > 0 and hasattr(window, "_refresh_tab_title"):
            for i in range(tab_widget.count()):
                tab = tab_widget.widget(i)
                try:
                    # Let native refresh logic run first, then clamp display text.
                    window._refresh_tab_title(tab)
                    title = tab_widget.tabText(i)
                    tab_widget.setTabText(i, _shorten_middle(title, max_title_len))
                except Exception:
                    continue

    recent_files = [p for p in settings.get("recent_files", []) if isinstance(p, str) and p]
    limit = recent_file_max_entries(settings)
    if len(recent_files) > limit:
        settings["recent_files"] = recent_files[:limit]


def _npp_encoding_to_app_encoding(value: str) -> str:
    text = str(value or "").strip().lower()
    mapping = {
        "ansi": "cp1252",
        "utf-8": "utf-8",
        "utf-8 with bom": "utf-8-sig",
        "utf-16 le": "utf-16-le",
        "utf-16 be": "utf-16-be",
        "windows-1252": "cp1252",
        "windows-1251": "cp1251",
        "iso-8859-1": "iso-8859-1",
        "oem 437": "cp437",
        "oem 850": "cp850",
    }
    return mapping.get(text, "utf-8")


def _npp_eol_to_app_eol(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "windows":
        return "CRLF"
    if text == "mac":
        return "LF"
    return "LF"


def new_document_defaults(settings: dict) -> dict[str, Any]:
    return {
        "encoding": _npp_encoding_to_app_encoding(str(settings.get("npp_new_doc_encoding", "UTF-8"))),
        "eol_mode": _npp_eol_to_app_eol(str(settings.get("npp_new_doc_eol", "windows"))),
        "language": str(settings.get("npp_new_doc_language", "None (Normal Text)") or "None (Normal Text)"),
    }


def _indent_defaults_for_language(settings: dict, language_hint: str | None) -> tuple[int, bool, bool]:
    lang = str(language_hint or "").strip().lower()
    width = int(settings.get("npp_indent_size", settings.get("tab_width", 4)) or 4)
    use_tabs = str(settings.get("npp_indent_using", "space")) == "tab"
    auto_indent = str(settings.get("npp_auto_indent_mode", "advanced")) != "none"
    scope = str(settings.get("npp_indent_scope", "default") or "default")
    raw_overrides = settings.get("npp_indent_language_overrides", {})
    if isinstance(raw_overrides, dict) and lang:
        candidates = [lang]
        if "(" in lang:
            candidates.append(lang.split("(", 1)[0].strip())
        if "/" in lang:
            candidates.extend([part.strip() for part in lang.split("/") if part.strip()])
        for key in candidates:
            cfg = raw_overrides.get(str(key).lower())
            if isinstance(cfg, dict):
                try:
                    width = int(cfg.get("size", width) or width)
                except Exception:
                    pass
                use_tabs = bool(cfg.get("use_tabs", use_tabs))
                auto_indent = bool(cfg.get("auto_indent", auto_indent))
                return max(1, min(16, width)), bool(use_tabs), bool(auto_indent)
    if scope == "language_specific" and lang:
        if any(x in lang for x in ("python", "yaml")):
            width, use_tabs = 4, False
        elif any(x in lang for x in ("go", "makefile")):
            width, use_tabs = 4, True
        elif any(x in lang for x in ("json", "javascript", "typescript", "css", "html", "xml", "markdown")):
            width, use_tabs = 2, False
    return max(1, min(16, width)), bool(use_tabs), bool(auto_indent)


def apply_indentation_defaults_to_tab(window, tab, *, language_hint: str | None = None) -> None:
    settings = getattr(window, "settings", {}) or {}
    hint = language_hint
    if not hint:
        hint = getattr(tab, "syntax_language_override", None)
    if not hint and getattr(tab, "current_file", None):
        suffix = Path(str(tab.current_file)).suffix.lower()
        hint = {
            ".py": "python",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".go": "go",
            ".js": "javascript",
            ".ts": "typescript",
            ".json": "json",
            ".css": "css",
            ".html": "html",
            ".xml": "xml",
            ".md": "markdown",
        }.get(suffix, "")
    if not hint:
        hint = new_document_defaults(settings).get("language", "")
    width, use_tabs, auto_indent = _indent_defaults_for_language(settings, str(hint))
    settings["tab_width"] = width
    settings["insert_spaces"] = not use_tabs
    settings["auto_indent"] = auto_indent
    editor = getattr(tab, "text_edit", None)
    if editor is not None and hasattr(editor, "configure_indentation"):
        try:
            editor.configure_indentation(tab_width=width, use_tabs=use_tabs)
        except Exception:
            pass


def _render_print_template_part(part: str, tab) -> str:
    text = str(part or "")
    if not text:
        return ""
    file_path = str(getattr(tab, "current_file", "") or "")
    file_name = Path(file_path).name if file_path else "Untitled"
    replacements = {
        "$(FULL_FILE_PATH)": file_path or "Untitled",
        "$(FILE_NAME)": file_name,
        "$(CURRENT_DATE)": datetime.now().strftime("%Y-%m-%d"),
        "$(CURRENT_TIME)": datetime.now().strftime("%H:%M:%S"),
    }
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def apply_npp_print_preferences_to_page_layout(settings: dict, tab, page_cfg) -> None:
    if bool(settings.get("npp_print_header_enabled", False)):
        header_parts = [
            _render_print_template_part(settings.get("npp_print_header_left", ""), tab),
            _render_print_template_part(settings.get("npp_print_header_center", ""), tab),
            _render_print_template_part(settings.get("npp_print_header_right", ""), tab),
        ]
        page_cfg.header_text = " | ".join([p for p in header_parts if p]).strip()
    if bool(settings.get("npp_print_footer_enabled", False)):
        footer_parts = [
            _render_print_template_part(settings.get("npp_print_footer_left", ""), tab),
            _render_print_template_part(settings.get("npp_print_footer_center", ""), tab),
            _render_print_template_part(settings.get("npp_print_footer_right", ""), tab),
        ]
        page_cfg.footer_text = " | ".join([p for p in footer_parts if p]).strip()
    # PageLayoutConfig enforces >=5 in from_settings; only override when user set >0 values.
    for key, attr in (
        ("npp_print_margin_left_mm", "margin_left_mm"),
        ("npp_print_margin_top_mm", "margin_top_mm"),
        ("npp_print_margin_right_mm", "margin_right_mm"),
        ("npp_print_margin_bottom_mm", "margin_bottom_mm"),
    ):
        try:
            value = int(settings.get(key, 0) or 0)
        except Exception:
            value = 0
        if value > 0:
            setattr(page_cfg, attr, max(5, value))
