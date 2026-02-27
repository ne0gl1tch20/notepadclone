from __future__ import annotations

import os
import re
import sys
import socket
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from pypad.ui.ai.ai_edit_preview_dialog import AIEditPreviewDialog, AIRewritePromptDialog
from pypad.ai_app_knowledge import DEFAULT_AI_APP_KNOWLEDGE
from pypad.logging_utils import get_logger
from pypad.ui.theme.asset_paths import resolve_asset_path

MISSING_API_KEY_MESSAGE = (
    "I don't have an API key! Do it in Settings > Preferences > AI and Updates > Gemini API Key! "
    "To add your own API Key, visit https://aistudio.google.com/app/api-keys"
)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
WINDOWS_PATH_RE = re.compile(r"(?<!\w)(?:[A-Za-z]:\\|\\\\)[^\s\"'<>|?*]+")
POSIX_PATH_RE = re.compile(r"(?<![\w:])/(?:[^/\s]+/)+[^/\s]+")
ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password|passwd)\b\s*[:=]\s*([^\s,;]+)"
)
BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/=]{8,}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\.[A-Za-z0-9_\-]+?\b")

_LOGGER = get_logger(__name__)


def sanitize_prompt_text(prompt: str, settings: dict) -> tuple[str, list[str]]:
    redacted = prompt
    changes: list[str] = []
    if bool(settings.get("ai_send_redact_emails", False)):
        updated, count = EMAIL_RE.subn("[REDACTED_EMAIL]", redacted)
        if count:
            redacted = updated
            changes.append(f"emails({count})")
    if bool(settings.get("ai_send_redact_paths", False)):
        updated, count_win = WINDOWS_PATH_RE.subn("[REDACTED_PATH]", redacted)
        updated, count_posix = POSIX_PATH_RE.subn("[REDACTED_PATH]", updated)
        total = count_win + count_posix
        if total:
            redacted = updated
            changes.append(f"paths({total})")
    if bool(settings.get("ai_send_redact_tokens", True)):
        updated, count_assign = ASSIGNMENT_SECRET_RE.subn(r"\1=[REDACTED_TOKEN]", redacted)
        updated, count_bearer = BEARER_TOKEN_RE.subn("Bearer [REDACTED_TOKEN]", updated)
        updated, count_jwt = JWT_RE.subn("[REDACTED_TOKEN]", updated)
        total = count_assign + count_bearer + count_jwt
        if total:
            redacted = updated
            changes.append(f"tokens({total})")
    return redacted, changes


class _AIWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str, api_key: str, model: str) -> None:
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            result = _generate_sync(self.prompt, self.api_key, self.model)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class _AIStreamWorker(QObject):
    chunk = Signal(str)
    finished = Signal(str)
    cancelled = Signal(str)
    failed = Signal(str)

    def __init__(self, prompt: str, api_key: str, model: str) -> None:
        super().__init__()
        self.prompt = prompt
        self.api_key = api_key
        self.model = model
        self._cancel_requested = False

    def cancel(self) -> None:
        _LOGGER.debug("AI stream worker cancel requested model=%s prompt_chars=%d", self.model, len(self.prompt))
        self._cancel_requested = True

    def run(self) -> None:
        _LOGGER.debug("AI stream worker run start model=%s prompt_chars=%d", self.model, len(self.prompt))
        try:
            parts: list[str] = []
            for piece in _generate_stream(self.prompt, self.api_key, self.model):
                if self._cancel_requested:
                    _LOGGER.debug("AI stream worker run cancelled-before-emit chunks=%d chars=%d", len(parts), len("".join(parts)))
                    self.cancelled.emit("".join(parts).strip())
                    return
                if not piece:
                    continue
                parts.append(piece)
                _LOGGER.debug("AI stream worker emit chunk chars=%d total_chunks=%d", len(piece), len(parts))
                self.chunk.emit(piece)
                if self._cancel_requested:
                    _LOGGER.debug("AI stream worker run cancelled-after-emit chunks=%d chars=%d", len(parts), len("".join(parts)))
                    self.cancelled.emit("".join(parts).strip())
                    return
            final_text = "".join(parts).strip()
            _LOGGER.debug("AI stream worker finished chunks=%d chars=%d", len(parts), len(final_text))
            self.finished.emit(final_text)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.exception("AI stream worker failed model=%s", self.model)
            self.failed.emit(str(exc))


