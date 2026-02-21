from __future__ import annotations

import ast
import hashlib
import hmac
import json
import re
import secrets
import shutil
import sys
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from ..app_settings.paths import get_plugins_dir_path


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass
class PluginRecord:
    plugin_id: str
    name: str
    description: str
    permissions: set[str]
    path: Path
    enabled: bool
    digest: str
    quarantined: bool = False
    instance: Any = None


def compute_plugin_digest(plugin_dir: Path) -> str:
    hasher = hashlib.sha256()
    for rel in ("plugin.json", "plugin.py"):
        path = plugin_dir / rel
        if not path.exists():
            continue
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def apply_text_operations(text: str, operations: list[dict[str, Any]]) -> str:
    out = text
    for op in operations:
        kind = str(op.get("op", "")).strip().lower()
        if kind == "insert":
            index = int(op.get("index", -1))
            payload = str(op.get("text", ""))
            if index < 0 or index > len(out):
                raise ValueError("insert index out of bounds")
            out = out[:index] + payload + out[index:]
            continue
        if kind in {"delete", "replace"}:
            start = int(op.get("start", -1))
            end = int(op.get("end", -1))
            if start < 0 or end < start or end > len(out):
                raise ValueError(f"{kind} range out of bounds")
            replacement = str(op.get("text", "")) if kind == "replace" else ""
            out = out[:start] + replacement + out[end:]
            continue
        raise ValueError(f"unsupported operation: {kind}")
    return out


class PluginAPI:
    def __init__(self, window, record: PluginRecord) -> None:
        self.window = window
        self.record = record

    def _allow(self, perm: str) -> None:
        if perm not in self.record.permissions:
            raise RuntimeError(f"Plugin '{self.record.plugin_id}' missing permission: {perm}")

    def notify(self, text: str) -> None:
        self.window.show_status_message(f"[Plugin:{self.record.name}] {text}", 3000)

    def current_text(self) -> str:
        tab = self.window.active_tab()
        return tab.text_edit.get_text() if tab is not None else ""

    def replace_text(self, text: str) -> None:
        self._allow("file")
        tab = self.window.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.set_text(text)
        tab.text_edit.set_modified(True)

    def ask_ai(self, prompt: str) -> None:
        self._allow("ai")
        self.window.ai_controller._start_generation(prompt, "Plugin AI", action_name=f"plugin:{self.record.plugin_id}")

    def network_allowed(self) -> bool:
        self._allow("network")
        return True


