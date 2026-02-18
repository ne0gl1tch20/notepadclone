import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QWidget

from notepadclone.ui.shortcut_mapper import ShortcutActionRow, ShortcutMapperDialog


class _WindowStub(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.settings = {}
        self.applied = False
        self.saved = False

    def apply_shortcut_settings(self) -> None:
        self.applied = True

    def save_settings_to_disk(self) -> None:
        self.saved = True


class ShortcutMapperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_live_persists_settings(self) -> None:
        win = _WindowStub()
        action = QAction("Save", win)
        action.setShortcut("Ctrl+S")
        rows = [ShortcutActionRow("save_action", "Save", action)]
        defaults = {"save_action": ["Ctrl+S"]}
        settings = {"shortcut_profile": "default", "shortcut_conflict_policy": "warn", "shortcut_map": {}}
        dlg = ShortcutMapperDialog(win, rows, defaults, settings)
        dlg._working_map["save_action"] = "Alt+S"
        dlg.apply_live()
        self.assertTrue(win.applied)
        self.assertTrue(win.saved)
        self.assertEqual(win.settings.get("shortcut_map", {}).get("save_action"), "Alt+S")


if __name__ == "__main__":
    unittest.main()
