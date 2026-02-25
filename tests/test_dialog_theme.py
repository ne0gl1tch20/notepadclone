import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.dialog_theme import build_dialog_theme_qss


class DialogThemeQssTests(unittest.TestCase):
    def test_build_dialog_theme_qss_light_contains_rounded_selectors(self) -> None:
        qss = build_dialog_theme_qss({"dark_mode": False, "theme": "Default", "accent_color": "#3366cc"})
        self.assertIn("QDialog", qss)
        self.assertIn("border-radius", qss)
        self.assertIn("#3366cc", qss)
        self.assertIn("QTabBar::tab", qss)

    def test_build_dialog_theme_qss_dark_contains_dialog_controls(self) -> None:
        qss = build_dialog_theme_qss({"dark_mode": True, "accent_color": "#44aa88"})
        self.assertIn("QSplitter::handle", qss)
        self.assertIn("QDialogButtonBox > QPushButton", qss)
        self.assertIn("QMenu", qss)
        self.assertIn("QToolButton", qss)
        self.assertIn("QHeaderView::section", qss)
        self.assertIn("QTabWidget::pane", qss)


if __name__ == "__main__":
    unittest.main()
