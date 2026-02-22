import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.main_window.misc import MiscMixin


class AIBatchRefactorPlannerTests(unittest.TestCase):
    def test_parse_batch_refactor_plan_accepts_json_and_filters_candidates(self) -> None:
        candidates = ["C:/w/a.py", "C:/w/b.py", "C:/w/c.py"]
        payload = {
            "files": [
                {"path": "C:/w/b.py", "reason": "core logic", "priority": 2},
                {"path": "C:/w/a.py", "reason": "api surface", "priority": 1},
                {"path": "C:/w/zzz.py", "reason": "not candidate", "priority": 0},
            ],
            "global_risks": ["format drift"],
            "suggested_order": ["C:/w/a.py", "C:/w/b.py"],
        }
        out = MiscMixin._parse_batch_refactor_plan(json.dumps(payload), candidates, max_files=10)
        files = out["files"]
        self.assertEqual([row["path"] for row in files], ["C:/w/a.py", "C:/w/b.py"])
        self.assertEqual(out["global_risks"], ["format drift"])

    def test_parse_batch_refactor_plan_accepts_fenced_json(self) -> None:
        candidates = ["x.py"]
        raw = """Plan:
```json
{"files":[{"path":"x.py","reason":"touch","priority":1}],"global_risks":[],"suggested_order":["x.py"]}
```"""
        out = MiscMixin._parse_batch_refactor_plan(raw, candidates, max_files=5)
        self.assertEqual(len(out["files"]), 1)
        self.assertEqual(out["files"][0]["path"], "x.py")


if __name__ == "__main__":
    unittest.main()
