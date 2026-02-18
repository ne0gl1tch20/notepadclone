from PySide6.QtCore import QPoint, Qt, QMimeData, Signal
from PySide6.QtGui import QDrag, QColor, QPainter
from PySide6.QtWidgets import QApplication, QTabBar, QToolButton

class DetachableTabBar(QTabBar):
    detach_requested = Signal(int, QPoint)
    _tab_mime_type = "application/x-notepad-tab"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._drag_start_pos: QPoint | None = None
        self._drag_index = -1
        self.setAcceptDrops(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideRight)
        self.setExpanding(False)

    def tabInserted(self, index: int) -> None:  # type: ignore[override]
        super().tabInserted(index)
        self._install_close_button(index)

    def _install_close_button(self, index: int) -> None:
        if index < 0:
            return
        existing = self.tabButton(index, QTabBar.RightSide)
        if isinstance(existing, QToolButton):
            existing.setAutoRaise(True)
            existing.setToolTip("Close tab")
            existing.setText("x")
            existing.setToolButtonStyle(Qt.ToolButtonTextOnly)
            existing.setStyleSheet("QToolButton { padding: 0px; margin: 0px; }")
            existing.setFixedSize(14, 14)
            return
        button = QToolButton(self)
        button.setAutoRaise(True)
        button.setCursor(Qt.ArrowCursor)
        button.setToolTip("Close tab")
        button.setText("x")
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setStyleSheet("QToolButton { padding: 0px; margin: 0px; }")
        button.setFixedSize(14, 14)
        button.clicked.connect(self._emit_close_from_button)
        self.setTabButton(index, QTabBar.RightSide, button)

    def tabLayoutChange(self) -> None:  # type: ignore[override]
        super().tabLayoutChange()
        for index in range(self.count()):
            self._install_close_button(index)

    def _emit_close_from_button(self) -> None:
        button = self.sender()
        if not isinstance(button, QToolButton):
            return
        center = button.mapTo(self, button.rect().center())
        index = self.tabAt(center)
        if index >= 0:
            self.tabCloseRequested.emit(index)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_index = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._drag_start_pos is not None
            and self._drag_index >= 0
            and (event.pos() - self._drag_start_pos).manhattanLength() >= QApplication.startDragDistance()
            and not self.rect().contains(event.pos())
        ):
            tab_widget = self.parentWidget()
            host_window = tab_widget.window() if tab_widget is not None else None
            source_window_id = getattr(host_window, "window_id", -1)

            drag = QDrag(self)
            mime = QMimeData()
            payload = f"{source_window_id}:{self._drag_index}".encode("ascii", errors="ignore")
            mime.setData(self._tab_mime_type, payload)
            drag.setMimeData(mime)
            result = drag.exec(Qt.MoveAction)
            if result != Qt.MoveAction:
                self.detach_requested.emit(self._drag_index, event.globalPosition().toPoint())
            self._drag_start_pos = None
            self._drag_index = -1
            return
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(self._tab_mime_type):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasFormat(self._tab_mime_type):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        if not event.mimeData().hasFormat(self._tab_mime_type):
            super().dropEvent(event)
            return

        payload = bytes(event.mimeData().data(self._tab_mime_type)).decode("ascii", errors="ignore")
        parts = payload.split(":")
        if len(parts) != 2:
            event.ignore()
            return
        try:
            source_window_id = int(parts[0])
            source_index = int(parts[1])
        except ValueError:
            event.ignore()
            return

        target_tab_widget = self.parentWidget()
        target_window = target_tab_widget.window() if target_tab_widget is not None else None
        receive_fn = getattr(target_window, "receive_external_tab", None)
        if callable(receive_fn):
            insert_index = self.tabAt(event.position().toPoint())
            moved = bool(receive_fn(source_window_id, source_index, insert_index))
            if moved:
                event.acceptProposedAction()
                return
        event.ignore()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.pos())
            if index >= 0:
                host_window = self.window()
                close_fn = getattr(host_window, "close_tab", None)
                if callable(close_fn):
                    close_fn(index)
                else:
                    self.tabCloseRequested.emit(index)
                self._drag_start_pos = None
                self._drag_index = -1
                return
        self._drag_start_pos = None
        self._drag_index = -1
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for index in range(self.count()):
            data = self.tabData(index)
            if not data:
                continue
            color = QColor(str(data))
            if not color.isValid():
                continue
            rect = self.tabRect(index)
            strip = rect.adjusted(3, 3, -3, -rect.height() + 6)
            painter.fillRect(strip, color)
        painter.end()

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        index = self.tabAt(event.pos())
        host_window = self.window()
        show_fn = getattr(host_window, "show_tab_context_menu", None)
        if callable(show_fn):
            show_fn(index, event.globalPos())
            return
        super().contextMenuEvent(event)


