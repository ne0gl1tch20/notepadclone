from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


@dataclass
class PageLayoutConfig:
    margin_left_mm: int = 18
    margin_top_mm: int = 18
    margin_right_mm: int = 18
    margin_bottom_mm: int = 18
    header_text: str = ""
    footer_text: str = ""
    show_ruler: bool = True
    show_page_breaks: bool = True

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "PageLayoutConfig":
        return cls(
            margin_left_mm=max(5, int(settings.get("page_layout_margin_left_mm", 18))),
            margin_top_mm=max(5, int(settings.get("page_layout_margin_top_mm", 18))),
            margin_right_mm=max(5, int(settings.get("page_layout_margin_right_mm", 18))),
            margin_bottom_mm=max(5, int(settings.get("page_layout_margin_bottom_mm", 18))),
            header_text=str(settings.get("page_layout_header_text", "") or ""),
            footer_text=str(settings.get("page_layout_footer_text", "") or ""),
            show_ruler=bool(settings.get("page_layout_show_ruler", True)),
            show_page_breaks=bool(settings.get("page_layout_show_page_breaks", True)),
        )

    def apply_to_settings(self, settings: dict[str, Any]) -> None:
        settings["page_layout_margin_left_mm"] = int(self.margin_left_mm)
        settings["page_layout_margin_top_mm"] = int(self.margin_top_mm)
        settings["page_layout_margin_right_mm"] = int(self.margin_right_mm)
        settings["page_layout_margin_bottom_mm"] = int(self.margin_bottom_mm)
        settings["page_layout_header_text"] = self.header_text
        settings["page_layout_footer_text"] = self.footer_text
        settings["page_layout_show_ruler"] = bool(self.show_ruler)
        settings["page_layout_show_page_breaks"] = bool(self.show_page_breaks)


class PageLayoutDialog(QDialog):
    def __init__(self, parent, config: PageLayoutConfig) -> None:
        super().__init__(parent)
        self.setWindowTitle("Page Layout")
        self.resize(460, 280)
        self._config = config

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.left_spin = QSpinBox(self)
        self.left_spin.setRange(5, 80)
        self.left_spin.setValue(config.margin_left_mm)
        form.addRow("Left margin (mm)", self.left_spin)

        self.top_spin = QSpinBox(self)
        self.top_spin.setRange(5, 80)
        self.top_spin.setValue(config.margin_top_mm)
        form.addRow("Top margin (mm)", self.top_spin)

        self.right_spin = QSpinBox(self)
        self.right_spin.setRange(5, 80)
        self.right_spin.setValue(config.margin_right_mm)
        form.addRow("Right margin (mm)", self.right_spin)

        self.bottom_spin = QSpinBox(self)
        self.bottom_spin.setRange(5, 80)
        self.bottom_spin.setValue(config.margin_bottom_mm)
        form.addRow("Bottom margin (mm)", self.bottom_spin)

        self.header_edit = QLineEdit(self)
        self.header_edit.setText(config.header_text)
        self.header_edit.setPlaceholderText("Optional header text")
        form.addRow("Header", self.header_edit)

        self.footer_edit = QLineEdit(self)
        self.footer_edit.setText(config.footer_text)
        self.footer_edit.setPlaceholderText("Footer text, supports {page}")
        form.addRow("Footer", self.footer_edit)

        self.show_ruler_check = QCheckBox("Show ruler in Page Layout View", self)
        self.show_ruler_check.setChecked(config.show_ruler)
        form.addRow(self.show_ruler_check)

        self.show_breaks_check = QCheckBox("Render page break markers", self)
        self.show_breaks_check.setChecked(config.show_page_breaks)
        form.addRow(self.show_breaks_check)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def config(self) -> PageLayoutConfig:
        return PageLayoutConfig(
            margin_left_mm=int(self.left_spin.value()),
            margin_top_mm=int(self.top_spin.value()),
            margin_right_mm=int(self.right_spin.value()),
            margin_bottom_mm=int(self.bottom_spin.value()),
            header_text=self.header_edit.text().strip(),
            footer_text=self.footer_edit.text().strip(),
            show_ruler=bool(self.show_ruler_check.isChecked()),
            show_page_breaks=bool(self.show_breaks_check.isChecked()),
        )


def _split_keep_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n"):
        return line[:-1], "\n"
    return line, ""


