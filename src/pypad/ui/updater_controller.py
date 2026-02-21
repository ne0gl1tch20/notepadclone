from __future__ import annotations

import ctypes
import hashlib
import os
import re
import socket
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PySide6.QtCore import QObject, QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from ..app_settings.defaults import DEFAULT_UPDATE_FEED_URL
from .updater_helpers import UpdateInfo, is_newer_version, parse_update_feed, verify_metadata_signature

def _read_app_version() -> str:
    app_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    version_file = app_root / "assets" / "version.txt"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "v?.?.?"
    return version or "v?.?.?"


APP_VERSION = _read_app_version()
CHECK_TIMEOUT_SEC = 3
DOWNLOAD_TIMEOUT_SEC = 20
CHECK_WATCHDOG_SEC = 6


class _UpdateCheckWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, feed_url: str) -> None:
        super().__init__()
        self.feed_url = feed_url

    def run(self) -> None:
        self.status.emit(f"Worker started for feed: {self.feed_url}")
        try:
            self.status.emit("Opening update feed URL...")
            with urlopen(self.feed_url, timeout=CHECK_TIMEOUT_SEC) as response:  # noqa: S310
                status_code = getattr(response, "status", "unknown")
                self.status.emit(f"Feed connection opened (status={status_code}). Reading body...")
                xml_text = response.read().decode("utf-8", errors="replace")
                self.status.emit(f"Feed body read: {len(xml_text)} chars")
        except (TimeoutError, socket.timeout):
            self.status.emit("Worker timeout while checking feed.")
            self.failed.emit(
                f"Network timeout while checking updates (>{CHECK_TIMEOUT_SEC}s).\n"
                "Please check your connection and try again."
            )
            return
        except URLError as exc:
            self.status.emit(f"Worker URLError while checking feed: {exc}")
            if isinstance(getattr(exc, "reason", None), socket.timeout):
                self.failed.emit(
                    f"Network timeout while checking updates (>{CHECK_TIMEOUT_SEC}s).\n"
                    "Please check your connection and try again."
                )
                return
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Worker exception while checking feed: {exc}")
            self.failed.emit(str(exc))
            return
        self.status.emit("Parsing update feed payload...")
        info = parse_update_feed(xml_text)
        self.status.emit(f"Parser result: {'metadata found' if info is not None else 'no metadata'}")
        self.finished.emit(info)


class _UpdateDownloadWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, download_url: str, destination: str) -> None:
        super().__init__()
        self.download_url = download_url
        self.destination = destination

    def run(self) -> None:
        self.status.emit(f"Worker started for download: {self.download_url}")
        try:
            self.status.emit("Opening download URL...")
            with urlopen(self.download_url, timeout=DOWNLOAD_TIMEOUT_SEC) as response:  # noqa: S310
                status_code = getattr(response, "status", "unknown")
                self.status.emit(f"Download connection opened (status={status_code}). Reading bytes...")
                data = response.read()
                self.status.emit(f"Download body read: {len(data)} bytes")
            self.status.emit(f"Writing file to: {self.destination}")
            Path(self.destination).write_bytes(data)
        except (TimeoutError, socket.timeout):
            self.status.emit("Worker timeout while downloading update.")
            self.failed.emit(f"Network timeout while downloading update (>{DOWNLOAD_TIMEOUT_SEC}s).")
            return
        except URLError as exc:
            self.status.emit(f"Worker URLError while downloading update: {exc}")
            if isinstance(getattr(exc, "reason", None), socket.timeout):
                self.failed.emit(f"Network timeout while downloading update (>{DOWNLOAD_TIMEOUT_SEC}s).")
                return
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self.status.emit(f"Worker exception while downloading update: {exc}")
            self.failed.emit(str(exc))
            return
        self.status.emit("Download worker finished successfully.")
        self.finished.emit(self.destination)


