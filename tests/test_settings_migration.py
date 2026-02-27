import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from pypad.app_settings import migrate_settings
except ModuleNotFoundError:
    from notepadclone.app_settings import migrate_settings


class SettingsMigrationTests(unittest.TestCase):
    def test_migrates_v1_and_sets_schema(self) -> None:
        source = {"dark_mode": True, "settings_schema_version": 1}
        migrated = migrate_settings(source)
        self.assertEqual(migrated["settings_schema_version"], 2)
        self.assertTrue(migrated["dark_mode"])
        self.assertIn("icon_size_px", migrated)

    def test_invalid_values_are_clamped_or_defaulted(self) -> None:
        source = {
            "settings_schema_version": 1,
            "icon_size_px": 99,
            "ui_density": "weird",
            "search_max_highlights": -1,
        }
        migrated = migrate_settings(source)
        self.assertEqual(migrated["icon_size_px"], 24)
        self.assertEqual(migrated["ui_density"], "comfortable")
        self.assertEqual(migrated["search_max_highlights"], 100)

    def test_unknown_keys_preserved(self) -> None:
        source = {"settings_schema_version": 1, "my_custom_flag": "x"}
        migrated = migrate_settings(source)
        self.assertEqual(migrated["my_custom_flag"], "x")

    def test_scintilla_profile_values_are_sanitized(self) -> None:
        source = {
            "settings_schema_version": 1,
            "scintilla_wrap_mode": "bad",
            "scintilla_auto_completion_threshold": 99,
            "scintilla_margin_left_px": -1,
            "scintilla_line_number_width_mode": "wat",
            "scintilla_line_number_width_px": 9,
            "scintilla_style_theme": "bad_theme",
            "scintilla_style_overrides": {"python": {"keyword": "zzzzzz", "string": "#123456"}},
        }
        migrated = migrate_settings(source)
        self.assertEqual(migrated["scintilla_wrap_mode"], "word")
        self.assertEqual(migrated["scintilla_auto_completion_threshold"], 12)
        self.assertEqual(migrated["scintilla_margin_left_px"], 0)
        self.assertEqual(migrated["scintilla_line_number_width_mode"], "dynamic")
        self.assertEqual(migrated["scintilla_line_number_width_px"], 24)
        self.assertEqual(migrated["scintilla_style_theme"], "default")
        self.assertEqual(migrated["scintilla_style_overrides"]["python"]["string"], "#123456")


if __name__ == "__main__":
    unittest.main()