def _strip_block_prefix(text: str) -> str:
    out = re.sub(r"^\s{0,3}#{1,6}\s+", "", text)
    out = re.sub(r"^\s{0,3}>\s+", "", out)
    out = re.sub(r"^\s{0,3}(\d+\.\s+|- \[ \]\s+|- \s+)", "", out)
    return out


def apply_style_to_text(
    text: str,
    style_name: str,
    selection_range: tuple[int, int, int, int] | None,
    cursor_line: int,
) -> str:
    lines = text.splitlines(keepends=True)
    if not lines:
        lines = [""]
    if selection_range is None:
        start_line = max(0, cursor_line)
        end_line = max(0, cursor_line)
    else:
        start_line = max(0, int(selection_range[0]))
        end_line = max(0, int(selection_range[2]))
    end_line = min(end_line, len(lines) - 1)

    key = style_name.strip().lower()
    if key == "code":
        body = "".join(lines[start_line : end_line + 1]).rstrip("\r\n")
        fenced = f"```\n{body}\n```"
        repl = fenced + ("\n" if end_line < len(lines) - 1 else "")
        lines[start_line : end_line + 1] = [repl]
        return "".join(lines)

    def make_prefix(content: str) -> str:
        if key == "heading1":
            return f"# {content}"
        if key == "heading2":
            return f"## {content}"
        if key == "heading3":
            return f"### {content}"
        if key == "heading4":
            return f"#### {content}"
        if key == "heading5":
            return f"##### {content}"
        if key == "heading6":
            return f"###### {content}"
        if key == "quote":
            return f"> {content}"
        return content

    for i in range(start_line, end_line + 1):
        raw = lines[i]
        content, newline = _split_keep_newline(raw)
        cleaned = _strip_block_prefix(content)
        lines[i] = make_prefix(cleaned) + newline
    return "".join(lines)


def extract_markdown_headings(text: str) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", line)
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        if title:
            headings.append((level, title))
    return headings


def build_markdown_toc(headings: list[tuple[int, str]]) -> str:
    def slugify(s: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", s).strip().lower()
        return re.sub(r"\s+", "-", slug)

    out: list[str] = []
    for level, title in headings:
        indent = "  " * max(0, level - 1)
        out.append(f"{indent}- [{title}](#{slugify(title)})")
    return "\n".join(out).strip()


def build_ruler_text(current_col_1based: int, width: int = 100) -> str:
    width = max(20, int(width))
    current_col_1based = max(1, int(current_col_1based))
    marks: list[str] = []
    for i in range(1, width + 1):
        if i % 10 == 0:
            marks.append("|")
        elif i % 5 == 0:
            marks.append("+")
        else:
            marks.append(".")
    idx = min(width, current_col_1based) - 1
    marks[idx] = "^"
    return "".join(marks)


def build_layout_html(text: str, cfg: PageLayoutConfig, *, font_family: str, font_pt: float) -> str:
    token = "__NP_PAGE_BREAK__"
    prepared = text.replace("\f", token).replace("[[PAGE_BREAK]]", token)
    escaped = html.escape(prepared)
    escaped = escaped.replace(token, "</div><div style='page-break-after:always;'></div><div>")
    escaped = escaped.replace("\r\n", "\n").replace("\n", "<br/>")
    header_html = html.escape(cfg.header_text.strip())
    footer_html = html.escape(cfg.footer_text.strip()).replace("{page}", "1")
    margin_css = (
        f"{cfg.margin_top_mm}mm {cfg.margin_right_mm}mm "
        f"{cfg.margin_bottom_mm}mm {cfg.margin_left_mm}mm"
    )
    body = (
        "<div style='border:1px solid #d9d9d9;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08);"
        f"padding:{margin_css};'>"
    )
    if header_html:
        body += f"<div style='font-size:{max(8.0, font_pt * 0.85):.1f}pt;color:#666;margin-bottom:6mm;'>{header_html}</div>"
    body += (
        f"<div style='white-space:pre-wrap;font-family:{html.escape(font_family)};"
        f"font-size:{font_pt:.2f}pt;color:#111;'>{escaped}</div>"
    )
    if footer_html:
        body += f"<div style='font-size:{max(8.0, font_pt * 0.85):.1f}pt;color:#666;margin-top:6mm;'>{footer_html}</div>"
    body += "</div>"
    return f"<html><body style='background:#f2f2f2;margin:0;padding:16px;'>{body}</body></html>"
