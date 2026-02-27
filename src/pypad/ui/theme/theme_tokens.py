from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


def _normalize_hex(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) not in (4, 7):
        return fallback
    chars = text[1:]
    if len(text) == 4:
        chars = "".join(ch * 2 for ch in chars)
    if not all(ch in "0123456789abcdefABCDEF" for ch in chars):
        return fallback
    return f"#{chars.lower()}"


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = _normalize_hex(value, "#000000")
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    t = max(0.0, min(1.0, float(t)))
    return _rgb_to_hex(
        int(round(ar + (br - ar) * t)),
        int(round(ag + (bg - ag) * t)),
        int(round(ab + (bb - ab) * t)),
    )


def _lighten(color: str, amount: float) -> str:
    return _mix(color, "#ffffff", amount)


def _darken(color: str, amount: float) -> str:
    return _mix(color, "#000000", amount)


def _relative_luma(color: str) -> float:
    r, g, b = _hex_to_rgb(color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _contrast_fg(bg: str, *, dark: str = "#111111", light: str = "#ffffff", threshold: float = 0.58) -> str:
    return dark if _relative_luma(bg) >= threshold else light


@dataclass(frozen=True)
class UIThemeTokens:
    dark_mode: bool
    theme_name: str
    density: str
    accent: str
    text: str
    text_muted: str
    text_on_accent: str
    window_bg: str
    editor_bg: str
    chrome_bg: str
    panel_bg: str
    surface_bg: str
    input_bg: str
    button_bg: str
    border: str
    border_soft: str
    border_strong: str
    selection_bg: str
    selection_fg: str
    toolbar_hover_bg: str
    toolbar_checked_bg: str
    toolbar_checked_hover_bg: str
    tab_hover_bg: str
    dock_button_bg: str
    dock_button_hover_bg: str
    dock_button_pressed_bg: str
    scrollbar_track: str
    scrollbar_handle: str
    scrollbar_hover: str
    radius_sm: int
    radius_md: int
    radius_lg: int
    radius_xl: int
    space_xs: int
    space_sm: int
    space_md: int
    space_lg: int
    toolbar_pad_v: int
    toolbar_pad_h: int
    input_height: int
    tab_min_height: int
    icon_fg: str


def build_tokens_from_settings(settings: dict[str, Any]) -> UIThemeTokens:
    s = settings if isinstance(settings, dict) else {}
    dark = bool(s.get("dark_mode", False))
    theme = str(s.get("theme", "Default") or "Default")
    density = str(s.get("ui_density", "comfortable") or "comfortable").lower()
    accent = _normalize_hex(s.get("accent_color", "#4a90e2"), "#4a90e2")

    palette_map = {
        "Default": {"window_bg": "#ffffff", "text": "#111111", "chrome_bg": "#f0f2f5"},
        "Soft Light": {"window_bg": "#f6f7fb", "text": "#1f2630", "chrome_bg": "#e8ecf3"},
        "High Contrast": {"window_bg": "#000000", "text": "#ffffff", "chrome_bg": "#000000"},
        "Solarized Light": {"window_bg": "#fdf6e3", "text": "#586e75", "chrome_bg": "#eee8d5"},
        "Ocean Blue": {"window_bg": "#eaf4ff", "text": "#10324a", "chrome_bg": "#dcecff"},
    }

    if dark:
        window_bg = "#1d2127"
        text = "#e8edf3"
        chrome_bg = "#252b33"
        panel_bg = "#20262d"
        surface_bg = "#1a2026"
        input_bg = "#161c22"
        button_bg = "#2a313a"
        border = "#3a4450"
        border_soft = "#2f3842"
        border_strong = "#4b5866"
        text_muted = "#9dadbf"
        selection_bg = _mix(accent, "#ffffff", 0.18)
        selection_fg = "#ffffff"
        scrollbar_track = "#1c2228"
        scrollbar_handle = "#516070"
        scrollbar_hover = "#647588"
        toolbar_checked_bg = _mix(chrome_bg, accent, 0.16)
        toolbar_checked_hover_bg = _mix(chrome_bg, accent, 0.24)
        tab_hover_bg = _lighten(chrome_bg, 0.08)
        dock_button_bg = _lighten(chrome_bg, 0.05)
        dock_button_hover_bg = _lighten(chrome_bg, 0.09)
        dock_button_pressed_bg = _darken(chrome_bg, 0.06)
    else:
        base = palette_map.get(theme, palette_map["Default"])
        window_bg = base["window_bg"]
        text = base["text"]
        chrome_bg = base["chrome_bg"]
        panel_bg = _mix(chrome_bg, "#ffffff", 0.38)
        surface_bg = "#ffffff"
        input_bg = "#ffffff"
        button_bg = _mix(chrome_bg, "#ffffff", 0.25)
        border = _mix(chrome_bg, "#7e8b99", 0.45)
        border_soft = _mix(chrome_bg, "#ffffff", 0.18)
        border_strong = _mix(chrome_bg, "#667484", 0.55)
        text_muted = _mix(text, "#ffffff", 0.55)
        selection_bg = _mix(accent, "#ffffff", 0.68)
        selection_fg = _contrast_fg(selection_bg)
        scrollbar_track = _mix(window_bg, "#d8dee8", 0.35)
        scrollbar_handle = _mix(chrome_bg, "#99a4b2", 0.52)
        scrollbar_hover = _mix(chrome_bg, "#7f8b99", 0.62)
        toolbar_checked_bg = _mix(accent, "#ffffff", 0.82)
        toolbar_checked_hover_bg = _mix(accent, "#ffffff", 0.74)
        tab_hover_bg = _mix(chrome_bg, "#ffffff", 0.34)
        dock_button_bg = _mix(chrome_bg, "#ffffff", 0.28)
        dock_button_hover_bg = _mix(chrome_bg, accent, 0.14)
        dock_button_pressed_bg = _mix(chrome_bg, accent, 0.22)

    if bool(s.get("use_custom_colors", False)):
        custom_editor_bg = _normalize_hex(s.get("custom_editor_bg", ""), "")
        custom_editor_fg = _normalize_hex(s.get("custom_editor_fg", ""), "")
        custom_chrome_bg = _normalize_hex(s.get("custom_chrome_bg", ""), "")
        if custom_editor_bg:
            window_bg = custom_editor_bg
            surface_bg = _mix(window_bg, "#ffffff" if not dark else "#000000", 0.06)
            input_bg = surface_bg
        if custom_editor_fg:
            text = custom_editor_fg
            text_muted = _mix(text, window_bg, 0.5)
        if custom_chrome_bg:
            chrome_bg = custom_chrome_bg
            panel_bg = _mix(chrome_bg, "#ffffff" if not dark else "#000000", 0.08)
            button_bg = _mix(chrome_bg, "#ffffff" if not dark else "#000000", 0.12)
            border = _mix(chrome_bg, text, 0.26)
            border_soft = _mix(chrome_bg, text, 0.16)
            border_strong = _mix(chrome_bg, text, 0.36)

    if density == "compact":
        radii = (5, 7, 9, 11)
        spaces = (3, 5, 7, 10)
        toolbar_pad = (2, 4)
        input_height = 24
        tab_h = 22
    else:
        radii = (6, 8, 10, 12)
        spaces = (4, 6, 8, 12)
        toolbar_pad = (3, 6)
        input_height = 26
        tab_h = 24

    toolbar_hover_bg = accent
    text_on_accent = _contrast_fg(accent, threshold=0.52)
    icon_fg = _contrast_fg(chrome_bg, dark="#000000", light="#ffffff")

    return UIThemeTokens(
        dark_mode=dark,
        theme_name=theme,
        density=density,
        accent=accent,
        text=text,
        text_muted=text_muted,
        text_on_accent=text_on_accent,
        window_bg=window_bg,
        editor_bg=window_bg,
        chrome_bg=chrome_bg,
        panel_bg=panel_bg,
        surface_bg=surface_bg,
        input_bg=input_bg,
        button_bg=button_bg,
        border=border,
        border_soft=border_soft,
        border_strong=border_strong,
        selection_bg=selection_bg,
        selection_fg=selection_fg,
        toolbar_hover_bg=toolbar_hover_bg,
        toolbar_checked_bg=toolbar_checked_bg,
        toolbar_checked_hover_bg=toolbar_checked_hover_bg,
        tab_hover_bg=tab_hover_bg,
        dock_button_bg=dock_button_bg,
        dock_button_hover_bg=dock_button_hover_bg,
        dock_button_pressed_bg=dock_button_pressed_bg,
        scrollbar_track=scrollbar_track,
        scrollbar_handle=scrollbar_handle,
        scrollbar_hover=scrollbar_hover,
        radius_sm=radii[0],
        radius_md=radii[1],
        radius_lg=radii[2],
        radius_xl=radii[3],
        space_xs=spaces[0],
        space_sm=spaces[1],
        space_md=spaces[2],
        space_lg=spaces[3],
        toolbar_pad_v=toolbar_pad[0],
        toolbar_pad_h=toolbar_pad[1],
        input_height=input_height,
        tab_min_height=tab_h,
        icon_fg=icon_fg,
    )


def tokens_signature(tokens: UIThemeTokens) -> str:
    payload = json.dumps(asdict(tokens), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def tokens_to_css_vars_qss(tokens: UIThemeTokens) -> str:
    rows = asdict(tokens)
    lines = ["/* pypad theme tokens"]
    for key in sorted(rows):
        lines.append(f"{key}: {rows[key]}")
    lines.append("*/")
    return "\n".join(lines)


def build_color_swatch_style(tokens: UIThemeTokens | None, value: str) -> str:
    val = str(value or "").strip()
    if not val:
        return ""
    border = "#888"
    if tokens is not None:
        border = tokens.border
    return f"background-color: {val}; border: 1px solid {border}; padding: 2px;"


def build_dialog_theme_qss_from_tokens(tokens: UIThemeTokens) -> str:
    return f"""
        QDialog {{
            background: {tokens.panel_bg};
            color: {tokens.text};
        }}
        QLabel, QCheckBox, QRadioButton, QGroupBox {{
            color: {tokens.text};
        }}
        QGroupBox {{
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
            margin-top: 10px;
            padding-top: {tokens.space_sm}px;
            background: {tokens.panel_bg};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
        }}
        QListWidget, QListView, QTreeView, QTextEdit, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget, QTreeWidget, QTableView, QScrollArea {{
            background: {tokens.input_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            selection-background-color: {tokens.accent};
            selection-color: {tokens.text_on_accent};
        }}
        QComboBox QAbstractItemView, QMenu {{
            background: {tokens.surface_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            selection-background-color: {tokens.accent};
            selection-color: {tokens.text_on_accent};
        }}
        QHeaderView::section {{
            background: {tokens.chrome_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            padding: {tokens.space_xs}px {tokens.space_sm}px;
        }}
        QTabWidget::pane {{
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
            background: {tokens.surface_bg};
        }}
        QTabBar::tab {{
            background: {tokens.chrome_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-top-left-radius: {tokens.radius_md}px;
            border-top-right-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_md}px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {tokens.surface_bg};
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            background: {tokens.tab_hover_bg};
        }}
        QPushButton, QToolButton {{
            background: {tokens.button_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_md}px;
        }}
        QPushButton:hover, QToolButton:hover {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
            border: 1px solid {tokens.accent};
        }}
        QPushButton:disabled {{
            color: {tokens.text_muted};
        }}
        QDialogButtonBox > QPushButton {{
            min-height: {tokens.input_height}px;
        }}
        QSplitter::handle {{
            background: {tokens.border_soft};
        }}
    """


def build_tool_dialog_qss(tokens: UIThemeTokens) -> str:
    return f"""
        QGroupBox {{
            padding-top: {tokens.space_sm}px;
            border-radius: {tokens.radius_lg}px;
        }}
        QLineEdit, QComboBox, QTextEdit, QTableWidget, QListWidget {{
            border-radius: {tokens.radius_md}px;
        }}
        QTabWidget::pane {{
            border-radius: {tokens.radius_lg}px;
        }}
        QTabBar::tab {{
            border-top-left-radius: {tokens.radius_md}px;
            border-top-right-radius: {tokens.radius_md}px;
        }}
    """


def build_quick_open_qss(tokens: UIThemeTokens) -> str:
    return f"""
        #quickOpenDialog {{ background: {tokens.panel_bg}; }}
        #quickOpenHeader {{ color: {tokens.text}; font-size: 13px; font-weight: 600; }}
        #quickOpenHint {{ color: {tokens.text_muted}; font-size: 11px; }}
        #quickOpenStatus {{ color: {_mix(tokens.accent, '#ffffff' if not tokens.dark_mode else '#c8ffd9', 0.25)}; font-size: 11px; }}
        #quickOpenDialog QLineEdit {{
            background: {tokens.input_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
            padding: {tokens.space_sm}px {tokens.space_md}px;
        }}
        #quickOpenDialog QListWidget {{
            background: {tokens.surface_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_xl}px;
            outline: none;
        }}
        #quickOpenDialog QListWidget::item {{
            padding: {tokens.space_sm}px {tokens.space_md}px;
            margin: 1px {tokens.space_xs}px;
            border-radius: {tokens.radius_sm}px;
        }}
        #quickOpenDialog QListWidget::item:selected {{
            background: {_mix(tokens.accent, tokens.surface_bg, 0.15 if tokens.dark_mode else 0.22)};
            color: {tokens.text};
        }}
        #quickOpenDialog QPushButton {{
            background: {tokens.button_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_sm}px {tokens.space_lg}px;
        }}
        #quickOpenDialog QPushButton:hover {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
            border: 1px solid {tokens.accent};
        }}
    """


def build_ai_chat_qss(tokens: UIThemeTokens) -> tuple[str, str]:
    surface_bg = _mix(tokens.surface_bg, "#000000" if tokens.dark_mode else "#ffffff", 0.03)
    user_bg = _mix(tokens.accent, tokens.surface_bg, 0.68 if tokens.dark_mode else 0.82)
    user_border = _mix(tokens.accent, tokens.border, 0.35)
    assistant_bg = _mix(tokens.surface_bg, tokens.chrome_bg, 0.25)
    assistant_border = tokens.border
    title_bg = tokens.panel_bg
    qss = f"""
        QDockWidget#aiChatDock {{ background: {tokens.panel_bg}; }}
        QWidget#aiChatHost {{ background: {tokens.panel_bg}; }}
        QScrollArea#aiChatScroll {{
            background: {surface_bg};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_xl}px;
        }}
        QWidget#aiChatViewport, QWidget#aiChatMessages {{ background: {surface_bg}; }}
        QWidget#aiChatRow, QWidget#aiChatBubbleActions {{ background: transparent; }}
        QFrame#userBubble {{
            background: {user_bg};
            border: 1px solid {user_border};
            border-radius: {tokens.radius_lg}px;
        }}
        QFrame#assistantBubble {{
            background: {assistant_bg};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_lg}px;
        }}
        QFrame#userBubble QTextBrowser, QFrame#assistantBubble QTextBrowser {{
            color: {tokens.text};
            background: transparent;
            border: none;
            font-family: "Segoe UI", "Noto Sans", sans-serif;
            font-size: 10pt;
        }}
        QPlainTextEdit#aiChatInput {{
            background: {tokens.input_bg};
            color: {tokens.text};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_lg}px;
        }}
        QWidget#aiChatAttachmentsBar {{
            background: {tokens.surface_bg};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_md}px;
        }}
        QScrollArea#aiChatAttachmentsScroll, QWidget#aiChatAttachmentsHost {{
            background: transparent; border: none;
        }}
        QWidget#aiChatAttachmentChip {{
            background: {tokens.button_bg};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_xl}px;
        }}
        QLabel#aiChatAttachmentChipIcon, QLabel#aiChatAttachmentChipText {{
            color: {tokens.text}; background: transparent; border: none;
        }}
        QPushButton#aiChatAttachmentChipRemove {{
            background: transparent; color: {tokens.text}; border: none; padding: 0px 4px; min-width: 16px;
        }}
        QPushButton#aiChatAttachmentChipRemove:hover {{
            background: {tokens.tab_hover_bg}; border-radius: {tokens.radius_md}px;
        }}
        QLabel#aiPendingInsertLabel {{
            color: {tokens.text};
            background: {tokens.button_bg};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_sm}px;
            padding: 4px 8px;
        }}
        QLabel#aiChatSessionTitle {{
            color: {tokens.text}; background: transparent; border: none; padding: 0px 4px; font-weight: 600;
        }}
        QPushButton {{
            background: {tokens.button_bg};
            color: {tokens.text};
            border: 1px solid {assistant_border};
            border-radius: {tokens.radius_md}px;
            padding: 4px 8px;
        }}
        QPushButton:disabled {{ color: {tokens.text_muted}; }}
        QPushButton#aiChatBubbleActionButton {{
            border-radius: {tokens.radius_sm}px;
            padding: 0px;
        }}
        QPushButton#aiChatBubbleActionButton:hover {{ background: {tokens.tab_hover_bg}; }}
        QPushButton#aiChatBubbleActionButton:pressed {{ background: {tokens.toolbar_checked_bg}; }}
    """
    title_qss = f"""
        QWidget#aiChatTitleBar {{
            background: {title_bg};
            border-bottom: 1px solid {assistant_border};
            border-top-left-radius: {tokens.radius_md}px;
            border-top-right-radius: {tokens.radius_md}px;
        }}
        QLabel#aiChatTitleLabel {{ color: {tokens.text}; font-weight: 600; }}
        QWidget#aiChatTitleBar QToolButton {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: {tokens.radius_sm}px;
            padding: 0px;
        }}
        QWidget#aiChatTitleBar QToolButton:hover {{
            background: {tokens.dock_button_hover_bg};
            border: 1px solid {tokens.border};
        }}
        QWidget#aiChatTitleBar QToolButton:pressed {{
            background: {tokens.dock_button_pressed_bg};
            border: 1px solid {tokens.border};
        }}
    """
    return qss, title_qss


def build_settings_dialog_qss(tokens: UIThemeTokens) -> str:
    nav_selected_bg = _mix(tokens.accent, tokens.surface_bg, 0.16 if tokens.dark_mode else 0.24)
    nav_hover_bg = _mix(tokens.tab_hover_bg, tokens.surface_bg, 0.25)
    scope_bg = _mix(tokens.button_bg, tokens.surface_bg, 0.15)
    page_text = tokens.text
    page_text_muted = tokens.text_muted
    return f"""
        #settingsHeaderCard {{
            background: {tokens.surface_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
        #settingsPageTitle {{
            color: {tokens.text};
            background: transparent;
        }}
        #settingsPageDesc {{
            color: {tokens.text_muted};
            background: transparent;
        }}
        #settingsNavList, #settingsPageStack {{
            background: {tokens.surface_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
        QWidget#settingsPageHost,
        QWidget#settingsPageScrollContent,
        QWidget#settingsPageBody {{
            background: {tokens.surface_bg};
            background-color: {tokens.surface_bg};
            color: {page_text};
        }}
        QScrollArea#settingsPageScroll {{
            background: {tokens.surface_bg};
            background-color: {tokens.surface_bg};
            border: none;
        }}
        QScrollArea#settingsPageScroll QWidget#qt_scrollarea_viewport {{
            background: {tokens.surface_bg};
            background-color: {tokens.surface_bg};
            border: none;
        }}
        QWidget#settingsPageHost QLabel,
        QWidget#settingsPageHost QCheckBox,
        QWidget#settingsPageHost QRadioButton,
        QWidget#settingsPageHost QGroupBox {{
            color: {page_text};
        }}
        QWidget#settingsPageHost QLabel:disabled,
        QWidget#settingsPageHost QCheckBox:disabled,
        QWidget#settingsPageHost QRadioButton:disabled,
        QWidget#settingsPageHost QGroupBox:disabled {{
            color: {page_text_muted};
        }}
        QWidget#settingsPageHost QGroupBox::title {{
            color: {page_text};
        }}
        #settingsNavList {{
            outline: none;
            padding: {tokens.space_xs}px;
        }}
        #settingsNavList::item {{
            padding: {tokens.space_xs}px {tokens.space_md}px;
            border: 1px solid transparent;
            border-radius: {tokens.radius_sm}px;
        }}
        #settingsNavList::item:hover {{
            background: {nav_hover_bg};
        }}
        #settingsNavList::item:selected {{
            background: {nav_selected_bg};
            color: {tokens.text};
            border: 1px solid {_mix(tokens.accent, tokens.border, 0.4)};
        }}
        #settingsSearchInput {{
            min-height: {tokens.input_height}px;
            padding: 2px {tokens.space_md}px;
            border-radius: {tokens.radius_md}px;
        }}
        QPushButton#settingsScopeBtn {{
            min-width: 64px;
            padding: {tokens.space_xs}px {tokens.space_lg}px;
            border-radius: 0px;
            background: {scope_bg};
        }}
        QPushButton#settingsScopeBtn[scopePos="left"] {{
            border-top-left-radius: {tokens.radius_md}px;
            border-bottom-left-radius: {tokens.radius_md}px;
        }}
        QPushButton#settingsScopeBtn[scopePos="right"] {{
            border-top-right-radius: {tokens.radius_md}px;
            border-bottom-right-radius: {tokens.radius_md}px;
        }}
        QPushButton#settingsScopeBtn:checked {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
            border: 1px solid {tokens.accent};
        }}
        QSlider::groove:horizontal {{
            border: 1px solid {tokens.border};
            background: {tokens.panel_bg};
            height: 6px;
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: {tokens.accent};
            width: 12px;
            margin: -5px 0;
            border-radius: 6px;
            border: 1px solid {tokens.accent};
        }}
    """


def build_tutorial_dialog_qss(tokens: UIThemeTokens) -> str:
    card_bg = _mix(tokens.surface_bg, tokens.chrome_bg, 0.16)
    return f"""
        QDialog {{
            background: {tokens.panel_bg};
            color: {tokens.text};
        }}
        QLabel {{
            color: {tokens.text};
            background: transparent;
        }}
        QPushButton {{
            min-height: {tokens.input_height}px;
            border-radius: {tokens.radius_md}px;
        }}
        #tutorialBodyCard {{
            background: {card_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
    """


def build_autosave_dialog_qss(tokens: UIThemeTokens) -> str:
    return f"""
        QListWidget, QTextEdit {{
            background: {tokens.surface_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
        QListWidget::item {{
            margin: 1px;
            padding: {tokens.space_xs}px {tokens.space_sm}px;
            border-radius: {tokens.radius_sm}px;
        }}
        QListWidget::item:selected {{
            background: {_mix(tokens.accent, tokens.surface_bg, 0.16 if tokens.dark_mode else 0.22)};
            color: {tokens.text};
            border: 1px solid {_mix(tokens.accent, tokens.border, 0.45)};
        }}
        QPushButton {{
            min-height: {tokens.input_height}px;
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_lg}px;
        }}
    """


def build_workspace_dialog_qss(tokens: UIThemeTokens) -> str:
    return f"""
        QListWidget, QTextEdit {{
            background: {tokens.surface_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
        QListWidget::item {{
            margin: 1px;
            padding: {tokens.space_xs}px {tokens.space_sm}px;
            border-radius: {tokens.radius_sm}px;
        }}
        QListWidget::item:selected {{
            background: {_mix(tokens.accent, tokens.surface_bg, 0.16 if tokens.dark_mode else 0.22)};
            color: {tokens.text};
            border: 1px solid {_mix(tokens.accent, tokens.border, 0.45)};
        }}
        QPushButton {{
            min-height: {tokens.input_height}px;
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_lg}px;
        }}
    """


def build_ai_edit_preview_dialog_qss(tokens: UIThemeTokens) -> str:
    return f"""
        QListWidget, QTextEdit {{
            background: {tokens.surface_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
        }}
        QListWidget::item {{
            padding: {tokens.space_xs}px {tokens.space_sm}px;
            border-radius: {tokens.radius_sm}px;
            margin: 1px;
        }}
        QListWidget::item:selected {{
            background: {_mix(tokens.accent, tokens.surface_bg, 0.16 if tokens.dark_mode else 0.22)};
            color: {tokens.text};
        }}
        QSplitter::handle {{
            background: {tokens.border_soft};
        }}
        QPushButton {{
            min-height: {tokens.input_height}px;
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_lg}px;
        }}
    """


def build_debug_logs_dialog_qss(tokens: UIThemeTokens) -> str:
    return f"""
        QTextEdit {{
            background: {tokens.surface_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
            selection-background-color: {tokens.accent};
            selection-color: {tokens.text_on_accent};
        }}
        QPushButton {{
            min-height: {tokens.input_height}px;
            border-radius: {tokens.radius_md}px;
            padding: {tokens.space_xs}px {tokens.space_lg}px;
        }}
    """


def build_main_window_qss(*, tokens: UIThemeTokens, tab_close_icon_url: str, close_button_visibility_qss: str = "") -> str:
    tool_padding = f"{tokens.toolbar_pad_v}px {tokens.toolbar_pad_h}px"
    tab_close_bg = _mix("#d13438", tokens.chrome_bg, 0.18 if tokens.dark_mode else 0.10)
    tab_close_hover_bg = _mix("#e74856", tokens.chrome_bg, 0.15 if tokens.dark_mode else 0.08)
    tab_close_pressed_bg = _mix("#a4262c", tokens.chrome_bg, 0.10 if tokens.dark_mode else 0.04)
    tab_close_border = _mix(tab_close_bg, "#6f1014", 0.38)
    tab_close_hover_border = _mix(tab_close_hover_bg, "#7a1217", 0.34)
    tab_close_pressed_border = _mix(tab_close_pressed_bg, "#5f0b0f", 0.28)
    return f"""
        QMainWindow {{
            background-color: {tokens.window_bg};
            color: {tokens.text};
        }}
        QTextEdit {{
            background-color: {tokens.editor_bg};
            color: {tokens.text};
            selection-background-color: {tokens.selection_bg};
            selection-color: {tokens.selection_fg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
        }}
        QMenuBar, QMenu, QStatusBar, QToolBar {{
            background-color: {tokens.chrome_bg};
            color: {tokens.text};
        }}
        QMenuBar {{
            border-bottom: 1px solid {tokens.border_soft};
        }}
        QMenu {{
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_lg}px;
            padding: {tokens.space_xs}px;
        }}
        QMenu::item {{
            padding: {tokens.space_xs + 1}px {tokens.space_lg}px {tokens.space_xs + 1}px {tokens.space_md}px;
            margin: 1px;
            border-radius: {tokens.radius_sm}px;
        }}
        QMenu::separator {{
            height: 1px;
            background: {tokens.border_soft};
            margin: {tokens.space_xs}px {tokens.space_sm}px;
        }}
        QMenuBar::item {{
            padding: {tokens.space_xs + 1}px {tokens.space_sm + 2}px;
            border-radius: {tokens.radius_sm}px;
            margin: 1px;
        }}
        QMenuBar::item:selected, QMenu::item:selected {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
        }}
        QToolBar {{
            border-top: 1px solid {tokens.border_soft};
            border-bottom: 1px solid {tokens.border_soft};
            spacing: 3px;
            padding: 2px;
        }}
        QDockWidget::title {{
            background: {tokens.chrome_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-top-left-radius: {tokens.radius_md}px;
            border-top-right-radius: {tokens.radius_md}px;
            padding: {tokens.space_sm}px {tokens.space_lg}px;
            text-align: left;
        }}
        QDockWidget::close-button,
        QDockWidget::float-button {{
            background: {tokens.dock_button_bg};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_sm}px;
            padding: 0px;
            margin: 2px;
            width: 16px;
            height: 16px;
        }}
        QDockWidget::close-button:hover,
        QDockWidget::float-button:hover {{
            background: {tokens.dock_button_hover_bg};
            border: 1px solid {tokens.accent};
        }}
        QDockWidget::close-button:pressed,
        QDockWidget::float-button:pressed {{
            background: {tokens.dock_button_pressed_bg};
        }}
        QToolButton {{
            color: {tokens.text};
            background: transparent;
            border: 1px solid transparent;
            border-radius: {tokens.radius_md}px;
            padding: {tool_padding};
        }}
        QToolButton:hover {{
            background: {tokens.toolbar_hover_bg};
            color: {tokens.text_on_accent};
            border: 1px solid {tokens.accent};
        }}
        QToolButton#pypadTabCloseButton {{
            color: {tokens.text};
            background: transparent;
            border: 1px solid transparent;
            border-radius: {tokens.radius_sm}px;
            padding: 0px;
            margin: 0px;
        }}
        QToolButton#pypadTabCloseButton:hover {{
            background: {tab_close_hover_bg};
            border: 1px solid {tab_close_hover_border};
            color: #ffffff;
        }}
        QToolButton#pypadTabCloseButton:pressed {{
            background: {tab_close_pressed_bg};
            border: 1px solid {tab_close_pressed_border};
            color: #ffffff;
        }}
        QToolButton:pressed {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
        }}
        QToolButton:checked {{
            background: {tokens.toolbar_checked_bg};
            color: {tokens.text};
            border: 1px solid {tokens.accent};
        }}
        QToolButton:checked:hover {{
            background: {tokens.toolbar_checked_hover_bg};
            color: {tokens.text};
            border: 1px solid {tokens.accent};
        }}
        QToolBar QLabel, QToolBar QCheckBox {{
            color: {tokens.text};
            background: transparent;
        }}
        QToolBar QLineEdit {{
            background: {tokens.input_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            min-height: {tokens.input_height}px;
            padding: 0px 6px;
        }}
        QToolBar QPushButton {{
            background: {tokens.button_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_md}px;
            min-height: {tokens.input_height}px;
            padding: 2px 10px;
        }}
        QToolBar QPushButton:hover {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
            border: 1px solid {tokens.accent};
        }}
        QToolBar QPushButton:pressed {{
            background: {tokens.accent};
            color: {tokens.text_on_accent};
        }}
        QStatusBar QLabel, QStatusBar::item {{
            color: {tokens.text};
        }}
        QStatusBar QComboBox {{
            background: {tokens.button_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
            border-radius: {tokens.radius_sm}px;
            padding: 1px 6px;
        }}
        QStatusBar QComboBox QAbstractItemView {{
            background: {tokens.surface_bg};
            color: {tokens.text};
            selection-background-color: {tokens.accent};
            selection-color: {tokens.text_on_accent};
        }}
        QTabWidget::pane {{
            border: 1px solid {tokens.border_soft};
            border-radius: {tokens.radius_lg}px;
            background: {tokens.chrome_bg};
        }}
        QTabBar::tab {{
            background: {tokens.chrome_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border_soft};
            border-top-left-radius: {tokens.radius_md}px;
            border-top-right-radius: {tokens.radius_md}px;
            padding: 6px 52px 6px 10px;
            margin-right: 3px;
            min-height: {tokens.tab_min_height}px;
        }}
        QTabBar::close-button {{
            subcontrol-position: right;
            subcontrol-origin: padding;
            margin-right: 4px;
            margin-left: 6px;
            width: 14px;
            height: 14px;
            image: url("{tab_close_icon_url}");
            background: {tab_close_bg};
            border: 1px solid {tab_close_border};
            border-radius: {tokens.radius_sm}px;
        }}
        QTabBar::close-button:hover {{
            background: {tab_close_hover_bg};
            border: 1px solid {tab_close_hover_border};
        }}
        QTabBar::close-button:pressed {{
            background: {tab_close_pressed_bg};
            border: 1px solid {tab_close_pressed_border};
        }}
        {close_button_visibility_qss}
        QTabBar::tab:selected {{
            background: {tokens.window_bg};
            color: {tokens.text};
            font-weight: 600;
            border: 1px solid {tokens.border};
        }}
        QTabBar::tab:hover {{
            background: {tokens.tab_hover_bg};
            color: {tokens.text};
            border: 1px solid {tokens.border};
        }}
        QScrollBar:vertical, QScrollBar:horizontal {{
            background: {tokens.scrollbar_track};
            border: 1px solid {tokens.border_soft};
            margin: 0px;
        }}
        QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
            background: {tokens.scrollbar_handle};
            min-height: 20px;
            min-width: 20px;
            border-radius: {tokens.radius_sm}px;
        }}
        QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
            background: {tokens.scrollbar_hover};
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            background: transparent;
            border: none;
            width: 0px;
            height: 0px;
        }}
        QLabel#emptyTabsHint {{
            color: {tokens.text_muted};
            font-size: 14px;
            background: transparent;
        }}
    """
