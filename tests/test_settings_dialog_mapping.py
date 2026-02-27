import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from PySide6.QtWidgets import QApplication, QMainWindow

try:
    from pypad.app_settings.defaults import build_default_settings
    from pypad.ui.main_window.settings_dialog import SettingsDialog
except ModuleNotFoundError:
    from notepadclone.app_settings.defaults import build_default_settings
    from notepadclone.ui.main_window.settings_dialog import SettingsDialog


class _Parent(QMainWindow):
    @staticmethod
    def _build_default_settings() -> dict:
        return build_default_settings(default_style="Windows", font_family="Segoe UI", font_size=11)


class SettingsDialogMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_apply_updates_settings(self) -> None:
        parent = _Parent()
        settings = parent._build_default_settings()
        dlg = SettingsDialog(parent, settings)
        dlg.ui_density_combo.setCurrentText("compact")
        dlg.icon_size_combo.setCurrentText("20")
        dlg._apply_to_memory()
        out = dlg.get_settings()
        self.assertEqual(out["ui_density"], "compact")
        self.assertEqual(out["icon_size_px"], 20)

    def test_cancel_keeps_unapplied_values(self) -> None:
        parent = _Parent()
        settings = parent._build_default_settings()
        dlg = SettingsDialog(parent, settings)
        dlg.ui_density_combo.setCurrentText("compact")
        # no apply
        out = dlg.get_settings()
        self.assertEqual(out["ui_density"], settings["ui_density"])

    def test_restore_defaults_only_changes_controls_until_apply(self) -> None:
        parent = _Parent()
        settings = parent._build_default_settings()
        settings["ui_density"] = "compact"
        dlg = SettingsDialog(parent, settings)
        dlg.ui_density_combo.setCurrentText("comfortable")
        # no apply yet
        out = dlg.get_settings()
        self.assertEqual(out["ui_density"], "compact")

    def test_scintilla_controls_map_to_settings(self) -> None:
        parent = _Parent()
        settings = parent._build_default_settings()
        dlg = SettingsDialog(parent, settings)
        dlg.scintilla_wrap_mode_combo.setCurrentText("none")
        dlg.scintilla_multi_caret_checkbox.setChecked(True)
        dlg.scintilla_margin_left_spin.setValue(20)
        dlg.scintilla_line_number_width_mode_combo.setCurrentText("constant")
        dlg.scintilla_line_number_width_spin.setValue(72)
        dlg.scintilla_style_theme_combo.setCurrentText("solarized_light")
        dlg.scintilla_style_language_combo.setCurrentText("python")
        dlg._set_color_label(dlg.scintilla_style_keyword_label, "#112233")
        dlg._apply_to_memory()
        out = dlg.get_settings()
        self.assertEqual(out["scintilla_wrap_mode"], "none")
        self.assertTrue(out["scintilla_multi_caret"])
        self.assertEqual(out["scintilla_margin_left_px"], 20)
        self.assertEqual(out["scintilla_line_number_width_mode"], "constant")
        self.assertEqual(out["scintilla_line_number_width_px"], 72)
        self.assertEqual(out["scintilla_style_theme"], "solarized_light")
        self.assertEqual(out["scintilla_style_overrides"]["python"]["keyword"], "#112233")


if __name__ == "__main__":
    unittest.main()
