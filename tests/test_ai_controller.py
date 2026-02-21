import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notepadclone.ui.ai_controller import AIController, _generate_sync, sanitize_prompt_text


class _WindowStub:
    def __init__(self, settings: dict) -> None:
        self.settings = settings
        self.toggled = None

    def toggle_ai_chat_panel(self, visible: bool) -> None:
        self.toggled = visible


class AIControllerTests(unittest.TestCase):
    def test_api_key_prefers_settings_value(self) -> None:
        window = _WindowStub({"gemini_api_key": "from_settings"})
        controller = AIController(window)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "from_env"}, clear=False):
            self.assertEqual(controller._api_key(), "from_settings")

    def test_api_key_falls_back_to_env(self) -> None:
        window = _WindowStub({"gemini_api_key": ""})
        controller = AIController(window)
        with patch.dict(os.environ, {"GEMINI_API_KEY": "from_env"}, clear=False):
            self.assertEqual(controller._api_key(), "from_env")

    def test_generate_sync_requires_api_key(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            _generate_sync("hello", "", "gemini-3-flash-preview")
        self.assertIn("I don't have an API key", str(ctx.exception))

    def test_generate_sync_uses_google_genai_path(self) -> None:
        class _FakeResponse:
            text = "OK"

        class _FakeModels:
            def generate_content(self, *, model: str, contents: str) -> _FakeResponse:
                self.model = model
                self.contents = contents
                return _FakeResponse()

        class _FakeClient:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                self.models = _FakeModels()

        fake_genai = types.SimpleNamespace(Client=_FakeClient)
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        with patch.dict(sys.modules, {"google": fake_google}, clear=False):
            out = _generate_sync("Reply", "k", "m")
        self.assertEqual(out, "OK")

    def test_generate_sync_falls_back_to_legacy_sdk(self) -> None:
        class _BrokenClient:
            def __init__(self, api_key: str) -> None:
                raise RuntimeError("primary failed")

        fake_genai = types.SimpleNamespace(Client=_BrokenClient)
        fake_google = types.ModuleType("google")
        fake_google.__path__ = []
        fake_google.genai = fake_genai

        class _LegacyResponse:
            text = "LEGACY_OK"

        class _LegacyModel:
            def __init__(self, model_name: str) -> None:
                self.model_name = model_name

            def generate_content(self, prompt: str) -> _LegacyResponse:
                self.prompt = prompt
                return _LegacyResponse()

        fake_legacy = types.ModuleType("google.generativeai")
        fake_legacy.configure = lambda api_key: None
        fake_legacy.GenerativeModel = _LegacyModel

        with patch.dict(
            sys.modules,
            {
                "google": fake_google,
                "google.generativeai": fake_legacy,
            },
            clear=False,
        ):
            out = _generate_sync("Reply", "k", "m")
        self.assertEqual(out, "LEGACY_OK")

    def test_ask_ai_opens_chat_panel_when_available(self) -> None:
        window = _WindowStub({"gemini_api_key": ""})
        controller = AIController(window)
        controller.ask_ai()
        self.assertTrue(window.toggled)

    def test_cancel_active_chat_request_without_stream_returns_false(self) -> None:
        window = _WindowStub({"gemini_api_key": ""})
        controller = AIController(window)
        self.assertFalse(controller.cancel_active_chat_request())

    def test_sanitize_prompt_redacts_emails_paths_and_tokens(self) -> None:
        prompt = (
            "Email me at a@b.com\n"
            "Path: C:\\Users\\me\\secret.txt and /home/me/token.txt\n"
            "api_key=abcd1234\n"
            "Bearer abcdefghijklmnop"
        )
        redacted, changes = sanitize_prompt_text(
            prompt,
            {
                "ai_send_redact_emails": True,
                "ai_send_redact_paths": True,
                "ai_send_redact_tokens": True,
            },
        )
        self.assertIn("[REDACTED_EMAIL]", redacted)
        self.assertIn("[REDACTED_PATH]", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)
        self.assertTrue(changes)


if __name__ == "__main__":
    unittest.main()
