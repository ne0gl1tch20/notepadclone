import getpass
import base64
import hashlib
import json
import os
import random
import sys
import time
import traceback
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
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from ..session_recovery import RecoveryStateStore
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
        startup_t0 = time.perf_counter()
        startup_stages: list[tuple[str, int]] = []

        def _mark_startup_stage(name: str) -> None:
            elapsed_ms = int((time.perf_counter() - startup_t0) * 1000)
            startup_stages.append((name, elapsed_ms))
            try:
                self.log_event("Info", f"[Startup] {name} at {elapsed_ms}ms")
            except Exception:
                pass

        app = QApplication.instance()
        if Notepad.system_style_name is None and app is not None:
            Notepad.system_style_name = app.style().objectName() or "Fusion"
        self.window_id = id(self)
        Notepad.windows_by_id[self.window_id] = self

        self.setWindowTitle("Untitled - Pypad")
        self.resize(800, 600)

        self.word_wrap_enabled = True
        self.last_search_text: str | None = None
        self.macro_recording = False
        self.macro_playing = False
        self._macro_events: list[tuple[str, str]] = []
        self._last_macro_events: list[tuple[str, str]] = []

        self._jump_history: list[dict[str, object]] = []
        self._jump_history_index = -1
        self._suspend_jump_recording = False
        self._search_results_query = ""
        self._search_results_items: list[dict[str, object]] = []
        self._search_results_index = -1
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
        placeholder = QWidget(self)
        placeholder.setFixedSize(0, 0)
        placeholder.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCentralWidget(placeholder)
        self.editor_dock = QDockWidget("Editor", self)
        self.editor_dock.setObjectName("editorDock")
        self.editor_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.editor_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.editor_dock.setWidget(self.central_stack)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.editor_dock)
        if hasattr(self, "_sync_layout_panel_actions"):
            self.editor_dock.visibilityChanged.connect(lambda _v: self._sync_layout_panel_actions())
        self.setAcceptDrops(True)

        # Simple in-memory settings
        self.settings: dict = self._build_default_settings()
        if hasattr(self, "apply_logging_preferences"):
            self.apply_logging_preferences()
        self.log_event("Info", "[Startup] Default settings created")
        self._easter_egg_running = False
        self.settings_file = self._get_settings_file_path()
        self.load_settings_from_disk()
        if hasattr(self, "apply_logging_preferences"):
            self.apply_logging_preferences()
        self.log_event("Info", f"[Startup] Settings loaded from: {self.settings_file}")
        self._page_layout_view_enabled = bool(self.settings.get("page_layout_view_enabled", False))
        _mark_startup_stage("settings_loaded")
        self.translator = AppTranslator(self._get_translation_cache_path())
        self.log_event("Info", "[Startup] Translator initialized")
        self.workspace_controller = WorkspaceController(self)
        self.log_event("Info", "[Startup] Workspace controller initialized")
        self.security_controller = SecurityController(self)
        self.log_event("Info", "[Startup] Security controller initialized")
        self.ai_controller = AIController(self)
        self.log_event("Info", "[Startup] AI controller initialized")
        self.ai_chat_dock = AIChatDock(self, self.ai_controller)
        self.ai_chat_dock.setObjectName("aiChatDock")
        self.ai_chat_dock.setMinimumWidth(320)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.ai_chat_dock)
        self.ai_chat_dock.visibilityChanged.connect(self.update_action_states)
        self.ai_chat_dock.hide()
        self.updater_controller = UpdaterController(self)
        self.log_event("Info", "[Startup] Updater controller initialized")
        self.reminders_store = ReminderStore(self._get_reminders_file_path())
        self.reminders_store.load()
        self.log_event("Info", "[Startup] Reminders loaded")
        self.autosave_store = AutoSaveStore(self._get_autosave_dir_path())
        self.autosave_store.load()
        self.log_event("Info", "[Startup] Autosave store loaded")
        self.recovery_state_store = RecoveryStateStore(self._get_autosave_dir_path())
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._run_autosave_cycle)
        self.reminder_timer = QTimer(self)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self._on_file_changed)
        _mark_startup_stage("controllers_initialized")

        # Status bar
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.log_event("Info", "[Startup] Status bar initialized")

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
        self.ruler_label = QLabel("", self)
        self.ruler_label.setMargin(3)
        self.ruler_label.setVisible(False)
        self.status.addPermanentWidget(self.ruler_label)
        self.ai_usage_label = QLabel("AI: 0 req | ~0 tok | ~$0.0000", self)
        self.ai_usage_label.setMargin(3)
        self.status.addPermanentWidget(self.ai_usage_label)
        self.log_event("Info", "[Startup] Status bar widgets attached")
        self.advanced_features = AdvancedFeaturesController(self)
        _mark_startup_stage("advanced_features_ready")
        self.log_event("Info", "[Startup] Advanced features ready")
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AllowNestedDocks
        )
        self.log_event("Info", "[Startup] Dock options set")
        if hasattr(self, "_init_layout_docks"):
            self._init_layout_docks()
            self.log_event("Info", "[Startup] Layout docks initialized")

        self.add_new_tab(make_current=True)
        self.update_status_bar()
        self.log_event("Info", "[Startup] Initial tab created")

        self.create_actions()
        self.log_event("Info", "[Startup] Actions created")
        self._connect_action_debug_tracing()
        self.configure_action_tooltips()
        self.create_menus()
        self.log_event("Info", "[Startup] Menus created")
        self.configure_menu_tooltips()
        self.create_toolbars()
        self.log_event("Info", "[Startup] Toolbars created")
        if bool(self.settings.get("simple_mode", False)):
            self.toggle_simple_mode(True)
        self._offer_crash_recovery()
        _mark_startup_stage("ui_ready")
        self.log_event("Info", "[Startup] UI ready")

        # Finish startup before showing the window.
        def _finish_startup_sequence() -> None:
            try:
                self.apply_settings()
                self.log_event("Info", "[Startup] Settings applied")
            except Exception as exc:  # noqa: BLE001
                self.log_event("Error", f"[Startup] apply_settings failed: {exc!r}")
                traceback_text = traceback.format_exc().strip()
                self.log_event("Error", traceback_text)
            startup_files, startup_folders = self._collect_startup_items()
            if startup_files or startup_folders:
                self._open_startup_items(startup_files, startup_folders)
            else:
                self.restore_last_session()
            self.log_event("Info", "[Startup] Session restore completed")
            self.update_action_states()
            self.log_event("Info", "Pypad initialized")
            _mark_startup_stage("session_restored")
            startup_total_ms = int((time.perf_counter() - startup_t0) * 1000)
            stage_summary = ", ".join(f"{name}={ms}ms" for name, ms in startup_stages)
            print(f"[startup] pypad_init_total={startup_total_ms}ms | {stage_summary}")
            self.log_event("Info", f"Startup timing: total={startup_total_ms}ms; {stage_summary}")
            if self.settings.get("auto_check_updates", True):
                QTimer.singleShot(1500, lambda: self.check_for_updates(manual=False))
            QTimer.singleShot(300, self._maybe_show_welcome_tutorial)

        _finish_startup_sequence()

        # Lock screen enforcement is triggered from main() after the window is shown.

    def focusInEvent(self, event: QEvent) -> None:  # type: ignore[override]
        super().focusInEvent(event)
        if hasattr(self, "_emit_plugin_event"):
            self._emit_plugin_event("window_focus", tab=self.active_tab())

    def focusOutEvent(self, event: QEvent) -> None:  # type: ignore[override]
        super().focusOutEvent(event)
        if hasattr(self, "_emit_plugin_event"):
            self._emit_plugin_event("window_blur", tab=self.active_tab())

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
            if hasattr(self, "_refresh_workspace_dock"):
                self._refresh_workspace_dock()
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
