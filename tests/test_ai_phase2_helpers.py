import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.ai_chat_dock import AIChatDock
from pypad.ui.main_window.misc import MiscMixin


class _TextEditStub:
    def __init__(self, text: str, selection: str, line: int, col: int) -> None:
        self._text = text
        self._selection = selection
        self._line = line
        self._col = col

    def get_text(self) -> str:
        return self._text

    def selected_text(self) -> str:
        return self._selection

    def cursor_position(self):
        return (self._line, self._col)


class _TabStub:
    def __init__(self) -> None:
        self.current_file = "example.py"
        self.text_edit = _TextEditStub(
            "line1\nline2\nline3\nline4\nline5\n",
            "line2",
            1,
            2,
        )


class _MiscStub(MiscMixin):
    def __init__(self) -> None:
        self.settings = {"ai_template_nearby_lines_radius": 1, "workspace_root": "C:/work"}


class AIPhase2HelperTests(unittest.TestCase):
    def test_sanitize_memory_policy_defaults(self) -> None:
        out = AIChatDock._sanitize_memory_policy({"strict_citations_only": True})
        self.assertTrue(out["strict_citations_only"])
        self.assertFalse(out["include_current_file_auto"])
        self.assertTrue(out["allow_hidden_apply_commands"])

    def test_sanitize_context_attachments_filters_and_trims(self) -> None:
        rows = AIChatDock._sanitize_context_attachments(
            [
                {"kind": "selection", "title": "Sel", "content": "abc", "line_start": "12"},
                {"kind": "bad", "title": "Nope", "content": "x"},
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "selection")
        self.assertEqual(rows[0]["line_start"], 12)

    def test_render_ai_template_expands_phase2_variables(self) -> None:
        stub = _MiscStub()
        tab = _TabStub()
        rendered = stub._render_ai_template(
            "{file_name}|{workspace_root}|{cursor_line}:{cursor_col}|{language}\n{selection}\n{nearby_lines}",
            tab,
        )
        self.assertIn("example.py", rendered)
        self.assertIn("C:/work", rendered)
        self.assertIn("2:3", rendered)
        self.assertIn("py", rendered)
        self.assertIn("line2", rendered)
        self.assertIn("0001: line1", rendered)


if __name__ == "__main__":
    unittest.main()
