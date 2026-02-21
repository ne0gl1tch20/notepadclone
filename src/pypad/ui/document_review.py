from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


_INS_RE = re.compile(r"\[\[INS:([A-Za-z0-9_-]+)\|([^\]]*)\]\](.*?)\[\[/INS:\1\]\]", re.DOTALL)
_DEL_RE = re.compile(r"\[\[DEL:([A-Za-z0-9_-]+)\|([^\]]*)\]\](.*?)\[\[/DEL:\1\]\]", re.DOTALL)
_CMT_ANCHOR_RE = re.compile(r"\[\[CMTREF:([A-Za-z0-9_-]+)\]\](.*?)\[\[/CMTREF:\1\]\]", re.DOTALL)
_COMMENTS_BLOCK_RE = re.compile(
    r"(?s)\n?<!-- COMMENTS START -->\n(.*?)\n<!-- COMMENTS END -->\n?"
)
_COMMENT_LINE_RE = re.compile(r"^- ([A-Za-z0-9_-]+) \| ([^|]*) \| ([^|]*) \| (.*)$")


@dataclass
class TrackedChange:
    change_id: str
    kind: str
    meta: str
    content: str
    start: int
    end: int


@dataclass
class CommentEntry:
    comment_id: str
    author: str
    timestamp: str
    comment: str
    anchor_preview: str
    anchor_start: int
    anchor_end: int


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _change_id() -> str:
    return uuid.uuid4().hex[:10]


def _scan_changes(text: str) -> list[TrackedChange]:
    out: list[TrackedChange] = []
    for match in _INS_RE.finditer(text):
        out.append(
            TrackedChange(
                change_id=match.group(1),
                kind="ins",
                meta=match.group(2),
                content=match.group(3),
                start=match.start(),
                end=match.end(),
            )
        )
    for match in _DEL_RE.finditer(text):
        out.append(
            TrackedChange(
                change_id=match.group(1),
                kind="del",
                meta=match.group(2),
                content=match.group(3),
                start=match.start(),
                end=match.end(),
            )
        )
    out.sort(key=lambda item: item.start)
    return out


def has_tracked_changes(text: str) -> bool:
    return bool(_INS_RE.search(text) or _DEL_RE.search(text))


def insert_tracked_insertion(text: str, index: int, content: str, author: str) -> tuple[str, str]:
    token_id = _change_id()
    meta = f"{author.strip() or 'author'}@{_ts()}"
    wrapped = f"[[INS:{token_id}|{meta}]]{content}[[/INS:{token_id}]]"
    idx = max(0, min(len(text), int(index)))
    return text[:idx] + wrapped + text[idx:], token_id


def mark_tracked_deletion(
    text: str,
    start: int,
    end: int,
    author: str,
) -> tuple[str, str] | None:
    lo = max(0, min(int(start), int(end)))
    hi = max(0, max(int(start), int(end)))
    if lo >= hi:
        return None
    token_id = _change_id()
    meta = f"{author.strip() or 'author'}@{_ts()}"
    removed = text[lo:hi]
    wrapped = f"[[DEL:{token_id}|{meta}]]{removed}[[/DEL:{token_id}]]"
    return text[:lo] + wrapped + text[hi:], token_id


def next_change_span(text: str, cursor_index: int) -> tuple[int, int, str, str] | None:
    idx = max(0, int(cursor_index))
    changes = _scan_changes(text)
    for change in changes:
        if change.start >= idx:
            return change.start, change.end, change.kind, change.change_id
    if changes:
        first = changes[0]
        return first.start, first.end, first.kind, first.change_id
    return None


def _change_at_cursor(text: str, cursor_index: int) -> TrackedChange | None:
    idx = max(0, int(cursor_index))
    changes = _scan_changes(text)
    for change in changes:
        if change.start <= idx <= change.end:
            return change
    for change in changes:
        if change.start >= idx:
            return change
    return None


def accept_or_reject_change_at_cursor(
    text: str,
    cursor_index: int,
    *,
    accept: bool,
) -> tuple[str, bool, str]:
    change = _change_at_cursor(text, cursor_index)
    if change is None:
        return text, False, ""
    if accept:
        replacement = change.content if change.kind == "ins" else ""
    else:
        replacement = "" if change.kind == "ins" else change.content
    updated = text[: change.start] + replacement + text[change.end :]
    return updated, True, change.kind


def accept_all_changes(text: str) -> tuple[str, int]:
    count = len(_scan_changes(text))
    if count <= 0:
        return text, 0
    updated = _INS_RE.sub(lambda m: m.group(3), text)
    updated = _DEL_RE.sub("", updated)
    return updated, count


def reject_all_changes(text: str) -> tuple[str, int]:
    count = len(_scan_changes(text))
    if count <= 0:
        return text, 0
    updated = _INS_RE.sub("", text)
    updated = _DEL_RE.sub(lambda m: m.group(3), updated)
    return updated, count


