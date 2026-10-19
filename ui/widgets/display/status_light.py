from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QPainter, QPen, QBrush
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout


class LightDot(QWidget):
    """
    Chấm trạng thái nhỏ dùng trong StatusLight.
    """

    def __init__(self, size: int = 14, color: str = "#5f6b7a", parent=None):
        super().__init__(parent)

        self._size = size
        self._color = QColor(color)

        self.setFixedSize(QSize(size, size))

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(QPen(QColor(25, 25, 25), 1))
        painter.setBrush(QBrush(self._color))
        painter.drawEllipse(rect)


class StatusLight(QWidget):
    """
    Đèn trạng thái cho UI Scan-to-Path.

    Dùng cho:
        - Camera / Orbbec
        - Edge AI
        - Point Cloud
        - Surface Map
        - Normal Field
        - Zigzag / Contour Path
        - Export Result

    Ví dụ:
        StatusLight("CAMERA", "success")
        StatusLight("EDGE AI", "warning")
        StatusLight("POINT CLOUD", "muted")
    """

    COLORS = {
        "muted": "#5f6b7a",
        "gray": "#5f6b7a",
        "success": "#23A559",
        "green": "#23A559",
        "warning": "#F0B232",
        "yellow": "#F0B232",
        "danger": "#DA373C",
        "red": "#DA373C",
        "info": "#00A8FC",
        "blue": "#00A8FC",
    }

    def __init__(
        self,
        text: str = "TRẠNG THÁI",
        state: str = "muted",
        parent=None,
    ):
        super().__init__(parent)

        self.dot = LightDot()
        self.label = QLabel(text)

        self.label.setObjectName("status_light_label")

        self._build_ui()
        self.set_state(state)

    # -----------------------------------------
    # UI
    # -----------------------------------------
    def _build_ui(self):
        self.setObjectName("status_light")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        self.label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(self.dot, 0)
        layout.addWidget(self.label, 1)

    # -----------------------------------------
    # Public API
    # -----------------------------------------
    def set_state(self, state: str):
        color = self.COLORS.get(state, self.COLORS["muted"])
        self.dot.set_color(color)

    def set_text(self, text: str):
        self.label.setText(text)

    def set_status(self, text: str, state: str = "muted"):
        self.set_text(text)
        self.set_state(state)

    def set_ok(self):
        self.set_state("success")

    def set_success(self):
        self.set_state("success")

    def set_warning(self):
        self.set_state("warning")

    def set_error(self):
        self.set_state("danger")

    def set_danger(self):
        self.set_state("danger")

    def set_info(self):
        self.set_state("info")

    def set_offline(self):
        self.set_state("muted")

    def set_waiting(self):
        self.set_state("muted")

    def set_processing(self):
        self.set_state("warning")