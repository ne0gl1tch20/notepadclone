from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime
from collections import deque

LOG_LEVEL_OPTIONS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
DEFAULT_LOG_LEVEL = "INFO"
_CONSOLE_BUFFER_MAX = 12000
_console_lines: deque[str] = deque(maxlen=_CONSOLE_BUFFER_MAX)
_console_lock = threading.Lock()
_console_capture_installed = False


def _append_console_line(line: str) -> None:
    text = str(line or "").rstrip("\r\n")
    if not text:
        return
    with _console_lock:
        _console_lines.append(text)


def get_console_log_lines() -> list[str]:
    with _console_lock:
        return list(_console_lines)


def clear_console_log_lines() -> None:
    with _console_lock:
        _console_lines.clear()


class _ConsoleCaptureTee:
    def __init__(self, stream, *, label: str) -> None:
        self._stream = stream
        self._label = label
        self._partial = ""
        self._pypad_console_capture_wrapper = True

    def write(self, data) -> int:
        text = str(data or "")
        if not text:
            return 0
        self._stream.write(text)
        self._partial += text
        while True:
            nl_idx = self._partial.find("\n")
            if nl_idx < 0:
                break
            line = self._partial[:nl_idx]
            self._partial = self._partial[nl_idx + 1 :]
            if line.strip():
                _append_console_line(f"[{self._label}] {line.rstrip(chr(13))}")
        return len(text)

    def flush(self) -> None:
        try:
            self._stream.flush()
        finally:
            if self._partial.strip():
                _append_console_line(f"[{self._label}] {self._partial.rstrip(chr(13))}")
            self._partial = ""

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


class _CapturingStreamHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            rendered = self.format(record)
        except Exception:
            rendered = ""
        if rendered:
            _append_console_line(rendered)
        super().emit(record)


class _PypadLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created)
        time_text = timestamp.strftime("%H:%M:%S.%f")[:-3]
        date_text = f"{timestamp.month}/{timestamp.day}/{timestamp.year}"
        level_text = str(record.levelname or "INFO").capitalize()
        message = record.getMessage()
        name = str(record.name or "").strip()
        if name:
            message = f"[{name}] {message}"
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            if exc_text:
                message = f"{message}\n{exc_text}"
        return f"[{level_text}] [{time_text} {date_text}] {message}"


def normalize_log_level_name(value: object, default: str = DEFAULT_LOG_LEVEL) -> str:
    text = str(value or "").strip().upper()
    return text if text in LOG_LEVEL_OPTIONS else str(default).strip().upper()


def get_level_number(value: object, default: str = DEFAULT_LOG_LEVEL) -> int:
    return int(getattr(logging, normalize_log_level_name(value, default), logging.INFO))


def configure_app_logging(level: object = DEFAULT_LOG_LEVEL) -> str:
    _install_console_capture()
    level_name = normalize_log_level_name(level)
    root_logger = logging.getLogger()
    handler = None
    for existing in root_logger.handlers:
        if getattr(existing, "_pypad_console_handler", False):
            handler = existing
            break
    if handler is None:
        handler = _CapturingStreamHandler(sys.__stdout__)
        handler._pypad_console_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(_PypadLogFormatter())
        root_logger.addHandler(handler)
    root_logger.setLevel(get_level_number(level_name))
    logging.captureWarnings(True)
    return level_name


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def _install_console_capture() -> None:
    global _console_capture_installed
    if _console_capture_installed:
        return
    if not getattr(sys.stdout, "_pypad_console_capture_wrapper", False):
        sys.stdout = _ConsoleCaptureTee(sys.stdout, label="stdout")
    if not getattr(sys.stderr, "_pypad_console_capture_wrapper", False):
        sys.stderr = _ConsoleCaptureTee(sys.stderr, label="stderr")
    _console_capture_installed = True
