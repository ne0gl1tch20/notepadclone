from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DiffStats:
    added: int
    removed: int
    hunks: int


@dataclass
class LargeFilePreview:
    text: str
    is_partial: bool
    total_lines: int
    total_chars: int


def _normalize_for_diff(line: str, *, ignore_whitespace: bool) -> str:
    if not ignore_whitespace:
        return line
    return re.sub(r"\s+", " ", line).strip()


def build_unified_diff_text(
    left_text: str,
    right_text: str,
    *,
    from_label: str,
    to_label: str,
    ignore_whitespace: bool = False,
) -> str:
    left_lines = left_text.splitlines()
    right_lines = right_text.splitlines()
    if ignore_whitespace:
        left_lines = [_normalize_for_diff(line, ignore_whitespace=True) for line in left_lines]
        right_lines = [_normalize_for_diff(line, ignore_whitespace=True) for line in right_lines]
    return "\n".join(
        difflib.unified_diff(
            left_lines,
            right_lines,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
        )
    )


def diff_stats_from_patch(patch_text: str) -> DiffStats:
    added = 0
    removed = 0
    hunks = 0
    for line in patch_text.splitlines():
        if line.startswith("@@"):
            hunks += 1
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return DiffStats(added=added, removed=removed, hunks=hunks)


def apply_unified_patch_to_text(original_text: str, patch_text: str) -> str:
    src_lines = original_text.splitlines()
    out_lines: list[str] = []
    src_index = 0
    in_hunk = False
    for raw_line in patch_text.splitlines():
        if raw_line.startswith("--- ") or raw_line.startswith("+++ "):
            continue
        if raw_line.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if not raw_line:
            prefix = " "
            line = ""
        else:
            prefix = raw_line[0]
            line = raw_line[1:]
        if prefix == " ":
            if src_index >= len(src_lines) or src_lines[src_index] != line:
                raise ValueError("Patch context mismatch.")
            out_lines.append(src_lines[src_index])
            src_index += 1
        elif prefix == "-":
            if src_index >= len(src_lines) or src_lines[src_index] != line:
                raise ValueError("Patch delete mismatch.")
            src_index += 1
        elif prefix == "+":
            out_lines.append(line)
    out_lines.extend(src_lines[src_index:])
    return "\n".join(out_lines)


def read_text_with_large_file_preview(
    path: str,
    *,
    encoding: str = "utf-8",
    fast_threshold_kb: int = 8192,
    head_lines: int = 2000,
    tail_lines: int = 250,
) -> LargeFilePreview:
    p = Path(path)
    size_kb = int(p.stat().st_size / 1024)
    if size_kb < max(1, int(fast_threshold_kb)):
        full = p.read_text(encoding=encoding, errors="replace")
        return LargeFilePreview(
            text=full,
            is_partial=False,
            total_lines=full.count("\n") + 1,
            total_chars=len(full),
        )

    head_lines = max(100, int(head_lines))
    tail_lines = max(50, int(tail_lines))
    top: list[str] = []
    bottom: list[str] = []
    total_lines = 0
    total_chars = 0
    with open(p, "r", encoding=encoding, errors="replace") as handle:
        for line in handle:
            total_lines += 1
            total_chars += len(line)
            if len(top) < head_lines:
                top.append(line)
                continue
            bottom.append(line)
            if len(bottom) > tail_lines:
                bottom.pop(0)
    omitted = max(0, total_lines - len(top) - len(bottom))
    banner = (
        f"[[LARGE_FILE_PREVIEW]] path={p} size_kb={size_kb} lines={total_lines} omitted_lines={omitted}\n"
        "This is a partial preview. Use 'Load Full Large File' before editing/saving.\n\n"
    )
    text = banner + "".join(top)
    if omitted > 0:
        text += f"\n... ({omitted} lines omitted) ...\n\n"
    text += "".join(bottom)
    return LargeFilePreview(
        text=text,
        is_partial=True,
        total_lines=total_lines,
        total_chars=total_chars,
    )
