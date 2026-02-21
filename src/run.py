import argparse
import os
import sys
import traceback
from pathlib import Path
from time import perf_counter
from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QPixmap, QPainter, QFontDatabase, QFont
from PySide6.QtCore import Qt, QTimer

# --- Handle paths for PyInstaller ---
APP_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))

def resource_path(relative_path: str) -> str:
    return str(APP_ROOT / relative_path)

# --- Add ROOT for imports ---
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypad.app import main
from pypad.app_settings import get_crash_logs_file_path


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

    startup_started_at = perf_counter()
    startup_reported = [False]
    app = QApplication([sys.argv[0], *qt_args])
    app.setQuitOnLastWindowClosed(True)  # <-- ensure app quits when main window closes

    # Load splash image
    splash_path = resource_path("assets/splash.png")
    pixmap = QPixmap(splash_path)
    pixmap = pixmap.scaled(
        600,
        400,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )

    # Load version text
    version_file = resource_path("assets/version.txt")
    try:
        with open(version_file, "r", encoding="utf-8") as f:
            version = f.read().strip()
    except FileNotFoundError:
        version = "v?.?.?"  # fallback
    print(f"Pypad, Version: {version}")
    print("Waiting for main_window to start...")

    # Load custom font
    font_path = resource_path("assets/splash.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)

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
        print(f"Took {elapsed_ms}ms (or {elapsed_sec:.2f} seconds) to intialize!")
        app.setProperty("app_started", True)

    app.setProperty("startup_ready_callback", mark_app_started)

    # Start main window after short delay
    def start_main():
        try:
            window = main(existing_app=app)
        except Exception:
            trace_text = traceback.format_exc()
            _save_startup_traceback(trace_text)
            print(trace_text)
            app.quit()
            return
        if window is None:
            app.quit()
            return
        mark_app_started(window)

        # Make sure app exits cleanly when main window closes
        window.destroyed.connect(app.quit)

    QTimer.singleShot(500, start_main)

    sys.exit(app.exec())
