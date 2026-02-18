from __future__ import annotations

import ast
import json
import re
import threading
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
    instance: Any = None


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
        self.plugins_dir = _root() / "plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.records: list[PluginRecord] = []
        self.reload()

    def _enabled(self) -> set[str]:
        return {str(x) for x in self.window.settings.get("enabled_plugins", []) if isinstance(x, str)}

    def _save_enabled(self, ids: set[str]) -> None:
        self.window.settings["enabled_plugins"] = sorted(ids)
        self.window.save_settings_to_disk()

    def discover(self) -> list[PluginRecord]:
        enabled = self._enabled()
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
                )
            )
        return out

    def reload(self) -> None:
        import importlib.util

        self.records = self.discover()
        for rec in self.records:
            if not rec.enabled:
                continue
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
                self.window.log_event("Error", f"Plugin load failed ({rec.plugin_id}): {exc}")

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        ids = self._enabled()
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
        close_btn = QPushButton("Close", self)
        row.addWidget(reload_btn)
        row.addStretch(1)
        row.addWidget(close_btn)
        v.addLayout(row)
        reload_btn.clicked.connect(self._reload)
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
            info = QLabel(f"{rec.description} | perms: {', '.join(sorted(rec.permissions)) or 'none'}", item_widget)
            row.addWidget(check)
            row.addWidget(info, 1)
            holder.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(holder)
            self.list_widget.setItemWidget(holder, item_widget)
            check.toggled.connect(lambda val, pid=rec.plugin_id: self.host.set_enabled(pid, val))

    def _reload(self) -> None:
        self.host.reload()
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

    def start(self, port: int, read_write: bool) -> None:
        if self.server is not None:
            return
        token = str(self.window.settings.get("collab_token", "") or "")
        if not token:
            token = f"np-{datetime.now().strftime('%H%M%S')}"
            self.window.settings["collab_token"] = token
            self.window.save_settings_to_disk()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def _send(self, code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/state":
                    self._send(404, {"error": "not_found"})
                    return
                if parse_qs(parsed.query).get("token", [""])[0] != token:
                    self._send(403, {"error": "forbidden"})
                    return
                tab = owner.window.active_tab()
                self._send(200, {"text": tab.text_edit.get_text() if tab else "", "rw": bool(read_write)})

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != "/apply":
                    self._send(404, {"error": "not_found"})
                    return
                if not read_write:
                    self._send(403, {"error": "read_only"})
                    return
                if parse_qs(parsed.query).get("token", [""])[0] != token:
                    self._send(403, {"error": "forbidden"})
                    return
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads((self.rfile.read(size) or b"{}").decode("utf-8"))
                tab = owner.window.active_tab()
                if tab is not None and not tab.text_edit.is_read_only():
                    tab.text_edit.set_text(str(payload.get("text", "")))
                    tab.text_edit.set_modified(True)
                self._send(200, {"ok": True})

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

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


class AdvancedFeaturesController:
    def __init__(self, window) -> None:
        self.window = window
        self.plugin_host = PluginHost(window)
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
            QMessageBox.information(self.window, "LAN Collaboration", f"http://127.0.0.1:{int(port_spin.value())}/state?token={token}")

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
