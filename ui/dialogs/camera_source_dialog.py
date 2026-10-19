from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
    QMessageBox,
)

from ui.panels.camera_control_panel import CameraControlPanel
from ui.widgets.camera_preview_widget import CameraPreviewWidget

from modules.acquisition.openni_scan_worker import (
    OpenNIScanWorker,
    OpenNIScanWorkerParams,
)

from services.multiview_scan_service import (
    MultiViewScanService,
    MultiViewScanParams,
)


class CameraSourceDialog(QDialog):
    """
    Dialog chọn nguồn dữ liệu 3D.

    Bản demo-stable:
        - Kết nối camera thật bằng OpenNI.
        - Stream RGB/Depth lên preview.
        - Chụp 1 frame tạo PLY.
        - Bấm QUÉT CẦM TAY thì trả path PLY về controller.
        - KHÔNG stop/destroy camera khi bấm QUÉT CẦM TAY.
    """

    ACTION_NONE = "none"
    ACTION_LOAD_FILE = "load_file"
    ACTION_CAPTURE_FRAME = "capture_frame"
    ACTION_HANDHELD_SCAN = "handheld_scan"
    ACTION_TURNTABLE_SCAN = "turntable_scan"
    ACTION_USE_CAPTURED_SCAN = "use_captured_scan"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.selected_action = self.ACTION_NONE
        self.selected_mode = CameraControlPanel.MODE_FILE

        self.angle_step_deg = 10.0
        self.total_angle_deg = 360.0

        self.preview_widget = None
        self.camera_panel = None
        self.btn_close = None

        self.scan_worker: OpenNIScanWorker | None = None

        self.last_capture_path: Path | None = None
        self.last_capture_point_count: int = 0
        self.last_capture_pitch: float = 0.0
        self.last_capture_yaw: float = 0.0

        self.enable_multiview = True
        self.multiview_view_count = 4
        self.multiview_service: MultiViewScanService | None = None

        self._build_window()
        self._build_ui()
        self._build_layout()
        self._bind_events()
        self._apply_styles()

    # -------------------------------------------------
    # Build
    # -------------------------------------------------
    def _build_window(self):
        self.setWindowTitle("Chọn nguồn dữ liệu 3D")
        self.setModal(True)

        self.setMinimumWidth(1120)
        self.setMinimumHeight(650)
        self.resize(1180, 720)

    def _build_ui(self):
        self.preview_widget = CameraPreviewWidget()
        self.preview_widget.set_status("CHƯA KẾT NỐI CAMERA")

        self.camera_panel = CameraControlPanel()
        self.camera_panel.set_camera_connected(False)
        self.camera_panel.set_session(None)
        self.camera_panel.set_output_path(None)

        self.camera_panel.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        self.camera_panel.setMinimumWidth(390)
        self.camera_panel.setMaximumWidth(430)

        self.btn_close = QPushButton("ĐÓNG")
        self.btn_close.setObjectName("CameraDialogCloseButton")
        self.btn_close.setMinimumHeight(38)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)

        content.addWidget(self.preview_widget, 1)
        content.addWidget(self.camera_panel, 0)

        root.addLayout(content, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch()
        bottom.addWidget(self.btn_close)

        root.addLayout(bottom)

    def _bind_events(self):
        self.btn_close.clicked.connect(self.reject)

        self.camera_panel.source_mode_changed.connect(
            self._on_source_mode_changed
        )

        self.camera_panel.load_file_requested.connect(
            self._select_load_file
        )

        self.camera_panel.connect_camera_requested.connect(
            self._connect_openni_camera
        )

        self.camera_panel.disconnect_camera_requested.connect(
            self._disconnect_openni_camera
        )

        self.camera_panel.capture_frame_requested.connect(
            self._on_capture_frame_clicked
        )

        self.camera_panel.handheld_scan_requested.connect(
            self._select_handheld_scan
        )

        self.camera_panel.turntable_scan_requested.connect(
            self._select_turntable_scan
        )

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0d10;
            }

            QPushButton#CameraDialogCloseButton {
                background-color: #303743;
                color: #ffffff;
                border: 1px solid #465263;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }

            QPushButton#CameraDialogCloseButton:hover {
                background-color: #3a4350;
            }
        """)

    # -------------------------------------------------
    # Public helper
    # -------------------------------------------------
    def _ensure_multiview_service(self):
        """
        Tạo session quét nhiều góc nếu chưa có.

        Giai đoạn hiện tại:
            - Chụp thủ công từng góc
            - Mỗi lần CHỤP 1 FRAME sẽ tự add vào service
            - QUÉT CẦM TAY sẽ merge nếu có >= 2 view
        """

        if self.multiview_service is not None:
            return self.multiview_service

        self.multiview_service = MultiViewScanService(
            MultiViewScanParams(
                view_count=self.multiview_view_count,
                auto_extract_object=True,
                save_each_object_view=True,
                save_merged_cloud=True,
            )
        )

        return self.multiview_service

    def reset_selection(self):
        """
        Reset action mỗi lần mở lại dialog.
        Không reset last_capture_path để nếu vừa chụp xong vẫn dùng được.
        """

        self.selected_action = self.ACTION_NONE

    # -------------------------------------------------
    # Source mode
    # -------------------------------------------------
    def _on_source_mode_changed(self, mode: str):
        self.selected_mode = mode

        if mode == CameraControlPanel.MODE_FILE:
            self.preview_widget.set_status("FILE POINT CLOUD MODE")

        elif mode == CameraControlPanel.MODE_HANDHELD:
            self.preview_widget.set_status("HANDHELD CAMERA MODE")

        elif mode == CameraControlPanel.MODE_TURNTABLE:
            self.preview_widget.set_status("TURNTABLE CAMERA MODE")

    # -------------------------------------------------
    # OpenNI Camera
    # -------------------------------------------------
    def _connect_openni_camera(self, mode: str):
        self.selected_mode = mode

        if mode == CameraControlPanel.MODE_FILE:
            self.camera_panel.set_status_text("FILE MODE - KHÔNG CẦN CAMERA")
            self.preview_widget.set_status("FILE POINT CLOUD MODE")
            return

        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.camera_panel.set_camera_connected(True)
            self.camera_panel.set_status_text("CAMERA ĐANG STREAM")
            self.preview_widget.set_status("CAMERA ĐANG STREAM")
            return

        try:
            params = OpenNIScanWorkerParams(
                output_root="data/pointcloud_raw",
                target_fps=20,
                session_prefix="OPENNI",
                min_depth_m=0.35,
                max_depth_m=1.60,
                stride=1,
                auto_disconnect_on_stop=False,
            )

            self.scan_worker = OpenNIScanWorker(
                params=params,
            )

            self.scan_worker.sig_frame_ready.connect(
                self._on_worker_frame_ready
            )

            self.scan_worker.sig_status.connect(
                self._on_worker_status
            )

            self.scan_worker.sig_capture_success.connect(
                self._on_capture_success
            )

            self.scan_worker.sig_capture_error.connect(
                self._on_capture_error
            )

            self.scan_worker.sig_error.connect(
                self._on_worker_error
            )

            self.camera_panel.set_camera_connected(True)
            self.camera_panel.set_status_text("ĐANG KẾT NỐI CAMERA...")
            self.camera_panel.set_session("Đang tạo session...")
            self.camera_panel.set_output_path(None)

            self.preview_widget.clear_all()
            self.preview_widget.set_status("ĐANG KẾT NỐI OPENNI/ASTRA...")

            self.scan_worker.start()

        except Exception as exc:
            self.camera_panel.set_camera_connected(False)
            self.camera_panel.set_status_text("LỖI KẾT NỐI CAMERA")
            self.preview_widget.set_status("LỖI KẾT NỐI CAMERA")

            QMessageBox.critical(
                self,
                "Lỗi camera OpenNI",
                f"Không thể khởi động camera OpenNI/Astra:\n\n{exc}",
            )

    def _disconnect_openni_camera(self, silent: bool = False):
        """
        Nút NGẮT CAMERA.

        Bản demo-stable:
            - Chỉ request_stop khi người dùng chủ động bấm NGẮT.
            - Không dùng hàm này khi bấm QUÉT CẦM TAY.
        """

        if self.scan_worker is None:
            self.camera_panel.set_camera_connected(False)
            self.camera_panel.set_status_text("CHƯA CÓ CAMERA ĐANG CHẠY")
            return

        try:
            self.scan_worker.request_stop()

            self.camera_panel.set_camera_connected(False)

            if not silent:
                self.camera_panel.set_status_text("ĐÃ GỬI LỆNH NGẮT CAMERA")
                self.preview_widget.set_status("ĐÃ GỬI LỆNH NGẮT CAMERA")

        except Exception as exc:
            if not silent:
                QMessageBox.warning(
                    self,
                    "Cảnh báo",
                    f"Có lỗi khi ngắt camera:\n\n{exc}",
                )

    # -------------------------------------------------
    # Worker callbacks
    # -------------------------------------------------
    def _on_worker_frame_ready(self, qt_rgb, qt_depth):
        """
        Nhận QImage đã copy từ worker và đưa lên preview.
        """

        self.preview_widget.set_rgb_pixmap(
            QPixmap.fromImage(qt_rgb),
            info="RGB STREAM | OPENNI",
        )

        self.preview_widget.set_depth_pixmap(
            QPixmap.fromImage(qt_depth),
            info="DEPTH STREAM | OPENNI",
        )

    def _on_worker_status(self, message: str, level: str = "info"):
        self.camera_panel.set_status_text(message)
        self.preview_widget.set_status(message)

        if self.scan_worker is not None:
            try:
                self.camera_panel.set_session(
                    self.scan_worker.get_session_id()
                )
            except Exception:
                pass

    def _on_worker_error(self, message: str):
        self.camera_panel.set_camera_connected(False)
        self.camera_panel.set_status_text("LỖI CAMERA")
        self.preview_widget.set_status("LỖI CAMERA")

        QMessageBox.critical(
            self,
            "Lỗi camera",
            message,
        )

    # -------------------------------------------------
    # Capture
    # -------------------------------------------------
    def _on_capture_frame_clicked(self, mode: str):
        self.selected_action = self.ACTION_CAPTURE_FRAME
        self.selected_mode = mode

        if self.scan_worker is None or not self.scan_worker.isRunning():
            self.camera_panel.set_status_text("CHƯA KẾT NỐI CAMERA")
            self.preview_widget.set_status("CHƯA KẾT NỐI CAMERA")

            QMessageBox.information(
                self,
                "Camera chưa kết nối",
                "Hãy chọn Camera cầm tay hoặc Bàn xoay, sau đó bấm KẾT NỐI CAMERA trước.",
            )
            return

        angle_step, total_angle = self.camera_panel.get_turntable_params()

        pitch = 0.0
        yaw = 0.0

        if mode == CameraControlPanel.MODE_TURNTABLE:
            yaw = angle_step

        self.camera_panel.set_status_text("ĐANG CHỤP 1 FRAME...")
        self.preview_widget.set_status("ĐANG CHỤP 1 FRAME...")

        ok = self.scan_worker.capture_latest_now(
            pitch_deg=pitch,
            yaw_deg=yaw,
        )

        if not ok:
            self.camera_panel.set_status_text("KHÔNG THỂ CHỤP FRAME")
            self.preview_widget.set_status("KHÔNG THỂ CHỤP FRAME")

    def _on_capture_success(
        self,
        file_path: str,
        pitch_deg: float,
        yaw_deg: float,
        point_count: int,
    ):
        self.last_capture_path = Path(file_path)
        self.last_capture_pitch = float(pitch_deg)
        self.last_capture_yaw = float(yaw_deg)
        self.last_capture_point_count = int(point_count)

        status_text = f"ĐÃ TẠO POINT CLOUD | {point_count} điểm"

        # -------------------------------------------------
        # Add view vào multiview session
        # -------------------------------------------------
        if self.enable_multiview:
            try:
                service = self._ensure_multiview_service()

                next_yaw = service.get_next_yaw_deg()

                view = service.add_raw_file_view(
                    file_path=str(self.last_capture_path),
                    yaw_deg=next_yaw,
                    name=f"camera_view_{service.get_next_view_index():02d}",
                )

                status_text = (
                    f"ĐÃ THÊM VIEW {view.index}/"
                    f"{service.params.view_count} | "
                    f"Yaw={view.yaw_deg:.1f}° | "
                    f"Object={view.object_point_count} điểm"
                )

                self.preview_widget.set_status(
                    "ĐÃ LƯU VIEW - XOAY VẬT/NGƯỜI RỒI CHỤP GÓC TIẾP THEO"
                )

            except Exception as exc:
                # Nếu multiview lỗi thì vẫn giữ single PLY để dùng như cũ.
                status_text = (
                    f"ĐÃ TẠO POINT CLOUD | {point_count} điểm | "
                    f"Multiview lỗi: {exc}"
                )

                self.preview_widget.set_status(
                    "ĐÃ LƯU PLY SINGLE VIEW - MULTIVIEW CHƯA THÊM ĐƯỢC"
                )

        else:
            self.preview_widget.set_status(
                "ĐÃ LƯU PLY - BẤM QUÉT CẦM TAY ĐỂ NẠP 3D"
            )

        self.camera_panel.set_status_text(status_text)
        self.camera_panel.set_output_path(str(self.last_capture_path))

    def _on_capture_error(self, error_text: str):
        self.camera_panel.set_status_text("LỖI TẠO POINT CLOUD")
        self.preview_widget.set_status("LỖI TẠO POINT CLOUD")

        QMessageBox.critical(
            self,
            "Lỗi tạo point cloud",
            error_text,
        )

    # -------------------------------------------------
    # Dialog actions
    # -------------------------------------------------
    def _select_load_file(self):
        self.selected_action = self.ACTION_LOAD_FILE
        self.selected_mode = CameraControlPanel.MODE_FILE
        super().accept()

    def _select_handheld_scan(self):
        """
        QUÉT CẦM TAY.

        Nếu có nhiều view:
            → merge nhiều góc
            → trả merged_multiview.ply cho pipeline

        Nếu chỉ có 1 view:
            → dùng single PLY như cũ
        """

        self.selected_mode = CameraControlPanel.MODE_HANDHELD

        if self.last_capture_path is None:
            QMessageBox.information(
                self,
                "Chưa có point cloud từ camera",
                (
                    "Chưa có file point cloud từ camera.\n\n"
                    "Hãy bấm CHỤP 1 FRAME trước để tạo PLY,\n"
                    "sau đó bấm QUÉT CẦM TAY để đưa file này vào pipeline."
                ),
            )
            return

        # -------------------------------------------------
        # Nếu đã có nhiều view thì merge trước khi trả path
        # -------------------------------------------------
        if self.enable_multiview and self.multiview_service is not None:
            view_count = len(self.multiview_service.get_views())

            if view_count >= 2:
                try:
                    self.camera_panel.set_status_text(
                        f"ĐANG MERGE {view_count} VIEW..."
                    )

                    self.preview_widget.set_status(
                        f"ĐANG GHÉP POINT CLOUD {view_count} GÓC..."
                    )

                    result = self.multiview_service.merge_views(
                        save_output=True,
                    )

                    if result.merged_path is not None:
                        self.last_capture_path = Path(result.merged_path)

                    self.camera_panel.set_status_text(
                        f"ĐÃ MERGE {result.used_view_count} VIEW | "
                        f"{result.merge_result.output_point_count} điểm"
                    )

                    self.camera_panel.set_output_path(
                        str(self.last_capture_path)
                    )

                    self.preview_widget.set_status(
                        "ĐÃ MERGE MULTIVIEW - ĐANG NẠP 3D"
                    )

                except Exception as exc:
                    QMessageBox.warning(
                        self,
                        "Lỗi merge nhiều góc",
                        (
                            "Không thể merge multiview.\n\n"
                            f"Lỗi: {exc}\n\n"
                            "Sẽ dùng file single-view cuối cùng."
                        ),
                    )

        self.selected_action = self.ACTION_USE_CAPTURED_SCAN

        # Không stop camera.
        # Không cleanup OpenNI.
        # Chỉ đóng dialog để controller lấy path và load 3D.
        super().accept()

    def _select_turntable_scan(
        self,
        angle_step_deg: float,
        total_angle_deg: float,
    ):
        self.selected_mode = CameraControlPanel.MODE_TURNTABLE
        self.angle_step_deg = float(angle_step_deg)
        self.total_angle_deg = float(total_angle_deg)

        if self.last_capture_path is None:
            QMessageBox.information(
                self,
                "Chưa có point cloud từ camera",
                (
                    "Chưa có file point cloud từ camera.\n\n"
                    "Ở giai đoạn này, hãy bấm CHỤP 1 FRAME trước.\n"
                    "Bản quét bàn xoay nhiều góc sẽ build sau."
                ),
            )
            return

        self.selected_action = self.ACTION_USE_CAPTURED_SCAN
        super().accept()

    # -------------------------------------------------
    # Public getters
    # -------------------------------------------------
    def get_selected_action(self) -> str:
        return self.selected_action

    def get_selected_mode(self) -> str:
        return self.selected_mode

    def get_turntable_params(self) -> tuple[float, float]:
        return self.angle_step_deg, self.total_angle_deg

    def get_captured_scan_path(self) -> str | None:
        if self.last_capture_path is None:
            return None

        return str(self.last_capture_path)

    def get_capture_point_count(self) -> int:
        return int(self.last_capture_point_count)

    # -------------------------------------------------
    # Close lifecycle
    # -------------------------------------------------
    def accept(self):
        """
        Demo-stable:
        Không stop camera khi accept.
        """

        super().accept()

    def reject(self):
        """
        Demo-stable:
        Đóng dialog nhưng không stop camera.
        Vì controller giữ dialog sống, camera vẫn an toàn.
        """

        super().reject()

    def closeEvent(self, event):
        """
        Nút X cũng chỉ đóng dialog.
        Không cleanup camera tại đây.
        """

        event.accept()