from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from fnmatch import fnmatch


@dataclass(frozen=True)
class WorkspaceSearchHit:
    path: str
    line_no: int
    line_text: str


def collect_workspace_files(
    root: str,
    allowed_suffixes: set[str] | None = None,
    max_files: int = 3000,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> list[str]:
    if not root:
        return []
    base = Path(root)
    if not base.exists():
        return []
    suffixes = allowed_suffixes or {".txt", ".md", ".markdown", ".mdown", ".py", ".json", ".js", ".ts", ".encnote"}
    files: list[str] = []
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.is_symlink() and not follow_symlinks:
            continue
        if not include_hidden and _is_hidden_path(path):
            continue
        if path.suffix.lower() not in suffixes:
            continue
        normalized = str(path).replace("\\", "/")
        if include_globs and not any(fnmatch(normalized, pat) for pat in include_globs):
            continue
        if exclude_globs and any(fnmatch(normalized, pat) for pat in exclude_globs):
            continue
        files.append(str(path))
        if len(files) >= max_files:
            break
    files.sort()
    return files


def _is_hidden_path(path: Path) -> bool:
    for part in path.parts:
        if part in {".", ".."}:
            continue
        if part.startswith("."):
            return True
    return False


def search_files_for_query(
    file_paths: list[str],
    query: str,
    max_results: int = 500,
    case_sensitive: bool = False,
) -> list[WorkspaceSearchHit]:
    if not query.strip():
        return []
    q = query if case_sensitive else query.lower()
    hits: list[WorkspaceSearchHit] = []
    for path in file_paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    haystack = line if case_sensitive else line.lower()
                    if q in haystack:
                        hits.append(WorkspaceSearchHit(path=path, line_no=line_no, line_text=line.rstrip("\n")))
                        if len(hits) >= max_results:
                            return hits
        except Exception:
            continue
    return hits
