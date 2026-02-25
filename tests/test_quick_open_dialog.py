import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.quick_open_dialog import (
    extract_symbol_rows,
    parse_quick_open_query,
    score_quick_open_match,
    split_workspace_symbol_scope,
)


class QuickOpenParserTests(unittest.TestCase):
    def test_parse_empty_query(self) -> None:
        q = parse_quick_open_query("")
        self.assertEqual(q.needle, "")
        self.assertIsNone(q.line)
        self.assertIsNone(q.command_query)

    def test_parse_command_query(self) -> None:
        q = parse_quick_open_query(">bookmark jump")
        self.assertEqual(q.command_query, "bookmark jump")

    def test_parse_symbol_query(self) -> None:
        q = parse_quick_open_query("@render thing")
        self.assertEqual(q.symbol_query, "render thing")

    def test_parse_workspace_symbol_query_aliases(self) -> None:
        q1 = parse_quick_open_query("@@render")
        q2 = parse_quick_open_query("@w render")
        self.assertEqual(q1.workspace_symbol_query, "render")
        self.assertEqual(q2.workspace_symbol_query, "render")

    def test_parse_workspace_symbol_scoped_query(self) -> None:
        q = parse_quick_open_query("@@models save")
        self.assertEqual(q.workspace_symbol_file_filter, "models")
        self.assertEqual(q.workspace_symbol_name_query, "save")

    def test_split_workspace_symbol_scope(self) -> None:
        self.assertEqual(split_workspace_symbol_scope("models save"), ("models", "save"))
        self.assertEqual(split_workspace_symbol_scope("onlysymbol"), (None, "onlysymbol"))

    def test_parse_current_tab_line(self) -> None:
        q = parse_quick_open_query(":42:7")
        self.assertTrue(q.current_tab_only)
        self.assertEqual(q.line, 42)
        self.assertEqual(q.col, 7)

    def test_parse_file_line_windows_path(self) -> None:
        q = parse_quick_open_query(r"C:\work\notes\todo.txt:120")
        self.assertEqual(q.needle, r"C:\work\notes\todo.txt")
        self.assertEqual(q.line, 120)
        self.assertIsNone(q.col)

    def test_parse_file_line_col(self) -> None:
        q = parse_quick_open_query("src/app.py:9:3")
        self.assertEqual(q.needle, "src/app.py")
        self.assertEqual(q.line, 9)
        self.assertEqual(q.col, 3)

    def test_score_prefers_prefix_and_subsequence(self) -> None:
        self.assertGreater(score_quick_open_match("app", "app.py"), score_quick_open_match("app", "src/app.py"))
        self.assertGreaterEqual(score_quick_open_match("sap", "src/app.py"), 0)
        self.assertLess(score_quick_open_match("zzz", "src/app.py"), 0)

    def test_extract_symbol_rows_python_and_markdown(self) -> None:
        py_rows = extract_symbol_rows("python", "class A:\n    pass\n\ndef run():\n    return 1\n")
        self.assertTrue(any("class A" in label for _, label in py_rows))
        self.assertTrue(any("def run" in label for _, label in py_rows))
        md_rows = extract_symbol_rows("markdown", "# Title\ntext\n## Sub\n")
        self.assertEqual(md_rows[0], (1, "# Title"))
        self.assertEqual(md_rows[1], (3, "## Sub"))


if __name__ == "__main__":
    unittest.main()
