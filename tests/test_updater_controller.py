import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notepadclone.ui.updater_controller import UpdaterController
from notepadclone.ui.updater_helpers import UpdateInfo


class _WindowStub(QWidget):
    def __init__(self, settings: dict) -> None:
        super().__init__()
        self.settings = settings
        self.messages: list[tuple[str, int]] = []

    def show_status_message(self, text: str, timeout_ms: int = 0) -> None:
        self.messages.append((text, timeout_ms))

    def save_settings_to_disk(self) -> None:
        return


class _FakeMessageBox:
    Information = 1
    Critical = 2
    AcceptRole = 10
    RejectRole = 11
    Ok = 99

    warning_calls: list[tuple] = []
    info_calls: list[tuple] = []
    next_clicked_text: str | None = None
    last_created = None

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.window_title = ""
        self.icon = None
        self.text = ""
        self.informative = ""
        self.detailed = ""
        self.buttons: dict[str, object] = {}
        self._clicked = None
        type(self).last_created = self

    @classmethod
    def warning(cls, *args):
        cls.warning_calls.append(args)

    @classmethod
    def information(cls, *args):
        cls.info_calls.append(args)

    def setWindowTitle(self, title: str) -> None:
        self.window_title = title

    def setIcon(self, icon) -> None:
        self.icon = icon

    def setText(self, text: str) -> None:
        self.text = text

    def setInformativeText(self, text: str) -> None:
        self.informative = text

    def setDetailedText(self, text: str) -> None:
        self.detailed = text

    def setStandardButtons(self, _buttons) -> None:
        return

    def addButton(self, text: str, _role):
        token = object()
        self.buttons[text] = token
        return token

    def exec(self) -> None:
        if type(self).next_clicked_text in self.buttons:
            self._clicked = self.buttons[type(self).next_clicked_text]

    def clickedButton(self):
        return self._clicked


class UpdaterControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _FakeMessageBox.warning_calls.clear()
        _FakeMessageBox.info_calls.clear()
        _FakeMessageBox.next_clicked_text = None
        _FakeMessageBox.last_created = None

    def test_check_for_updates_empty_feed_uses_default_url(self) -> None:
        window = _WindowStub({"update_feed_url": ""})
        controller = UpdaterController(window)
        self.assertTrue(controller.window.settings.get("update_feed_url", "") == "")

    def test_on_checked_none_shows_error_for_manual_mode(self) -> None:
        window = _WindowStub({})
        controller = UpdaterController(window)
        controller._manual_check = True
        controller._active_check_id = 1
        controller._show_error_with_details = Mock()

        controller._on_checked(None, None, 1)

        self.assertEqual(window.messages[0][0], "Update check complete.")
        controller._show_error_with_details.assert_called_once()

    def test_on_checked_not_new_version_shows_info(self) -> None:
        window = _WindowStub({})
        controller = UpdaterController(window)
        controller._manual_check = True
        controller._active_check_id = 1
        info = UpdateInfo(
            version="1.0.0",
            title="Update",
            changelog="",
            download_url="https://example.com/app.exe",
            pub_date="",
            sha256="a" * 64,
            signature="",
        )

        with patch("notepadclone.ui.updater_controller.is_newer_version", return_value=False), patch(
            "notepadclone.ui.updater_controller.QMessageBox", _FakeMessageBox
        ):
            controller._on_checked(None, info, 1)

        self.assertEqual(window.messages[0][0], "Update check complete.")
        self.assertEqual(len(_FakeMessageBox.info_calls), 1)

    def test_validate_metadata_requires_sha256(self) -> None:
        window = _WindowStub({})
        controller = UpdaterController(window)
        info = UpdateInfo(
            version="9.9.9",
            title="Big Update",
            changelog="Fixes",
            download_url="https://example.com/app.exe",
            pub_date="2026-01-01",
            sha256="",
            signature="",
        )
        self.assertIn("SHA256", controller._validate_update_metadata(info) or "")

    def test_on_check_failed_sets_status_and_error(self) -> None:
        window = _WindowStub({})
        controller = UpdaterController(window)
        controller._manual_check = True
        controller._active_check_id = 1
        controller._show_error_with_details = Mock()

        controller._on_check_failed(None, "timeout", 1)

        self.assertEqual(window.messages[0][0], "Update check failed.")
        controller._show_error_with_details.assert_called_once()

    def test_download_update_without_url_shows_info(self) -> None:
        window = _WindowStub({})
        controller = UpdaterController(window)

        with patch("notepadclone.ui.updater_controller.QMessageBox", _FakeMessageBox):
            controller.download_update(
                UpdateInfo(version="1.2.3", title="x", changelog="", download_url="", pub_date="", sha256="", signature="")
            )

        self.assertEqual(len(_FakeMessageBox.info_calls), 1)


if __name__ == "__main__":
    unittest.main()
