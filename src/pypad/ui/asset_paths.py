from __future__ import annotations

import sys
from pathlib import Path


def resolve_asset_path(*parts: str) -> Path | None:
    for root in _candidate_asset_roots():
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
    return None


def _candidate_asset_roots() -> list[Path]:
    roots: list[Path] = []

    # PyInstaller onefile extracts bundled data into _MEIPASS.
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        roots.append(Path(meipass) / "assets")

    # Dist folder layout: run.exe next to assets/.
    executable = Path(sys.executable).resolve()
    roots.append(executable.parent / "assets")

    # Development layout: <repo>/src/run.py and <repo>/assets/.
    ui_dir = Path(__file__).resolve().parent
    roots.append(ui_dir.parents[2] / "assets")

    # Backward compatibility with old icon location in source tree.
    roots.append(ui_dir / "icons")
    roots.append(ui_dir)

    return roots
