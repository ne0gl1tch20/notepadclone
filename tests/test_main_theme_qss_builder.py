import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.theme_tokens import build_main_window_qss, build_tokens_from_settings


class MainThemeQssBuilderTests(unittest.TestCase):
    def test_build_main_window_qss_contains_expected_selectors(self) -> None:
        tokens = build_tokens_from_settings({"dark_mode": True, "accent_color": "#4a90e2"})
        hover_snippet = 'QTabBar::tab:hover QTabBar::close-button { image: url("icons/tab-close.svg"); }'
        qss = build_main_window_qss(
            tokens=tokens,
            tab_close_icon_url="icons/tab-close.svg",
            close_button_visibility_qss=hover_snippet,
        )
        self.assertIn("QDockWidget::title", qss)
        self.assertIn("QTabBar::close-button", qss)
        self.assertIn("QMenu::item", qss)
        self.assertIn("QStatusBar QComboBox", qss)
        self.assertIn(hover_snippet, qss)


if __name__ == "__main__":
    unittest.main()
