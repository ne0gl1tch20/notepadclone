from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog, QMessageBox


class MiscAiTemplatesMixin:
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...

    def _ai_templates(self) -> dict[str, str]:
        templates = self.settings.get("ai_prompt_templates", {})
        if not isinstance(templates, dict):
            templates = {}
        defaults = {
            "Explain selection": "Explain this clearly:\n\n{selection}",
            "Summarize file": "Summarize this file with key points and action items:\n\n{file_text}",
            "Code review notes": "Review this file for bugs and risks:\n\n{file_text}",
        }
        merged = dict(defaults)
        for key, value in templates.items():
            if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                merged[key.strip()] = value
        return merged

    def _render_ai_template(self, template: str, tab) -> str:
        text = tab.text_edit.get_text()
        selection = tab.text_edit.selected_text() or text[:5000]
        file_name = str(tab.current_file or "Untitled")
        workspace_root = str(self.settings.get("workspace_root", "") or "")
        line, col = (0, 0)
        try:
            line, col = tab.text_edit.cursor_position()
        except Exception:
            pass
        radius = int(self.settings.get("ai_template_nearby_lines_radius", 20) or 20)
        all_lines = text.splitlines()
        start = max(0, line - radius)
        end = min(len(all_lines), line + radius + 1)
        nearby = "\n".join(f"{idx + 1:04d}: {all_lines[idx]}" for idx in range(start, end))
        language = Path(file_name).suffix.lstrip(".").lower() if "." in Path(file_name).name else ""
        return (
            str(template or "")
            .replace("{selection}", selection)
            .replace("{file_text}", text[:20000])
            .replace("{file_name}", file_name)
            .replace("{workspace_root}", workspace_root)
            .replace("{cursor_line}", str(line + 1))
            .replace("{cursor_col}", str(col + 1))
            .replace("{nearby_lines}", nearby)
            .replace("{language}", language)
        )

    def run_ai_prompt_template(self) -> None:
        templates = self._ai_templates()
        names = sorted(templates.keys())
        if not names:
            QMessageBox.information(self, "AI Templates", "No templates available.")
            return
        name, ok = QInputDialog.getItem(self, "AI Prompt Templates", "Template:", names, 0, False)
        if not ok or not name:
            return
        template = templates.get(name, "")
        tab = self.active_tab()
        if tab is None:
            QMessageBox.information(self, "AI Templates", "Open a tab first.")
            return
        rendered = self._render_ai_template(template, tab)
        self._send_ai_chat_prompt(prompt=rendered, visible_prompt=f"Template: {name}")

    def save_ai_prompt_template(self) -> None:
        name, ok = QInputDialog.getText(self, "Save AI Template", "Template name:")
        if not ok or not name.strip():
            return
        body, ok = QInputDialog.getMultiLineText(
            self,
            "Save AI Template",
            "Template body (use {selection}, {file_text}, {file_name}):",
        )
        if not ok or not body.strip():
            return
        templates = self.settings.get("ai_prompt_templates", {})
        if not isinstance(templates, dict):
            templates = {}
        templates[name.strip()] = body.strip()
        self.settings["ai_prompt_templates"] = templates
        self.save_settings_to_disk()
        self.show_status_message(f'Saved AI template "{name.strip()}".', 3000)

    def toggle_ai_private_mode(self, checked: bool) -> None:
        self.settings["ai_private_mode"] = bool(checked)
        if checked:
            self.toggle_ai_chat_panel(False)
            self.show_status_message("AI private mode enabled (AI actions disabled).", 3000)
        else:
            self.show_status_message("AI private mode disabled.", 3000)
        self.save_settings_to_disk()
        self.update_action_states()
