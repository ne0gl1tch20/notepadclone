import os
import sys
import unittest
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication

try:
    from pypad.ui.main_window import Notepad
except ModuleNotFoundError:
    from notepadclone.ui.main_window import Notepad


class SettingsApplyRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _runtime_patches(self) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch("pypad.ui.session_recovery._atomic_write_json", lambda *_args, **_kwargs: None))
        stack.enter_context(patch("pypad.ui.autosave.AutoSaveStore.save", lambda *_args, **_kwargs: None))
        stack.enter_context(patch.object(Notepad, "restore_last_session", lambda self: None))
        stack.enter_context(patch.object(Notepad, "save_settings_to_disk", lambda self: None))
        return stack

    def test_toolbar_visibility_and_icon_size_apply(self) -> None:
        with self._runtime_patches():
            window = Notepad()
            window.settings["show_main_toolbar"] = False
            window.settings["icon_size_px"] = 24
            window.apply_settings()
            self.assertFalse(window.main_toolbar.isVisible())
            self.assertEqual(window.main_toolbar.iconSize().width(), 24)
            window.close()

    def test_apply_settings_hover_tab_close_mode_smoke(self) -> None:
        with self._runtime_patches():
            window = Notepad()
            window.settings["dark_mode"] = True
            window.settings["tab_close_button_mode"] = "hover"
            window.settings["accent_color"] = "#4a90e2"
            window.apply_settings()
            style_sheet = self.app.styleSheet()
            self.assertIn("QTabBar::close-button", style_sheet)
            self.assertIn("QTabBar::tab:hover QTabBar::close-button", style_sheet)
            window.close()


if __name__ == "__main__":
    unittest.main()
