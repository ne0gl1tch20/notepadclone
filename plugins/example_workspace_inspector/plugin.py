from datetime import datetime

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class Plugin:
    def __init__(self, api) -> None:
        self.api = api
        self.status_label = None
        self.root_label = None
        self.last_notice_ready = False

    def on_load(self) -> None:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.root_label = QLabel("Workspace: (none)")
        self.status_label = QLabel("Index: not started")
        layout.addWidget(self.root_label)
        layout.addWidget(self.status_label)
        self.api.add_panel("Workspace Index", panel)
        self.api.add_menu_action("Plugins/Workspace", "Refresh Workspace Index", self.refresh_index)
        self.api.start_timer(5000, self._refresh_status)
        self.refresh_index()

    def on_window_focus(self, _event) -> None:
        self._refresh_status()

    def refresh_index(self) -> None:
        self.api.refresh_workspace_index()
        self.api.notify("Workspace index refresh requested.")

    def _refresh_status(self) -> None:
        status = self.api.workspace_index_status()
        root = status.get("root") or "(none)"
        count = int(status.get("count", 0) or 0)
        scanning = bool(status.get("scanning", False))
        ready = bool(status.get("ready", False))
        if self.root_label is not None:
            self.root_label.setText(f"Workspace: {root}")
        if self.status_label is not None:
            state = "scanning" if scanning else ("ready" if ready else "idle")
            self.status_label.setText(f"Index: {state} | files: {count} | {datetime.now().strftime('%H:%M:%S')}")
        if ready and not self.last_notice_ready:
            self.api.notify(f"Workspace index ready: {count} files.")
        self.last_notice_ready = ready
