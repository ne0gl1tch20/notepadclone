from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox, QTextEdit, QVBoxLayout

from pypad.ui.theme.dialog_theme import apply_dialog_theme_from_window


class MiscAiUsageMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def record_ai_usage(self, *, tokens: int, estimated_cost: float) -> None:
        usage = getattr(self, "ai_usage_session", None)
        if not isinstance(usage, dict):
            usage = {"requests": 0, "tokens": 0, "estimated_cost": 0.0}
            self.ai_usage_session = usage
        usage["requests"] = int(usage.get("requests", 0)) + 1
        usage["tokens"] = int(usage.get("tokens", 0)) + max(0, int(tokens))
        usage["estimated_cost"] = float(usage.get("estimated_cost", 0.0)) + max(0.0, float(estimated_cost))
        self._refresh_ai_usage_label()

    def _refresh_ai_usage_label(self) -> None:
        label = getattr(self, "ai_usage_label", None)
        usage = getattr(self, "ai_usage_session", {})
        if label is None or not isinstance(usage, dict):
            return
        requests = int(usage.get("requests", 0))
        tokens = int(usage.get("tokens", 0))
        cost = float(usage.get("estimated_cost", 0.0))
        label.setText(f"AI: {requests} req | ~{tokens} tok | ~${cost:.4f}")

    def show_ai_action_history(self) -> None:
        history = self.settings.get("ai_action_history", [])
        if not isinstance(history, list):
            history = []
        if not history:
            QMessageBox.information(self, "AI Action History", "No AI actions recorded yet.")
            return
        lines: list[str] = []
        for row in history[-120:]:
            if not isinstance(row, dict):
                continue
            ts = str(row.get("timestamp", ""))
            action = str(row.get("action", "AI"))
            model = str(row.get("model", ""))
            p = int(row.get("prompt_chars", 0) or 0)
            r = int(row.get("response_chars", 0) or 0)
            lines.append(f"{ts} | {action} | {model} | prompt={p} chars | response={r} chars")
        dlg = QDialog(self)
        dlg.setWindowTitle("AI Action History")
        dlg.resize(780, 480)
        apply_dialog_theme_from_window(self, dlg)
        v = QVBoxLayout(dlg)
        view = QTextEdit(dlg)
        view.setReadOnly(True)
        view.setPlainText("\n".join(lines))
        v.addWidget(view)
        btn = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, dlg)
        btn.rejected.connect(dlg.reject)
        btn.accepted.connect(dlg.accept)
        v.addWidget(btn)
        dlg.exec()

    def show_ai_usage_summary(self) -> None:
        usage = getattr(self, "ai_usage_session", {})
        requests = int(usage.get("requests", 0))
        tokens = int(usage.get("tokens", 0))
        cost = float(usage.get("estimated_cost", 0.0))
        QMessageBox.information(
            self,
            "AI Usage Summary",
            f"Session requests: {requests}\nEstimated tokens: {tokens}\nEstimated cost: ${cost:.4f}",
        )