def _parse_comments_index(text: str) -> dict[str, tuple[str, str, str]]:
    match = _COMMENTS_BLOCK_RE.search(text)
    if not match:
        return {}
    out: dict[str, tuple[str, str, str]] = {}
    for line in match.group(1).splitlines():
        m = _COMMENT_LINE_RE.match(line.strip())
        if not m:
            continue
        out[m.group(1)] = (m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
    return out


def _replace_comments_index(text: str, index: dict[str, tuple[str, str, str]]) -> str:
    if not index:
        return _COMMENTS_BLOCK_RE.sub("", text).rstrip() + ("\n" if text.endswith("\n") else "")
    lines = ["<!-- COMMENTS START -->"]
    for comment_id in sorted(index.keys()):
        author, timestamp, comment = index[comment_id]
        lines.append(f"- {comment_id} | {author} | {timestamp} | {comment}")
    lines.append("<!-- COMMENTS END -->")
    block = "\n".join(lines)
    if _COMMENTS_BLOCK_RE.search(text):
        return _COMMENTS_BLOCK_RE.sub("\n" + block + "\n", text)
    if not text.endswith("\n"):
        text += "\n"
    return text + "\n" + block + "\n"


def add_comment(text: str, start: int, end: int, comment: str, author: str) -> tuple[str, str] | None:
    lo = max(0, min(int(start), int(end)))
    hi = max(0, max(int(start), int(end)))
    if lo >= hi:
        return None
    clean = " ".join(str(comment or "").strip().split()).replace("|", "/")
    if not clean:
        return None
    comment_id = _change_id()
    wrapped = f"[[CMTREF:{comment_id}]]{text[lo:hi]}[[/CMTREF:{comment_id}]]"
    updated = text[:lo] + wrapped + text[hi:]
    index = _parse_comments_index(updated)
    index[comment_id] = (author.strip() or "author", _ts(), clean)
    return _replace_comments_index(updated, index), comment_id


def list_comments(text: str) -> list[CommentEntry]:
    index = _parse_comments_index(text)
    out: list[CommentEntry] = []
    for match in _CMT_ANCHOR_RE.finditer(text):
        comment_id = match.group(1)
        author, timestamp, comment = index.get(comment_id, ("", "", ""))
        preview = " ".join(match.group(2).strip().split())
        if len(preview) > 60:
            preview = preview[:57] + "..."
        out.append(
            CommentEntry(
                comment_id=comment_id,
                author=author,
                timestamp=timestamp,
                comment=comment,
                anchor_preview=preview,
                anchor_start=match.start(),
                anchor_end=match.end(),
            )
        )
    out.sort(key=lambda item: item.anchor_start)
    return out


def remove_comment(text: str, comment_id: str) -> tuple[str, bool]:
    cid = str(comment_id or "").strip()
    if not cid:
        return text, False
    anchor_re = re.compile(rf"\[\[CMTREF:{re.escape(cid)}\]\](.*?)\[\[/CMTREF:{re.escape(cid)}\]\]", re.DOTALL)
    updated = anchor_re.sub(lambda m: m.group(1), text)
    index = _parse_comments_index(updated)
    had_index = cid in index
    index.pop(cid, None)
    updated = _replace_comments_index(updated, index)
    return updated, bool(had_index or updated != text)


def extract_heading_targets(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", line)
        if not match:
            continue
        title = match.group(2).strip()
        if not title:
            continue
        slug = re.sub(r"\s+", "-", re.sub(r"[^a-zA-Z0-9\s-]", "", title).strip().lower())
        out.append((title, slug))
    return out


def insert_cross_reference(text: str, index: int, title: str, slug: str) -> str:
    idx = max(0, min(len(text), int(index)))
    return text[:idx] + f"[{title}](#{slug})" + text[idx:]


def _next_note_number(text: str, *, endnote: bool) -> int:
    prefix = "e" if endnote else ""
    marker_re = re.compile(rf"\[\^{prefix}(\d+)\]")
    def_re = re.compile(rf"(?m)^\[\^{prefix}(\d+)\]:")
    nums: list[int] = []
    nums.extend(int(m.group(1)) for m in marker_re.finditer(text))
    nums.extend(int(m.group(1)) for m in def_re.finditer(text))
    return (max(nums) + 1) if nums else 1


def insert_note(
    text: str,
    index: int,
    note_body: str,
    *,
    endnote: bool,
) -> tuple[str, str]:
    cleaned = " ".join(str(note_body or "").strip().split())
    if not cleaned:
        cleaned = "note"
    num = _next_note_number(text, endnote=endnote)
    prefix = "e" if endnote else ""
    marker = f"[^{prefix}{num}]"
    definition = f"[^{prefix}{num}]: {cleaned}"
    idx = max(0, min(len(text), int(index)))
    updated = text[:idx] + marker + text[idx:]
    heading = "## Endnotes" if endnote else "## Footnotes"
    if heading.lower() not in updated.lower():
        if not updated.endswith("\n"):
            updated += "\n"
        updated += f"\n{heading}\n{definition}\n"
    else:
        if not updated.endswith("\n"):
            updated += "\n"
        updated += definition + "\n"
    return updated, marker
