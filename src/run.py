import argparse
import atexit
import faulthandler
import os
import sys
import threading
import traceback
from pathlib import Path
from time import perf_counter
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QFontDatabase, QFont
from PySide6.QtCore import QObject, QEvent, Qt, QTimer, qInstallMessageHandler, QtMsgType

_MAIN_WINDOW = None

# --- Add ROOT for imports ---
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypad.app import main
from pypad.app_settings import get_crash_logs_file_path
from pypad.logging_utils import configure_app_logging, get_logger
from pypad.ui.theme.asset_paths import resolve_asset_path

configure_app_logging("INFO")
LOGGER = get_logger(__name__)


def _build_shell_open_command() -> str:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        return f'"{exe}" "%1"'
    python_exe = Path(sys.executable).resolve()
    script = Path(__file__).resolve()
    return f'"{python_exe}" "{script}" "%1"'


def _register_windows_shell_menu() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows shell integration is only supported on Windows.")
    import winreg

    label = "Open with Pypad"
    icon_target = Path(sys.executable).resolve()
    command = _build_shell_open_command()
    key_path = r"Software\Classes\*\shell\Open with Pypad"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, label)
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, str(icon_target))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command") as cmd:
        winreg.SetValueEx(cmd, "", 0, winreg.REG_SZ, command)


def _delete_registry_tree(root, subkey: str) -> None:
    import winreg

    with winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        while True:
            try:
                child_name = winreg.EnumKey(key, 0)
            except OSError:
                break
            _delete_registry_tree(root, subkey + "\\" + child_name)
    winreg.DeleteKey(root, subkey)