class PluginHost:
    def __init__(self, window) -> None:
        self.window = window
        self.plugins_dir = get_plugins_dir_path()
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self._install_example_plugins_if_missing()
        self.records: list[PluginRecord] = []
        self.reload(startup=True)

    def _packaged_plugins_dir(self) -> Path:
        if getattr(sys, "frozen", False):
            meipass = Path(str(getattr(sys, "_MEIPASS", "")))
            if meipass:
                bundled = meipass / "plugins"
                if bundled.exists():
                    return bundled
        return _root() / "plugins"

    def runtime_mode_label(self) -> str:
        return "production" if getattr(sys, "frozen", False) else "development"

    def _install_example_plugins_if_missing(self) -> None:
        source_root = self._packaged_plugins_dir()
        if not source_root.exists():
            return
        for name in ("example_word_tools", "example_hello_network"):
            src_dir = source_root / name
            if not src_dir.exists() or not src_dir.is_dir():
                continue
            if not (src_dir / "plugin.json").exists() or not (src_dir / "plugin.py").exists():
                continue
            dst_dir = self.plugins_dir / name
            if dst_dir.exists():
                continue
            try:
                shutil.copytree(src_dir, dst_dir)
            except Exception as exc:  # noqa: BLE001
                self.window.log_event("Error", f"Could not install bundled example plugin {name}: {exc}")

    def _enabled(self) -> set[str]:
        return {str(x) for x in self.window.settings.get("enabled_plugins", []) if isinstance(x, str)}

    def _save_enabled(self, ids: set[str]) -> None:
        self.window.settings["enabled_plugins"] = sorted(ids)
        self.window.save_settings_to_disk()

    def _trusted_hashes(self) -> dict[str, str]:
        raw = self.window.settings.get("trusted_plugin_hashes", {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, str] = {}
        for key, value in raw.items():
            k = str(key).strip()
            v = str(value).strip().lower()
            if k and v:
                out[k] = v
        return out

    def _save_trusted_hashes(self, mapping: dict[str, str]) -> None:
        self.window.settings["trusted_plugin_hashes"] = dict(sorted(mapping.items()))
        self.window.save_settings_to_disk()

    def _quarantined(self) -> set[str]:
        raw = self.window.settings.get("quarantined_plugins", [])
        return {str(x).strip() for x in raw if str(x).strip()}

    def _save_quarantined(self, ids: set[str]) -> None:
        self.window.settings["quarantined_plugins"] = sorted(ids)
        self.window.save_settings_to_disk()

    def _is_startup_safe_mode(self) -> bool:
        return bool(self.window.settings.get("plugin_startup_safe_mode", False))

    def _trust_prompt(self, rec: PluginRecord) -> bool:
        box = QMessageBox(self.window)
        box.setWindowTitle("Trust Plugin")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"Plugin '{rec.name}' is not trusted yet.")
        box.setInformativeText("Trust this plugin hash and allow it to load?")
        box.setDetailedText(f"Plugin ID: {rec.plugin_id}\nDigest (SHA256): {rec.digest}")
        trust_btn = box.addButton("Trust and Load", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec()
        return box.clickedButton() == trust_btn

    def _is_plugin_trusted(self, rec: PluginRecord) -> bool:
        trusted = self._trusted_hashes()
        return trusted.get(rec.plugin_id, "").strip().lower() == rec.digest.lower()

    def _mark_trusted(self, rec: PluginRecord) -> None:
        trusted = self._trusted_hashes()
        trusted[rec.plugin_id] = rec.digest.lower()
        self._save_trusted_hashes(trusted)

    def _quarantine_plugin(self, rec: PluginRecord, reason: str) -> None:
        quarantined = self._quarantined()
        quarantined.add(rec.plugin_id)
        self._save_quarantined(quarantined)
        enabled = self._enabled()
        if rec.plugin_id in enabled:
            enabled.discard(rec.plugin_id)
            self._save_enabled(enabled)
        self.window.log_event("Error", f"Plugin quarantined ({rec.plugin_id}): {reason}")

    def discover(self) -> list[PluginRecord]:
        enabled = self._enabled()
        quarantined = self._quarantined()
        out: list[PluginRecord] = []
        for folder in sorted(self.plugins_dir.iterdir()):
            if not folder.is_dir():
                continue
            manifest = folder / "plugin.json"
            code = folder / "plugin.py"
            if not manifest.exists() or not code.exists():
                continue
            try:
                meta = json.loads(manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(meta, dict):
                continue
            pid = str(meta.get("id", folder.name))
            perms = {
                str(p).lower()
                for p in meta.get("permissions", [])
                if str(p).lower() in {"file", "network", "ai"}
            }
            out.append(
                PluginRecord(
                    plugin_id=pid,
                    name=str(meta.get("name", pid)),
                    description=str(meta.get("description", "")),
                    permissions=perms,
                    path=folder,
                    enabled=pid in enabled,
                    digest=compute_plugin_digest(folder),
                    quarantined=pid in quarantined,
                )
            )
        return out

    def reload(self, *, startup: bool = False) -> None:
        import importlib.util

        self.records = self.discover()
        if startup and self._is_startup_safe_mode():
            self.window.show_status_message("Plugin startup safe mode is enabled.", 3000)
            return
        for rec in self.records:
            if not rec.enabled:
                continue
            if rec.quarantined:
                self.window.log_event("Info", f"Skipping quarantined plugin: {rec.plugin_id}")
                continue
            if not self._is_plugin_trusted(rec):
                if not self._trust_prompt(rec):
                    self.window.log_event("Info", f"Plugin trust denied: {rec.plugin_id}")
                    continue
                self._mark_trusted(rec)
            try:
                spec = importlib.util.spec_from_file_location(f"np_plugin_{rec.plugin_id}", rec.path / "plugin.py")
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                cls = getattr(module, "Plugin", None)
                if cls is None:
                    continue
                rec.instance = cls(PluginAPI(self.window, rec))
                on_load = getattr(rec.instance, "on_load", None)
                if callable(on_load):
                    on_load()
            except Exception as exc:  # noqa: BLE001
                self._quarantine_plugin(rec, str(exc))
                self.window.show_status_message(f"Plugin quarantined: {rec.plugin_id}", 3500)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        ids = self._enabled()
        rec = next((x for x in self.discover() if x.plugin_id == plugin_id), None)
        if enabled and rec is not None:
            if rec.quarantined:
                QMessageBox.warning(
                    self.window,
                    "Plugin Quarantined",
                    f"Plugin '{plugin_id}' is quarantined due to a previous failure.\nRemove it from quarantine first.",
                )
                return
            if not self._is_plugin_trusted(rec):
                if not self._trust_prompt(rec):
                    return
                self._mark_trusted(rec)
        if enabled:
            ids.add(plugin_id)
        else:
            ids.discard(plugin_id)
        self._save_enabled(ids)


class PluginManagerDialog(QDialog):
    def __init__(self, parent, host: PluginHost) -> None:
        super().__init__(parent)
        self.host = host
        self.setWindowTitle("Plugin Manager")
        self.resize(700, 460)
        v = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        v.addWidget(self.list_widget, 1)
        row = QHBoxLayout()
        reload_btn = QPushButton("Reload", self)
        clear_quarantine_btn = QPushButton("Clear Quarantine", self)
        close_btn = QPushButton("Close", self)
        row.addWidget(reload_btn)
        row.addWidget(clear_quarantine_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        v.addLayout(row)
        reload_btn.clicked.connect(self._reload)
        clear_quarantine_btn.clicked.connect(self._clear_quarantine)
        close_btn.clicked.connect(self.accept)
        self._populate()

    def _populate(self) -> None:
        self.list_widget.clear()
        for rec in self.host.discover():
            holder = QListWidgetItem(self.list_widget)
            item_widget = QWidget(self.list_widget)
            row = QHBoxLayout(item_widget)
            row.setContentsMargins(6, 4, 6, 4)
            check = QCheckBox(f"{rec.name} ({rec.plugin_id})", item_widget)
            check.setChecked(rec.enabled)
            state = "QUARANTINED" if rec.quarantined else "ok"
            info = QLabel(
                (
                    f"{rec.description} | perms: {', '.join(sorted(rec.permissions)) or 'none'} | "
                    f"state: {state} | sha256: {rec.digest[:12]}..."
                ),
                item_widget,
            )
            row.addWidget(check)
            row.addWidget(info, 1)
            holder.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(holder)
            self.list_widget.setItemWidget(holder, item_widget)
            check.toggled.connect(lambda val, pid=rec.plugin_id: self.host.set_enabled(pid, val))

    def _reload(self) -> None:
        self.host.reload()
        self._populate()

    def _clear_quarantine(self) -> None:
        self.host.window.settings["quarantined_plugins"] = []
        self.host.window.save_settings_to_disk()
        self._populate()


class MinimapDock(QDockWidget):
    def __init__(self, parent) -> None:
        super().__init__("Minimap", parent)
        self.text = QTextEdit(self)
        self.text.setReadOnly(True)
        f = self.text.font()
        f.setPointSize(max(6, f.pointSize() - 4))
        self.text.setFont(f)
        self.setWidget(self.text)

    def refresh(self, src: str) -> None:
        self.text.setPlainText("\n".join(x[:140] for x in src.splitlines()[:1800]))


class OutlineDock(QDockWidget):
    def __init__(self, parent, jump_cb) -> None:
        super().__init__("Symbol Outline", parent)
        self.jump_cb = jump_cb
        self.list_widget = QListWidget(self)
        self.setWidget(self.list_widget)
        self.list_widget.itemDoubleClicked.connect(self._jump)

    def _jump(self, item: QListWidgetItem) -> None:
        line = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(line, int):
            self.jump_cb(line)

    def refresh(self, language: str, text: str) -> None:
        self.list_widget.clear()
        rows: list[tuple[int, str]] = []
        if language == "python":
            try:
                tree = ast.parse(text)
                for n in ast.walk(tree):
                    if isinstance(n, ast.ClassDef):
                        rows.append((n.lineno - 1, f"class {n.name}"))
                    if isinstance(n, ast.FunctionDef):
                        rows.append((n.lineno - 1, f"def {n.name}"))
            except Exception:
                pass
        if language == "markdown":
            for i, ln in enumerate(text.splitlines()):
                if ln.strip().startswith("#"):
                    rows.append((i, ln.strip()))
        if not rows:
            for i, ln in enumerate(text.splitlines()):
                s = ln.strip()
                if re.match(r"^(class|def|function)\s+\w+", s):
                    rows.append((i, s))
        for line, title in rows[:500]:
            item = QListWidgetItem(f"{line + 1}: {title}")
            item.setData(Qt.ItemDataRole.UserRole, line)
            self.list_widget.addItem(item)


class CollaborationServer:
    def __init__(self, window) -> None:
        self.window = window
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._revision = 0
        self._events: list[dict[str, Any]] = []
        self._clients: dict[str, dict[str, Any]] = {}
        self._read_write = False
        self._session_text = ""

    def _ensure_token(self) -> str:
        token = str(self.window.settings.get("collab_token", "") or "").strip()
        if token:
            return token
        token = secrets.token_urlsafe(24)
        self.window.settings["collab_token"] = token
        self.window.save_settings_to_disk()
        return token

    def start(self, port: int, read_write: bool) -> None:
        if self.server is not None:
            return
        token = self._ensure_token()
        self._read_write = bool(read_write)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _raw_body(self) -> str:
                size = int(self.headers.get("Content-Length", "0") or 0)
                raw = (self.rfile.read(size) if size > 0 else b"") or b""
                return raw.decode("utf-8", errors="replace")

            def _read_json(self) -> tuple[dict[str, Any], str]:
                raw = self._raw_body()
                if not raw:
                    return {}, raw
                try:
                    data = json.loads(raw)
                except Exception:
                    return {}, raw
                return data if isinstance(data, dict) else {}, raw

            def _authorized(self) -> bool:
                auth = str(self.headers.get("Authorization", "") or "")
                if auth.startswith("Bearer "):
                    supplied = auth[7:].strip()
                else:
                    supplied = str(self.headers.get("X-Collab-Token", "") or "").strip()
                return bool(supplied) and hmac.compare_digest(supplied, token)

            def _verify_signature(self, method: str, path: str, raw_body: str) -> bool:
                timestamp = str(self.headers.get("X-Collab-Timestamp", "") or "").strip()
                signature = str(self.headers.get("X-Collab-Signature", "") or "").strip().lower()
                if not timestamp or not signature:
                    return False
                try:
                    ts = int(timestamp)
                except Exception:
                    return False
                now = int(time.time())
                if abs(now - ts) > 120:
                    return False
                payload = f"{method}\n{path}\n{timestamp}\n{raw_body}".encode("utf-8")
                expected = hmac.new(token.encode("utf-8"), payload, hashlib.sha256).hexdigest()
                return hmac.compare_digest(signature, expected)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if not self._authorized():
                    self._send(403, {"error": "forbidden"})
                    return
                if parsed.path != "/state":
                    if parsed.path != "/events":
                        self._send(404, {"error": "not_found"})
                        return
                    since = parse_qs(parsed.query).get("since", ["0"])[0]
                    try:
                        since_rev = int(since)
                    except Exception:
                        since_rev = 0
                    with owner._lock:
                        events = [event for event in owner._events if int(event.get("rev", 0)) > since_rev]
                    self._send(200, {"events": events[-100:]})
                    return
                tab = owner.window.active_tab()
                with owner._lock:
                    revision = owner._revision
                    clients = len(owner._clients)
                    text = owner._session_text if owner._session_text else (tab.text_edit.get_text() if tab else "")
                self._send(
                    200,
                    {
                        "text": text,
                        "rw": bool(owner._read_write),
                        "revision": revision,
                        "clients": clients,
                    },
                )

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if not self._authorized():
                    self._send(403, {"error": "forbidden"})
                    return
                payload, raw_body = self._read_json()
                if parsed.path == "/join":
                    name = str(payload.get("name", "") or "client").strip()[:64] or "client"
                    client_id = str(payload.get("client_id", "") or "").strip()[:64] or uuid.uuid4().hex[:16]
                    with owner._lock:
                        owner._clients[client_id] = {"name": name, "last_seen": int(time.time())}
                        revision = owner._revision
                        text = owner._session_text
                    self._send(
                        200,
                        {"client_id": client_id, "revision": revision, "text": text},
                    )
                    return
                if parsed.path != "/edit":
                    self._send(404, {"error": "not_found"})
                    return
                if not owner._read_write:
                    self._send(403, {"error": "read_only"})
                    return
                if not self._verify_signature("POST", parsed.path, raw_body):
                    self._send(403, {"error": "bad_signature"})
                    return
                client_id = str(payload.get("client_id", "") or "").strip()
                base_revision = int(payload.get("base_revision", -1))
                operations = payload.get("operations", [])
                if not client_id or not isinstance(operations, list):
                    self._send(400, {"error": "bad_request"})
                    return
                with owner._lock:
                    if client_id not in owner._clients:
                        self._send(403, {"error": "unknown_client"})
                        return
                    owner._clients[client_id]["last_seen"] = int(time.time())
                    current_revision = owner._revision
                if base_revision != current_revision:
                    self._send(409, {"error": "revision_conflict", "current_revision": current_revision})
                    return
                with owner._lock:
                    current_text = owner._session_text
                try:
                    new_text = apply_text_operations(current_text, operations)
                except Exception as exc:
                    self._send(400, {"error": "invalid_operations", "detail": str(exc)})
                    return
                with owner._lock:
                    owner._session_text = new_text
                    owner._revision += 1
                    rev = owner._revision
                    owner._events.append(
                        {
                            "rev": rev,
                            "client_id": client_id,
                            "operations": operations[:50],
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                        }
                    )
                    owner._events = owner._events[-300:]
                QTimer.singleShot(0, lambda txt=new_text: owner._apply_session_text_to_active_tab(txt))
                self._send(200, {"ok": True, "revision": rev})

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        with self._lock:
            self._revision = 0
            self._events = []
            self._clients = {}
            tab = self.window.active_tab()
            self._session_text = tab.text_edit.get_text() if tab is not None else ""
        self.server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if self.server is None:
            return
        self.server.shutdown()
        self.server.server_close()
        self.server = None
        self.thread = None

    def _apply_session_text_to_active_tab(self, text: str) -> None:
        tab = self.window.active_tab()
        if tab is None or tab.text_edit.is_read_only():
            return
        tab.text_edit.set_text(text)
        tab.text_edit.set_modified(True)


class AdvancedFeaturesController:
    def __init__(self, window) -> None:
        self.window = window
        self.plugin_host = PluginHost(window)
        try:
            self.window.show_status_message(
                f"Plugins loaded from: {self.plugin_host.plugins_dir} ({self.plugin_host.runtime_mode_label()})",
                4500,
            )
        except Exception:
            pass
        self.minimap_dock = MinimapDock(window)
        self.minimap_dock.hide()
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.minimap_dock)
        self.outline_dock = OutlineDock(window, self._jump_line)
        self.outline_dock.hide()
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.outline_dock)
        self.collab = CollaborationServer(window)
        self.backup_timer = QTimer(window)
        self.backup_timer.timeout.connect(self.backup_now)
        self.apply_backup_schedule()

    def _jump_line(self, line: int) -> None:
        tab = self.window.active_tab()
        if tab is not None:
            tab.text_edit.set_cursor_position(max(0, line), 0)

    def refresh_views(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            self.minimap_dock.refresh("")
            self.outline_dock.refresh("plain", "")
            self.window._set_breadcrumb_text("-")
            return
        txt = tab.text_edit.get_text()
        self.minimap_dock.refresh(txt)
        lang = self.window._detect_language_for_tab(tab)
        self.outline_dock.refresh(lang, txt)
        line, _ = tab.text_edit.cursor_position()
        self.window._set_breadcrumb_text(f"{tab.current_file or 'Untitled'} > line {line + 1}")

    def toggle_minimap(self, checked: bool) -> None:
        self.minimap_dock.setVisible(bool(checked))
        self.refresh_views()

    def toggle_outline(self, checked: bool) -> None:
        self.outline_dock.setVisible(bool(checked))
        self.refresh_views()

    def open_plugin_manager(self) -> None:
        PluginManagerDialog(self.window, self.plugin_host).exec()
        self.plugin_host.reload()

    def go_to_definition(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        symbol = tab.text_edit.selected_text().strip()
        if not symbol:
            symbol, ok = QInputDialog.getText(self.window, "Go To Definition", "Symbol:")
            if not ok or not symbol.strip():
                return
            symbol = symbol.strip()
        pats = [rf"^\s*def\s+{re.escape(symbol)}\b", rf"^\s*class\s+{re.escape(symbol)}\b", rf"^\s*{re.escape(symbol)}\s*="]
        for idx, ln in enumerate(tab.text_edit.get_text().splitlines()):
            if any(re.search(p, ln) for p in pats):
                tab.text_edit.set_cursor_position(idx, 0)
                self.window.show_status_message(f"Definition found at line {idx + 1}", 2500)
                return
        self.window.show_status_message("Definition not found in current file.", 2500)

    def open_diff(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        path, _ = QFileDialog.getOpenFileName(self.window, "Compare With File", "", "All Files (*.*)")
        if not path:
            return
        try:
            other = Path(path).read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.window, "Diff", f"Could not open file:\n{exc}")
            return
        dlg = QDialog(self.window)
        dlg.setWindowTitle("Side-by-side Diff")
        dlg.resize(980, 620)
        h = QHBoxLayout(dlg)
        left = QTextEdit(dlg)
        right = QTextEdit(dlg)
        left.setReadOnly(True)
        right.setReadOnly(True)
        left.setPlainText(tab.text_edit.get_text())
        right.setPlainText(other)
        h.addWidget(left, 1)
        h.addWidget(right, 1)
        dlg.exec()

    def open_merge_helper(self) -> None:
        base, _ = QFileDialog.getOpenFileName(self.window, "Base File", "", "All Files (*.*)")
        ours, _ = QFileDialog.getOpenFileName(self.window, "Ours File", "", "All Files (*.*)")
        theirs, _ = QFileDialog.getOpenFileName(self.window, "Theirs File", "", "All Files (*.*)")
        if not base or not ours or not theirs:
            return
        b = Path(base).read_text(encoding="utf-8")
        o = Path(ours).read_text(encoding="utf-8")
        t = Path(theirs).read_text(encoding="utf-8")
        merged = o if o == t else (t if b == o else (o if b == t else f"<<<<<<< OURS\n{o}\n=======\n{t}\n>>>>>>> THEIRS\n"))
        dlg = QDialog(self.window)
        dlg.setWindowTitle("3-way Merge")
        dlg.resize(920, 620)
        v = QVBoxLayout(dlg)
        edit = QTextEdit(dlg)
        edit.setPlainText(merged)
        v.addWidget(edit, 1)
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close, Qt.Orientation.Horizontal, dlg)
        v.addWidget(box)
        box.rejected.connect(dlg.reject)
        box.accepted.connect(lambda: self._save_text_dialog(edit.toPlainText()))
        dlg.exec()

    def _save_text_dialog(self, text: str) -> None:
        path, _ = QFileDialog.getSaveFileName(self.window, "Save File", "", "All Files (*.*)")
        if path:
            Path(path).write_text(text, encoding="utf-8")

    def open_snippets(self) -> None:
        snippets = self.window.settings.get("snippets", {})
        if not isinstance(snippets, dict):
            snippets = {}
        snippets.setdefault("python_func", "def ${1:name}(${2:args}):\n    ${3:pass}")
        snippets.setdefault("markdown_task", "- [ ] ${1:task}")
        self.window.settings["snippets"] = snippets
        self.window.save_settings_to_disk()
        names = sorted(snippets.keys())
        name, ok = QInputDialog.getItem(self.window, "Snippets", "Choose snippet:", names, 0, False)
        if not ok or not name:
            return
        text = re.sub(r"\$\{\d+:([^}]+)\}", r"\1", str(snippets[name]))
        text = re.sub(r"\$\{\d+\}", "", text)
        tab = self.window.active_tab()
        if tab is not None:
            tab.text_edit.insert_text(text)

    def ensure_template_packs(self) -> None:
        packs = self.window.settings.get("template_packs", {})
        if not isinstance(packs, dict):
            packs = {}
        packs.setdefault("notes/meeting", "## Meeting\nDate: ${1:date}\n")
        packs.setdefault("docs/changelog", "## [Unreleased]\n### Added\n- ${1:item}\n")
        packs.setdefault("code/class", "class ${1:Name}:\n    pass\n")
        self.window.settings["template_packs"] = packs
        self.window.save_settings_to_disk()
        self.window.show_status_message("Template packs are ready.", 2500)

    def show_tasks(self) -> None:
        tasks: list[str] = []
        due = re.compile(r"due[:=]\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
        for i in range(self.window.tab_widget.count()):
            tab = self.window.tab_widget.widget(i)
            if tab is None:
                continue
            name = tab.current_file or f"Tab {i + 1}"
            for ln, line in enumerate(tab.text_edit.get_text().splitlines(), start=1):
                if "TODO" in line.upper() or "FIXME" in line.upper():
                    d = due.search(line)
                    tasks.append(f"{name}:{ln} | due={d.group(1) if d else '-'} | {line.strip()}")
                    if d and hasattr(self.window, "reminders_store"):
                        try:
                            self.window.reminders_store.upsert(
                                reminder_id=f"task:{name}:{ln}",
                                title=f"Task {Path(name).name}:{ln}",
                                when_iso=f"{d.group(1)}T09:00:00",
                                note=line.strip(),
                            )
                        except Exception:
                            pass
        dlg = QDialog(self.window)
        dlg.setWindowTitle("Task Workflow")
        dlg.resize(900, 520)
        v = QVBoxLayout(dlg)
        lst = QListWidget(dlg)
        for t in tasks or ["No tasks found."]:
            lst.addItem(t)
        v.addWidget(lst)
        box = QDialogButtonBox(QDialogButtonBox.Close, Qt.Orientation.Horizontal, dlg)
        box.rejected.connect(dlg.reject)
        box.accepted.connect(dlg.accept)
        v.addWidget(box)
        dlg.exec()
        if tasks and hasattr(self.window, "reminders_store"):
            try:
                self.window.reminders_store.save()
            except Exception:
                pass

    def backup_now(self) -> None:
        configured = str(self.window.settings.get("backup_output_dir", "") or "").strip()
        dest = Path(configured) if configured else (_root() / "backups")
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i in range(self.window.tab_widget.count()):
                tab = self.window.tab_widget.widget(i)
                if tab is None:
                    continue
                name = Path(tab.current_file).name if tab.current_file else f"unsaved_{i + 1}.txt"
                zf.writestr(name, tab.text_edit.get_text())
        self.window.show_status_message(f"Backup created: {out}", 3500)

    def apply_backup_schedule(self) -> None:
        enabled = bool(self.window.settings.get("backup_scheduler_enabled", False))
        mins = max(1, int(self.window.settings.get("backup_interval_min", 15) or 15))
        if enabled:
            self.backup_timer.start(mins * 60 * 1000)
        else:
            self.backup_timer.stop()

    def configure_backup(self) -> None:
        dlg = QDialog(self.window)
        dlg.setWindowTitle("Backup Scheduler")
        form = QFormLayout(dlg)
        enabled = QCheckBox("Enable background scheduler", dlg)
        enabled.setChecked(bool(self.window.settings.get("backup_scheduler_enabled", False)))
        mins = QSpinBox(dlg)
        mins.setRange(1, 720)
        mins.setValue(int(self.window.settings.get("backup_interval_min", 15) or 15))
        output_dir = QLineEdit(dlg)
        output_dir.setText(str(self.window.settings.get("backup_output_dir", "") or ""))
        browse_btn = QPushButton("Browse...", dlg)
        output_row = QWidget(dlg)
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(output_dir, 1)
        output_layout.addWidget(browse_btn)

        def pick_output() -> None:
            start_dir = output_dir.text().strip() or ""
            picked = QFileDialog.getExistingDirectory(dlg, "Choose Backup Output Folder", start_dir)
            if picked:
                output_dir.setText(picked)

        browse_btn.clicked.connect(pick_output)
        form.addRow(enabled)
        form.addRow("Interval minutes:", mins)
        form.addRow("Output folder (optional):", output_row)
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Orientation.Horizontal, dlg)
        form.addRow(box)
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        self.window.settings["backup_scheduler_enabled"] = enabled.isChecked()
        self.window.settings["backup_interval_min"] = int(mins.value())
        self.window.settings["backup_output_dir"] = output_dir.text().strip()
        self.window.save_settings_to_disk()
        self.apply_backup_schedule()

    def export_diagnostics(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self.window, "Diagnostics Bundle", str(_root() / "diagnostics_bundle.zip"), "Zip Files (*.zip)")
        if not path:
            return
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("settings.json", json.dumps(self.window.settings, indent=2))
            zf.writestr("debug_logs.txt", "\n".join(getattr(self.window, "debug_logs", [])))
            zf.writestr("meta.json", json.dumps({"timestamp": datetime.now().isoformat()}, indent=2))
        self.window.show_status_message("Diagnostics exported.", 2500)

    def toggle_keyboard_only(self, checked: bool) -> None:
        self.window.settings["keyboard_only_mode"] = bool(checked)
        if checked:
            self.window.main_toolbar.hide()
            if hasattr(self.window, "markdown_toolbar"):
                self.window.markdown_toolbar.hide()
            if hasattr(self.window, "search_toolbar"):
                self.window.search_toolbar.hide()
        else:
            self.window._layout_top_toolbars()
        self.window.save_settings_to_disk()

    def apply_accessibility_high_contrast(self) -> None:
        self.window.settings["theme"] = "High Contrast"
        self.window.settings["dark_mode"] = True
        self.window.apply_settings()

    def apply_accessibility_dyslexic(self) -> None:
        self.window.settings["font_family"] = "OpenDyslexic"
        self.window.settings["font_size"] = max(13, int(self.window.settings.get("font_size", 11)))
        self.window.apply_settings()

    def open_collaboration(self) -> None:
        port = int(self.window.settings.get("collab_port", 8765) or 8765)
        rw = bool(self.window.settings.get("collab_rw", False))
        dlg = QDialog(self.window)
        dlg.setWindowTitle("LAN Collaboration")
        form = QFormLayout(dlg)
        port_spin = QSpinBox(dlg)
        port_spin.setRange(1024, 65535)
        port_spin.setValue(port)
        rw_check = QCheckBox("Read/Write mode", dlg)
        rw_check.setChecked(rw)
        form.addRow("Port:", port_spin)
        form.addRow(rw_check)
        box = QDialogButtonBox(dlg)
        start_btn = box.addButton("Start", QDialogButtonBox.ButtonRole.AcceptRole)
        stop_btn = box.addButton("Stop", QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = box.addButton(QDialogButtonBox.StandardButton.Close)
        form.addRow(box)
        close_btn.clicked.connect(dlg.reject)
        stop_btn.clicked.connect(self.collab.stop)

        def start() -> None:
            self.window.settings["collab_port"] = int(port_spin.value())
            self.window.settings["collab_rw"] = rw_check.isChecked()
            self.window.save_settings_to_disk()
            self.collab.start(int(port_spin.value()), bool(rw_check.isChecked()))
            token = str(self.window.settings.get("collab_token", ""))
            QMessageBox.information(
                self.window,
                "LAN Collaboration",
                (
                    f"Server: http://127.0.0.1:{int(port_spin.value())}\n"
                    "Use Authorization header:\n"
                    f"Bearer {token}\n\n"
                    "Endpoints: POST /join, GET /state, GET /events?since=<rev>, POST /edit"
                ),
            )

        start_btn.clicked.connect(start)
        dlg.exec()

    def open_annotations(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        key = tab.current_file or "__untitled__"
        all_notes = self.window.settings.get("annotations", {})
        if not isinstance(all_notes, dict):
            all_notes = {}
        notes = all_notes.get(key, {})
        if not isinstance(notes, dict):
            notes = {}
        dlg = QDialog(self.window)
        dlg.setWindowTitle("Annotations")
        dlg.resize(760, 480)
        v = QVBoxLayout(dlg)
        lst = QListWidget(dlg)
        for ln, txt in sorted(notes.items(), key=lambda x: int(str(x[0]))):
            lst.addItem(f"Line {ln}: {txt}")
        v.addWidget(lst, 1)
        row = QHBoxLayout()
        add_btn = QPushButton("Add", dlg)
        del_btn = QPushButton("Delete", dlg)
        close_btn = QPushButton("Close", dlg)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        v.addLayout(row)

        def persist() -> None:
            all_notes[key] = notes
            self.window.settings["annotations"] = all_notes
            self.window.save_settings_to_disk()

        def add() -> None:
            line, ok = QInputDialog.getInt(dlg, "Line", "Line number:", 1, 1, 1000000)
            if not ok:
                return
            text, ok = QInputDialog.getMultiLineText(dlg, "Annotation", "Comment:")
            if not ok or not text.strip():
                return
            notes[str(line)] = text.strip()
            lst.addItem(f"Line {line}: {text.strip()}")
            persist()

        def delete() -> None:
            item = lst.currentItem()
            if item is None:
                return
            m = re.match(r"Line\s+(\d+):", item.text())
            if m:
                notes.pop(m.group(1), None)
            lst.takeItem(lst.row(item))
            persist()

        add_btn.clicked.connect(add)
        del_btn.clicked.connect(delete)
        close_btn.clicked.connect(dlg.accept)
        dlg.exec()