class UpdaterController(QObject):
    def __init__(self, window) -> None:
        super().__init__(window)
        self.window = window
        self._threads: list[QThread] = []
        self._manual_check = True
        self._last_info: UpdateInfo | None = None
        self._last_feed_url = DEFAULT_UPDATE_FEED_URL
        self._progress_dialog: QProgressDialog | None = None
        self._check_started_at: float = 0.0
        self._check_in_progress = False
        self._check_request_seq = 0
        self._active_check_id = 0
        self._timed_out_check_ids: set[int] = set()
        self._workers: dict[QThread, QObject] = {}
        self._check_workers: dict[_UpdateCheckWorker, tuple[QThread, int]] = {}
        self._download_workers: dict[_UpdateDownloadWorker, QThread] = {}
        self._active_check_thread: QThread | None = None
        self._update_available_box: QMessageBox | None = None
        self._pending_download_version: str = ""
        self._pending_download_sha256: str = ""
        self._pending_download_signature: str = ""
        self._cleanup_pending_update_capsule()
        pending_state = self._pending_capsule_state_text()
        self._log_update(f"Pending update capsule state: {pending_state}")
        print(f"[Updater] Pending update capsule state: {pending_state}")

    def _log_update(self, message: str) -> None:
        if hasattr(self.window, "log_event"):
            try:
                self.window.log_event("Info", f"[Updater] {message}")
                return
            except Exception:
                pass
        print(f"[Updater] {message}")

    def check_for_updates(self, manual: bool = True) -> None:
        if self._check_in_progress:
            self._log_update("Update check requested while another check is already running.")
            if manual:
                QMessageBox.information(
                    self.window,
                    "Check for Updates",
                    "An update check is already in progress. Please wait a moment.",
                )
            return
        feed_url = str(self.window.settings.get("update_feed_url", DEFAULT_UPDATE_FEED_URL) or "").strip()
        if not feed_url:
            feed_url = DEFAULT_UPDATE_FEED_URL
        if not feed_url:
            if manual:
                self._show_error_with_details(
                    title="Check for Updates Error",
                    summary="Update feed URL is empty.",
                    details="Configure it in Settings > AI & Updates.",
                )
            return
        self._manual_check = manual
        self._last_feed_url = feed_url
        self._check_started_at = time.monotonic()
        self._check_in_progress = True
        self._check_request_seq += 1
        check_id = self._check_request_seq
        self._active_check_id = check_id
        self._log_update(
            f"Starting update check (id={check_id}, manual={manual}) feed={feed_url} timeout={CHECK_TIMEOUT_SEC}s watchdog={CHECK_WATCHDOG_SEC}s"
        )
        if manual:
            self._show_checking_progress(feed_url)
        worker = _UpdateCheckWorker(feed_url)
        thread = QThread(self.window)
        self._workers[thread] = worker
        self._check_workers[worker] = (thread, check_id)
        self._active_check_thread = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self._on_check_worker_status)
        worker.finished.connect(self._on_check_worker_finished)
        worker.failed.connect(self._on_check_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append(thread)
        self.window.show_status_message("Checking for updates...", 0)
        self._log_update(f"Check thread queued to start (id={check_id}).")
        thread.start()
        QTimer.singleShot(CHECK_WATCHDOG_SEC * 1000, lambda cid=check_id: self._on_check_watchdog_timeout(cid))

    def _on_checked(self, _thread: QThread, info: object, check_id: int) -> None:
        if check_id in self._timed_out_check_ids:
            self._timed_out_check_ids.discard(check_id)
            self._log_update(f"Ignoring late successful result for timed-out check (id={check_id}).")
            return
        if check_id != self._active_check_id:
            self._log_update(f"Ignoring stale successful result (id={check_id}, active={self._active_check_id}).")
            return
        self._check_in_progress = False
        self._close_checking_progress()
        elapsed = max(0.0, time.monotonic() - self._check_started_at)
        self._log_update(f"Update check finished (id={check_id}) in {elapsed:.2f}s")
        self.window.show_status_message("Update check complete.", 3000)
        if info is None:
            self._log_update("Feed parsed but no update metadata was found.")
            if self._manual_check:
                self._show_error_with_details(
                    title="Check for Updates Error",
                    summary="No update metadata found in feed.",
                    details="Please verify your XML format and required fields (version/download URL).",
                )
            return
        if not isinstance(info, UpdateInfo):
            self._log_update(f"Feed parsed into unexpected type: {type(info).__name__}")
            if self._manual_check:
                self._show_error_with_details(
                    title="Check for Updates Error",
                    summary="Received invalid update metadata.",
                    details=f"Parsed object type: {type(info).__name__}",
                )
            return
        self._last_info = info
        self._log_update(
            "Feed metadata: "
            f"version={info.version or 'unknown'} "
            f"download_url={'yes' if bool(info.download_url) else 'no'} "
            f"pub_date={info.pub_date or 'n/a'}"
        )
        if not is_newer_version(info.version, APP_VERSION):
            self._log_update(f"No update: current={APP_VERSION} remote={info.version or 'unknown'}")
            if self._manual_check:
                QMessageBox.information(
                    self.window,
                    "App Is Up To Date",
                    (
                        "No updates are available right now.\n"
                        f"Feed: {self._last_feed_url}\n"
                        f"Current: {APP_VERSION}\n"
                        f"Latest in feed: {info.version or 'unknown'}"
                    ),
                )
                self._log_update("Displayed 'App Is Up To Date' dialog.")
            return

        metadata_error = self._validate_update_metadata(info)
        if metadata_error:
            self._log_update(f"Update metadata validation failed: {metadata_error}")
            if self._manual_check:
                self._show_error_with_details(
                    title="Update Metadata Validation Failed",
                    summary="Update metadata is invalid or untrusted.",
                    details=metadata_error,
                )
            return

        self._log_update(f"Update available: current={APP_VERSION} remote={info.version or 'unknown'}")
        details = [f"Current: {APP_VERSION}", f"Latest: {info.version or 'unknown'}"]
        if info.pub_date:
            details.append(f"Published: {info.pub_date}")
        details.append(f"SHA256: {info.sha256 or 'missing'}")
        details.append(f"Signature: {'present' if bool(info.signature) else 'missing'}")
        if info.changelog:
            details.append("")
            details.append("Changelog:")
            details.append(info.changelog[:4000])
        text = "\n".join(details)

        box = QMessageBox(self.window)
        box.setWindowTitle("Update Available")
        box.setIcon(QMessageBox.Information)
        box.setText(info.title or "Update available")
        box.setInformativeText(text)
        download_btn = box.addButton("Download and Update", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.setWindowModality(Qt.WindowModality.WindowModal)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._update_available_box = box

        def _on_finished(_result: int, dialog=box, dl_btn=download_btn, update_info=info) -> None:
            clicked = dialog.clickedButton()
            self._update_available_box = None
            if clicked == dl_btn:
                self._log_update("User chose 'Download and Update'.")
                self.download_update(update_info)
            else:
                self._log_update("User chose 'Later' on update dialog.")

        box.finished.connect(_on_finished)
        self._log_update("Opening non-blocking 'Update Available' dialog.")
        box.open()

    def _on_check_failed(self, _thread: QThread, message: str, check_id: int) -> None:
        if check_id in self._timed_out_check_ids:
            self._timed_out_check_ids.discard(check_id)
            self._log_update(f"Ignoring late failed result for timed-out check (id={check_id}): {message}")
            return
        if check_id != self._active_check_id:
            self._log_update(f"Ignoring stale failed result (id={check_id}, active={self._active_check_id}): {message}")
            return
        self._check_in_progress = False
        self._close_checking_progress()
        elapsed = max(0.0, time.monotonic() - self._check_started_at)
        self._log_update(f"Update check failed (id={check_id}) after {elapsed:.2f}s: {message}")
        self.window.show_status_message("Update check failed.", 4000)
        if self._manual_check:
            self._show_error_with_details(
                title="Check for Updates Error",
                summary="Could not check for updates.",
                details=message,
            )

    def _on_check_watchdog_timeout(self, check_id: int) -> None:
        if not self._check_in_progress:
            return
        if check_id != self._active_check_id:
            return
        self._timed_out_check_ids.add(check_id)
        self._check_in_progress = False
        self._close_checking_progress()
        elapsed = max(0.0, time.monotonic() - self._check_started_at)
        message = (
            f"Update check exceeded watchdog timeout ({CHECK_WATCHDOG_SEC}s). "
            "Network call may be blocked or stalled."
        )
        self._log_update(f"Watchdog timeout for check (id={check_id}) after {elapsed:.2f}s.")
        stuck_thread = self._active_check_thread
        if stuck_thread is not None and stuck_thread.isRunning():
            self._log_update(f"Requesting check thread stop after watchdog timeout (id={check_id}).")
            stuck_thread.requestInterruption()
            stuck_thread.quit()
        self.window.show_status_message("Update check timed out.", 5000)
        if self._manual_check:
            self._show_error_with_details(
                title="Check for Updates Timeout",
                summary="Update check took too long and was canceled.",
                details=message,
            )

    def _show_checking_progress(self, feed_url: str) -> None:
        self._close_checking_progress()
        dlg = QProgressDialog(self.window)
        dlg.setWindowTitle("Checking for Updates")
        dlg.setLabelText(
            "Checking update feed...\n"
            f"{feed_url}\n\n"
            f"Timeout: {CHECK_TIMEOUT_SEC}s"
        )
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setRange(0, 0)  # indeterminate/loading
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.show()
        QApplication.processEvents()
        self._progress_dialog = dlg
        self._log_update("Displayed checking-progress dialog.")
        QTimer.singleShot(1200, self._refresh_progress_waiting_text)

    def _on_check_worker_status(self, message: str) -> None:
        self._log_update(f"[CheckWorker] {message}")

    def _on_check_worker_finished(self, info: object) -> None:
        worker = self.sender()
        if not isinstance(worker, _UpdateCheckWorker):
            return
        meta = self._check_workers.get(worker)
        if meta is None:
            return
        thread, check_id = meta
        self._on_checked(thread, info, check_id)

    def _on_check_worker_failed(self, message: str) -> None:
        worker = self.sender()
        if not isinstance(worker, _UpdateCheckWorker):
            return
        meta = self._check_workers.get(worker)
        if meta is None:
            return
        thread, check_id = meta
        self._on_check_failed(thread, message, check_id)

    def _refresh_progress_waiting_text(self) -> None:
        dlg = self._progress_dialog
        if dlg is None:
            return
        dlg.setLabelText(
            "Still checking for updates...\n"
            f"{self._last_feed_url}\n\n"
            f"Timeout: {CHECK_TIMEOUT_SEC}s"
        )
        self._log_update("Updated progress dialog label to 'Still checking...'.")

    def _close_checking_progress(self) -> None:
        dlg = self._progress_dialog
        self._progress_dialog = None
        if dlg is None:
            return
        try:
            dlg.close()
            dlg.deleteLater()
            self._log_update("Closed checking-progress dialog.")
        except RuntimeError:
            pass

    def download_update(self, info: UpdateInfo | None = None) -> None:
        update = info or self._last_info
        if update is None or not update.download_url:
            self._log_update("Download requested but no downloadable URL was available.")
            QMessageBox.information(self.window, "Download Update", "No downloadable update found.")
            return

        destination = self._build_capsule_destination(update.download_url)
        self._pending_download_version = str(update.version or "").strip()
        self._pending_download_sha256 = str(update.sha256 or "").strip().lower()
        self._pending_download_signature = str(update.signature or "").strip()
        worker = _UpdateDownloadWorker(update.download_url, destination)
        self._log_update(f"Starting update download: {update.download_url} -> {destination}")
        thread = QThread(self.window)
        self._workers[thread] = worker
        self._download_workers[worker] = thread
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.status.connect(self._on_download_worker_status)
        worker.finished.connect(self._on_download_worker_finished)
        worker.failed.connect(self._on_download_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        self._threads.append(thread)
        self.window.show_status_message("Downloading update...", 0)
        self._log_update("Download thread queued to start.")
        thread.start()

    def _on_download_finished(self, _thread: QThread, path: str) -> None:
        hash_error = self._verify_download_hash(path, self._pending_download_sha256)
        if hash_error:
            self._log_update(f"Downloaded installer failed hash validation: {hash_error}")
            self.window.show_status_message("Downloaded update failed SHA256 verification.", 5000)
            self._show_error_with_details(
                title="Update Integrity Check Failed",
                summary="The downloaded installer failed SHA256 verification.",
                details=hash_error,
            )
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass
            return
        self._log_update(f"Update download finished: {path}")
        self._persist_pending_update_capsule(path, self._pending_download_version)
        self.window.show_status_message(f"Update downloaded: {path}", 4000)
        box = QMessageBox(self.window)
        box.setWindowTitle("Update Downloaded")
        box.setIcon(QMessageBox.Information)
        box.setText("Update installer is ready.")
        box.setInformativeText("A temporary update capsule has been downloaded and is ready to run.")
        box.setDetailedText(path)
        open_btn = box.addButton("Open Installer", QMessageBox.AcceptRole)
        box.addButton("Close", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() == open_btn:
            self._log_update("User chose 'Open Installer'.")
            if self._open_path(path):
                self._log_update("Installer started successfully; closing app to avoid phantom task.")
                QApplication.instance().quit()
        else:
            self._log_update("User closed update-downloaded dialog without opening installer.")

    def _on_download_failed(self, _thread: QThread, message: str) -> None:
        self._log_update(f"Update download failed: {message}")
        self.window.show_status_message("Update download failed.", 4000)
        self._show_error_with_details(
            title="Update Download Failed",
            summary="Could not download update.",
            details=message,
        )

    def _on_download_worker_status(self, message: str) -> None:
        self._log_update(f"[DownloadWorker] {message}")

    def _on_download_worker_finished(self, path: str) -> None:
        worker = self.sender()
        if not isinstance(worker, _UpdateDownloadWorker):
            return
        thread = self._download_workers.get(worker)
        if thread is None:
            return
        self._on_download_finished(thread, path)

    def _on_download_worker_failed(self, message: str) -> None:
        worker = self.sender()
        if not isinstance(worker, _UpdateDownloadWorker):
            return
        thread = self._download_workers.get(worker)
        if thread is None:
            return
        self._on_download_failed(thread, message)

    def _open_path(self, path: str) -> bool:
        try:
            if os.name == "nt":
                self._log_update(f"Opening installer as administrator via ShellExecuteW runas: {path}")
                rc = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
                    None,
                    "runas",
                    str(Path(path).resolve()),
                    None,
                    None,
                    1,
                )
                if int(rc) <= 32:
                    raise RuntimeError(f"ShellExecuteW failed with code {int(rc)}")
            else:
                self._log_update(f"Opening installer via webbrowser: {path}")
                webbrowser.open(f"file://{Path(path).resolve()}")
            return True
        except Exception as exc:  # noqa: BLE001
            self._log_update(f"Failed to open installer: {exc}")
            self._show_error_with_details(
                title="Install Update Error",
                summary="Could not open installer.",
                details=str(exc),
            )
            return False

    def _build_capsule_destination(self, download_url: str) -> str:
        filename = Path(download_url.split("?")[0]).name or "pypad-update.bin"
        capsule_dir = Path(tempfile.gettempdir()) / "pypad"
        capsule_dir.mkdir(parents=True, exist_ok=True)
        base = f"update-capsule-{int(time.time())}-{filename}"
        return str(capsule_dir / base)

    def _persist_pending_update_capsule(self, path: str, version: str) -> None:
        self.window.settings["pending_update_installer_path"] = path
        self.window.settings["pending_update_version"] = version
        save_settings = getattr(self.window, "save_settings_to_disk", None)
        if callable(save_settings):
            try:
                save_settings()
            except Exception as exc:  # noqa: BLE001
                self._log_update(f"Failed to persist pending update capsule metadata: {exc}")

    def _clear_pending_update_capsule(self) -> None:
        self.window.settings.pop("pending_update_installer_path", None)
        self.window.settings.pop("pending_update_version", None)
        save_settings = getattr(self.window, "save_settings_to_disk", None)
        if callable(save_settings):
            try:
                save_settings()
            except Exception as exc:  # noqa: BLE001
                self._log_update(f"Failed to clear pending update capsule metadata: {exc}")

    def _cleanup_pending_update_capsule(self) -> None:
        path_raw = str(self.window.settings.get("pending_update_installer_path", "") or "").strip()
        version_raw = str(self.window.settings.get("pending_update_version", "") or "").strip()
        if not path_raw:
            return
        capsule_path = Path(path_raw)
        can_delete = bool(version_raw) and not is_newer_version(version_raw, APP_VERSION)
        if can_delete and capsule_path.exists():
            try:
                capsule_path.unlink()
                self._log_update(f"Deleted stale update capsule after restart: {capsule_path}")
            except Exception as exc:  # noqa: BLE001
                self._log_update(f"Failed to delete stale update capsule: {exc}")
                return
        if can_delete or not capsule_path.exists():
            self._clear_pending_update_capsule()

    def _pending_capsule_state_text(self) -> str:
        path_raw = str(self.window.settings.get("pending_update_installer_path", "") or "").strip()
        version_raw = str(self.window.settings.get("pending_update_version", "") or "").strip()
        if not path_raw:
            return "none"
        return f"version={version_raw or 'unknown'} path={path_raw}"

    def _cleanup_thread(self, thread: QThread) -> None:
        self._workers.pop(thread, None)
        for worker, meta in list(self._check_workers.items()):
            if meta[0] is thread:
                self._check_workers.pop(worker, None)
        for worker, worker_thread in list(self._download_workers.items()):
            if worker_thread is thread:
                self._download_workers.pop(worker, None)
        if thread is self._active_check_thread:
            self._active_check_thread = None
        if thread in self._threads:
            self._threads.remove(thread)
        self._log_update(f"Thread cleanup complete. Active updater threads: {len(self._threads)}")
        thread.deleteLater()

    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if isinstance(thread, QThread):
            self._cleanup_thread(thread)

    def _show_error_with_details(self, title: str, summary: str, details: str) -> None:
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Critical)
        box.setText(summary)
        box.setInformativeText("Open 'Show Details...' for technical information.")
        box.setDetailedText(details)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _validate_update_metadata(self, info: UpdateInfo) -> str | None:
        digest = str(info.sha256 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            return "Feed must provide a valid 64-char SHA256 digest for the installer."
        signature = str(info.signature or "").strip().lower()
        require_signed = bool(self.window.settings.get("update_require_signed_metadata", False))
        if not signature:
            return "Signed metadata is required but signature is missing." if require_signed else None
        signing_key = str(
            self.window.settings.get("update_signing_key", "")
            or os.getenv("PYPAD_UPDATE_SIGNING_KEY", "")
            or os.getenv("NOTEPAD_UPDATE_SIGNING_KEY", "")
        ).strip()
        if not signing_key:
            return "Feed signature is present but signing key is not configured (settings or PYPAD_UPDATE_SIGNING_KEY)."
        if not verify_metadata_signature(info, signing_key):
            return "Feed signature does not match metadata payload."
        return None

    def _verify_download_hash(self, path: str, expected_sha256: str) -> str | None:
        expected = str(expected_sha256 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            return "Expected SHA256 is missing or malformed."
        try:
            hasher = hashlib.sha256()
            with open(path, "rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
            actual = hasher.hexdigest().lower()
        except Exception as exc:  # noqa: BLE001
            return f"Could not compute SHA256: {exc}"
        if actual != expected:
            return f"Expected SHA256: {expected}\nActual SHA256:   {actual}"
        return None
