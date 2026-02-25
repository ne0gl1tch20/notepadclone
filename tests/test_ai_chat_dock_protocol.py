import base64
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pypad.ui.ai_chat_dock import AIChatDock


def _b64_json(obj: dict) -> str:
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "base64:" + base64.b64encode(raw).decode("ascii")


class AIChatDockProtocolTests(unittest.TestCase):
    def test_extract_hidden_commands_parses_insert_set_file_title_patch_and_action(self) -> None:
        patch_payload = {
            "format": "unified_diff",
            "target": "current_tab",
            "scope": "whole_file",
            "base_text_hash": "a" * 64,
            "diff": "@@ -1 +1 @@\n-old\n+new\n",
            "summary": "Update line",
        }
        action_payload = {
            "action_id": "open_settings",
            "args": {"section": "layout"},
            "label": "Open Layout Settings",
            "summary": "Open layout preferences",
            "requires_confirmation": True,
        }
        title_b64 = base64.b64encode("Chat Title".encode("utf-8")).decode("ascii")
        text = "\n".join(
            [
                "Visible summary",
                "[PYPAD_CMD_OFFER_INSERT_BEGIN]",
                "base64:" + base64.b64encode("insert me".encode("utf-8")).decode("ascii"),
                "[PYPAD_CMD_OFFER_INSERT_END]",
                "[PYPAD_CMD_SET_FILE_BEGIN]",
                "base64:" + base64.b64encode("full file".encode("utf-8")).decode("ascii"),
                "[PYPAD_CMD_SET_FILE_END]",
                "[PYPAD_CMD_SET_CHAT_TITLE_BEGIN]",
                f"base64:{title_b64}",
                "[PYPAD_CMD_SET_CHAT_TITLE_END]",
                "[PYPAD_CMD_OFFER_PATCH_BEGIN]",
                _b64_json(patch_payload),
                "[PYPAD_CMD_OFFER_PATCH_END]",
                "[PYPAD_CMD_PROPOSE_ACTION_BEGIN]",
                _b64_json(action_payload),
                "[PYPAD_CMD_PROPOSE_ACTION_END]",
            ]
        )
        clean, insert_text, set_file_text, chat_title, patch_offer, action_offer = AIChatDock._extract_hidden_commands(text)
        self.assertEqual(clean, "Visible summary")
        self.assertEqual(insert_text, "insert me")
        self.assertEqual(set_file_text, "full file")
        self.assertEqual(chat_title, "Chat Title")
        self.assertIsInstance(patch_offer, dict)
        self.assertEqual(patch_offer["scope"], "whole_file")
        self.assertIsInstance(action_offer, dict)
        self.assertEqual(action_offer["action_id"], "open_settings")

    def test_extract_hidden_commands_ignores_malformed_patch_payload(self) -> None:
        text = "\n".join(
            [
                "Visible text",
                "[PYPAD_CMD_OFFER_PATCH_BEGIN]",
                "base64:not-valid-b64!",
                "[PYPAD_CMD_OFFER_PATCH_END]",
            ]
        )
        clean, insert_text, set_file_text, chat_title, patch_offer, action_offer = AIChatDock._extract_hidden_commands(text)
        self.assertEqual(clean, "Visible text")
        self.assertEqual(insert_text, "")
        self.assertEqual(set_file_text, "")
        self.assertEqual(chat_title, "")
        self.assertIsNone(patch_offer)
        self.assertIsNone(action_offer)

    def test_extract_hidden_commands_accepts_off_insert_alias(self) -> None:
        insert_b64 = base64.b64encode("essay text".encode("utf-8")).decode("ascii")
        text = "\n".join(
            [
                "Visible text",
                "[PYPAD_CMD_OFF_INSERT_BEGIN]",
                f"base64:{insert_b64}",
                "[PYPAD_CMD_OFF_INSERT_END]",
            ]
        )
        clean, insert_text, set_file_text, chat_title, patch_offer, action_offer = AIChatDock._extract_hidden_commands(text)
        self.assertEqual(clean, "Visible text")
        self.assertEqual(insert_text, "essay text")
        self.assertEqual(set_file_text, "")
        self.assertEqual(chat_title, "")
        self.assertIsNone(patch_offer)
        self.assertIsNone(action_offer)

    def test_apply_unified_diff_to_text(self) -> None:
        original = "alpha\nbeta\ngamma\n"
        diff_text = (
            "--- a.txt\n"
            "+++ b.txt\n"
            "@@ -1,3 +1,3 @@\n"
            " alpha\n"
            "-beta\n"
            "+BETA\n"
            " gamma\n"
        )
        out = AIChatDock._apply_unified_diff_to_text(original, diff_text)
        self.assertEqual(out, "alpha\nBETA\ngamma\n")

    def test_parse_proposed_action_rejects_unknown_action(self) -> None:
        payload = _b64_json({"action_id": "shell_exec", "args": {"cmd": "rm -rf /"}})
        self.assertIsNone(AIChatDock._parse_proposed_action(payload))


if __name__ == "__main__":
    unittest.main()