def _generate_sync(prompt: str, api_key: str, model: str) -> str:
    if not api_key:
        raise RuntimeError(MISSING_API_KEY_MESSAGE)
    if not model.strip():
        raise RuntimeError("AI model is not configured. Set it in Settings > AI & Updates.")

    # Preferred SDK path (`google-genai`).
    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model.strip(),
            contents=prompt,
        )
        text = getattr(response, "text", None)
        if text:
            return str(text)
    except Exception:
        pass

    # Compatibility fallback (`google-generativeai`).
    try:
        import google.generativeai as legacy_genai  # type: ignore

        legacy_genai.configure(api_key=api_key)
        legacy_model = legacy_genai.GenerativeModel(model_name=model.strip())
        response = legacy_model.generate_content(prompt)
        text = getattr(response, "text", None)
        if text:
            return str(text)
    except Exception:
        pass

    raise RuntimeError(
        "AI request failed. Check your connection and try again. It is possible that the rate limit has been exceeded or the model is unavailable. Please try again later."
    )


def _split_for_live_ui(text: str) -> Iterator[str]:
    words = text.split()
    if not words:
        return
    chunk: list[str] = []
    size = 0
    for word in words:
        add_size = len(word) + (1 if chunk else 0)
        if size + add_size > 24 and chunk:
            yield " ".join(chunk) + " "
            chunk = [word]
            size = len(word)
            continue
        chunk.append(word)
        size += add_size
    if chunk:
        yield " ".join(chunk)


def _generate_stream(prompt: str, api_key: str, model: str) -> Iterator[str]:
    if not api_key:
        raise RuntimeError(MISSING_API_KEY_MESSAGE)
    if not model.strip():
        raise RuntimeError("AI model is not configured. Set it in Settings > AI & Updates.")

    try:
        from google import genai  # type: ignore

        client = genai.Client(api_key=api_key)
        stream = client.models.generate_content_stream(
            model=model.strip(),
            contents=prompt,
        )
        yielded = False
        for chunk in stream:
            text = str(getattr(chunk, "text", "") or "")
            if text:
                yielded = True
                yield text
        if yielded:
            return
    except Exception:
        pass

    text = _generate_sync(prompt, api_key, model)
    for piece in _split_for_live_ui(text):
        yield piece


