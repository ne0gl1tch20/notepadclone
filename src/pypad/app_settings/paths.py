from __future__ import annotations

import os
from pathlib import Path


def _app_roaming_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    base_dir = Path(appdata) if appdata else (Path.home() / "AppData" / "Roaming")
    return base_dir / "notepadclone"


def get_settings_file_path() -> Path:
    return _app_roaming_dir() / "settings.json"


def get_legacy_settings_file_path() -> Path:
    return _app_roaming_dir() / "save.bin"


def get_password_file_path() -> Path:
    return _app_roaming_dir() / "password.bin"


def get_reminders_file_path() -> Path:
    return _app_roaming_dir() / "reminders.json"


def get_autosave_dir_path() -> Path:
    return _app_roaming_dir() / "autosave"


def get_translation_cache_path() -> Path:
    return _app_roaming_dir() / "translation_cache.json"


def get_plugins_dir_path() -> Path:
    return _app_roaming_dir() / "plugins"


def get_debug_logs_file_path() -> Path:
    return _app_roaming_dir() / "debug_logs.log"


def get_crash_logs_file_path() -> Path:
    return _app_roaming_dir() / "crash_tracebacks.log"
