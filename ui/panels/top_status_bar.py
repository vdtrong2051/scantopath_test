from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QLabel,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
)

from ui.styles.theme import theme


class TopStatusBar(QFrame):
    """
    Thanh trạng thái phía trên cho hệ thống Scan-to-Path.

    Hiển thị:
        - Tên hệ thống
        - Trạng thái hệ thống
        - Trạng thái dữ liệu quét / bản đồ bề mặt
        - Trạng thái đường dẫn
        - Đồng hồ thời gian thực

    Giữ lại tên hàm cũ để tương thích với MainWindow:
        set_machine_status() -> trạng thái hệ thống
        set_camera_status()  -> trạng thái dữ liệu quét / bề mặt
        set_robot_status()   -> trạng thái đường dẫn
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl_app = None
        self.lbl_system = None
        self.lbl_scan = None
        self.lbl_path = None
        self.lbl_time = None

        self.timer = None

        self._build_ui()
        self._build_layout()
        self._build_timer()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("top_status_bar")
        self.setProperty("role", "flat")

        self.setFixedHeight(theme.sizes.TOP_BAR_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.lbl_app = QLabel("SCAN-TO-PATH")
        self.lbl_app.setStyleSheet(
            f"""
            font-size: {theme.fonts.SIZE_LG}px;
            font-weight: 700;
            """
        )

        self.lbl_system = QLabel("HỆ THỐNG: SẴN SÀNG")
        self.lbl_system.setProperty("role", "success")
        self.lbl_system.setMinimumWidth(170)

        self.lbl_scan = QLabel("QUÉT: CHỜ DỮ LIỆU")
        self.lbl_scan.setProperty("role", "muted")
        self.lbl_scan.setMinimumWidth(190)

        self.lbl_path = QLabel("ĐƯỜNG DẪN: SẴN SÀNG")
        self.lbl_path.setProperty("role", "muted")
        self.lbl_path.setMinimumWidth(210)

        self.lbl_time = QLabel("--:--:--")
        self.lbl_time.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.lbl_time.setMinimumWidth(80)

    def _build_layout(self):
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            theme.spacing.MD,
            0,
            theme.spacing.MD,
            0,
        )

        layout.setSpacing(theme.spacing.LG)

        layout.addWidget(self.lbl_app)
        layout.addSpacing(18)

        layout.addWidget(self.lbl_system)
        layout.addWidget(self.lbl_scan)
        layout.addWidget(self.lbl_path)

        layout.addStretch()

        layout.addWidget(self.lbl_time)

    def _build_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_clock)
        self.timer.start(1000)

        self._update_clock()

    # -------------------------------------------------
    # Runtime
    # -------------------------------------------------
    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_time.setText(now)

    # -------------------------------------------------
    # Public API mới
    # -------------------------------------------------
    def set_system_status(self, text: str, level: str = "success"):
        self.lbl_system.setText(text)
        self.lbl_system.setProperty("role", level)
        self._refresh_label(self.lbl_system)

    def set_scan_status(self, text: str, level: str = "success"):
        self.lbl_scan.setText(text)
        self.lbl_scan.setProperty("role", level)
        self._refresh_label(self.lbl_scan)

    def set_path_status(self, text: str, level: str = "muted"):
        self.lbl_path.setText(text)
        self.lbl_path.setProperty("role", level)
        self._refresh_label(self.lbl_path)

    def set_app_name(self, text: str):
        self.lbl_app.setText(text)

    # -------------------------------------------------
    # API tương thích tên cũ
    # -------------------------------------------------
    def set_machine_status(self, text: str, level: str = "success"):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            machine status -> trạng thái hệ thống
        """
        self.set_system_status(text, level)

    def set_camera_status(self, text: str, level: str = "success"):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            camera status -> trạng thái dữ liệu quét / bản đồ bề mặt
        """
        self.set_scan_status(text, level)

    def set_robot_status(self, text: str, level: str = "muted"):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            robot status -> trạng thái đường dẫn đã sinh
        """
        self.set_path_status(text, level)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _refresh_label(self, widget: QLabel):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()