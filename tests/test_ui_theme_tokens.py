import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from pypad.ui.theme.theme_tokens import (
        build_ai_edit_preview_dialog_qss,
        build_autosave_dialog_qss,
        build_debug_logs_dialog_qss,
        build_main_window_qss,
        build_settings_dialog_qss,
        build_tokens_from_settings,
        build_tutorial_dialog_qss,
        build_workspace_dialog_qss,
        tokens_signature,
        tokens_to_css_vars_qss,
    )
except ModuleNotFoundError:
    from pypad.ui.theme_tokens import (
        build_ai_edit_preview_dialog_qss,
        build_autosave_dialog_qss,
        build_debug_logs_dialog_qss,
        build_main_window_qss,
        build_settings_dialog_qss,
        build_tokens_from_settings,
        build_tutorial_dialog_qss,
        build_workspace_dialog_qss,
        tokens_signature,
        tokens_to_css_vars_qss,
    )


class ThemeTokensTests(unittest.TestCase):
    def test_dark_mode_tokens_are_dark_and_have_rounding(self) -> None:
        t = build_tokens_from_settings({"dark_mode": True, "theme": "Default", "accent_color": "#4a90e2"})
        self.assertTrue(t.dark_mode)
        self.assertEqual(t.accent, "#4a90e2")
        self.assertGreaterEqual(t.radius_md, 8)
        self.assertNotEqual(t.window_bg, "#ffffff")
        self.assertEqual(t.text_on_accent in {"#111111", "#ffffff"}, True)

    def test_custom_colors_override(self) -> None:
        t = build_tokens_from_settings(
            {
                "dark_mode": False,
                "theme": "Default",
                "use_custom_colors": True,
                "custom_editor_bg": "#112233",
                "custom_editor_fg": "#f0f0f0",
                "custom_chrome_bg": "#445566",
            }
        )
        self.assertEqual(t.window_bg, "#112233")
        self.assertEqual(t.text, "#f0f0f0")
        self.assertEqual(t.chrome_bg, "#445566")

    def test_density_changes_metrics(self) -> None:
        a = build_tokens_from_settings({"ui_density": "compact"})
        b = build_tokens_from_settings({"ui_density": "comfortable"})
        self.assertLess(a.input_height, b.input_height)
        self.assertLessEqual(a.radius_md, b.radius_md)

    def test_signature_changes_when_tokens_change(self) -> None:
        a = build_tokens_from_settings({"dark_mode": False})
        b = build_tokens_from_settings({"dark_mode": True})
        self.assertNotEqual(tokens_signature(a), tokens_signature(b))

    def test_tokens_to_css_vars_qss_contains_keys(self) -> None:
        t = build_tokens_from_settings({})
        qss = tokens_to_css_vars_qss(t)
        self.assertIn("accent", qss)
        self.assertIn("radius_md", qss)

    def test_component_qss_builders_include_rounded_selectors(self) -> None:
        t = build_tokens_from_settings({"dark_mode": True, "accent_color": "#2266dd"})
        settings_qss = build_settings_dialog_qss(t)
        tutorial_qss = build_tutorial_dialog_qss(t)
        autosave_qss = build_autosave_dialog_qss(t)
        workspace_qss = build_workspace_dialog_qss(t)
        ai_preview_qss = build_ai_edit_preview_dialog_qss(t)
        debug_logs_qss = build_debug_logs_dialog_qss(t)

        self.assertIn("#settingsNavList::item:selected", settings_qss)
        self.assertIn("border-radius", settings_qss)
        self.assertIn("QSlider::handle:horizontal", settings_qss)
        self.assertIn("#tutorialBodyCard", tutorial_qss)
        self.assertIn("border-radius", tutorial_qss)
        self.assertIn("QListWidget::item:selected", autosave_qss)
        self.assertIn("QPushButton", autosave_qss)
        self.assertIn("QListWidget::item:selected", workspace_qss)
        self.assertIn("QSplitter::handle", ai_preview_qss)
        self.assertIn("QTextEdit", debug_logs_qss)

    def test_settings_qss_enforces_page_stack_text_colors(self) -> None:
        t = build_tokens_from_settings({"dark_mode": True, "accent_color": "#2266dd"})
        settings_qss = build_settings_dialog_qss(t)
        self.assertIn("QWidget#settingsPageHost,", settings_qss)
        self.assertIn("QWidget#settingsPageScrollContent,", settings_qss)
        self.assertIn("QWidget#settingsPageBody {", settings_qss)
        self.assertIn("QScrollArea#settingsPageScroll {", settings_qss)
        self.assertIn("QWidget#settingsPageHost QLabel:disabled,", settings_qss)

    def test_main_window_qss_contains_core_selectors_and_hover_override(self) -> None:
        t = build_tokens_from_settings({"dark_mode": False, "accent_color": "#1188dd"})
        hover_qss = 'QTabBar::tab:hover QTabBar::close-button { image: url("x"); }'
        qss = build_main_window_qss(tokens=t, tab_close_icon_url="icons/tab-close.svg", close_button_visibility_qss=hover_qss)
        self.assertIn("QDockWidget::title", qss)
        self.assertIn("QTabBar::close-button", qss)
        self.assertIn("QMenu::item", qss)
        self.assertIn("QStatusBar QComboBox", qss)
        self.assertIn(hover_qss, qss)


if __name__ == "__main__":
    unittest.main()
