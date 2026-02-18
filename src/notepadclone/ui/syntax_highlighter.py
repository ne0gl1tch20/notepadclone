from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class CodeSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, language: str = "plain") -> None:
        super().__init__(document)
        self.language = language
        self._rules_by_lang: dict[str, list[tuple[re.Pattern, QTextCharFormat]]] = {}
        self._md_fence_lang: str = ""
        self._build_rules()

    def set_language(self, language: str) -> None:
        self.language = language
        self._build_rules()
        self.rehighlight()

    def _build_rules(self) -> None:
        self._rules_by_lang = {"plain": []}

        keyword_fmt = _fmt("#5b2c6f", bold=True)
        string_fmt = _fmt("#1f618d")
        comment_fmt = _fmt("#7f8c8d", italic=True)
        number_fmt = _fmt("#b03a2e")

        rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del", "elif", "else",
            "except", "False", "finally", "for", "from", "global", "if", "import", "in",
            "is", "lambda", "None", "nonlocal", "not", "or", "pass", "raise", "return",
            "True", "try", "while", "with", "yield",
        ]
        for word in keywords:
            rules.append((re.compile(rf"\\b{word}\\b"), keyword_fmt))
        rules.append((re.compile(r"#.*"), comment_fmt))
        rules.append((re.compile(r"('''[\\s\\S]*?'''|\"\"\"[\\s\\S]*?\"\"\")"), string_fmt))
        rules.append((re.compile(r"('([^'\\\\]|\\\\.)*'|\"([^\"\\\\]|\\\\.)*\")"), string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), number_fmt))
        self._rules_by_lang["python"] = rules

        rules = []
        keywords = [
            "break", "case", "catch", "class", "const", "continue", "debugger", "default",
            "delete", "do", "else", "export", "extends", "false", "finally", "for", "function",
            "if", "import", "in", "instanceof", "let", "new", "null", "return", "super",
            "switch", "this", "throw", "true", "try", "typeof", "var", "void", "while", "with",
            "yield",
        ]
        for word in keywords:
            rules.append((re.compile(rf"\\b{word}\\b"), keyword_fmt))
        rules.append((re.compile(r"//.*"), comment_fmt))
        rules.append((re.compile(r"/\\*[\\s\\S]*?\\*/"), comment_fmt))
        rules.append((re.compile(r"('([^'\\\\]|\\\\.)*'|\"([^\"\\\\]|\\\\.)*\"|`([^`\\\\]|\\\\.)*`)"), string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), number_fmt))
        self._rules_by_lang["javascript"] = rules

        rules = []
        rules.append((re.compile(r"\"(\\\\.|[^\"])*\"(?=\\s*:)"), keyword_fmt))
        rules.append((re.compile(r"\"(\\\\.|[^\"])*\""), string_fmt))
        rules.append((re.compile(r"\\b\\d+(\\.\\d+)?\\b"), number_fmt))
        rules.append((re.compile(r"\\b(true|false|null)\\b"), keyword_fmt))
        self._rules_by_lang["json"] = rules

        rules = []
        rules.append((re.compile(r"^#{1,6} .*$"), keyword_fmt))
        rules.append((re.compile(r"`{1,3}[^`]+`{1,3}"), string_fmt))
        rules.append((re.compile(r"\\*\\*[^*]+\\*\\*"), keyword_fmt))
        rules.append((re.compile(r"\\*[^*]+\\*"), comment_fmt))
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
