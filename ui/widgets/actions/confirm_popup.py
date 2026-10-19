from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)


class ConfirmPopup(QDialog):
    """
    Reusable confirmation popup for Scan-to-Path UI.

    Use cases:
        - Confirm export results
        - Confirm clear current scan
        - Confirm reset pipeline
        - Confirm close application

    Example:
        dlg = ConfirmPopup(
            title="XÁC NHẬN",
            message="Bạn có muốn xuất kết quả Scan-to-Path không?",
            ok_text="XUẤT",
            cancel_text="HỦY",
        )

        if dlg.exec():
            ...
    """

    def __init__(
        self,
        title: str = "XÁC NHẬN",
        message: str = "Bạn có chắc chắn muốn thực hiện thao tác này?",
        ok_text: str = "ĐỒNG Ý",
        cancel_text: str = "HỦY",
        danger: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.title_text = title
        self.message_text = message
        self.ok_text = ok_text
        self.cancel_text = cancel_text
        self.danger = danger

        self.btn_cancel = None
        self.btn_ok = None

        self.setModal(True)
        self.setWindowTitle(title)
        self.setObjectName("confirm_popup")

        self._build_ui()

    # -----------------------------------------
    # UI
    # -----------------------------------------
    def _build_ui(self):
        self.setFixedSize(440, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title_label = QLabel(self.title_text)
        title_label.setObjectName("confirm_title")

        msg_label = QLabel(self.message_text)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignTop
        )
        msg_label.setObjectName("confirm_message")

        layout.addWidget(title_label)
        layout.addWidget(msg_label, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_row.addStretch()

        self.btn_cancel = QPushButton(self.cancel_text)
        self.btn_cancel.setMinimumHeight(42)
        self.btn_cancel.setProperty("role", "default")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton(self.ok_text)
        self.btn_ok.setMinimumHeight(42)
        self.btn_ok.setProperty("role", "danger" if self.danger else "primary")
        self.btn_ok.clicked.connect(self.accept)

        self._refresh_button(self.btn_cancel)
        self._refresh_button(self.btn_ok)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_ok)

        layout.addLayout(btn_row)

    # -----------------------------------------
    # UX
    # -----------------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self.accept()
            return

        super().keyPressEvent(event)

    # -----------------------------------------
    # Helpers
    # -----------------------------------------
    def _refresh_button(self, button: QPushButton):
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()