import getpass
import base64
import hashlib
import json
import os
import random
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal, Slot, QFileSystemWatcher
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPdfWriter,
    QPixmap,
    QTextCursor,
    QTextCharFormat,
    QTextDocument,
) 
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QStackedWidget,
    QStyle,
    QStyleFactory,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter

from ..debug_logs_dialog import DebugLogsDialog
from ..detachable_tab_bar import DetachableTabBar
from ..editor_tab import EditorTab
from ..ai_controller import AIController
from ..ai_chat_dock import AIChatDock
from ..asset_paths import resolve_asset_path
from ..autosave import AutoSaveRecoveryDialog, AutoSaveStore
from ..reminders import ReminderStore, RemindersDialog
from ..security_controller import SecurityController
from ..syntax_highlighter import CodeSyntaxHighlighter
from ..updater_controller import UpdaterController
from ..version_history import VersionHistoryDialog
from ..workspace_controller import WorkspaceController
from ..advanced_features import AdvancedFeaturesController
from ...i18n.translator import AppTranslator

from .ui_setup import UiSetupMixin
from .file_ops import FileOpsMixin
from .edit_ops import EditOpsMixin
from .view_ops import ViewOpsMixin
from .misc import MiscMixin
class Notepad(UiSetupMixin, FileOpsMixin, EditOpsMixin, ViewOpsMixin, MiscMixin, QMainWindow):
    windows_by_id: dict[int, "Notepad"] = {}
    system_style_name: str | None = None
    templates: dict[str, str] = {
        "Meeting Notes": "## Meeting Notes\n\nDate: \nAttendees:\n\n### Agenda\n- \n\n### Notes\n- \n\n### Action Items\n- [ ] ",
        "Daily Log": "## Daily Log\n\nDate: \n\n### Priorities\n- [ ] \n\n### Progress\n- \n\n### Blockers\n- \n\n### Wrap Up\n- ",
        "Checklist": "## Checklist\n\n- [ ] Item 1\n- [ ] Item 2\n- [ ] Item 3\n",
    }

    def __init__(self) -> None:
        super().__init__()
        app = QApplication.instance()
        if Notepad.system_style_name is None and app is not None:
            Notepad.system_style_name = app.style().objectName() or "Fusion"
        self.window_id = id(self)
        Notepad.windows_by_id[self.window_id] = self

        self.setWindowTitle("Untitled - Notepad")
        self.resize(800, 600)

        self.word_wrap_enabled = True
        self.last_search_text: str | None = None
        self.macro_recording = False
        self.macro_playing = False
        self._macro_events: list[tuple[str, str]] = []
        self._last_macro_events: list[tuple[str, str]] = []
        self.ai_usage_session = {
            "requests": 0,
            "tokens": 0,
            "estimated_cost": 0.0,
        }
        self.detached_windows: list["Notepad"] = []
        self.debug_logs: list[str] = []
        self.debug_logs_dialog: DebugLogsDialog | None = None
        self._icon_color: QColor | None = None

        self.tab_widget = QTabWidget(self)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        tab_bar = DetachableTabBar(self.tab_widget)
        tab_bar.detach_requested.connect(self.detach_tab_to_window)
        tab_bar.setDrawBase(False)
        tab_bar.setMovable(True)
        self.tab_widget.setTabBar(tab_bar)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.empty_tabs_widget = self._build_empty_tabs_widget()
        self.central_stack = QStackedWidget(self)
        self.central_stack.addWidget(self.tab_widget)
        self.central_stack.addWidget(self.empty_tabs_widget)
        self.setCentralWidget(self.central_stack)
        self.setAcceptDrops(True)

        # Simple in-memory settings
        self.settings: dict = self._build_default_settings()
        self._easter_egg_running = False
        self.settings_file = self._get_settings_file_path()
        self.load_settings_from_disk()
        self.translator = AppTranslator(self._get_translation_cache_path())
        self.workspace_controller = WorkspaceController(self)
        self.security_controller = SecurityController(self)
        self.ai_controller = AIController(self)
        self.ai_chat_dock = AIChatDock(self, self.ai_controller)
        self.ai_chat_dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.ai_chat_dock)
        self.ai_chat_dock.visibilityChanged.connect(self.update_action_states)
        self.ai_chat_dock.hide()
        self.updater_controller = UpdaterController(self)
        self.reminders_store = ReminderStore(self._get_reminders_file_path())
        self.reminders_store.load()
        self.autosave_store = AutoSaveStore(self._get_autosave_dir_path())
        self.autosave_store.load()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._run_autosave_cycle)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self._on_file_changed)

        # Status bar
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)

        # Status bar widgets
        self.position_label = QLabel("Ln 1, Col 1", self)
        self.zoom_label = QLabel("100%", self)
        # End-of-line and encoding indicators (bottom-right by default)
        # Values are updated dynamically in update_status_bar()
        self.eol_label = QLabel("", self)
        self.encoding_label = QLabel("UTF-8", self)

        for label in (self.position_label, self.zoom_label, self.eol_label, self.encoding_label):
            label.setMargin(3)
            self.status.addPermanentWidget(label)

        self.syntax_label = QLabel("Lang:", self)
        self.syntax_label.setMargin(3)
        self.syntax_combo = QComboBox(self)
        self.syntax_combo.addItems(["Auto", "Python", "JavaScript", "JSON", "Markdown", "Plain"])
        self.syntax_combo.currentTextChanged.connect(self._set_active_tab_language)
        self.status.addPermanentWidget(self.syntax_label)
        self.status.addPermanentWidget(self.syntax_combo)
        self.breadcrumb_label = QLabel("-", self)
        self.breadcrumb_label.setMargin(3)
        self.status.addPermanentWidget(self.breadcrumb_label)
        self.ai_usage_label = QLabel("AI: 0 req | ~0 tok | ~$0.0000", self)
        self.ai_usage_label.setMargin(3)
        self.status.addPermanentWidget(self.ai_usage_label)
        self.advanced_features = AdvancedFeaturesController(self)

        self.add_new_tab(make_current=True)
        self.update_status_bar()

        self.create_actions()
        self._connect_action_debug_tracing()
        self.configure_action_tooltips()
        self.create_menus()
        self.configure_menu_tooltips()
        self.create_toolbars()
        if bool(self.settings.get("simple_mode", False)):
            self.toggle_simple_mode(True)
        self._offer_crash_recovery()

        # Apply initial settings
        self.apply_settings()
        startup_files, startup_folders = self._collect_startup_items()
        if startup_files or startup_folders:
            self._open_startup_items(startup_files, startup_folders)
        else:
            self.restore_last_session()
        self.update_action_states()
        self.log_event("Info", "Notepad initialized")
        if self.settings.get("auto_check_updates", True):
            QTimer.singleShot(1500, lambda: self.check_for_updates(manual=False))
        QTimer.singleShot(300, self._maybe_show_welcome_tutorial)

        # Lock screen enforcement is triggered from main() after the window is shown.

    def _collect_startup_items(self) -> tuple[list[str], list[str]]:
        app = QApplication.instance()
        if app is None:
            return [], []
        args = list(app.arguments())[1:]
        if not args:
            return [], []
        seen: set[str] = set()
        files: list[str] = []
        folders: list[str] = []
        for arg in args:
            if not arg:
                continue
            if arg.startswith("-") and not Path(arg).exists():
                continue
            candidate = Path(arg)
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            try:
                resolved = candidate.resolve()
            except Exception:
                resolved = candidate
            if not resolved.exists():
                continue
            path_str = str(resolved)
            if path_str in seen:
                continue
            seen.add(path_str)
            if resolved.is_dir():
                folders.append(path_str)
            elif resolved.is_file():
                files.append(path_str)
        return files, folders

    def _open_startup_items(self, files: list[str], folders: list[str]) -> None:
        if folders:
            workspace_root = folders[0]
            self.settings["workspace_root"] = workspace_root
            self.show_status_message(f"Workspace: {workspace_root}", 3000)
            self.show_workspace_files()

        opened: list[str] = []
        first_opened: str | None = None
        for path in files:
            if self._open_file_path(path):
                opened.append(path)
                if first_opened is None:
                    first_opened = path
        if first_opened:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                if isinstance(tab, EditorTab) and tab.current_file == first_opened:
                    self.tab_widget.setCurrentIndex(index)
                    break
        if opened:
            self.log_event("Info", f"Opened on startup: {', '.join(opened)}")

