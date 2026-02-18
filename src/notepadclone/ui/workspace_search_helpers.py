from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceSearchHit:
    path: str
    line_no: int
    line_text: str


def collect_workspace_files(
    root: str,
    allowed_suffixes: set[str] | None = None,
    max_files: int = 3000,
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
        if path.suffix.lower() not in suffixes:
            continue
        files.append(str(path))
        if len(files) >= max_files:
            break
    files.sort()
    return files


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
