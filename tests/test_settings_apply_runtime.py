import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication

from notepadclone.ui.main_window import Notepad


class SettingsApplyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_toolbar_visibility_and_icon_size_apply(self) -> None:
        window = Notepad()
        window.settings["show_main_toolbar"] = False
        window.settings["icon_size_px"] = 24
        window.apply_settings()
        self.assertFalse(window.main_toolbar.isVisible())
        self.assertEqual(window.main_toolbar.iconSize().width(), 24)
        window.close()


if __name__ == "__main__":
    unittest.main()
