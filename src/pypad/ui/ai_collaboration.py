from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class CitationSnippet:
    path: str
    excerpt: str
    score: int


WORD_RE = re.compile(r"[A-Za-z0-9_]{3,}")
FENCE_RE = re.compile(r"^\s*```[\w-]*\s*|\s*```\s*$", re.MULTILINE)


def strip_model_fences(text: str) -> str:
    cleaned = FENCE_RE.sub("", text or "").strip()
    return cleaned.strip()


def paragraph_bounds(text: str, cursor_index: int) -> tuple[int, int]:
    if not text:
        return 0, 0
    idx = max(0, min(len(text), int(cursor_index)))
    start = idx
    end = idx
    while start > 0:
        if text[start - 1] == "\n" and (start - 2 < 0 or text[start - 2] == "\n"):
            break
        start -= 1
    while end < len(text):
        if text[end] == "\n" and (end + 1 >= len(text) or text[end + 1] == "\n"):
            break
        end += 1
    return start, end


def _keywords(question: str) -> set[str]:
    return {w.lower() for w in WORD_RE.findall(question or "") if len(w) >= 3}


def _line_score(line: str, keys: set[str]) -> int:
    if not line.strip():
        return 0
    lowered = line.lower()
    score = 0
    for key in keys:
        if key in lowered:
            score += 1
    return score


def _safe_read_text(path: Path) -> str:
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
    if "\x00" in raw:
        return ""
    return raw


def build_workspace_citation_snippets(
    question: str,
    file_paths: list[str],
    *,
    max_files: int = 10,
    max_lines_per_file: int = 60,
    max_total_chars: int = 24000,
) -> list[CitationSnippet]:
    keys = _keywords(question)
    scored: list[CitationSnippet] = []
    for raw_path in file_paths:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        if path.suffix.lower() not in {
            ".py",
            ".md",
            ".markdown",
            ".mdown",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".toml",
            ".ini",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".xml",
            ".csv",
            ".log",
        }:
            continue
        if path.stat().st_size > 1_000_000:
            continue
        text = _safe_read_text(path)
        if not text:
            continue
        best: list[tuple[int, int, str]] = []
        for ln, line in enumerate(text.splitlines(), start=1):
            s = _line_score(line, keys) if keys else (1 if line.strip() else 0)
            if s <= 0:
                continue
            best.append((s, ln, line.rstrip()))
        if not best:
            continue
        best.sort(key=lambda row: (-row[0], row[1]))
        pick = best[:max_lines_per_file]
        excerpt = "\n".join(f"{ln:04d}: {line}" for _score, ln, line in pick)
        total_score = sum(row[0] for row in pick)
        scored.append(CitationSnippet(path=str(path), excerpt=excerpt, score=total_score))
    scored.sort(key=lambda s: (-s.score, s.path.lower()))
    out: list[CitationSnippet] = []
    used_chars = 0
    for snip in scored[:max_files]:
        blob = f"FILE: {snip.path}\n{snip.excerpt}\n"
        if used_chars + len(blob) > max_total_chars and out:
            break
        out.append(snip)
        used_chars += len(blob)
    return out


def build_project_qa_prompt(question: str, snippets: list[CitationSnippet]) -> str:
    sections: list[str] = []
    for snip in snippets:
        sections.append(f"FILE: {snip.path}\n{snip.excerpt}")
    context = "\n\n".join(sections)
    return (
        "Answer the question using only the provided file excerpts. "
        "Cite concrete evidence inline using this format: [file:<path>#line:<line>]. "
        "If evidence is insufficient, say what is missing.\n\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"EXCERPTS:\n{context}"
    )


def build_collab_presence_text(snapshot: dict) -> str:
    running = bool(snapshot.get("running", False))
    if not running:
        return "Collaboration server is not running."
    lines = [
        f"Running: yes",
        f"Read/Write: {'yes' if snapshot.get('rw') else 'no'}",
        f"Revision: {int(snapshot.get('revision', 0))}",
        f"Connected clients: {int(snapshot.get('clients', 0))}",
    ]
    client_rows = snapshot.get("client_rows", [])
    if isinstance(client_rows, list) and client_rows:
        lines.append("")
        lines.append("Clients:")
        for row in client_rows:
            lines.append(f"- {row}")
    return "\n".join(lines)


def build_ai_conflict_merge_prompt(local_text: str, shared_text: str) -> str:
    return (
        "Merge the two document versions into one coherent result. "
        "Preserve intent from both where possible. Prefer the most recent and specific details. "
        "Return only merged document text, no commentary.\n\n"
        "LOCAL VERSION:\n"
        f"{local_text[:30000]}\n\n"
        "SHARED VERSION:\n"
        f"{shared_text[:30000]}"
    )


def build_conflict_markers(local_text: str, shared_text: str) -> str:
    if local_text == shared_text:
        return local_text
    return (
        "<<<<<<< LOCAL\n"
        f"{local_text.rstrip()}\n"
        "=======\n"
        f"{shared_text.rstrip()}\n"
        ">>>>>>> SHARED\n"
    )