class AIResultDialog(QDialog):
    def __init__(self, parent, title: str, text: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Result", self))
        self.output = QTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setPlainText(text)
        layout.addWidget(self.output)

        row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy", self)
        self.insert_btn = QPushButton("Insert", self)
        self.replace_btn = QPushButton("Replace Selection", self)
        row.addWidget(self.copy_btn)
        row.addWidget(self.insert_btn)
        row.addWidget(self.replace_btn)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, Qt.Horizontal, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.copy_btn.clicked.connect(self._copy_text)
        self.insert_btn.clicked.connect(self._insert_text)
        self.replace_btn.clicked.connect(self._replace_selection)

    def _copy_text(self) -> None:
        QApplication.clipboard().setText(self.output.toPlainText())

    def _insert_text(self) -> None:
        parent = self.parent()
        tab = parent.active_tab() if parent else None
        if tab is None:
            return
        tab.text_edit.insert_text(self.output.toPlainText())

    def _replace_selection(self) -> None:
        parent = self.parent()
        tab = parent.active_tab() if parent else None
        if tab is None:
            return
        tab.text_edit.replace_selection(self.output.toPlainText())


class AIRedactionPreviewDialog(QDialog):
    def __init__(self, parent, action_title: str, changes: list[str], original: str, redacted: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Prompt Redaction Preview")
        self.resize(920, 620)
        layout = QVBoxLayout(self)
        summary = QLabel(
            f"{action_title}: redactions applied ({', '.join(changes)}). The redacted prompt will be sent.",
            self,
        )
        layout.addWidget(summary)
        panes = QHBoxLayout()
        left = QTextEdit(self)
        right = QTextEdit(self)
        left.setReadOnly(True)
        right.setReadOnly(True)
        left.setPlainText(original)
        right.setPlainText(redacted)
        panes.addWidget(left, 1)
        panes.addWidget(right, 1)
        layout.addLayout(panes, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        ok_btn = buttons.button(QDialogButtonBox.Ok)
        if ok_btn is not None:
            ok_btn.setText("Send Redacted Prompt")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class AIController:
    def __init__(self, window) -> None:
        self.window = window
        self._threads: list[QThread] = []
        self._active_stream_worker: _AIStreamWorker | None = None
        self._active_stream_thread: QThread | None = None
        self._app_metadata_block = self._build_app_metadata_block()
        self._ai_request_counter = 0

    def _log_ai(self, message: str) -> None:
        if not bool(self.window.settings.get("ai_verbose_logging", False)):
            return
        logger = getattr(self.window, "log_event", None)
        if callable(logger):
            logger("Info", f"[AI] {message}")

    def _build_app_metadata_block(self) -> str:
        app_name = str(QApplication.applicationName() or "Pypad").strip() or "Pypad"
        version = "v?.?.?"
        try:
            version_file = resolve_asset_path("version.txt")
            if version_file is not None:
                version = version_file.read_text(encoding="utf-8").strip() or version
        except Exception:
            pass
        if getattr(os, "name", "") == "nt" and getattr(sys, "frozen", False):
            build = "windows-frozen"
        elif getattr(sys, "frozen", False):
            build = "frozen"
        else:
            build = "source"
        return (
            "[APP_METADATA]\n"
            f"app_name={app_name}\n"
            f"app_version={version}\n"
            f"app_build={build}\n"
            "[/APP_METADATA]"
        )

    def _build_app_knowledge_block(self) -> str:
        knowledge = str(DEFAULT_AI_APP_KNOWLEDGE or "").strip()
        if not knowledge:
            return ""
        return (
            "[PYPAD_KNOWLEDGE]\n"
            f"{knowledge}\n"
            "[/PYPAD_KNOWLEDGE]"
        )

    def _build_user_knowledge_block(self) -> str:
        # Keep built-in app knowledge intact; this field is user-appended guidance.
        user_knowledge = str(self.window.settings.get("ai_app_knowledge_override", "") or "").strip()
        if not user_knowledge:
            return ""
        return (
            "[PYPAD_USER_KNOWLEDGE]\n"
            f"{user_knowledge}\n"
            "[/PYPAD_USER_KNOWLEDGE]"
        )

    def _build_advanced_personality_block(self) -> str:
        personality = str(self.window.settings.get("ai_personality_advanced", "") or "").strip()
        if not personality:
            return ""
        return (
            "[PYPAD_AI_PERSONALITY_ADVANCED]\n"
            f"{personality}\n"
            "[/PYPAD_AI_PERSONALITY_ADVANCED]"
        )

    def _build_runtime_context_block(self) -> str:
        tab = self.window.active_tab() if hasattr(self.window, "active_tab") else None
        file_name = "Untitled"
        is_markdown = False
        has_selection = False
        selection_preview = ""
        if tab is not None:
            file_name = str(getattr(tab, "current_file", "") or "Untitled")
            is_markdown = bool(getattr(tab, "markdown_mode_enabled", False))
            try:
                has_selection = bool(tab.text_edit.has_selection())
                if has_selection:
                    selection_preview = str(tab.text_edit.selected_text() or "")[:500]
            except Exception:
                has_selection = False
                selection_preview = ""
        workspace_root = str(self.window.settings.get("workspace_root", "") or "").strip()
        return (
            "[APP_RUNTIME_CONTEXT]\n"
            f"active_file={file_name}\n"
            f"workspace_root={workspace_root or '(none)'}\n"
            f"markdown_mode={'true' if is_markdown else 'false'}\n"
            f"has_selection={'true' if has_selection else 'false'}\n"
            f"selection_preview={selection_preview}\n"
            "[/APP_RUNTIME_CONTEXT]"
        )

    def _api_key(self) -> str:
        storage_mode = str(self.window.settings.get("ai_key_storage_mode", "settings") or "settings").strip().lower()
        configured = str(self.window.settings.get("gemini_api_key", "") or "").strip()
        if storage_mode != "env_only" and configured:
            return configured
        return str(os.getenv("GEMINI_API_KEY", "")).strip()

    def _model(self) -> str:
        return str(self.window.settings.get("ai_model", "gemini-3-flash-preview") or "gemini-3-flash-preview")

    def _ai_private_mode_enabled(self) -> bool:
        return bool(self.window.settings.get("ai_private_mode", False))

    def _guard_ai_private_mode(self, title: str) -> bool:
        if not self._ai_private_mode_enabled():
            return False
        QMessageBox.information(
            self.window,
            title,
            "AI private mode is enabled. Disable it in Settings or the AI menu to run AI actions.",
        )
        return True

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, int(len(text) / 4)) if text else 0

    def _record_ai_metrics(self, *, action: str, prompt: str, response: str, model: str) -> None:
        tokens = self._estimate_tokens(prompt) + self._estimate_tokens(response)
        rate = float(self.window.settings.get("ai_estimated_cost_per_1k_tokens", 0.0005) or 0.0005)
        est_cost = (tokens / 1000.0) * rate
        self._log_ai(
            f"metrics action={action!r} model={model!r} tokens={tokens} est_cost=${est_cost:.6f}"
        )

        if hasattr(self.window, "record_ai_usage"):
            self.window.record_ai_usage(tokens=tokens, estimated_cost=est_cost)

        history = self.window.settings.get("ai_action_history", [])
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "model": model,
                "prompt_chars": len(prompt),
                "response_chars": len(response),
                "prompt_preview": prompt[:160],
                "response_preview": response[:200],
            }
        )
        self.window.settings["ai_action_history"] = history[-300:]
        if hasattr(self.window, "save_settings_to_disk"):
            self.window.save_settings_to_disk()

    def _prepare_prompt_for_send(self, prompt: str, action_title: str) -> str | None:
        candidate = prompt.strip()
        if not candidate:
            self._log_ai(f"prepare prompt skipped (empty) action={action_title!r}")
            return None
        self._log_ai(
            f"prepare prompt action={action_title!r} chars={len(candidate)}"
        )
        app_name = str(QApplication.applicationName() or "Pypad").strip() or "Pypad"
        self.window.settings["ai_last_prompt_app_name"] = app_name
        if hasattr(self.window, "save_settings_to_disk"):
            self.window.save_settings_to_disk()
        blocks = [
            self._app_metadata_block,
            self._build_app_knowledge_block(),
            self._build_user_knowledge_block(),
            self._build_advanced_personality_block(),
            self._build_runtime_context_block(),
            candidate,
        ]
        candidate = "\n\n".join(part for part in blocks if str(part).strip())
        redacted, changes = sanitize_prompt_text(candidate, self.window.settings)
        if not changes:
            self._log_ai(
                f"prompt redaction none action={action_title!r} final_chars={len(redacted)}"
            )
            return redacted
        self._log_ai(
            f"prompt redaction action={action_title!r} changes={','.join(changes)}"
        )
        if bool(self.window.settings.get("ai_preview_redacted_prompt", True)):
            dialog = AIRedactionPreviewDialog(self.window, action_title, changes, candidate, redacted)
            if dialog.exec() != QDialog.Accepted:
                self._log_ai(f"redaction preview canceled action={action_title!r}")
                self.window.show_status_message("AI request canceled by redaction preview.", 3000)
                return None
            self._log_ai(f"redaction preview accepted action={action_title!r}")
        return redacted

    @staticmethod
    def _has_internet_connection(timeout_sec: float = 0.8) -> bool:
        try:
            sock = socket.create_connection(("1.1.1.1", 53), timeout=timeout_sec)
            sock.close()
            return True
        except OSError:
            return False

    def _start_stream_generation(
        self,
        prompt: str,
        action_name: str,
        on_chunk: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
        on_cancel: Callable[[str], None] | None = None,
        *,
        debug_correlation_id: str | None = None,
    ) -> None:
        self._ai_request_counter += 1
        request_id = self._ai_request_counter
        if not self._has_internet_connection():
            self._log_ai(f"stream start blocked (offline) action={action_name!r} id={request_id}")
            on_error("You're offline! Check your connection and try again.")
            return
        prepared_prompt = self._prepare_prompt_for_send(prompt, action_name)
        if not prepared_prompt:
            self._log_ai(f"stream start canceled (prepare failed) action={action_name!r} id={request_id}")
            return
        api_key = self._api_key()
        model = self._model()
        self._log_ai(
            f"stream start action={action_name!r} id={request_id} model={model!r} prompt_chars={len(prepared_prompt)}"
        )
        _LOGGER.debug(
            "AIController stream start action=%r id=%d cid=%r model=%r prompt_chars=%d on_cancel=%s",
            action_name,
            request_id,
            debug_correlation_id,
            model,
            len(prepared_prompt),
            on_cancel is not None,
        )

        thread = QThread(self.window)
        worker = _AIStreamWorker(prepared_prompt, api_key, model)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _run_ui(action: Callable[[], None]) -> None:
            # Stream worker signals are connected to Python callables; without an explicit
            # receiver object Qt may invoke them on the worker thread. Marshal to UI thread.
            QTimer.singleShot(0, self.window, action)

        def _dispatch_chunk(piece: str) -> None:
            def _apply() -> None:
                _LOGGER.debug(
                    "AIController stream callback on_chunk action=%r id=%d chars=%d",
                    action_name,
                    request_id,
                    len(piece or ""),
                )
                if debug_correlation_id:
                    _LOGGER.debug("AIController stream callback on_chunk cid=%r", debug_correlation_id)
                on_chunk(piece)

            _run_ui(_apply)

        def _dispatch_done(text: str) -> None:
            def _apply() -> None:
                _LOGGER.debug(
                    "AIController stream callback on_done action=%r id=%d cid=%r chars=%d",
                    action_name,
                    request_id,
                    debug_correlation_id,
                    len(text or ""),
                )
                on_done(text)

            _run_ui(_apply)

        def _dispatch_error(message: str) -> None:
            def _apply() -> None:
                _LOGGER.debug(
                    "AIController stream callback on_error action=%r id=%d cid=%r message_len=%d",
                    action_name,
                    request_id,
                    debug_correlation_id,
                    len(message or ""),
                )
                on_error(message)

            _run_ui(_apply)

        worker.chunk.connect(_dispatch_chunk)
        worker.chunk.connect(
            lambda piece: _run_ui(
                lambda piece=piece: self._log_ai(
                    f"stream chunk action={action_name!r} id={request_id} chars={len(piece)}"
                )
            )
        )
        worker.finished.connect(
            lambda text: _run_ui(
                lambda text=text: self._record_ai_metrics(action=action_name, prompt=prepared_prompt, response=text, model=model)
            )
        )
        worker.finished.connect(
            lambda text: _run_ui(
                lambda text=text: self._log_ai(
                    f"stream finished action={action_name!r} id={request_id} chars={len(text)}"
                )
            )
        )
        worker.finished.connect(_dispatch_done)
        worker.failed.connect(
            lambda message: _run_ui(
                lambda message=message: self._log_ai(
                    f"stream failed action={action_name!r} id={request_id} error={message!r}"
                )
            )
        )
        worker.failed.connect(_dispatch_error)
        if on_cancel is not None:
            def _dispatch_cancel(text: str) -> None:
                def _apply() -> None:
                    _LOGGER.debug(
                        "AIController stream callback on_cancel action=%r id=%d cid=%r chars=%d",
                        action_name,
                        request_id,
                        debug_correlation_id,
                        len(text or ""),
                    )
                    on_cancel(text)

                _run_ui(_apply)

            worker.cancelled.connect(
                lambda text: _run_ui(
                    lambda text=text: self._log_ai(
                        f"stream cancelled action={action_name!r} id={request_id} chars={len(text)}"
                    )
                )
            )
            worker.cancelled.connect(_dispatch_cancel)
        worker.finished.connect(thread.quit)
        worker.cancelled.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        self._threads.append(thread)
        self._active_stream_worker = worker
        self._active_stream_thread = thread
        self.window.show_status_message(f"AI generating ({model})...", 0)
        _LOGGER.debug("AIController stream thread start action=%r id=%d cid=%r", action_name, request_id, debug_correlation_id)
        thread.start()

    def _insert_generated_text(self, text: str) -> bool:
        tab = self.window.active_tab()
        if tab is None:
            return False
        if tab.text_edit.get_text().strip():
            tab.text_edit.insert_text("\n\n")
        tab.text_edit.insert_text(text)
        return True

    def _start_generation(
        self,
        prompt: str,
        result_title: str,
        *,
        action_name: str = "Generate Text",
        auto_insert: bool = False,
        on_result: Callable[[str], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._ai_request_counter += 1
        request_id = self._ai_request_counter
        if not self._has_internet_connection():
            self._log_ai(f"start blocked (offline) action={action_name!r} id={request_id}")
            QMessageBox.information(
                self.window,
                action_name,
                "You're offline! Check your connection and try again.",
            )
            return
        prepared_prompt = self._prepare_prompt_for_send(prompt, action_name)
        if not prepared_prompt:
            self._log_ai(f"start canceled (prepare failed) action={action_name!r} id={request_id}")
            return
        api_key = self._api_key()
        model = self._model()
        self._log_ai(
            f"start action={action_name!r} id={request_id} model={model!r} prompt_chars={len(prepared_prompt)}"
        )

        thread = QThread(self.window)
        worker = _AIWorker(prepared_prompt, api_key, model)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            lambda text: self._record_ai_metrics(action=action_name, prompt=prepared_prompt, response=text, model=model)
        )
        worker.finished.connect(
            lambda text: self._log_ai(
                f"finished action={action_name!r} id={request_id} chars={len(text)}"
            )
        )
        worker.finished.connect(lambda text: self._on_result(thread, result_title, text, auto_insert, on_result=on_result))
        if on_error is None:
            worker.failed.connect(
                lambda message: self._log_ai(
                    f"failed action={action_name!r} id={request_id} error={message!r}"
                )
            )
            worker.failed.connect(lambda message: self._on_error(thread, message, result_title, model))
        else:
            worker.failed.connect(
                lambda message: self._log_ai(
                    f"failed action={action_name!r} id={request_id} error={message!r}"
                )
            )
            worker.failed.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._cleanup_thread(thread))
        self._threads.append(thread)
        self.window.show_status_message(f"AI generating ({model})...", 0)
        thread.start()

    def _cleanup_thread(self, thread: QThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)
        if thread is self._active_stream_thread:
            self._active_stream_thread = None
            self._active_stream_worker = None
        thread.deleteLater()
        self._log_ai("generation thread cleaned up")
        self.window.show_status_message("AI generation finished.", 3000)

    def _on_result(
        self,
        _thread: QThread,
        title: str,
        text: str,
        auto_insert: bool,
        on_result: Callable[[str], None] | None = None,
    ) -> None:
        self._log_ai(f"result delivered title={title!r} chars={len(text)} auto_insert={auto_insert}")
        if on_result is not None:
            on_result(text)
            return
        if auto_insert and self._insert_generated_text(text):
            self.window.show_status_message("Generated text inserted into current tab.", 3000)
        dialog = AIResultDialog(self.window, title, text)
        dialog.exec()

    def _on_error(self, _thread: QThread, message: str, action_title: str, model: str) -> None:
        self._log_ai(f"error action={action_title!r} model={model!r} message={message!r}")
        self._show_error_with_details(
            title="Error Generating Text",
            summary=f"Error generating text for '{action_title}'.",
            details=f"Model: {model}\n\n{message}",
        )

    def _show_error_with_details(self, title: str, summary: str, details: str) -> None:
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Critical)
        box.setText(summary)
        box.setInformativeText("Open 'Show Details...' for technical information.")
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def ask_ai(self) -> None:
        if self._guard_ai_private_mode("Ask AI"):
            return
        if hasattr(self.window, "toggle_ai_chat_panel"):
            self.window.toggle_ai_chat_panel(True)
            return
        prompt, ok = QInputDialog.getMultiLineText(self.window, "Ask AI", "Prompt:")
        if not ok or not prompt.strip():
            return
        self._start_generation(prompt, "AI Response", action_name="Ask AI")

    def explain_selection(self) -> None:
        if self._guard_ai_private_mode("Explain Selection"):
            return
        tab = self.window.active_tab()
        if tab is None:
            return
        selected = tab.text_edit.selected_text().strip()
        if not selected:
            QMessageBox.information(self.window, "Explain Selection", "Select text first.")
            return
        prompt = f"Explain this text: {selected}"
        self._start_generation(prompt, "AI Explanation", action_name="Explain Selection")

    def generate_to_tab(self) -> None:
        if self._guard_ai_private_mode("Generate Text"):
            return
        tab = self.window.active_tab()
        if tab is None:
            QMessageBox.information(self.window, "Generate Text", "Open a tab first.")
            return
        prompt, ok = QInputDialog.getMultiLineText(self.window, "Generate Text", "Prompt:")
        if not ok or not prompt.strip():
            return
        self._start_generation(prompt, "Generated Text", action_name="Generate To Tab", auto_insert=True)

    def rewrite_selection(self, mode: str) -> None:
        if self._guard_ai_private_mode("AI Rewrite"):
            return
        tab = self.window.active_tab()
        if tab is None:
            return
        selected = tab.text_edit.selected_text().strip()
        if not selected:
            QMessageBox.information(self.window, "AI Rewrite", "Select text first.")
            return
        prompts = {
            "shorten": "Rewrite the text to be concise while preserving meaning.",
            "formal": "Rewrite the text in a formal professional tone.",
            "fix_grammar": "Fix grammar and punctuation while preserving tone.",
            "summarize": "Summarize this text into a concise version.",
        }
        dialog = AIRewritePromptDialog(self.window, selected[:800], prompts)
        try:
            dialog.mode_combo.setCurrentText(mode)
        except Exception:
            pass
        if dialog.exec() != QDialog.Accepted:
            return
        instruction = dialog.instruction() or prompts.get(mode, "Rewrite the text.")
        prompt = f"{instruction}\n\nText:\n{selected}"

        progress = QProgressDialog("AI rewrite in progress...", "Cancel", 0, 0, self.window)
        progress.setWindowTitle("AI Rewrite")
        progress.setWindowModality(Qt.NonModal)
        progress.setCancelButtonText("Cancel")
        progress.setMinimumDuration(0)
        progress.show()
        progress.canceled.connect(self.cancel_active_chat_request)

        def _run_ui(action: Callable[[], None]) -> None:
            QTimer.singleShot(0, self.window, action)

        def on_rewrite_result(result: str) -> None:
            progress.close()
            progress.deleteLater()
            requires_approval = bool(self.window.settings.get("ai_rewrite_require_approval", True))
            if requires_approval:
                preview = AIEditPreviewDialog(self.window, selected, result, title=f"AI Rewrite Preview ({mode})")
                if preview.exec() != QDialog.Accepted:
                    return
                final_text = preview.final_text
            else:
                final_text = result
            QApplication.clipboard().setText(final_text)
            tab.text_edit.replace_selection(final_text)
            self.window.show_status_message("AI rewrite applied (copied to clipboard).", 3000)

        def on_rewrite_error(message: str) -> None:
            def _apply() -> None:
                progress.close()
                progress.deleteLater()
                model = self._model()
                self._on_error(self._active_stream_thread, message, f"AI Rewrite ({mode})", model)

            _run_ui(_apply)

        chunks: list[str] = []

        def on_chunk(piece: str) -> None:
            if piece:
                chunks.append(piece)

        def on_cancel(partial: str) -> None:
            def _apply() -> None:
                progress.close()
                progress.deleteLater()
                self.window.show_status_message("AI rewrite canceled.", 3000)

            _run_ui(_apply)

        def on_done(text: str) -> None:
            if not text and chunks:
                text = "".join(chunks).strip()
            _run_ui(lambda: on_rewrite_result(text))

        self._start_stream_generation(
            prompt,
            action_name=f"Rewrite Selection ({mode})",
            on_chunk=on_chunk,
            on_done=on_done,
            on_error=on_rewrite_error,
            on_cancel=on_cancel,
        )

    def ask_about_context(self) -> None:
        if self._guard_ai_private_mode("Ask About File"):
            return
        tab = self.window.active_tab()
        if tab is None:
            QMessageBox.information(self.window, "Ask About File", "Open a tab first.")
            return
        question, ok = QInputDialog.getMultiLineText(self.window, "Ask About File", "Question:")
        if not ok or not question.strip():
            return
        file_name = tab.current_file or "Untitled"
        content = tab.text_edit.get_text()
        context = content[:20000]
        prompt = (
            f"You are helping with the current file.\n"
            f"File: {file_name}\n\n"
            f"Question:\n{question.strip()}\n\n"
            f"File contents (possibly truncated):\n{context}"
        )
        self._start_generation(prompt, "AI File Context Answer", action_name="Ask About File")

    def ask_ai_chat(
        self,
        prompt: str,
        on_chunk: Callable[[str], None],
        on_done: Callable[[str], None],
        on_error: Callable[[str], None],
        on_cancel: Callable[[str], None] | None = None,
        *,
        debug_correlation_id: str | None = None,
    ) -> None:
        if self._guard_ai_private_mode("AI Chat"):
            return
        _LOGGER.debug(
            "AIController.ask_ai_chat prompt_chars=%d on_cancel=%s cid=%r",
            len(prompt or ""),
            on_cancel is not None,
            debug_correlation_id,
        )
        self._start_stream_generation(
            prompt,
            "AI Chat",
            on_chunk,
            on_done,
            on_error,
            on_cancel=on_cancel,
            debug_correlation_id=debug_correlation_id,
        )

    def cancel_active_chat_request(self) -> bool:
        if self._active_stream_worker is None:
            _LOGGER.debug("AIController.cancel_active_chat_request no active stream")
            return False
        self._log_ai("cancel requested for active stream")
        _LOGGER.debug("AIController.cancel_active_chat_request dispatching cancel to active worker")
        self._active_stream_worker.cancel()
        self.window.show_status_message("AI generation cancel requested.", 2000)
        return True

