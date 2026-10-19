from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QSizePolicy,
)


class InfoCard(QWidget):
    """
    Thẻ hiển thị thông tin ngắn cho UI Scan-to-Path.

    Dùng cho:
        - Thống kê số điểm point cloud
        - Trạng thái Edge AI
        - Số lượng normal vector
        - Số điểm đường Zigzag / Contour
        - Thời gian xử lý
        - Trạng thái xuất kết quả

    Ví dụ:
        InfoCard("POINT CLOUD", "125000 điểm")
        InfoCard("EDGE AI", "Đã tách vật thể")
        InfoCard("ZIGZAG", "2300 điểm")
    """

    def __init__(
        self,
        title: str = "THÔNG TIN",
        value: str = "--",
        min_width: int = 120,
        parent=None,
    ):
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.value_label = QLabel(value)

        self.min_width = min_width

        self._build_ui()

    # -----------------------------------------
    # UI
    # -----------------------------------------
    def _build_ui(self):
        self.setObjectName("info_card")

        self.setMinimumWidth(self.min_width)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.title_label.setObjectName("info_card_title")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.value_label.setObjectName("info_card_value")
        self.value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.value_label.setWordWrap(False)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    # -----------------------------------------
    # Public API
    # -----------------------------------------
    def set_title(self, text: str):
        self.title_label.setText(text)

    def set_value(self, text):
        self.value_label.setText(str(text))

    def set_count(self, value: int, suffix: str = "điểm"):
        self.value_label.setText(f"{value:,} {suffix}".replace(",", "."))

    def set_status(self, text: str, level: str = "muted"):
        """
        level:
            muted
            success
            warning
            danger
        """
        self.value_label.setText(text)
        self.value_label.setProperty("role", level)
        self._refresh_label(self.value_label)

    def value(self) -> str:
        return self.value_label.text()

    def title(self) -> str:
        return self.title_label.text()

    # -----------------------------------------
    # Helpers
    # -----------------------------------------
    def _refresh_label(self, widget: QLabel):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()