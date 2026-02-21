import sys
import unittest
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notepadclone.ui.note_crypto import decrypt_text
from notepadclone.ui.security_controller import SecurityController


class _TextEditStub:
    def __init__(self, text: str) -> None:
        self._text = text
        self.modified = False

    def get_text(self) -> str:
        return self._text

    def set_modified(self, value: bool) -> None:
        self.modified = value


class _TabStub:
    def __init__(self, text: str) -> None:
        self.text_edit = _TextEditStub(text)
        self.encryption_enabled = False
        self.encryption_password = None


class _WindowStub:
    pass


class SecurityControllerTests(unittest.TestCase):
    def test_build_payload_plain(self) -> None:
        controller = SecurityController(_WindowStub())
        tab = _TabStub("hello")
        self.assertEqual(controller.build_payload_for_save(tab), "hello")

    def test_build_payload_encrypted_roundtrip(self) -> None:
        controller = SecurityController(_WindowStub())
        tab = _TabStub("secret body")
        tab.encryption_enabled = True
        tab.encryption_password = "pw123"
        payload = controller.build_payload_for_save(tab)
        self.assertIsInstance(payload, str)
        self.assertEqual(decrypt_text(payload or "", "pw123"), "secret body")

    def test_load_text_from_encrypted_path(self) -> None:
        controller = SecurityController(_WindowStub())
        controller.prompt_password = lambda _title, _label: "pw123"
        tab = _TabStub("from file")
        tab.encryption_enabled = True
        tab.encryption_password = "pw123"
        payload = controller.build_payload_for_save(tab)
        self.assertIsNotNone(payload)
        tmp_root = ROOT / "tests_tmp"
        tmp = tmp_root / f"security_{time.time_ns()}"
        tmp.mkdir(parents=True, exist_ok=True)
        try:
            path = tmp / "note.encnote"
            path.write_text(payload or "", encoding="utf-8")
            text, encrypted, password = controller.load_text_from_path(str(path))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(text, "from file")
        self.assertTrue(encrypted)
        self.assertEqual(password, "pw123")


if __name__ == "__main__":
    unittest.main()
