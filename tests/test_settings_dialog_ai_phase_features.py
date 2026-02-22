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

from pypad.app_settings.defaults import build_default_settings
from pypad.ui.main_window.settings_dialog import SettingsDialog


class _Parent(QMainWindow):
    @staticmethod
    def _build_default_settings() -> dict:
        return build_default_settings(default_style="Windows", font_family="Segoe UI", font_size=11)


class SettingsDialogAIPhaseFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_ai_phase_controls_round_trip(self) -> None:
        parent = _Parent()
        settings = parent._build_default_settings()
        dlg = SettingsDialog(parent, settings)

        dlg.ai_apply_review_mode_combo.setCurrentText("legacy_direct_apply")
        dlg.ai_regression_guard_checkbox.setChecked(False)
        dlg.ai_template_nearby_lines_radius_spin.setValue(42)
        dlg.ai_session_default_include_current_file_auto_checkbox.setChecked(True)
        dlg.ai_session_default_include_workspace_snippets_auto_checkbox.setChecked(True)
        dlg.ai_session_default_strict_citations_only_checkbox.setChecked(True)
        dlg.ai_session_default_allow_hidden_apply_commands_checkbox.setChecked(False)

        dlg._apply_to_memory()
        out = dlg.get_settings()
        self.assertEqual(out["ai_apply_review_mode"], "legacy_direct_apply")
        self.assertFalse(out["ai_enable_regression_guard_prompts"])
        self.assertEqual(out["ai_template_nearby_lines_radius"], 42)
        self.assertTrue(out["ai_session_default_include_current_file_auto"])
        self.assertTrue(out["ai_session_default_include_workspace_snippets_auto"])
        self.assertTrue(out["ai_session_default_strict_citations_only"])
        self.assertFalse(out["ai_session_default_allow_hidden_apply_commands"])


if __name__ == "__main__":
    unittest.main()
