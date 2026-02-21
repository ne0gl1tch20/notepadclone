import sys
import time
import unittest
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notepadclone.ui.workspace_controller import WorkspaceController


class _TabWidgetStub:
    def count(self) -> int:
        return 0

    def widget(self, _index: int):
        return None


class _WindowStub:
    def __init__(self, root: str) -> None:
        self.settings = {
            "workspace_root": root,
            "workspace_show_hidden_files": False,
            "workspace_follow_symlinks": False,
            "workspace_max_scan_files": 2000,
            "backup_output_dir": "",
        }
        self.tab_widget = _TabWidgetStub()
        self.messages: list[str] = []

    def show_status_message(self, text: str, _timeout_ms: int = 0) -> None:
        self.messages.append(text)

    def reload_tab_from_disk(self, _tab) -> None:
        return


class WorkspaceControllerTests(unittest.TestCase):
    def test_workspace_index_respects_hidden_setting(self) -> None:
        tmp_root = ROOT / "tests_tmp"
        tmp = tmp_root / f"workspace_{time.time_ns()}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp
            (base / "visible.txt").write_text("ok", encoding="utf-8")
            hidden_dir = base / ".hidden"
            hidden_dir.mkdir()
            (hidden_dir / "hidden.txt").write_text("x", encoding="utf-8")
            window = _WindowStub(str(base))
            controller = WorkspaceController(window)
            controller._start_background_scan(force=True)
            deadline = time.time() + 5
            while not controller._index_ready and time.time() < deadline:
                time.sleep(0.05)
            files = controller.workspace_files()
            joined = "\n".join(files)
            self.assertIn("visible.txt", joined)
            self.assertNotIn("hidden.txt", joined)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_replace_snapshot_create_and_restore(self) -> None:
        tmp_root = ROOT / "tests_tmp"
        tmp = tmp_root / f"workspace_{time.time_ns()}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            base = tmp
            file_path = base / "a.txt"
            file_path.write_text("before", encoding="utf-8")
            window = _WindowStub(str(base))
            window.settings["backup_output_dir"] = str(base)
            controller = WorkspaceController(window)
            changes = [
                {
                    "path": str(file_path),
                    "encoding": "utf-8",
                    "before": "before",
                    "after": "after",
                    "count": 1,
                    "tab": None,
                }
            ]
            snapshot = controller._create_replace_snapshot(changes)
            file_path.write_text("after", encoding="utf-8")
            restored = controller._restore_replace_snapshot(snapshot)
            self.assertEqual(restored, 1)
            self.assertEqual(file_path.read_text(encoding="utf-8"), "before")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
