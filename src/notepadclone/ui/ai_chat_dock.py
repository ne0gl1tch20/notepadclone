from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QResizeEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from .asset_paths import resolve_asset_path

if TYPE_CHECKING:
    from .ai_controller import AIController


class _Bubble(QFrame):
    def __init__(self, text: str, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._role = role
        self._raw_text = text
        self._view = QTextBrowser(self)
        self._view.setFrameStyle(QFrame.NoFrame)
        self._view.setReadOnly(True)
        self._view.setOpenExternalLinks(True)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._view.document().setDocumentMargin(0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.addWidget(self._view)
        if role == "user":
            self.setObjectName("userBubble")
        else:
            self.setObjectName("assistantBubble")
        self._render_markdown()
        self._sync_height()

    def append_text(self, text: str) -> None:
        self._raw_text += text
        self._render_markdown()
        self._sync_height()

    def text(self) -> str:
        return self._raw_text

    def _render_markdown(self) -> None:
        self._view.setMarkdown(self._raw_text)

    def _sync_height(self) -> None:
        width = max(220, self._view.viewport().width())
        self._view.document().setTextWidth(width)
        doc_height = self._view.document().size().height()
        self._view.setFixedHeight(int(doc_height + 8))

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_height()


class _DockTitleBar(QWidget):
    def __init__(self, dock: "AIChatDock") -> None:
        super().__init__(dock)
        self.setObjectName("aiChatTitleBar")
        self._dock = dock
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)
        self.label = QLabel("AI Chat", self)
        self.label.setObjectName("aiChatTitleLabel")
        self.float_btn = QToolButton(self)
        self.close_btn = QToolButton(self)
        for btn in (self.float_btn, self.close_btn):
            btn.setAutoRaise(True)
            btn.setFixedSize(20, 20)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.float_btn.setToolTip("Float / Dock")
        self.close_btn.setToolTip("Close")
        self.float_btn.clicked.connect(self._toggle_floating)
        self.close_btn.clicked.connect(self._dock.close)
        layout.addWidget(self.label)
        layout.addStretch(1)
        layout.addWidget(self.float_btn)
        layout.addWidget(self.close_btn)
        self.setMinimumHeight(28)

    def _toggle_floating(self) -> None:
        self._dock.setFloating(not self._dock.isFloating())


class AIChatDock(QDockWidget):
    def __init__(self, parent: QWidget, ai_controller: "AIController") -> None:
        super().__init__("AI Chat", parent)
        self.setObjectName("aiChatDock")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.ai_controller = ai_controller
        self._active_reply_bubble: _Bubble | None = None
        self._active_reply_index: int | None = None
        self._history: list[dict[str, str]] = []
        self._icon_cache: dict[tuple[str, str, int], QIcon] = {}
        self._title_bar = _DockTitleBar(self)
        self.setTitleBarWidget(self._title_bar)

        host = QWidget(self)
        host.setObjectName("aiChatHost")
        self.setWidget(host)
        root = QVBoxLayout(host)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self.scroll = QScrollArea(host)
        self.scroll.setObjectName("aiChatScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.viewport().setObjectName("aiChatViewport")
        self.scroll.viewport().setAutoFillBackground(True)
        root.addWidget(self.scroll, 1)

        self.messages_host = QWidget(self.scroll)
        self.messages_host.setObjectName("aiChatMessages")
        self.messages_host.setAutoFillBackground(True)
        self.messages_layout = QVBoxLayout(self.messages_host)
        self.messages_layout.setContentsMargins(4, 4, 4, 4)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch(1)
        self.scroll.setWidget(self.messages_host)

        self.input = QPlainTextEdit(host)
        self.input.setObjectName("aiChatInput")
        self.input.setPlaceholderText("Ask AI...")
        self.input.setFixedHeight(90)
        root.addWidget(self.input)

        row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear", host)
        self.stop_btn = QPushButton("Stop", host)
        self.stop_btn.setEnabled(False)
        self.send_btn = QPushButton("Send", host)
        self._setup_button_icons()
        row.addWidget(self.clear_btn)
        row.addWidget(self.stop_btn)
        row.addStretch(1)
        row.addWidget(self.send_btn)
        root.addLayout(row)

        self.clear_btn.clicked.connect(self.clear_chat)
        self.stop_btn.clicked.connect(self._stop_generation)
        self.send_btn.clicked.connect(self._send_prompt)
        self._apply_styles()
        self._load_history()

    def _is_effective_dark_mode(self) -> bool:
        icon_color = getattr(self.ai_controller.window, "_icon_color", None)
        if isinstance(icon_color, QColor) and icon_color.isValid():
            # Light text color usually means dark UI chrome.
            return icon_color.lightnessF() >= 0.65
        return bool(getattr(self.ai_controller.window, "settings", {}).get("dark_mode", False))

    def _icon(self, name: str, size: int = 16) -> QIcon:
        path = resolve_asset_path("icons", f"{name}.svg")
        if path is None:
            return QIcon()
        dark_mode = self._is_effective_dark_mode()
        color = QColor("#ffffff" if dark_mode else "#000000")
        key = (name, color.name(), int(size))
        cached = self._icon_cache.get(key)
        if cached is not None:
            return cached
        try:
            svg_text = path.read_text(encoding="utf-8")
            svg_text = self._force_svg_monochrome(svg_text, color.name())
            renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
            if renderer.isValid():
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()
                icon = QIcon(pixmap)
                self._icon_cache[key] = icon
                return icon
        except Exception:
            pass
        icon = QIcon(str(path))
        self._icon_cache[key] = icon
        return icon

    @staticmethod
    def _force_svg_monochrome(svg_text: str, color_hex: str) -> str:
        text = re.sub(
            r'\b(stroke|fill)\b\s*=\s*["\'](?!none\b)[^"\']*["\']',
            lambda m: f'{m.group(1)}="{color_hex}"',
            svg_text,
            flags=re.IGNORECASE,
        )
        text = text.replace("currentColor", color_hex)
        return text

    def _setup_button_icons(self) -> None:
        send_icon = self._icon("ai-send", size=18)
        stop_icon = self._icon("ai-stop", size=18)
        self.send_btn.setText("Send")
        self.stop_btn.setText("Stop")
        if not send_icon.isNull():
            self.send_btn.setIcon(send_icon)
            self.send_btn.setText("")
        if not stop_icon.isNull():
            self.stop_btn.setIcon(stop_icon)
            self.stop_btn.setText("")
        self.send_btn.setToolTip("Send")
        self.stop_btn.setToolTip("Stop")
        for btn in (self.send_btn, self.stop_btn):
            btn.setMinimumSize(34, 30)
            if not btn.text():
                btn.setMaximumWidth(38)

    def _apply_styles(self) -> None:
        dark_mode = self._is_effective_dark_mode()
        surface_bg = "#1f2329" if dark_mode else "#ffffff"
        user_bg = "#2f343a" if dark_mode else "#daf1ff"
        user_border = "#51565c" if dark_mode else "#9ecff2"
        assistant_bg = "#24272b" if dark_mode else "#f0f0f0"
        assistant_border = "#464a50" if dark_mode else "#d0d0d0"
        text_color = "#ffffff" if dark_mode else "#111111"
        panel_bg = "#1d2024" if dark_mode else "#f5f7fb"
        self.setStyleSheet(
            f"""
            QDockWidget#aiChatDock {{
                background: {panel_bg};
            }}
            QWidget#aiChatHost {{
                background: {panel_bg};
            }}
            QScrollArea#aiChatScroll {{
                background: {surface_bg};
                border: 1px solid {assistant_border};
                border-radius: 10px;
            }}
            QWidget#aiChatViewport,
            QWidget#aiChatMessages {{
                background: {surface_bg};
            }}
            QWidget#aiChatRow {{
                background: transparent;
            }}
            QFrame#userBubble {{
                background: {user_bg};
                border: 1px solid {user_border};
                border-radius: 10px;
            }}
            QFrame#assistantBubble {{
                background: {assistant_bg};
                border: 1px solid {assistant_border};
                border-radius: 10px;
            }}
            QFrame#userBubble QTextBrowser,
            QFrame#assistantBubble QTextBrowser {{
                color: {text_color};
                background: transparent;
                border: none;
            }}
            QPlainTextEdit#aiChatInput {{
                background: {"#2a2d31" if dark_mode else "#ffffff"};
                color: {text_color};
                border: 1px solid {assistant_border};
            }}
            QPushButton {{
                background: {"#2f3338" if dark_mode else "#f5f6f8"};
                color: {text_color};
                border: 1px solid {assistant_border};
                padding: 4px 8px;
            }}
            QPushButton:disabled {{
                color: {"#9aa0a6" if dark_mode else "#888888"};
            }}
            """
        )
        self._title_bar.label.setStyleSheet(f"color: {'#ffffff' if dark_mode else '#000000'};")
        self._title_bar.setStyleSheet(
            f"""
            QWidget#aiChatTitleBar {{
                background: {panel_bg};
                border-bottom: 1px solid {assistant_border};
            }}
            QLabel#aiChatTitleLabel {{
                color: {'#ffffff' if dark_mode else '#000000'};
                font-weight: 600;
            }}
            QWidget#aiChatTitleBar QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 0px;
            }}
            QWidget#aiChatTitleBar QToolButton:hover {{
                background: {'#2f3338' if dark_mode else '#e7ebf1'};
                border: 1px solid {assistant_border};
            }}
            QWidget#aiChatTitleBar QToolButton:pressed {{
                background: {'#3a3f45' if dark_mode else '#dfe5ee'};
                border: 1px solid {assistant_border};
            }}
            """
        )
        float_icon = self._icon("view-fullscreen", size=12)
        close_icon = self._icon("tab-close", size=12)
        if not float_icon.isNull():
            self._title_bar.float_btn.setIcon(float_icon)
        if not close_icon.isNull():
            self._title_bar.close_btn.setIcon(close_icon)

    def refresh_theme(self) -> None:
        self._icon_cache.clear()
        self._apply_styles()
        self._setup_button_icons()
        self._refresh_message_action_icons()

    def _refresh_message_action_icons(self) -> None:
        for button in self.messages_host.findChildren(QPushButton):
            icon_name = button.property("ai_icon_name")
            if not icon_name:
                continue
            icon = self._icon(str(icon_name), size=14)
            if icon.isNull():
                continue
            button.setIcon(icon)

    def focus_prompt(self) -> None:
        self.input.setFocus()

    def clear_chat(self) -> None:
        self._active_reply_bubble = None
        self._active_reply_index = None
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._history = []
        self._persist_history(save=True)

    def _send_prompt(self) -> None:
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        self.input.clear()
        self._add_bubble(prompt, "user", persist=True)
        self._active_reply_bubble = self._add_bubble("", "assistant")
        self._active_reply_index = len(self._history)
        self._history.append({"role": "assistant", "text": ""})
        self._persist_history(save=False)
        self.send_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.ai_controller.ask_ai_chat(
            prompt,
            on_chunk=self._on_stream_chunk,
            on_done=self._on_stream_done,
            on_error=self._on_stream_error,
            on_cancel=self._on_stream_cancel,
        )

    def _on_stream_chunk(self, text: str) -> None:
        if self._active_reply_bubble is None:
            self._active_reply_bubble = self._add_bubble("", "assistant")
            self._active_reply_index = len(self._history)
            self._history.append({"role": "assistant", "text": ""})
        self._active_reply_bubble.append_text(text)
        if self._active_reply_index is not None and 0 <= self._active_reply_index < len(self._history):
            self._history[self._active_reply_index]["text"] += text
            self._persist_history(save=False)
        self._scroll_to_bottom()

    def _on_stream_done(self, _full_text: str) -> None:
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._active_reply_bubble = None
        self._active_reply_index = None
        self._persist_history(save=True)
        self._scroll_to_bottom()

    def _on_stream_error(self, message: str) -> None:
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._active_reply_bubble = None
        self._active_reply_index = None
        self._add_bubble(f"Error: {message}", "assistant", persist=True)
        self._persist_history(save=True)
        self._scroll_to_bottom()

    def _on_stream_cancel(self, _partial: str) -> None:
        self.send_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._active_reply_bubble = None
        self._active_reply_index = None
        self._persist_history(save=True)
        self._scroll_to_bottom()

    def _add_bubble(self, text: str, role: str, *, persist: bool = False) -> _Bubble:
        bubble = _Bubble(text, role, self.messages_host)
        row = QWidget(self.messages_host)
        row.setObjectName("aiChatRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble, 0)
        else:
            row_layout.addWidget(bubble, 0)
            actions = QWidget(row)
            actions_layout = QVBoxLayout(actions)
            actions_layout.setContentsMargins(4, 0, 0, 0)
            actions_layout.setSpacing(4)
            copy_btn = QPushButton("", actions)
            insert_btn = QPushButton("", actions)
            copy_icon = self._icon("ai-copy", size=14)
            insert_icon = self._icon("ai-insert", size=14)
            copy_btn.setProperty("ai_icon_name", "ai-copy")
            insert_btn.setProperty("ai_icon_name", "ai-insert")
            copy_btn.setText("Copy")
            insert_btn.setText("Insert")
            if not copy_icon.isNull():
                copy_btn.setIcon(copy_icon)
                copy_btn.setText("")
            if not insert_icon.isNull():
                insert_btn.setIcon(insert_icon)
                insert_btn.setText("")
            copy_btn.setToolTip("Copy")
            insert_btn.setToolTip("Insert to tab")
            for btn in (copy_btn, insert_btn):
                btn.setMinimumSize(28, 24)
                if not btn.text():
                    btn.setMaximumWidth(32)
            copy_btn.clicked.connect(lambda: self._copy_bubble_text(bubble))
            insert_btn.clicked.connect(lambda: self._insert_bubble_text_to_tab(bubble))
            actions_layout.addWidget(copy_btn)
            actions_layout.addWidget(insert_btn)
            actions_layout.addStretch(1)
            row_layout.addWidget(actions, 0)
            row_layout.addStretch(1)
        self.messages_layout.insertWidget(self.messages_layout.count() - 1, row)
        if persist:
            self._history.append({"role": role, "text": text})
            self._persist_history(save=True)
        self._scroll_to_bottom()
        return bubble

    def _copy_bubble_text(self, bubble: _Bubble) -> None:
        QApplication.clipboard().setText(bubble.text())

    def _insert_bubble_text_to_tab(self, bubble: _Bubble) -> None:
        tab = self.ai_controller.window.active_tab()
        if tab is None:
            QMessageBox.information(self, "Insert", "Open a tab first.")
            return
        text = bubble.text().strip()
        if not text:
            return
        if tab.text_edit.get_text().strip():
            tab.text_edit.insert_text("\n\n")
        tab.text_edit.insert_text(text)

    def _stop_generation(self) -> None:
        self.ai_controller.cancel_active_chat_request()

    def _load_history(self) -> None:
        settings = getattr(self.ai_controller.window, "settings", {})
        raw = settings.get("ai_chat_history", [])
        if not isinstance(raw, list):
            return
        self._history = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip().lower()
            text = str(item.get("text", ""))
            if role not in {"user", "assistant"}:
                continue
            self._history.append({"role": role, "text": text})
            self._add_bubble(text, role, persist=False)

    def _persist_history(self, *, save: bool) -> None:
        window = self.ai_controller.window
        window.settings["ai_chat_history"] = list(self._history[-200:])
        self._history = list(window.settings["ai_chat_history"])
        if save and hasattr(window, "save_settings_to_disk"):
            window.save_settings_to_disk()

    def _scroll_to_bottom(self) -> None:
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
