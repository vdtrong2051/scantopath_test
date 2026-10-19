from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QSizePolicy,
)


class FormRow(QWidget):
    """
    Dòng nhập thông số dùng lại trong UI Scan-to-Path.

    Layout:
        [ Nhãn thông số ]   [ Widget nhập liệu ]

    Dùng cho:
        - Thông số quét 3D
        - Thông số Edge AI
        - Thông số lọc point cloud
        - Thông số tính pháp tuyến
        - Thông số sinh đường Zigzag / Contour
        - Thông số xuất file

    Ví dụ:
        FormRow("Voxel Size", spinbox)
        FormRow("Normal Radius", spinbox)
        FormRow("Path Spacing", spinbox)
        FormRow("Thư mục xuất", lineedit)
    """

    def __init__(
        self,
        label_text: str,
        field_widget: QWidget,
        label_width: int = 160,
        spacing: int = 12,
        parent=None,
    ):
        super().__init__(parent)

        self.label = QLabel(label_text)
        self.field = field_widget

        self.label_width = label_width
        self.spacing = spacing

        self._build_ui()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("form_row")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.spacing)

        self.label.setFixedWidth(self.label_width)

        self.label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter
            | Qt.AlignmentFlag.AlignLeft
        )

        self.label.setObjectName("form_row_label")

        self.field.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout.addWidget(self.label)
        layout.addWidget(self.field, 1)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_label(self, text: str):
        self.label.setText(text)

    def set_label_width(self, width: int):
        self.label_width = width
        self.label.setFixedWidth(width)

    def set_enabled(self, enabled: bool):
        self.label.setEnabled(enabled)
        self.field.setEnabled(enabled)

    def get_field(self):
        return self.field

    def get_label(self):
        return self.label