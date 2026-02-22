from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget, QWidgetAction
from typing import Any

from .editor_widget import EditorWidget

from .version_history import VersionHistory

class EditorTab(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.text_edit = EditorWidget(self)
        if hasattr(self.text_edit.widget, "setVerticalScrollBarPolicy"):
            self.text_edit.widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        if hasattr(self.text_edit.widget, "setHorizontalScrollBarPolicy"):
            self.text_edit.widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.markdown_preview = QTextEdit(self)
        self.markdown_preview.setReadOnly(True)
        self.markdown_preview.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.markdown_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.markdown_preview.hide()

        self.editor_splitter = QSplitter(Qt.Horizontal, self)
        self.editor_splitter.addWidget(self.text_edit.widget)
        self.editor_splitter.addWidget(self.markdown_preview)
        self.editor_splitter.setStretchFactor(0, 3)
        self.editor_splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.editor_splitter)

        self.current_file: str | None = None
        self.zoom_steps = 0
        self.markdown_mode_enabled = False
        self.track_changes_enabled = False
        self.version_history = VersionHistory()
        self.last_snapshot_time: float | None = None
        self.syntax_highlighter: Any = None
        self.syntax_language_override: str | None = None
        self.autosave_id: str | None = None
        self.autosave_path: str | None = None
        self.pinned = False
        self.favorite = False
        self.read_only = False
        self.tab_color: str | None = None
        self.bookmarks: set[int] = set()
        self.bookmark_marker_id: int | None = None
        self.encoding: str | None = None
        self.eol_mode: str | None = None
        self.large_file = False
        self.large_file_notice_shown = False
        self.partial_large_preview = False
        self.large_file_total_lines = 0
        self.large_file_total_chars = 0
        self.clone_editor: EditorWidget | None = None
        self.split_mode: str | None = None
        self.column_mode = False
        self.multi_caret = False
        self.code_folding = True
        self.show_space_tab = False
        self.show_eol = False
        self.show_non_printing = False
        self.show_control_chars = False
        self.show_all_chars = False
        self.show_indent_guides = True
        self.show_wrap_symbol = False
        self.auto_completion_mode = "all"
        self.tags: list[str] = []
        self.encryption_enabled = False
        self.encryption_password: str | None = None

        self._setup_editor_context_menu()

    def _setup_editor_context_menu(self) -> None:
        widget = self.text_edit.widget
        if not hasattr(widget, "setContextMenuPolicy") or not hasattr(widget, "customContextMenuRequested"):
            return
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(self._show_editor_context_menu)

    def _main_window(self):
        window = self.window()
        return window if window is not None else None

    @staticmethod
    def _context_icon(window, icon_name: str, size: int = 14) -> QIcon:
        icon_fn = getattr(window, "_icon", None)
        if callable(icon_fn):
            try:
                return icon_fn(icon_name, size=size)
            except Exception:
                return QIcon()
        return QIcon()

    @classmethod
    def _context_icon_name_for_action(cls, action_attr: str) -> str | None:
        mapping = {
            "explain_selection_ai_action": "ai-explain",
            "ai_inline_edit_action": "ai-inline-edit",
            "ai_rewrite_shorten_action": "ai-refactor",
            "ai_rewrite_formal_action": "ai-refactor",
            "ai_rewrite_grammar_action": "ai-refactor",
            "ai_rewrite_summarize_action": "ai-refactor",
            "ai_attach_selection_chat_action": "ai-attach",
            "ai_attach_current_file_chat_action": "ai-attach",
            "ai_attach_workspace_search_chat_action": "ai-attach-search",
            "ai_ask_context_action": "ai-citations",
            "ai_workspace_citations_action": "ai-workspace-cite",
            "workspace_search_action": "edit-find",
            "find_action": "edit-find",
            "replace_action": "edit-find-replace",
            "find_next_action": "edit-find",
            "find_prev_action": "edit-find",
            "search_selection_web_action": "ai-sparkles",
            "open_selection_file_action": "document-list",
            "open_selection_folder_action": "document-map",
            "comment_toggle_action": "md-quote",
            "comment_single_action": "md-quote",
            "comment_single_un_action": "md-quote",
            "comment_block_action": "md-code-block",
            "comment_block_un_action": "md-code-block",
            "add_comment_action": "collab-presence",
            "review_comments_action": "collab-resolve",
            "convert_uppercase_action": "format-bold",
            "convert_lowercase_action": "format-italic",
            "convert_propercase_action": "format-text-wrapping",
            "convert_sentencecase_action": "format-text-wrapping",
            "convert_invertcase_action": "show-symbol",
            "convert_randomcase_action": "show-all-chars",
            "style_all_occurrences_action": "sync-horizontal",
            "style_one_token_action": "sync-vertical",
            "clear_style_action": "ai-clear",
            "copy_styled_text_action": "edit-copy",
            "indent_action": "indent-guide",
            "unindent_action": "indent-guide",
            "blank_trim_trailing_action": "tail-follow",
            "line_duplicate_action": "md-bullets",
            "line_join_action": "md-link",
            "line_split_action": "sync-vertical",
            "line_remove_empty_action": "ai-clear",
        }
        return mapping.get(action_attr)

    @classmethod
    def _set_action_context_icon(cls, window, action, action_attr: str) -> None:
        if action is None:
            return
        icon_name = cls._context_icon_name_for_action(action_attr)
        if not icon_name:
            return
        icon = cls._context_icon(window, icon_name)
        if not icon.isNull():
            action.setIcon(icon)

    @staticmethod
    def _add_window_action(menu: QMenu, window, action_attr: str) -> bool:
        action = getattr(window, action_attr, None)
        if action is None:
            return False
        menu.addAction(action)
        return True

    @staticmethod
    def _swatch_icon(color_hex: str) -> QIcon:
        pix = QPixmap(12, 12)
        pix.fill(QColor(color_hex))
        return QIcon(pix)

    @classmethod
    def _add_window_action_if_enabled(cls, menu: QMenu, window, action_attr: str) -> bool:
        action = getattr(window, action_attr, None)
        if action is None or not action.isEnabled():
            return False
        cls._set_action_context_icon(window, action, action_attr)
        menu.addAction(action)
        return True

    @staticmethod
    def _prune_empty_menu(parent_menu: QMenu, submenu: QMenu) -> None:
        if not submenu.actions():
            submenu.menuAction().setVisible(False)
            try:
                parent_menu.removeAction(submenu.menuAction())
            except Exception:
                pass

    def _build_basic_fallback_menu(self, window) -> QMenu:
        menu = QMenu(self.text_edit.widget)
        for attr in (
            "cut_action",
            "copy_action",
            "paste_action",
            "delete_action",
            "select_all_action",
        ):
            self._add_window_action(menu, window, attr)
        return menu

    def _add_quick_ai_row(self, menu: QMenu, window) -> bool:
        entries = [
            ("Explain", "explain_selection_ai_action", "ai-explain"),
            ("Rewrite", "ai_inline_edit_action", "ai-inline-edit"),
            ("Attach", "ai_attach_selection_chat_action", "ai-attach"),
        ]
        enabled_entries = []
        for label, attr, icon_name in entries:
            action = getattr(window, attr, None)
            if action is None or not action.isEnabled():
                continue
            enabled_entries.append((label, action, icon_name))
        if not enabled_entries:
            return False
        row_host = QWidget(menu)
        row_layout = QHBoxLayout(row_host)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(6)
        for label, action, icon_name in enabled_entries:
            btn = QToolButton(row_host)
            btn.setText(label)
            btn.setAutoRaise(False)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            icon = self._context_icon(window, icon_name, size=14)
            if not icon.isNull():
                btn.setIcon(icon)
            shortcut_text = action.shortcut().toString() if hasattr(action, "shortcut") else ""
            tooltip = action.text()
            if shortcut_text:
                tooltip += f" ({shortcut_text})"
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda _checked=False, a=action, m=menu: (m.close(), a.trigger()))
            row_layout.addWidget(btn)
        row_layout.addStretch(1)
        row_action = QWidgetAction(menu)
        row_action.setDefaultWidget(row_host)
        menu.addAction(row_action)
        return True

    def _attach_more_ai_button(self, menu: QMenu, ai_menu: QMenu) -> None:
        if ai_menu is None or not ai_menu.actions():
            return
        row_action = None
        for act in menu.actions():
            if isinstance(act, QWidgetAction):
                row_action = act
                break
        if row_action is None:
            return
        row_host = row_action.defaultWidget()
        if row_host is None:
            return
        row_layout = row_host.layout()
        if not isinstance(row_layout, QHBoxLayout):
            return
        more_btn = QToolButton(row_host)
        more_btn.setText("More AI...")
        more_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        icon = self._context_icon(self._main_window(), "ai-sparkles", size=14)
        if not icon.isNull():
            more_btn.setIcon(icon)
        more_btn.setToolTip("Open the full AI context submenu")
        more_btn.clicked.connect(
            lambda _checked=False, m=menu, sub=ai_menu, btn=more_btn: sub.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        )
        row_layout.insertWidget(max(0, row_layout.count() - 1), more_btn)

    def _add_style_swatch_submenus(self, style_menu: QMenu, window) -> bool:
        swatches = [
            ("Using 1st Style", "style_all_1_action", "style_one_1_action", "#8fb6a2"),
            ("Using 2nd Style", "style_all_2_action", "style_one_2_action", "#e6ea8e"),
            ("Using 3rd Style", "style_all_3_action", "style_one_3_action", "#e293ab"),
            ("Using 4th Style", "style_all_4_action", "style_one_4_action", "#53aa66"),
            ("Using 5th Style", "style_all_5_action", "style_one_5_action", "#8f7ce8"),
        ]
        any_added = False
        style_all_menu = style_menu.addMenu("Style all occurrences of token")
        style_one_menu = style_menu.addMenu("Style one token")
        clear_menu = style_menu.addMenu("Clear style")
        for label, all_attr, one_attr, color in swatches:
            all_action = getattr(window, all_attr, None)
            if all_action is not None and all_action.isEnabled():
                all_action.setIcon(self._swatch_icon(color))
                style_all_menu.addAction(all_action)
                any_added = True
            one_action = getattr(window, one_attr, None)
            if one_action is not None and one_action.isEnabled():
                one_action.setIcon(self._swatch_icon(color))
                style_one_menu.addAction(one_action)
                any_added = True
        clear_added = False
        for idx, color in enumerate(["#8fb6a2", "#e6ea8e", "#e293ab", "#53aa66", "#8f7ce8"], start=1):
            clear_action = getattr(window, f"clear_style_{idx}_action", None)
            if clear_action is not None and clear_action.isEnabled():
                clear_action.setIcon(self._swatch_icon(color))
                clear_menu.addAction(clear_action)
                clear_added = True
                any_added = True
        clear_all_action = getattr(window, "clear_style_all_action", None)
        if clear_all_action is not None and clear_all_action.isEnabled():
            clear_menu.addSeparator()
            clear_menu.addAction(clear_all_action)
            clear_added = True
            any_added = True
        self._prune_empty_menu(style_menu, style_all_menu)
        self._prune_empty_menu(style_menu, style_one_menu)
        if not clear_added:
            self._prune_empty_menu(style_menu, clear_menu)
        return any_added

    def _show_editor_context_menu(self, pos) -> None:
        window = self._main_window()
        if window is None:
            return
        if hasattr(window, "update_action_states"):
            try:
                window.update_action_states()
            except Exception:
                pass

        widget = self.text_edit.widget
        menu = QMenu(widget)
        added_quick_ai = self._add_quick_ai_row(menu, window)
        if added_quick_ai:
            menu.addSeparator()
        for attr in (
            "cut_action",
            "copy_action",
            "paste_action",
            "delete_action",
            "select_all_action",
        ):
            self._add_window_action(menu, window, attr)
        menu.addSeparator()
        selection_menu = menu.addMenu("Selection")
        selection_icon = self._context_icon(window, "edit-copy")
        if not selection_icon.isNull():
            selection_menu.setIcon(selection_icon)

        selection_search_menu = selection_menu.addMenu("Search / Open")
        search_icon = self._context_icon(window, "edit-find")
        if not search_icon.isNull():
            selection_search_menu.setIcon(search_icon)
        selection_search_added = False
        for attr in (
            "open_selection_file_action",
            "open_selection_folder_action",
            "search_selection_web_action",
            "find_next_action",
            "find_prev_action",
        ):
            selection_search_added = self._add_window_action_if_enabled(selection_search_menu, window, attr) or selection_search_added
        if not selection_search_added:
            self._prune_empty_menu(selection_menu, selection_search_menu)

        convert_menu = selection_menu.addMenu("Convert Case")
        convert_icon = self._context_icon(window, "format-text-wrapping")
        if not convert_icon.isNull():
            convert_menu.setIcon(convert_icon)
        convert_added = False
        for attr in (
            "convert_uppercase_action",
            "convert_lowercase_action",
            "convert_propercase_action",
            "convert_sentencecase_action",
            "convert_invertcase_action",
            "convert_randomcase_action",
        ):
            convert_added = self._add_window_action_if_enabled(convert_menu, window, attr) or convert_added
        if not convert_added:
            self._prune_empty_menu(selection_menu, convert_menu)

        comment_menu = selection_menu.addMenu("Comment / Review")
        comment_icon = self._context_icon(window, "md-quote")
        if not comment_icon.isNull():
            comment_menu.setIcon(comment_icon)
        comment_count = 0
        for attr in (
            "comment_toggle_action",
            "comment_single_action",
            "comment_single_un_action",
            "comment_block_action",
            "comment_block_un_action",
        ):
            if self._add_window_action_if_enabled(comment_menu, window, attr):
                comment_count += 1
        review_added = False
        for attr in ("add_comment_action", "review_comments_action"):
            review_added = self._add_window_action_if_enabled(comment_menu, window, attr) or review_added
        if review_added and comment_count:
            comment_menu.addSeparator()
        if not comment_count and not review_added:
            self._prune_empty_menu(selection_menu, comment_menu)

        style_menu = selection_menu.addMenu("Style Tokens")
        style_icon = self._context_icon(window, "sync-horizontal")
        if not style_icon.isNull():
            style_menu.setIcon(style_icon)
        style_added = False
        for attr in ("copy_styled_text_action",):
            style_added = self._add_window_action_if_enabled(style_menu, window, attr) or style_added
        if self._add_style_swatch_submenus(style_menu, window):
            style_added = True
        if not style_added:
            self._prune_empty_menu(selection_menu, style_menu)

        ai_menu = menu.addMenu("AI")
        ai_icon = self._context_icon(window, "ai-sparkles")
        if not ai_icon.isNull():
            ai_menu.setIcon(ai_icon)
        ai_added = False
        for attr in ("explain_selection_ai_action", "ai_inline_edit_action"):
            ai_added = self._add_window_action_if_enabled(ai_menu, window, attr) or ai_added
        rewrite_menu = ai_menu.addMenu("Rewrite Selection")
        rewrite_icon = self._context_icon(window, "ai-refactor")
        if not rewrite_icon.isNull():
            rewrite_menu.setIcon(rewrite_icon)
        rewrite_added = False
        for attr in (
            "ai_rewrite_shorten_action",
            "ai_rewrite_formal_action",
            "ai_rewrite_grammar_action",
            "ai_rewrite_summarize_action",
        ):
            rewrite_added = self._add_window_action_if_enabled(rewrite_menu, window, attr) or rewrite_added
        if rewrite_added:
            ai_added = True
        else:
            self._prune_empty_menu(ai_menu, rewrite_menu)
        attach_menu = ai_menu.addMenu("Attach to AI Chat")
        attach_icon = self._context_icon(window, "ai-attach")
        if not attach_icon.isNull():
            attach_menu.setIcon(attach_icon)
        attach_added = False
        for attr in (
            "ai_attach_selection_chat_action",
            "ai_attach_current_file_chat_action",
            "ai_attach_workspace_search_chat_action",
        ):
            attach_added = self._add_window_action_if_enabled(attach_menu, window, attr) or attach_added
        if attach_added:
            ai_added = True
        else:
            self._prune_empty_menu(ai_menu, attach_menu)
        for attr in ("ai_ask_context_action", "ai_workspace_citations_action"):
            ai_added = self._add_window_action_if_enabled(ai_menu, window, attr) or ai_added
        if not ai_added:
            self._prune_empty_menu(menu, ai_menu)
        elif added_quick_ai:
            self._attach_more_ai_button(menu, ai_menu)

        advanced_menu = menu.addMenu("Advanced")
        advanced_icon = self._context_icon(window, "command-palette")
        if not advanced_icon.isNull():
            advanced_menu.setIcon(advanced_icon)
        advanced_added = False

        search_menu = advanced_menu.addMenu("Search")
        if not search_icon.isNull():
            search_menu.setIcon(search_icon)
        search_added = False
        for attr in ("find_action", "replace_action", "workspace_search_action"):
            search_added = self._add_window_action_if_enabled(search_menu, window, attr) or search_added
        if search_added:
            advanced_added = True
        else:
            self._prune_empty_menu(advanced_menu, search_menu)

        lines_menu = advanced_menu.addMenu("Lines / Text")
        lines_icon = self._context_icon(window, "md-bullets")
        if not lines_icon.isNull():
            lines_menu.setIcon(lines_icon)
        lines_added = False
        for attr in (
            "indent_action",
            "unindent_action",
            "blank_trim_trailing_action",
            "line_duplicate_action",
            "line_join_action",
            "line_split_action",
            "line_remove_empty_action",
        ):
            lines_added = self._add_window_action_if_enabled(lines_menu, window, attr) or lines_added
        if lines_added:
            advanced_added = True
        else:
            self._prune_empty_menu(advanced_menu, lines_menu)

        if not selection_menu.actions():
            self._prune_empty_menu(menu, selection_menu)
        if not advanced_added:
            self._prune_empty_menu(menu, advanced_menu)
        if menu.actions() and menu.actions()[-1].isSeparator():
            menu.removeAction(menu.actions()[-1])

        global_pos = widget.mapToGlobal(pos) if hasattr(widget, "mapToGlobal") else pos
        menu.exec(global_pos)

