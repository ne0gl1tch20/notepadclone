import shutil
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from pypad.ui.main_window.misc import MiscMixin
except ModuleNotFoundError:
    from notepadclone.ui.main_window.misc import MiscMixin

MISC_MODULE = MiscMixin.__module__


class _TextEditStub:
    def __init__(self, text: str) -> None:
        self._text = text
        self._modified = True

    def is_modified(self) -> bool:
        return self._modified

    def set_modified(self, value: bool) -> None:
        self._modified = bool(value)

    def get_text(self) -> str:
        return self._text


class _EditorTabStub:
    def __init__(self, autosave_path: str) -> None:
        self.text_edit = _TextEditStub("autosaved text")
        self.large_file = False
        self.current_file = ""
        self.autosave_id = "tab-1"
        self.autosave_path = autosave_path


class _TabWidgetStub:
    def __init__(self, tabs: list[_EditorTabStub]) -> None:
        self._tabs = tabs

    def count(self) -> int:
        return len(self._tabs)

    def widget(self, index: int):
        return self._tabs[index]


class _AutoSaveStoreStub:
    def __init__(self) -> None:
        self.upserts = 0
        self.saves = 0

    def upsert(self, **_kwargs) -> None:
        self.upserts += 1

    def save(self) -> None:
        self.saves += 1


class _LabelStub:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, value: str) -> None:
        self.text = value


class _WindowStub(MiscMixin):
    def __init__(self, tab: _EditorTabStub) -> None:
        self.settings = {"autosave_enabled": True}
        self.tab_widget = _TabWidgetStub([tab])
        self.autosave_store = _AutoSaveStoreStub()
        self.autosave_status_label = _LabelStub()
        self.action_state_updates = 0
        self.window_title_updates = 0
        self.status_updates = 0

    def _ensure_tab_autosave_meta(self, _tab: _EditorTabStub) -> None:
        return

    def _tab_display_name(self, _tab: _EditorTabStub) -> str:
        return "Doc"

    def _persist_tab_local_history(self, _tab: _EditorTabStub) -> None:
        return

    def _capture_crash_snapshot(self) -> None:
        return

    def update_action_states(self) -> None:
        self.action_state_updates += 1

    def update_window_title(self) -> None:
        self.window_title_updates += 1

    def update_status_bar(self) -> None:
        self.status_updates += 1


class AutoSaveCycleTests(unittest.TestCase):
    def test_autosave_marks_tab_saved(self) -> None:
        tmp_root = Path(__file__).resolve().parents[1] / "tests_tmp"
        tmp = tmp_root / f"autosave_cycle_{time.time_ns()}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            autosave_path = str(tmp / "tab-1.autosave.txt")
            tab = _EditorTabStub(autosave_path)
            window = _WindowStub(tab)
            with patch(f"{MISC_MODULE}.EditorTab", _EditorTabStub):
                window._run_autosave_cycle()

            self.assertFalse(tab.text_edit.is_modified())
            self.assertEqual(window.autosave_store.upserts, 1)
            self.assertEqual(window.autosave_store.saves, 1)
            self.assertEqual(Path(autosave_path).read_text(encoding="utf-8"), "autosaved text")
            self.assertTrue(window.autosave_status_label.text.startswith("Autosaved at "))
            self.assertEqual(window.action_state_updates, 1)
            self.assertEqual(window.window_title_updates, 1)
            self.assertEqual(window.status_updates, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
