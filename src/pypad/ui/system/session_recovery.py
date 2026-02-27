from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class RecoveryStateStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = self.base_dir / "crash_session_snapshot.json"
        self.local_history_path = self.base_dir / "local_history_index.json"

    def save_crash_snapshot(
        self,
        *,
        tabs: list[dict[str, str]],
        active_file: str,
        workspace_root: str,
    ) -> None:
        payload = {
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "active_file": active_file,
            "workspace_root": workspace_root,
            "tabs": tabs,
        }
        _atomic_write_json(self.snapshot_path, payload)

    def load_crash_snapshot(self) -> dict[str, Any] | None:
        if not self.snapshot_path.exists():
            return None
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        tabs = payload.get("tabs", [])
        if not isinstance(tabs, list):
            return None
        return payload

    def clear_crash_snapshot(self) -> None:
        try:
            if self.snapshot_path.exists():
                self.snapshot_path.unlink()
        except Exception:
            pass

    def load_local_history(self) -> dict[str, list[dict[str, str]]]:
        if not self.local_history_path.exists():
            return {}
        try:
            payload = json.loads(self.local_history_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        out: dict[str, list[dict[str, str]]] = {}
        for key, items in payload.items():
            if not isinstance(key, str) or not isinstance(items, list):
                continue
            cleaned: list[dict[str, str]] = []
            for row in items:
                if not isinstance(row, dict):
                    continue
                text = str(row.get("text", ""))
                if text == "":
                    continue
                cleaned.append(
                    {
                        "timestamp": str(row.get("timestamp", "")),
                        "label": str(row.get("label", "Snapshot")),
                        "text": text,
                    }
                )
            if cleaned:
                out[key] = cleaned
        return out

    def save_local_history(self, payload: dict[str, list[dict[str, str]]]) -> None:
        _atomic_write_json(self.local_history_path, payload)

    def prune_local_history(self, max_keys: int, max_entries_per_key: int) -> None:
        data = self.load_local_history()
        if not data:
            return
        max_keys = max(20, int(max_keys))
        max_entries_per_key = max(5, int(max_entries_per_key))
        trimmed: dict[str, list[dict[str, str]]] = {}
        keys = sorted(data.keys())
        if len(keys) > max_keys:
            keys = keys[-max_keys:]
        for key in keys:
            entries = data.get(key, [])
            trimmed[key] = entries[-max_entries_per_key:]
        self.save_local_history(trimmed)


def local_history_key(file_path: str | None, autosave_id: str | None, title: str) -> str:
    if file_path:
        return f"file:{file_path}"
    if autosave_id:
        return f"autosave:{autosave_id}"
    return f"title:{title.strip().lower() or 'untitled'}"

