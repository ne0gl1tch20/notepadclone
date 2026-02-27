from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

STYLE_LANGUAGES: tuple[str, ...] = ("python", "javascript", "json", "markdown", "plain")
STYLE_TOKENS: tuple[str, ...] = ("keyword", "string", "comment", "number")
STYLE_THEMES: tuple[str, ...] = ("default", "high_contrast", "solarized_light")


def _normalize_hex(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return None
    return text.lower()


def _sanitize_style_overrides(raw: Any) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    if not isinstance(raw, dict):
        return out
    for lang, payload in raw.items():
        language = str(lang or "").strip().lower()
        if language not in STYLE_LANGUAGES or not isinstance(payload, dict):
            continue
        token_map: dict[str, str] = {}
        for token, color in payload.items():
            token_key = str(token or "").strip().lower()
            if token_key not in STYLE_TOKENS:
                continue
            normalized = _normalize_hex(color)
            if normalized:
                token_map[token_key] = normalized
        if token_map:
            out[language] = token_map
    return out


@dataclass(slots=True)
class ScintillaProfile:
    wrap_mode: str = "word"
    auto_completion_mode: str = "all"
    auto_completion_threshold: int = 1
    tab_width: int = 4
    use_tabs: bool = False
    auto_indent: bool = True
    trim_trailing_whitespace_on_save: bool = False
    column_mode: bool = False
    multi_caret: bool = False
    code_folding: bool = True
    show_space_tab: bool = False
    show_eol: bool = False
    show_non_printing: bool = False
    show_control_chars: bool = False
    show_all_chars: bool = False
    show_indent_guides: bool = True
    show_wrap_symbol: bool = False
    line_numbers_visible: bool = True
    margin_left_px: int = 8
    margin_right_px: int = 4
    line_number_width_mode: str = "dynamic"
    line_number_width_px: int = 48
    caret_width_px: int = 1
    highlight_current_line: bool = True
    style_theme: str = "default"
    style_overrides: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "ScintillaProfile":
        s = settings if isinstance(settings, dict) else {}
        return cls(
            wrap_mode=str(s.get("scintilla_wrap_mode", "word") or "word"),
            auto_completion_mode=str(s.get("auto_completion_mode", "all") or "all"),
            auto_completion_threshold=int(s.get("scintilla_auto_completion_threshold", 1) or 1),
            tab_width=int(s.get("tab_width", 4) or 4),
            use_tabs=bool(s.get("scintilla_use_tabs", not bool(s.get("insert_spaces", True)))),
            auto_indent=bool(s.get("auto_indent", True)),
            trim_trailing_whitespace_on_save=bool(s.get("trim_trailing_whitespace_on_save", False)),
            column_mode=bool(s.get("scintilla_column_mode", False)),
            multi_caret=bool(s.get("scintilla_multi_caret", False)),
            code_folding=bool(s.get("scintilla_code_folding", True)),
            show_space_tab=bool(s.get("show_symbol_space_tab", False)),
            show_eol=bool(s.get("show_symbol_eol", False)),
            show_non_printing=bool(s.get("show_symbol_non_printing", False)),
            show_control_chars=bool(s.get("show_symbol_control_chars", False)),
            show_all_chars=bool(s.get("show_symbol_all_chars", False)),
            show_indent_guides=bool(s.get("show_symbol_indent_guide", True)),
            show_wrap_symbol=bool(s.get("show_symbol_wrap_symbol", False)),
            line_numbers_visible=bool(s.get("npp_margin_line_numbers_enabled", True)),
            margin_left_px=int(s.get("scintilla_margin_left_px", 8) or 8),
            margin_right_px=int(s.get("scintilla_margin_right_px", 4) or 4),
            line_number_width_mode=str(s.get("scintilla_line_number_width_mode", "dynamic") or "dynamic"),
            line_number_width_px=int(s.get("scintilla_line_number_width_px", 48) or 48),
            caret_width_px=int(s.get("caret_width_px", 1) or 1),
            highlight_current_line=bool(s.get("highlight_current_line", True)),
            style_theme=str(s.get("scintilla_style_theme", "default") or "default"),
            style_overrides=_sanitize_style_overrides(s.get("scintilla_style_overrides", {})),
        ).sanitized()

    def sanitized(self) -> "ScintillaProfile":
        mode = self.wrap_mode.strip().lower()
        if mode not in {"word", "none"}:
            mode = "word"
        ac_mode = self.auto_completion_mode.strip().lower()
        if ac_mode not in {"none", "off", "all", "document", "doc", "apis", "api", "open_docs"}:
            ac_mode = "all"
        ln_mode = self.line_number_width_mode.strip().lower()
        if ln_mode not in {"dynamic", "constant"}:
            ln_mode = "dynamic"
        style_theme = self.style_theme.strip().lower()
        if style_theme not in STYLE_THEMES:
            style_theme = "default"
        return ScintillaProfile(
            wrap_mode=mode,
            auto_completion_mode=ac_mode,
            auto_completion_threshold=max(1, min(12, int(self.auto_completion_threshold))),
            tab_width=max(1, min(16, int(self.tab_width))),
            use_tabs=bool(self.use_tabs),
            auto_indent=bool(self.auto_indent),
            trim_trailing_whitespace_on_save=bool(self.trim_trailing_whitespace_on_save),
            column_mode=bool(self.column_mode),
            multi_caret=bool(self.multi_caret),
            code_folding=bool(self.code_folding),
            show_space_tab=bool(self.show_space_tab),
            show_eol=bool(self.show_eol),
            show_non_printing=bool(self.show_non_printing),
            show_control_chars=bool(self.show_control_chars),
            show_all_chars=bool(self.show_all_chars),
            show_indent_guides=bool(self.show_indent_guides),
            show_wrap_symbol=bool(self.show_wrap_symbol),
            line_numbers_visible=bool(self.line_numbers_visible),
            margin_left_px=max(0, min(64, int(self.margin_left_px))),
            margin_right_px=max(0, min(64, int(self.margin_right_px))),
            line_number_width_mode=ln_mode,
            line_number_width_px=max(24, min(160, int(self.line_number_width_px))),
            caret_width_px=max(1, min(6, int(self.caret_width_px))),
            highlight_current_line=bool(self.highlight_current_line),
            style_theme=style_theme,
            style_overrides=_sanitize_style_overrides(self.style_overrides),
        )

    def apply_to_settings(self, settings: dict[str, Any]) -> None:
        s = settings if isinstance(settings, dict) else {}
        clean = self.sanitized()
        s["scintilla_wrap_mode"] = clean.wrap_mode
        s["word_wrap"] = clean.wrap_mode == "word"
        s["auto_completion_mode"] = clean.auto_completion_mode
        s["scintilla_auto_completion_threshold"] = int(clean.auto_completion_threshold)
        s["tab_width"] = int(clean.tab_width)
        s["scintilla_use_tabs"] = bool(clean.use_tabs)
        s["insert_spaces"] = not bool(clean.use_tabs)
        s["auto_indent"] = bool(clean.auto_indent)
        s["trim_trailing_whitespace_on_save"] = bool(clean.trim_trailing_whitespace_on_save)
        s["scintilla_column_mode"] = bool(clean.column_mode)
        s["scintilla_multi_caret"] = bool(clean.multi_caret)
        s["scintilla_code_folding"] = bool(clean.code_folding)
        s["show_symbol_space_tab"] = bool(clean.show_space_tab)
        s["show_symbol_eol"] = bool(clean.show_eol)
        s["show_symbol_non_printing"] = bool(clean.show_non_printing)
        s["show_symbol_control_chars"] = bool(clean.show_control_chars)
        s["show_symbol_all_chars"] = bool(clean.show_all_chars)
        s["show_symbol_indent_guide"] = bool(clean.show_indent_guides)
        s["show_symbol_wrap_symbol"] = bool(clean.show_wrap_symbol)
        s["npp_margin_line_numbers_enabled"] = bool(clean.line_numbers_visible)
        s["scintilla_margin_left_px"] = int(clean.margin_left_px)
        s["scintilla_margin_right_px"] = int(clean.margin_right_px)
        s["scintilla_line_number_width_mode"] = clean.line_number_width_mode
        s["scintilla_line_number_width_px"] = int(clean.line_number_width_px)
        s["caret_width_px"] = int(clean.caret_width_px)
        s["highlight_current_line"] = bool(clean.highlight_current_line)
        s["scintilla_style_theme"] = clean.style_theme
        s["scintilla_style_overrides"] = dict(clean.style_overrides)

    def to_json_dict(self) -> dict[str, Any]:
        clean = self.sanitized()
        return {
            "wrap_mode": clean.wrap_mode,
            "auto_completion_mode": clean.auto_completion_mode,
            "auto_completion_threshold": int(clean.auto_completion_threshold),
            "tab_width": int(clean.tab_width),
            "use_tabs": bool(clean.use_tabs),
            "auto_indent": bool(clean.auto_indent),
            "trim_trailing_whitespace_on_save": bool(clean.trim_trailing_whitespace_on_save),
            "column_mode": bool(clean.column_mode),
            "multi_caret": bool(clean.multi_caret),
            "code_folding": bool(clean.code_folding),
            "show_space_tab": bool(clean.show_space_tab),
            "show_eol": bool(clean.show_eol),
            "show_non_printing": bool(clean.show_non_printing),
            "show_control_chars": bool(clean.show_control_chars),
            "show_all_chars": bool(clean.show_all_chars),
            "show_indent_guides": bool(clean.show_indent_guides),
            "show_wrap_symbol": bool(clean.show_wrap_symbol),
            "line_numbers_visible": bool(clean.line_numbers_visible),
            "margin_left_px": int(clean.margin_left_px),
            "margin_right_px": int(clean.margin_right_px),
            "line_number_width_mode": clean.line_number_width_mode,
            "line_number_width_px": int(clean.line_number_width_px),
            "caret_width_px": int(clean.caret_width_px),
            "highlight_current_line": bool(clean.highlight_current_line),
            "style_theme": clean.style_theme,
            "style_overrides": dict(clean.style_overrides),
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "ScintillaProfile":
        p = payload if isinstance(payload, dict) else {}
        return cls(
            wrap_mode=str(p.get("wrap_mode", "word") or "word"),
            auto_completion_mode=str(p.get("auto_completion_mode", "all") or "all"),
            auto_completion_threshold=int(p.get("auto_completion_threshold", 1) or 1),
            tab_width=int(p.get("tab_width", 4) or 4),
            use_tabs=bool(p.get("use_tabs", False)),
            auto_indent=bool(p.get("auto_indent", True)),
            trim_trailing_whitespace_on_save=bool(p.get("trim_trailing_whitespace_on_save", False)),
            column_mode=bool(p.get("column_mode", False)),
            multi_caret=bool(p.get("multi_caret", False)),
            code_folding=bool(p.get("code_folding", True)),
            show_space_tab=bool(p.get("show_space_tab", False)),
            show_eol=bool(p.get("show_eol", False)),
            show_non_printing=bool(p.get("show_non_printing", False)),
            show_control_chars=bool(p.get("show_control_chars", False)),
            show_all_chars=bool(p.get("show_all_chars", False)),
            show_indent_guides=bool(p.get("show_indent_guides", True)),
            show_wrap_symbol=bool(p.get("show_wrap_symbol", False)),
            line_numbers_visible=bool(p.get("line_numbers_visible", True)),
            margin_left_px=int(p.get("margin_left_px", 8) or 8),
            margin_right_px=int(p.get("margin_right_px", 4) or 4),
            line_number_width_mode=str(p.get("line_number_width_mode", "dynamic") or "dynamic"),
            line_number_width_px=int(p.get("line_number_width_px", 48) or 48),
            caret_width_px=int(p.get("caret_width_px", 1) or 1),
            highlight_current_line=bool(p.get("highlight_current_line", True)),
            style_theme=str(p.get("style_theme", "default") or "default"),
            style_overrides=_sanitize_style_overrides(p.get("style_overrides", {})),
        ).sanitized()
