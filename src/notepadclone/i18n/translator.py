from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


_LANGUAGE_OPTIONS: list[tuple[str, str]] = [
    ("English", "en"),
    ("Español", "es"),
    ("Deutsch", "de"),
    ("Français", "fr"),
    ("Italiano", "it"),
    ("Português", "pt"),
    ("Русский", "ru"),
    ("日本語", "ja"),
    ("한국어", "ko"),
    ("中文 (简体)", "zh-cn"),
    ("Hindi", "hi"),
    ("العربية", "ar"),
]


def get_language_display_options() -> list[str]:
    return [label for label, _ in _LANGUAGE_OPTIONS]


def language_code_for(label: str) -> str:
    normalized = (label or "").strip()
    if not normalized:
        return "en"
    for display, code in _LANGUAGE_OPTIONS:
        if normalized.lower() == display.lower():
            return code
    if len(normalized) <= 5 and normalized.replace("-", "").isalpha():
        return normalized.lower()
    return "en"


class AppTranslator:
    def __init__(self, cache_path: Path) -> None:
        self._cache_path = Path(cache_path)
        self._cache: dict[str, dict[str, str]] = {}
        self._loaded = False
        self._translator = None

    def clear_cache(self) -> None:
        self._cache = {}
        self._loaded = True
        try:
            self._cache_path.unlink(missing_ok=True)
        except OSError:
            pass

    def translate(self, text: str, target_lang: str) -> str:
        if not text:
            return text
        target = (target_lang or "").strip().lower()
        if not target or target in {"en", "english"}:
            return text
        self._load_cache()
        bucket = self._cache.setdefault(target, {})
        cached = bucket.get(text)
        if cached:
            return cached
        translated = self._translate_remote(text, target)
        if translated and translated != text:
            bucket[text] = translated
            self._save_cache()
            return translated
        return text

    def translate_many(self, values: Iterable[str], target_lang: str) -> list[str]:
        return [self.translate(value, target_lang) for value in values]

    def _load_cache(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            if self._cache_path.exists():
                with open(self._cache_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    normalized: dict[str, dict[str, str]] = {}
                    for lang, mapping in data.items():
                        if isinstance(mapping, dict):
                            normalized[str(lang)] = {
                                str(src): str(dst) for src, dst in mapping.items() if isinstance(src, str)
                            }
                    self._cache = normalized
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as handle:
                json.dump(self._cache, handle, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _translate_remote(self, text: str, target_lang: str) -> str:
        try:
            if self._translator is None:
                from googletrans import Translator  # type: ignore

                self._translator = Translator()
            result = self._translator.translate(text, dest=target_lang)
            return str(getattr(result, "text", "")) or text
        except Exception:
            return text
