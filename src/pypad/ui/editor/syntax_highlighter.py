from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter

THEME_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "keyword": "#5b2c6f",
        "string": "#1f618d",
        "comment": "#7f8c8d",
        "number": "#b03a2e",
    },
    "high_contrast": {
        "keyword": "#5a00ff",
        "string": "#0057d8",
        "comment": "#3f3f3f",
        "number": "#b00020",
    },
    "solarized_light": {
        "keyword": "#6c71c4",
        "string": "#2aa198",
        "comment": "#93a1a1",
        "number": "#dc322f",
    },
}
STYLE_LANGUAGES: tuple[str, ...] = ("python", "javascript", "json", "markdown", "plain")
STYLE_TOKENS: tuple[str, ...] = ("keyword", "string", "comment", "number")


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class CodeSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(
        self,
        document,
        language: str = "plain",
        *,
        style_theme: str = "default",
        style_overrides: dict[str, dict[str, str]] | None = None,
    ) -> None:
        super().__init__(document)
        self.language = language
        self.style_theme = str(style_theme or "default").strip().lower()
        self.style_overrides = self._sanitize_style_overrides(style_overrides or {})
        self._rules_by_lang: dict[str, list[tuple[re.Pattern, QTextCharFormat]]] = {}
        self._md_fence_lang: str = ""
        self._build_rules()

    def set_language(self, language: str) -> None:
        self.language = language
        self._build_rules()
        self.rehighlight()

    def set_style_profile(self, *, style_theme: str, style_overrides: dict[str, dict[str, str]]) -> None:
        self.style_theme = str(style_theme or "default").strip().lower()
        self.style_overrides = self._sanitize_style_overrides(style_overrides)
        self._build_rules()
        self.rehighlight()

    @staticmethod
    def _sanitize_style_overrides(raw: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        if not isinstance(raw, dict):
            return out
        for lang, payload in raw.items():
            language = str(lang or "").strip().lower()
            if language not in STYLE_LANGUAGES or not isinstance(payload, dict):
                continue
            token_map: dict[str, str] = {}
            for token, color in payload.items():
                key = str(token or "").strip().lower()
                if key not in STYLE_TOKENS:
                    continue
                text = str(color or "").strip()
                if not text.startswith("#"):
                    text = f"#{text}"
                if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
                    token_map[key] = text.lower()
            if token_map:
                out[language] = token_map
        return out

    def _style_color(self, language: str, token: str) -> str:
        theme = self.style_theme if self.style_theme in THEME_PRESETS else "default"
        fallback = THEME_PRESETS[theme][token]
        language_key = str(language or "plain").strip().lower()
        if language_key not in STYLE_LANGUAGES:
            language_key = "plain"
        language_overrides = self.style_overrides.get(language_key, {})
        shared_overrides = self.style_overrides.get("plain", {})
        return str(language_overrides.get(token) or shared_overrides.get(token) or fallback)

    def _build_rules(self) -> None:
        self._rules_by_lang = {"plain": []}

        py_keyword_fmt = _fmt(self._style_color("python", "keyword"), bold=True)
        py_string_fmt = _fmt(self._style_color("python", "string"))
        py_comment_fmt = _fmt(self._style_color("python", "comment"), italic=True)
        py_number_fmt = _fmt(self._style_color("python", "number"))

        rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del", "elif", "else",
            "except", "False", "finally", "for", "from", "global", "if", "import", "in",
            "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return",
            "True", "try", "while", "with", "yield",
        ]
        for word in keywords:
            rules.append((re.compile(rf"\\b{word}\\b"), py_keyword_fmt))
        rules.append((re.compile(r"#.*"), py_comment_fmt))
        rules.append((re.compile(r"('''[\\s\\S]*?'''|\"\"\"[\\s\\S]*?\"\"\")"), py_string_fmt))
        rules.append((re.compile(r"('([^'\\\\]|\\\\.)*'|\"([^\"\\\\]|\\\\.)*\")"), py_string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), py_number_fmt))
        self._rules_by_lang["python"] = rules

        js_keyword_fmt = _fmt(self._style_color("javascript", "keyword"), bold=True)
        js_string_fmt = _fmt(self._style_color("javascript", "string"))
        js_comment_fmt = _fmt(self._style_color("javascript", "comment"), italic=True)
        js_number_fmt = _fmt(self._style_color("javascript", "number"))
        rules = []
        keywords = [
            "break", "case", "catch", "class", "const", "continue", "debugger", "default",
            "delete", "do", "else", "export", "extends", "false", "finally", "for", "function",
            "if", "import", "in", "instanceof", "let", "new", "null", "return", "super",
            "switch", "this", "throw", "true", "try", "typeof", "var", "void", "while", "with",
            "yield",
        ]
        for word in keywords:
            rules.append((re.compile(rf"\\b{word}\\b"), js_keyword_fmt))
        rules.append((re.compile(r"//.*"), js_comment_fmt))
        rules.append((re.compile(r"/\\*[\\s\\S]*?\\*/"), js_comment_fmt))
        rules.append((re.compile(r"('([^'\\\\]|\\\\.)*'|\"([^\"\\\\]|\\\\.)*\"|`([^`\\\\]|\\\\.)*`)"), js_string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), js_number_fmt))
        self._rules_by_lang["javascript"] = rules

        json_keyword_fmt = _fmt(self._style_color("json", "keyword"), bold=True)
        json_string_fmt = _fmt(self._style_color("json", "string"))
        json_number_fmt = _fmt(self._style_color("json", "number"))
        rules = []
        rules.append((re.compile(r"\"(\\\\.|[^\"])*\"(?=\\s*:)"), json_keyword_fmt))
        rules.append((re.compile(r"\"(\\\\.|[^\"])*\""), json_string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), json_number_fmt))
        rules.append((re.compile(r"\\b(true|false|null)\\b"), json_keyword_fmt))
        self._rules_by_lang["json"] = rules

        md_keyword_fmt = _fmt(self._style_color("markdown", "keyword"), bold=True)
        md_string_fmt = _fmt(self._style_color("markdown", "string"))
        md_comment_fmt = _fmt(self._style_color("markdown", "comment"), italic=True)
        rules = []
        rules.append((re.compile(r"^#{1,6} .*$"), md_keyword_fmt))
        rules.append((re.compile(r"`{1,3}[^`]+`{1,3}"), md_string_fmt))
        rules.append((re.compile(r"\\*\\*[^*]+\\*\\*"), md_keyword_fmt))
        rules.append((re.compile(r"\\*[^*]+\\*"), md_comment_fmt))
        self._rules_by_lang["markdown"] = rules

    def _apply_rules(self, text: str, language: str) -> None:
        rules = self._rules_by_lang.get(language, self._rules_by_lang["plain"])
        for pattern, fmt in rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

    def highlightBlock(self, text: str) -> None:
        language = self.language.lower()
        if language in {"markdown", "md"}:
            in_code = self.previousBlockState() == 1
            fence_match = re.match(r"^\\s*```\\s*([A-Za-z0-9_-]+)?\\s*$", text)
            if fence_match:
                self._md_fence_lang = (fence_match.group(1) or "").lower()
                self.setCurrentBlockState(0 if in_code else 1)
                self._apply_rules(text, "markdown")
                return

            if in_code:
                self.setCurrentBlockState(1)
                code_lang = self._md_fence_lang or "plain"
                self._apply_rules(text, code_lang)
                return

            self.setCurrentBlockState(0)
            self._apply_rules(text, "markdown")
            return

        self._apply_rules(text, language)