def _unregister_windows_shell_menu() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows shell integration is only supported on Windows.")
    import winreg

    key_path = r"Software\Classes\*\shell\Open with Pypad"
    try:
        _delete_registry_tree(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass


def _save_startup_traceback(traceback_text: str) -> None:
    try:
        path = get_crash_logs_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("[Startup Crash]\n")
            handle.write(traceback_text.rstrip("\n"))
            handle.write("\n\n")
    except Exception:
        pass


def _startup_log(message: str) -> None:
    LOGGER.info(message)
    _save_startup_traceback(f"[Startup] {message}")


def _install_startup_exception_hooks() -> None:
    def _handle_exception(exc_type, exc_value, exc_tb) -> None:
        error_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_tb)
        ).strip()
        _save_startup_traceback(error_text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        error_text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        ).strip()
        _save_startup_traceback(error_text)
        if args.thread is not None:
            sys.__excepthook__(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = _handle_exception
    threading.excepthook = _handle_thread_exception

    # Capture Qt warnings/critical/fatal messages.
    def _qt_message_handler(mode, context, message) -> None:
        if isinstance(mode, QtMsgType):
            mode_name = mode.name
        else:
            mode_name = str(mode)
        location = ""
        if context is not None:
            parts = []
            if context.file:
                parts.append(context.file)
            if context.line:
                parts.append(str(context.line))
            if context.function:
                parts.append(context.function)
            if parts:
                location = " (" + ":".join(parts) + ")"
        _save_startup_traceback(f"[Qt:{mode_name}]{location} {message}")
    qInstallMessageHandler(_qt_message_handler)

    # Capture low-level crashes (segfaults, aborts) to the same log.
    try:
        path = get_crash_logs_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            faulthandler.enable(file=handle, all_threads=True)
    except Exception:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--register-shell-menu",
        action="store_true",
        help="Register 'Open with Pypad' in File Explorer context menu (current user).",
    )
    parser.add_argument(
        "--unregister-shell-menu",
        action="store_true",
        help="Remove 'Open with Pypad' from File Explorer context menu (current user).",
    )
    parsed_args, qt_args = parser.parse_known_args(sys.argv[1:])
    LOGGER.debug("Parsed startup args: parsed=%s qt=%s", parsed_args, qt_args)

    if parsed_args.register_shell_menu and parsed_args.unregister_shell_menu:
        print("Choose either --register-shell-menu or --unregister-shell-menu, not both.")
        sys.exit(2)
    if parsed_args.register_shell_menu:
        try:
            _register_windows_shell_menu()
            print("Registered: 'Open with Pypad' in File Explorer context menu.")
        except Exception as exc:
            print(f"Failed to register shell menu: {exc}")
            sys.exit(1)
        sys.exit(0)
    if parsed_args.unregister_shell_menu:
        try:
            _unregister_windows_shell_menu()
            print("Removed: 'Open with Pypad' from File Explorer context menu.")
        except Exception as exc:
            print(f"Failed to unregister shell menu: {exc}")
            sys.exit(1)
        sys.exit(0)

    _install_startup_exception_hooks()
    LOGGER.info("Startup exception hooks installed")
    atexit.register(lambda: _startup_log("Process exiting (atexit)."))
    startup_started_at = perf_counter()
    startup_reported = [False]
    app = QApplication([sys.argv[0], *qt_args])
    LOGGER.info("QApplication created")
    # Closing the main window should terminate the app process.
    app.setQuitOnLastWindowClosed(True)

    # Load splash image
    splash_asset = resolve_asset_path("splash.png")
    splash_path = str(splash_asset) if splash_asset is not None else ""
    if splash_asset is None:
        LOGGER.warning("Splash image asset not found: splash.png")
    pixmap = QPixmap(splash_path)
    LOGGER.debug("Loaded splash pixmap from %s", splash_path)
    pixmap = pixmap.scaled(
        600,
        400,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Load version text
    version_asset = resolve_asset_path("version.txt")
    version_file = str(version_asset) if version_asset is not None else ""
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            version = f.read().strip()
    except FileNotFoundError:
        version = "v?.?.?"  # fallback
        LOGGER.warning("Version file not found: %s", version_file)
    _startup_log(f"Pypad, Version: {version}")
    _startup_log("Waiting for main_window to start...")

    # Load custom font
    font_asset = resolve_asset_path("splash.ttf")
    font_path = str(font_asset) if font_asset is not None else ""
    if font_asset is None:
        LOGGER.warning("Splash font asset not found: splash.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)
    LOGGER.debug("Splash font load attempted from %s (font_id=%s)", font_path, font_id)

    if font_id == -1:
        print(f"Warning: Failed to load font at {font_path}, using default font.")
        font = QFont("Arial", 14)  # fallback
    else:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            font = QFont(families[0], 14)
        else:
            print(
                f"Warning: No font families found in {font_path}, using default font."
            )
            font = QFont("Arial", 14)  # fallback

    # Draw version text on splash
    painter = QPainter(pixmap)
    painter.setFont(font)
    painter.setPen(Qt.GlobalColor.white)
    margin = 20
    painter.drawText(margin, pixmap.height() - margin, f"App Version: {version}")
    painter.end()

    # Show splash
    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.show()

    def mark_app_started(window) -> None:
        if startup_reported[0]:
            return
        startup_reported[0] = True
        if splash.isVisible():
            splash.finish(window)
        elapsed_ms = int((perf_counter() - startup_started_at) * 1000)
        elapsed_sec = elapsed_ms / 1000.0
        _startup_log(f"Took {elapsed_ms}ms (or {elapsed_sec:.2f} seconds) to intialize!")
        app.setProperty("app_started", True)

    app.setProperty("startup_ready_callback", mark_app_started)

    # Start main window after short delay
    def start_main():
        LOGGER.info("Launching main window bootstrap")
        try:
            window = main(existing_app=app)
        except Exception:
            trace_text = traceback.format_exc()
            _save_startup_traceback(trace_text)
            LOGGER.exception("Main window bootstrap failed")
            app.quit()
            return
        if window is None:
            LOGGER.warning("main() returned None; quitting app")
            app.quit()
            return
        # Keep a strong reference so Qt doesn't destroy the window.
        global _MAIN_WINDOW
        _MAIN_WINDOW = window
        # Diagnostics for unexpected exits (connect before showing in case startup quits immediately)
        def _log_quit(reason: str) -> None:
            _startup_log(f"App quitting ({reason})")

        app.aboutToQuit.connect(lambda: _log_quit("aboutToQuit"))
        app.lastWindowClosed.connect(lambda: _log_quit("lastWindowClosed"))

        # Make sure app exits cleanly when main window closes
        window.destroyed.connect(lambda: _log_quit("main window destroyed"))
        window.destroyed.connect(app.quit)

        try:
            _startup_log("[Startup] Showing main window...")
            if window.isMinimized():
                window.showNormal()
            else:
                window.show()
            window.setWindowState(window.windowState() & ~Qt.WindowState.WindowMinimized)
            _startup_log(
                f"[Startup] Main window shown: visible={window.isVisible()} minimized={window.isMinimized()}"
            )
            if getattr(window, "_layout_restore_pending_after_show", False):
                _startup_log("[Startup] Applying deferred layout restore...")
                window._layout_restore_pending_after_show = False
                try:
                    if hasattr(window, "_restore_layout_from_settings"):
                        window._restore_layout_from_settings()
                except Exception as exc:
                    _startup_log(f"Warning: deferred layout restore failed: {exc}")
            mark_app_started(window)
            # Defer native activation calls; they can be fragile during first show on some setups.
            def _activate_main_window() -> None:
                try:
                    if not window.isVisible():
                        window.show()
                    _startup_log("[Startup] Activating main window...")
                    window.raise_()
                    window.activateWindow()
                except Exception as exc:
                    _startup_log(f"Warning: failed to raise/activate main window: {exc}")
            QTimer.singleShot(0, _activate_main_window)
            QTimer.singleShot(0, window.enforce_privacy_lock)
        except Exception as exc:
            _startup_log(f"Warning: failed to show main window: {exc}")

        def _check_window_visibility() -> None:
            try:
                visible = window.isVisible()
                minimized = window.isMinimized()
                _startup_log(
                    f"[Startup] Window state: visible={visible} minimized={minimized} "
                    f"active={window.isActiveWindow()}"
                )
                if not visible:
                    _startup_log("Warning: main window not visible after startup.")
            except Exception as exc:
                _startup_log(f"Warning: failed to read window state: {exc}")

        QTimer.singleShot(1500, _check_window_visibility)

    class _QuitEventFilter(QObject):
        def eventFilter(self, obj, event):  # type: ignore[override]
            if event.type() == QEvent.Type.Quit:
                _startup_log("Quit event received by QApplication.")
            return False

    _quit_filter = _QuitEventFilter(app)
    app.installEventFilter(_quit_filter)

    QTimer.singleShot(500, start_main)

    exit_code = app.exec()
    _startup_log(f"Qt event loop exited with code {exit_code}")
    sys.exit(exit_code)
