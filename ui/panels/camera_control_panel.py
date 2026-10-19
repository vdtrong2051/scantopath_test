from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CameraControlPanel(QFrame):
    """
    Panel điều khiển nguồn dữ liệu 3D.

    Vai trò:
        - Chọn nguồn dữ liệu:
            + FILE_POINTCLOUD
            + HANDHELD_CAMERA
            + TURNTABLE_CAMERA

        - Giữ logic liên quan đến nút "NẠP / QUÉT MẪU 3D"
          nhưng hiển thị rõ ràng hơn thay vì chỉ dùng popup.

        - Chưa capture camera thật.
        - Chỉ phát signal để controller xử lý.

    Panel này KHÔNG xử lý:
        - Open file dialog
        - Orbbec SDK
        - Point cloud filtering
        - Surface map
        - Zigzag

    Các phần đó vẫn do controller/service xử lý.
    """

    # -------------------------------------------------
    # Signals
    # -------------------------------------------------
    source_mode_changed = pyqtSignal(str)

    load_file_requested = pyqtSignal()

    connect_camera_requested = pyqtSignal(str)
    disconnect_camera_requested = pyqtSignal()

    capture_frame_requested = pyqtSignal(str)

    handheld_scan_requested = pyqtSignal()
    turntable_scan_requested = pyqtSignal(float, float)

    # -------------------------------------------------
    # Source mode constants
    # -------------------------------------------------
    MODE_FILE = "FILE_POINTCLOUD"
    MODE_HANDHELD = "HANDHELD_CAMERA"
    MODE_TURNTABLE = "TURNTABLE_CAMERA"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.current_mode = self.MODE_FILE
        self.is_camera_connected = False
        self.is_busy = False

        self.lbl_title = None
        self.lbl_status = None
        self.lbl_session = None
        self.lbl_output = None

        self.cmb_source = None

        self.btn_load_file = None
        self.btn_connect = None
        self.btn_disconnect = None
        self.btn_capture_frame = None
        self.btn_handheld_scan = None
        self.btn_turntable_scan = None

        self.spn_angle_step = None
        self.spn_total_angle = None

        self._build_ui()
        self._build_layout()
        self._bind_events()
        self._apply_styles()
        self._apply_mode_state()

    # -------------------------------------------------
    # Build UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("CameraControlPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.lbl_title = QLabel("CAMERA / NGUỒN DỮ LIỆU 3D")
        self.lbl_title.setObjectName("CameraPanelTitle")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.lbl_status = QLabel("Trạng thái: CHƯA KẾT NỐI")
        self.lbl_status.setObjectName("CameraPanelStatus")

        self.lbl_session = QLabel("Session: --")
        self.lbl_session.setObjectName("CameraPanelInfo")

        self.lbl_output = QLabel("Output: --")
        self.lbl_output.setObjectName("CameraPanelInfo")
        self.lbl_output.setWordWrap(True)

        self.cmb_source = QComboBox()
        self.cmb_source.setObjectName("CameraSourceCombo")
        self.cmb_source.addItem("Nạp file point cloud", self.MODE_FILE)
        self.cmb_source.addItem("Camera cầm tay", self.MODE_HANDHELD)
        self.cmb_source.addItem("Bàn xoay Stop-and-Go", self.MODE_TURNTABLE)

        self.btn_load_file = QPushButton("NẠP FILE POINT CLOUD")
        self.btn_load_file.setObjectName("CameraPrimaryButton")

        self.btn_connect = QPushButton("KẾT NỐI CAMERA")
        self.btn_connect.setObjectName("CameraButton")

        self.btn_disconnect = QPushButton("NGẮT CAMERA")
        self.btn_disconnect.setObjectName("CameraButton")

        self.btn_capture_frame = QPushButton("CHỤP 1 FRAME")
        self.btn_capture_frame.setObjectName("CameraButton")

        self.btn_handheld_scan = QPushButton("QUÉT CẦM TAY")
        self.btn_handheld_scan.setObjectName("CameraPrimaryButton")

        self.btn_turntable_scan = QPushButton("QUÉT BÀN XOAY")
        self.btn_turntable_scan.setObjectName("CameraPrimaryButton")

        self.spn_angle_step = QDoubleSpinBox()
        self.spn_angle_step.setObjectName("CameraSpinBox")
        self.spn_angle_step.setRange(1.0, 90.0)
        self.spn_angle_step.setSingleStep(1.0)
        self.spn_angle_step.setDecimals(1)
        self.spn_angle_step.setValue(10.0)
        self.spn_angle_step.setSuffix("°")

        self.spn_total_angle = QDoubleSpinBox()
        self.spn_total_angle.setObjectName("CameraSpinBox")
        self.spn_total_angle.setRange(10.0, 360.0)
        self.spn_total_angle.setSingleStep(10.0)
        self.spn_total_angle.setDecimals(1)
        self.spn_total_angle.setValue(360.0)
        self.spn_total_angle.setSuffix("°")

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        root.addWidget(self.lbl_title)

        source_row = QVBoxLayout()
        source_row.setSpacing(4)

        lbl_source = QLabel("Nguồn dữ liệu:")
        lbl_source.setObjectName("CameraPanelLabel")

        source_row.addWidget(lbl_source)
        source_row.addWidget(self.cmb_source)

        root.addLayout(source_row)

        status_box = QVBoxLayout()
        status_box.setSpacing(3)
        status_box.addWidget(self.lbl_status)
        status_box.addWidget(self.lbl_session)
        status_box.addWidget(self.lbl_output)

        root.addLayout(status_box)

        root.addWidget(self._make_separator())

        file_box = QVBoxLayout()
        file_box.setSpacing(6)

        lbl_file = QLabel("FILE POINT CLOUD")
        lbl_file.setObjectName("CameraSectionLabel")

        file_box.addWidget(lbl_file)
        file_box.addWidget(self.btn_load_file)

        root.addLayout(file_box)

        root.addWidget(self._make_separator())

        camera_box = QVBoxLayout()
        camera_box.setSpacing(6)

        lbl_camera = QLabel("CAMERA")
        lbl_camera.setObjectName("CameraSectionLabel")

        camera_buttons = QHBoxLayout()
        camera_buttons.setSpacing(6)
        camera_buttons.addWidget(self.btn_connect)
        camera_buttons.addWidget(self.btn_disconnect)

        camera_box.addWidget(lbl_camera)
        camera_box.addLayout(camera_buttons)
        camera_box.addWidget(self.btn_capture_frame)
        camera_box.addWidget(self.btn_handheld_scan)

        root.addLayout(camera_box)

        root.addWidget(self._make_separator())

        turntable_box = QVBoxLayout()
        turntable_box.setSpacing(6)

        lbl_turntable = QLabel("BÀN XOAY STOP-AND-GO")
        lbl_turntable.setObjectName("CameraSectionLabel")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        lbl_angle_step = QLabel("Góc bước:")
        lbl_angle_step.setObjectName("CameraPanelLabel")

        lbl_total_angle = QLabel("Tổng góc:")
        lbl_total_angle.setObjectName("CameraPanelLabel")

        grid.addWidget(lbl_angle_step, 0, 0)
        grid.addWidget(self.spn_angle_step, 0, 1)
        grid.addWidget(lbl_total_angle, 1, 0)
        grid.addWidget(self.spn_total_angle, 1, 1)

        turntable_box.addWidget(lbl_turntable)
        turntable_box.addLayout(grid)
        turntable_box.addWidget(self.btn_turntable_scan)

        root.addLayout(turntable_box)

    def _make_separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("CameraPanelSeparator")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    # -------------------------------------------------
    # Events
    # -------------------------------------------------
    def _bind_events(self):
        self.cmb_source.currentIndexChanged.connect(
            self._on_source_changed
        )

        self.btn_load_file.clicked.connect(
            self.load_file_requested.emit
        )

        self.btn_connect.clicked.connect(
            self._on_connect_clicked
        )

        self.btn_disconnect.clicked.connect(
            self.disconnect_camera_requested.emit
        )

        self.btn_capture_frame.clicked.connect(
            self._on_capture_frame_clicked
        )

        self.btn_handheld_scan.clicked.connect(
            self.handheld_scan_requested.emit
        )

        self.btn_turntable_scan.clicked.connect(
            self._on_turntable_scan_clicked
        )

    def _on_source_changed(self):
        mode = self.cmb_source.currentData()

        if not mode:
            mode = self.MODE_FILE

        self.current_mode = mode
        self.source_mode_changed.emit(mode)

        self._apply_mode_state()

    def _on_connect_clicked(self):
        self.connect_camera_requested.emit(self.current_mode)

    def _on_capture_frame_clicked(self):
        self.capture_frame_requested.emit(self.current_mode)

    def _on_turntable_scan_clicked(self):
        angle_step = float(self.spn_angle_step.value())
        total_angle = float(self.spn_total_angle.value())

        self.turntable_scan_requested.emit(
            angle_step,
            total_angle,
        )

    # -------------------------------------------------
    # Public API - state update
    # -------------------------------------------------
    def set_source_mode(self, mode: str):
        """
        Đổi source mode từ bên ngoài.
        """

        mode = str(mode).strip().upper()

        index = self.cmb_source.findData(mode)

        if index >= 0:
            self.cmb_source.setCurrentIndex(index)
            return

        self.cmb_source.setCurrentIndex(0)

    def get_source_mode(self) -> str:
        return self.current_mode

    def set_camera_connected(self, connected: bool):
        self.is_camera_connected = bool(connected)

        if self.is_camera_connected:
            self.lbl_status.setText("Trạng thái: ĐÃ KẾT NỐI CAMERA")
        else:
            self.lbl_status.setText("Trạng thái: CHƯA KẾT NỐI")

        self._apply_mode_state()

    def set_busy(self, busy: bool):
        self.is_busy = bool(busy)
        self._apply_mode_state()

    def set_session(self, session_id: str | None):
        if session_id:
            self.lbl_session.setText(f"Session: {session_id}")
        else:
            self.lbl_session.setText("Session: --")

    def set_output_path(self, output_path: str | None):
        if output_path:
            self.lbl_output.setText(f"Output: {output_path}")
            self.lbl_output.setToolTip(output_path)
        else:
            self.lbl_output.setText("Output: --")
            self.lbl_output.setToolTip("")

    def set_status_text(self, text: str):
        self.lbl_status.setText(f"Trạng thái: {text}")

    def set_turntable_params(
        self,
        angle_step_deg: float = 10.0,
        total_angle_deg: float = 360.0,
    ):
        self.spn_angle_step.setValue(float(angle_step_deg))
        self.spn_total_angle.setValue(float(total_angle_deg))

    def get_turntable_params(self) -> tuple[float, float]:
        return (
            float(self.spn_angle_step.value()),
            float(self.spn_total_angle.value()),
        )
    
    def _apply_styles(self):
        self.setStyleSheet("""
            QFrame#CameraControlPanel {
                background-color: #1b1d21;
                border: 1px solid #2f3b46;
                border-radius: 8px;
            }

            QLabel#CameraPanelTitle {
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }

            QLabel#CameraPanelStatus {
                color: #27d17f;
                font-size: 11px;
                font-weight: 600;
            }

            QLabel#CameraPanelInfo {
                color: #aeb6c2;
                font-size: 10px;
            }

            QLabel#CameraPanelLabel {
                color: #aeb6c2;
                font-size: 10px;
                font-weight: 600;
            }

            QLabel#CameraSectionLabel {
                color: #7f8da3;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }

            QComboBox#CameraSourceCombo {
                background-color: #24272d;
                color: #ffffff;
                border: 1px solid #3a4654;
                border-radius: 5px;
                padding: 5px 8px;
                min-height: 24px;
            }

            QDoubleSpinBox#CameraSpinBox {
                background-color: #24272d;
                color: #ffffff;
                border: 1px solid #3a4654;
                border-radius: 5px;
                padding: 4px 6px;
                min-height: 22px;
            }

            QPushButton#CameraButton {
                background-color: #303743;
                color: #ffffff;
                border: 1px solid #465263;
                border-radius: 6px;
                padding: 7px 8px;
                font-size: 11px;
                font-weight: 600;
            }

            QPushButton#CameraButton:hover {
                background-color: #3a4350;
            }

            QPushButton#CameraButton:disabled {
                background-color: #22252b;
                color: #5c6470;
                border-color: #2b3138;
            }

            QPushButton#CameraPrimaryButton {
                background-color: #0f7d70;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 8px;
                font-size: 11px;
                font-weight: 700;
            }

            QPushButton#CameraPrimaryButton:hover {
                background-color: #119383;
            }

            QPushButton#CameraPrimaryButton:disabled {
                background-color: #24423f;
                color: #6f8581;
            }

            QFrame#CameraPanelSeparator {
                color: #303743;
                background-color: #303743;
                max-height: 1px;
            }
        """)

    # -------------------------------------------------
    # Internal state logic
    # -------------------------------------------------
    def _apply_mode_state(self):
        """
        Bật/tắt nút theo nguồn dữ liệu.

        Quan trọng:
            - FILE mode chỉ bật nạp file point cloud.
            - Camera mode mới bật connect/capture/scan camera.
        """

        is_file = self.current_mode == self.MODE_FILE
        is_handheld = self.current_mode == self.MODE_HANDHELD
        is_turntable = self.current_mode == self.MODE_TURNTABLE
        is_camera_mode = is_handheld or is_turntable

        can_interact = not self.is_busy

        self.btn_load_file.setEnabled(
            can_interact and is_file
        )

        self.btn_connect.setEnabled(
            can_interact
            and is_camera_mode
            and not self.is_camera_connected
        )

        self.btn_disconnect.setEnabled(
            can_interact
            and is_camera_mode
            and self.is_camera_connected
        )

        self.btn_capture_frame.setEnabled(
            can_interact
            and is_camera_mode
            and self.is_camera_connected
        )

        self.btn_handheld_scan.setEnabled(
            can_interact
            and is_handheld
            and self.is_camera_connected
        )

        self.btn_turntable_scan.setEnabled(
            can_interact
            and is_turntable
            and self.is_camera_connected
        )

        self.spn_angle_step.setEnabled(
            can_interact and is_turntable
        )

        self.spn_total_angle.setEnabled(
            can_interact and is_turntable
        )

        if is_file:
            self.lbl_status.setText(
                "Trạng thái: SẴN SÀNG NẠP FILE POINT CLOUD"
            )

        elif is_camera_mode and self.is_camera_connected:
            self.lbl_status.setText(
                "Trạng thái: ĐÃ KẾT NỐI CAMERA"
            )

        elif is_camera_mode:
            self.lbl_status.setText(
                "Trạng thái: CAMERA CHƯA KẾT NỐI"
            )