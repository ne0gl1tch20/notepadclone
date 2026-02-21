from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class LineRef:
    kind: str
    line_no: int
    style_id: int | None
    text: str


@dataclass
class RegexFilterResult:
    total_matches: int
    filtered_matches: int
    preview_lines: list[str]
    replaced_text: str


def _line_span(source: str, start: int, end: int) -> tuple[int, int, str]:
    line_start = source.rfind("\n", 0, start)
    line_start = 0 if line_start < 0 else line_start + 1
    line_end = source.find("\n", end)
    if line_end < 0:
        line_end = len(source)
    return line_start, line_end, source[line_start:line_end]


def build_line_refs(
    source_text: str,
    bookmarks: set[int],
    styled_lines: dict[int, int],
    *,
    include_bookmarks: bool = True,
    include_marks: bool = True,
) -> list[LineRef]:
    lines = source_text.splitlines()
    out: list[LineRef] = []
    if include_bookmarks:
        for line in sorted(int(x) for x in bookmarks if isinstance(x, int)):
            if 0 <= line < len(lines):
                out.append(LineRef(kind="bookmark", line_no=line + 1, style_id=None, text=lines[line]))
    if include_marks:
        for line, style_id in sorted(styled_lines.items()):
            if not isinstance(line, int):
                continue
            if 0 <= line < len(lines):
                try:
                    parsed_style = int(style_id)
                except Exception:
                    parsed_style = 0
                out.append(LineRef(kind="mark", line_no=line + 1, style_id=parsed_style, text=lines[line]))
    out.sort(key=lambda row: (row.line_no, row.kind != "bookmark", row.style_id or 0))
    return out


def export_line_refs_text(rows: list[LineRef]) -> str:
    lines: list[str] = ["Line | Kind | Style | Text", "---- | ---- | ----- | ----"]
    for row in rows:
        style = "" if row.style_id is None else str(row.style_id)
        lines.append(f"{row.line_no} | {row.kind} | {style} | {row.text}")
    return "\n".join(lines)


def compute_regex_filtered_replacement(
    source: str,
    pattern: str,
    replacement: str,
    *,
    flags: int = 0,
    include_pattern: str = "",
    exclude_pattern: str = "",
    max_preview_rows: int = 200,
) -> RegexFilterResult:
    rx = re.compile(pattern, flags)
    include_rx = re.compile(include_pattern, flags) if include_pattern.strip() else None
    exclude_rx = re.compile(exclude_pattern, flags) if exclude_pattern.strip() else None
    matches = list(rx.finditer(source))
    selected: list[re.Match[str]] = []
    preview: list[str] = []
    for idx, match in enumerate(matches, start=1):
        start, end = match.start(), match.end()
        _, _, line_text = _line_span(source, start, end)
        if include_rx is not None and include_rx.search(line_text) is None:
            continue
        if exclude_rx is not None and exclude_rx.search(line_text) is not None:
            continue
        selected.append(match)
        filtered_idx = len(selected)
        if len(preview) // 3 < max_preview_rows:
            line_no = source.count("\n", 0, start) + 1
            col_no = (start - source.rfind("\n", 0, start)) if source.rfind("\n", 0, start) >= 0 else start + 1
            preview.append(f"{filtered_idx}. Ln {line_no}, Col {col_no}")
            preview.append(f"   - {match.group(0)!r}")
            preview.append(f"   + {match.expand(replacement)!r}")

    pieces: list[str] = []
    last = 0
    for match in selected:
        pieces.append(source[last : match.start()])
        pieces.append(match.expand(replacement))
        last = match.end()
    pieces.append(source[last:])
    replaced = "".join(pieces)
    return RegexFilterResult(
        total_matches=len(matches),
        filtered_matches=len(selected),
        preview_lines=preview,
        replaced_text=replaced,
    )
