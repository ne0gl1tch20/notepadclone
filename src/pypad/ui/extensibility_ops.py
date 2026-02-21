from __future__ import annotations

from dataclasses import dataclass
import ast
import re
from pathlib import Path
from typing import Any

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar


PLUGIN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")
NETWORK_IMPORT_PREFIXES = ("socket", "http", "urllib", "requests", "ftplib", "websocket")
FILE_IMPORT_PREFIXES = ("os", "pathlib", "shutil", "glob", "tempfile")
ALWAYS_BLOCKED_IMPORTS = {"ctypes", "subprocess", "importlib"}
ALWAYS_BLOCKED_CALLS = {"eval", "exec", "__import__", "compile"}


@dataclass(frozen=True)
class DiscoverableAction:
    action_id: str
    label: str
    section: str
    action: QAction
    shortcut_text: str


def _clean_action_text(text: str) -> str:
    return str(text or "").replace("&", "").strip()


def _seq_to_text(seq: QKeySequence) -> str:
    return seq.toString(QKeySequence.SequenceFormat.NativeText).strip()


def _action_shortcut_text(action: QAction) -> str:
    seqs = [_seq_to_text(x) for x in action.shortcuts() if not x.isEmpty()]
    if not seqs:
        fallback = action.shortcut()
        if not fallback.isEmpty():
            seqs = [_seq_to_text(fallback)]
    return ", ".join(s for s in seqs if s)


def _walk_menu(menu: QMenu, parent_path: str, sink: dict[int, str]) -> None:
    title = _clean_action_text(menu.title())
    path = f"{parent_path} > {title}" if parent_path and title else (title or parent_path)
    for action in menu.actions():
        try:
            sink[id(action)] = path or "Global"
            submenu = action.menu()
        except RuntimeError:
            continue
        if submenu is not None:
            _walk_menu(submenu, path, sink)


def discover_window_actions(window: Any) -> list[DiscoverableAction]:
    attr_name_by_action_id: dict[int, str] = {}
    for name, value in vars(window).items():
        if isinstance(value, QAction):
            attr_name_by_action_id[id(value)] = str(name).strip()

    section_by_action_id: dict[int, str] = {}
    menu_bar = window.menuBar() if hasattr(window, "menuBar") else None
    if isinstance(menu_bar, QMenuBar):
        for action in menu_bar.actions():
            try:
                menu = action.menu()
            except RuntimeError:
                continue
            if menu is not None:
                _walk_menu(menu, "", section_by_action_id)

    candidates: list[QAction] = []
    candidates.extend([v for v in vars(window).values() if isinstance(v, QAction)])
    try:
        candidates.extend(window.findChildren(QAction))
    except Exception:
        pass

    out: list[DiscoverableAction] = []
    seen: set[int] = set()
    for action in candidates:
        aid = id(action)
        if aid in seen:
            continue
        seen.add(aid)
        try:
            if action.isSeparator():
                continue
            label = _clean_action_text(action.text())
        except RuntimeError:
            continue
        if not label:
            continue
        action_id = action.objectName().strip() if action.objectName().strip() else attr_name_by_action_id.get(aid, "")
        if not action_id:
            action_id = f"action_{aid:x}"
        section = section_by_action_id.get(aid, "Global")
        out.append(
            DiscoverableAction(
                action_id=action_id,
                label=label,
                section=section,
                action=action,
                shortcut_text=_action_shortcut_text(action),
            )
        )
    out.sort(key=lambda x: (x.section.lower(), x.label.lower(), x.action_id.lower()))
    return out


def assess_plugin_security(
    *,
    plugin_root: Path,
    plugin_dir: Path,
    plugin_id: str,
    permissions: set[str],
) -> list[str]:
    issues: list[str] = []
    try:
        root_resolved = plugin_root.resolve()
        dir_resolved = plugin_dir.resolve()
        if root_resolved not in dir_resolved.parents:
            issues.append("Plugin directory escapes plugins root.")
    except Exception:
        issues.append("Could not resolve plugin directory safely.")
        return issues

    if plugin_dir.is_symlink():
        issues.append("Plugin directory symlink is not allowed.")
    if not PLUGIN_ID_RE.match(plugin_id):
        issues.append("Plugin id must match [a-z0-9][a-z0-9_.-]{1,63}.")

    manifest = plugin_dir / "plugin.json"
    script = plugin_dir / "plugin.py"
    if manifest.is_symlink() or script.is_symlink():
        issues.append("Symlinked plugin files are not allowed.")
    if not manifest.exists() or not script.exists():
        issues.append("plugin.json and plugin.py are required.")
        return issues
    if script.stat().st_size > 512_000:
        issues.append("plugin.py exceeds 512 KB policy limit.")

    risky_payloads = {".exe", ".dll", ".pyd", ".so", ".dylib", ".bat", ".cmd", ".ps1"}
    for child in plugin_dir.rglob("*"):
        try:
            if child.is_symlink():
                issues.append(f"Symlink payload is not allowed: {child.name}")
                break
            if child.is_file() and child.suffix.lower() in risky_payloads:
                issues.append(f"Binary/script payload blocked: {child.name}")
                break
        except Exception:
            continue

    try:
        source = script.read_text(encoding="utf-8")
    except Exception:
        issues.append("plugin.py must be valid UTF-8 text.")
        return issues
    try:
        tree = ast.parse(source)
    except Exception as exc:
        issues.append(f"plugin.py parse failed: {exc}")
        return issues

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".", 1)[0].lower())
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".", 1)[0].lower())
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in ALWAYS_BLOCKED_CALLS:
                issues.append(f"Blocked dynamic execution call: {func.id}()")

    for mod in sorted(imported):
        if mod in ALWAYS_BLOCKED_IMPORTS:
            issues.append(f"Blocked module import: {mod}")
    if "network" not in permissions:
        for mod in sorted(imported):
            if any(mod == prefix or mod.startswith(prefix + ".") for prefix in NETWORK_IMPORT_PREFIXES):
                issues.append(f"Network module import requires network permission: {mod}")
    if "file" not in permissions:
        for mod in sorted(imported):
            if any(mod == prefix or mod.startswith(prefix + ".") for prefix in FILE_IMPORT_PREFIXES):
                issues.append(f"File system module import requires file permission: {mod}")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                issues.append("open(...) requires file permission.")
                break
    return issues
