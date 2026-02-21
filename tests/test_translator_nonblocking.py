import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from notepadclone.i18n.translator import AppTranslator


class TranslatorNonBlockingTests(unittest.TestCase):
    def test_translate_returns_quickly_when_cache_miss(self) -> None:
        cache_file = ROOT / "translator_test_cache.json"
        try:
            if cache_file.exists():
                cache_file.unlink()
        except Exception:
            pass
        tr = AppTranslator(cache_file)

        def slow_remote(_text: str, _lang: str) -> str:
            time.sleep(0.5)
            return "hola"

        tr._translate_remote = slow_remote  # type: ignore[method-assign]
        start = time.perf_counter()
        out = tr.translate("hello", "es")
        elapsed = time.perf_counter() - start
        self.assertEqual(out, "hello")
        self.assertLess(elapsed, 0.1)

        deadline = time.time() + 2.0
        cached = None
        while time.time() < deadline:
            cached = tr.translate("hello", "es")
            if cached == "hola":
                break
            time.sleep(0.05)
        self.assertEqual(cached, "hola")
        try:
            if cache_file.exists():
                cache_file.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
