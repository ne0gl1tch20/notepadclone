import sys
import traceback
from typing import Optional
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .ui.main_window import Notepad

def main(existing_app: Optional[QApplication] = None) -> Notepad:
    # Use existing QApplication if passed (from run.py), otherwise create one
    app = existing_app or QApplication(sys.argv)
    app.setApplicationName("Pypad")

    window = Notepad()

    def _global_exception_hook(exc_type, exc_value, exc_tb) -> None:
        error_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb)).strip()
        window.log_event("Error", error_text)
        save_crash = getattr(window, "save_crash_traceback", None)
        if callable(save_crash):
            save_crash(error_text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _global_exception_hook

    window.show()

    # Enforce lock screen (if enabled) once the window is visible
    QTimer.singleShot(0, window.enforce_privacy_lock)

    return window  # return the main window for splash.finish()
