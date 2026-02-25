import json
import sys
import unittest
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.advanced_features import apply_text_operations, compute_plugin_digest


class AdvancedFeaturesHelpersTests(unittest.TestCase):
    def test_apply_text_operations_sequence(self) -> None:
        text = "hello world"
        out = apply_text_operations(
            text,
            [
                {"op": "insert", "index": 5, "text": ","},
                {"op": "replace", "start": 6, "end": 11, "text": "there"},
                {"op": "delete", "start": 11, "end": 12},
            ],
        )
        self.assertEqual(out, "hello,there")

    def test_compute_plugin_digest_changes_with_content(self) -> None:
        tmp_root = ROOT / "tests_tmp"
        tmp = tmp_root / f"advanced_{time.time_ns()}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            root = tmp
            (root / "plugin.json").write_text(json.dumps({"id": "p"}), encoding="utf-8")
            (root / "plugin.py").write_text("class Plugin:\n    pass\n", encoding="utf-8")
            d1 = compute_plugin_digest(root)
            (root / "plugin.py").write_text("class Plugin:\n    def on_load(self):\n        return\n", encoding="utf-8")
            d2 = compute_plugin_digest(root)
            self.assertNotEqual(d1, d2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
