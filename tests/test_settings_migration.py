import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

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


if __name__ == "__main__":
    unittest.main()
