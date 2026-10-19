from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QFrame,
    QSizePolicy,
)


class SectionCard(QFrame):
    """
    Card chứa một nhóm nội dung trong UI Scan-to-Path.

    Dùng cho:
        - Nhóm thông số quét 3D
        - Nhóm thông số Edge AI
        - Nhóm thông số xử lý point cloud
        - Nhóm thông số tính pháp tuyến
        - Nhóm thông số sinh đường Zigzag / Contour
        - Nhóm hiển thị kết quả xử lý

    Ví dụ:
        card = SectionCard("THÔNG SỐ POINT CLOUD")
        card.add_widget(FormRow(...))
    """

    def __init__(
        self,
        title: str = "NHÓM THÔNG TIN",
        parent=None,
    ):
        super().__init__(parent)

        self.title_label = QLabel(title)
        self.body = QWidget()
        self.body_layout = None

        self._build_ui()

    # -----------------------------------------
    # UI
    # -----------------------------------------
    def _build_ui(self):
        self.setObjectName("section_card")
        self.setProperty("role", "card")

        self.setFrameShape(QFrame.Shape.NoFrame)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(10)

        self.title_label.setObjectName("section_card_title")
        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)

        root.addWidget(self.title_label)
        root.addWidget(self.body)

    # -----------------------------------------
    # Public API
    # -----------------------------------------
    def set_title(self, text: str):
        self.title_label.setText(text)

    def add_widget(self, widget):
        self.body_layout.addWidget(widget)

    def add_layout(self, layout):
        self.body_layout.addLayout(layout)

    def add_stretch(self):
        self.body_layout.addStretch()

    def clear(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)

            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()

            elif child_layout is not None:
                self._clear_layout(child_layout)

    # -----------------------------------------
    # Helpers
    # -----------------------------------------
    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)

            widget = item.widget()
            child_layout = item.layout()

            if widget is not None:
                widget.deleteLater()

            elif child_layout is not None:
                self._clear_layout(child_layout)