# overlay/overlay_window.py

import time
from PyQt6.QtWidgets import QWidget, QLabel, QApplication
from PyQt6.QtGui import QPainter, QPen, QColor, QFont, QScreen
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer
from typing import List, Dict, Any, Optional, Tuple

class OverlayWindow(QWidget):
    """A transparent, always-on-top window for displaying debug info."""
    close_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        primary_screen = QApplication.primaryScreen()
        screen_geometry = primary_screen.geometry() if primary_screen else QRect(0, 0, 1920, 1080)
        self.setGeometry(screen_geometry)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._draw_items: List[Dict[str, Any]] = []
        self._status_text: Optional[str] = None
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self.clear_timed_items)

        print("OverlayWindow initialized.")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw Status Text
        if self._status_text:
            painter.setPen(QPen(QColor("white"), 1))
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            text_rect = painter.fontMetrics().boundingRect(self._status_text)
            # Position status at bottom-center (adjust as needed)
            status_x = (self.width() - (text_rect.width() + 10)) // 2
            status_y = self.height() - (text_rect.height() + 10) - 10
            bg_rect = QRect(status_x, status_y, text_rect.width() + 10, text_rect.height() + 10)
            painter.fillRect(bg_rect, QColor(0, 0, 0, 180))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, self._status_text)


        # Draw items
        current_time_ms = time.time() * 1000
        items_to_keep = []
        needs_repaint = False

        for item in self._draw_items:
            duration = item.get("duration_ms")
            if duration is not None:
                add_time = item.setdefault("add_time", current_time_ms)
                if (add_time + duration) <= current_time_ms:
                    needs_repaint = True; continue

            items_to_keep.append(item)

            item_type = item.get("type")
            color = item.get("color", QColor("red"))
            thickness = item.get("thickness", 2)
            label = item.get("label") # Base label (e.g., filename or "Click")
            confidence = item.get("confidence") # Get confidence if present

            pen = QPen(color, thickness)
            painter.setPen(pen)
            painter.setFont(QFont("Arial", 10))

            # --- Construct final display label ---
            display_label = label if label else ""
            if confidence is not None:
                display_label += f" ({confidence:.2f})" # Append confidence

            if item_type == "rect":
                rect_data = item.get("rect")
                if rect_data and len(rect_data) == 4:
                    rect = QRect(int(rect_data[0]), int(rect_data[1]), int(rect_data[2]), int(rect_data[3]))
                    painter.drawRect(rect)
                    if display_label: # Use combined label
                        text_pos = rect.topLeft() + QPoint(2, -2 - painter.fontMetrics().height() if rect.top() > 20 else 2)
                        text_bg_rect = painter.fontMetrics().boundingRect(text_pos.x(), text_pos.y(), 0, 0, 0, display_label)
                        text_bg_rect.adjust(-2, -2, 2, 2)
                        painter.fillRect(text_bg_rect, QColor(0, 0, 0, 150))
                        painter.setPen(QColor("white"))
                        painter.drawText(text_pos, display_label)
                        painter.setPen(pen) # Restore pen

            elif item_type == "point":
                pos_data = item.get("pos")
                if pos_data and len(pos_data) == 2:
                    point = QPoint(int(pos_data[0]), int(pos_data[1]))
                    radius = item.get("radius", 5)
                    painter.setBrush(color); painter.drawEllipse(point, radius, radius); painter.setBrush(Qt.BrushStyle.NoBrush)
                    if display_label: # Use combined label (though confidence unlikely for point)
                        text_pos = point + QPoint(radius + 2, radius + 2)
                        text_bg_rect = painter.fontMetrics().boundingRect(text_pos.x(), text_pos.y(), 0, 0, 0, display_label)
                        text_bg_rect.adjust(-2, -2, 2, 2)
                        painter.fillRect(text_bg_rect, QColor(0, 0, 0, 150))
                        painter.setPen(QColor("white"))
                        painter.drawText(text_pos, display_label)
                        painter.setPen(pen)

        painter.end()

        if needs_repaint:
            self._draw_items = items_to_keep
            self._schedule_clear()


    def update_status(self, text: Optional[str]):
        if self._status_text != text:
            self._status_text = text
            self.update()

    def add_item(self, item_data: Dict[str, Any]):
        item_data["add_time"] = time.time() * 1000
        self._draw_items.append(item_data)
        self._schedule_clear()
        self.update()

    def clear_items(self):
        if self._draw_items:
            self._draw_items = []
            self._clear_timer.stop()
            self.update()

    def clear_timed_items(self):
        current_time = time.time() * 1000
        initial_count = len(self._draw_items)
        self._draw_items = [
            item for item in self._draw_items
            if item.get("duration_ms") is None or
               (item.get("add_time", 0) + item["duration_ms"]) > current_time
        ]
        if len(self._draw_items) < initial_count:
            self._schedule_clear()
            self.update()


    def _schedule_clear(self):
        self._clear_timer.stop()
        next_expiry = float('inf'); current_time = time.time() * 1000; has_timed_items = False
        for item in self._draw_items:
            duration = item.get("duration_ms")
            if duration is not None:
                has_timed_items = True; add_time = item.get("add_time", current_time); expiry_time = add_time + duration
                next_expiry = min(next_expiry, expiry_time)
        if has_timed_items and next_expiry != float('inf'):
            delay = max(1, int(next_expiry - current_time)); self._clear_timer.start(delay)

    def showEvent(self, event):
        print("Overlay shown.")
        primary_screen = QApplication.primaryScreen()
        if primary_screen: self.setGeometry(primary_screen.geometry())
        super().showEvent(event)

    def hideEvent(self, event):
        print("Overlay hidden.")
        self.clear_items()
        super().hideEvent(event)