from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QInputDialog, QLineEdit

from .note_crypto import decrypt_text, encrypt_text, is_encrypted_payload
from .editor_tab import EditorTab


class SecurityController:
    def __init__(self, window) -> None:
        self.window = window

    def prompt_password(self, title: str, label: str) -> str | None:
        password, ok = QInputDialog.getText(self.window, title, label, QLineEdit.Password)
        if not ok or not password:
            return None
        return password

    def load_text_from_path(self, path: str, encoding: str = "utf-8") -> tuple[str, bool, str | None]:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            raw = f.read()
        encrypted = is_encrypted_payload(raw) or Path(path).suffix.lower() == ".encnote"
        if not encrypted:
            return raw, False, None
        password = self.prompt_password("Encrypted Note", "Enter password:")
        if password is None:
            raise ValueError("Password required")
        plain = decrypt_text(raw, password)
        return plain, True, password

    def build_payload_for_save(self, tab: EditorTab) -> str | None:
        payload = tab.text_edit.get_text()
        if not tab.encryption_enabled:
            return payload
        password = tab.encryption_password or self.prompt_password("Encrypted Save", "Enter note password:")
        if not password:
            return None
        tab.encryption_password = password
        return encrypt_text(payload, password)

    def enable_note_encryption(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        if tab.encryption_enabled:
            self.change_note_password()
            return
        password = self.prompt_password("Enable Encryption", "Set note password:")
        if not password:
            return
        tab.encryption_enabled = True
        tab.encryption_password = password
        self.window.update_action_states()
        self.window._refresh_tab_title(tab)

    def disable_note_encryption(self) -> None:
        tab = self.window.active_tab()
        if tab is None:
            return
        tab.encryption_enabled = False
        tab.encryption_password = None
        self.window.update_action_states()
        self.window._refresh_tab_title(tab)

    def change_note_password(self) -> None:
        tab = self.window.active_tab()
        if tab is None or not tab.encryption_enabled:
            return
        password = self.prompt_password("Change Password", "New note password:")
        if not password:
            return
        tab.encryption_password = password
        tab.text_edit.set_modified(True)
