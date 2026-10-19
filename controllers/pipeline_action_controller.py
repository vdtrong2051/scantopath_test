from __future__ import annotations

from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QDialog,
)
from PyQt6.QtCore import QTimer

from controllers.pipeline_controller import PipelineController
from controllers.pipeline_presenter import PipelinePresenter
from ui.dialogs.camera_source_dialog import CameraSourceDialog

class PipelineActionController:
    """
    Controller điều phối action từ RightActionPanel.

    Vai trò:
        - Nhận action name từ UI.
        - Gọi PipelineController để xử lý dữ liệu.
        - Gọi PipelinePresenter để hiển thị kết quả.

    Ghi chú:
        - Nút "NẠP / QUÉT MẪU 3D" hiện ưu tiên đọc mode từ CameraControlPanel.
        - Nếu chưa có CameraControlPanel thì fallback về popup cũ.
    """

    MODE_FILE = "FILE_POINTCLOUD"
    MODE_HANDHELD = "HANDHELD_CAMERA"
    MODE_TURNTABLE = "TURNTABLE_CAMERA"

    def __init__(
        self,
        window,
        pipeline: PipelineController,
    ):
        self.window = window
        self.pipeline = pipeline
        self.presenter = PipelinePresenter(window)
        self._camera_dialog = None
        self._pending_camera_capture_path = None

    # -------------------------------------------------
    # Main entry
    # -------------------------------------------------
    def handle_action(self, action: str):
        print(f"[UI] Action requested: {action}")

        try:
            if action == "load_scan":
                self._handle_load_scan()

            elif action == "camera_load_file":
                self._handle_load_scan_from_file()

            elif action.startswith("camera_connect:"):
                mode = action.split(":", 1)[1]
                self._handle_camera_connect(mode)

            elif action == "camera_disconnect":
                self._handle_camera_disconnect()

            elif action.startswith("camera_capture_frame:"):
                mode = action.split(":", 1)[1]
                self._handle_camera_capture_frame(mode)

            elif action == "camera_handheld_scan":
                self._handle_handheld_camera_mock()

            elif action.startswith("camera_turntable_scan:"):
                angle_step, total_angle = self._parse_turntable_action(action)
                self._handle_turntable_camera_mock(
                    angle_step_deg=angle_step,
                    total_angle_deg=total_angle,
                )

            elif action == "edge_ai_mask":
                self._handle_extract_nearest_object()

            elif action == "build_pointcloud":
                self.presenter.show_build_pointcloud_placeholder()

            elif action == "filter_pointcloud":
                self._handle_filter_pointcloud()

            elif action == "estimate_normals":
                self._handle_estimate_normals()

            elif action == "build_surface_map":
                self._handle_build_surface_map()

            elif action == "generate_zigzag":
                self._handle_generate_zigzag()

            elif action == "generate_contour":
                self.presenter.show_contour_placeholder()

            elif action == "export_results":
                self._handle_export_results()

            else:
                self.presenter.show_unknown_action(action)

        finally:
            self.apply_pipeline_stage()

    # -------------------------------------------------
    # Stage
    # -------------------------------------------------
    def apply_pipeline_stage(self):
        try:
            self.pipeline.refresh_stage()

            right_panel = getattr(self.window, "right_panel", None)

            if right_panel is not None and hasattr(right_panel, "apply_action_state"):
                right_panel.apply_action_state(
                    self.pipeline.get_action_state()
                )

        except Exception as exc:
            print(f"[PIPELINE STAGE WARNING] {exc}")

    # -------------------------------------------------
    # Input source
    # -------------------------------------------------
    def _handle_load_scan(self):
        """
        Mở dialog chọn nguồn dữ liệu 3D.

        Không mở QFileDialog trực tiếp nữa.
        QFileDialog chỉ mở khi người dùng bấm:
            NẠP FILE POINT CLOUD
        trong CameraSourceDialog.
        """

        if self._camera_dialog is None:
            self._camera_dialog = CameraSourceDialog(self.window)

        dialog = self._camera_dialog

        if hasattr(dialog, "reset_selection"):
            dialog.reset_selection()

        dialog_result = dialog.exec()

        if dialog_result != QDialog.DialogCode.Accepted:
            self.presenter.show_source_selection_cancelled()
            return

        selected_action = dialog.get_selected_action()

        if selected_action == CameraSourceDialog.ACTION_LOAD_FILE:
            self._handle_load_scan_from_file()
            return

        if selected_action == CameraSourceDialog.ACTION_USE_CAPTURED_SCAN:
            captured_path = dialog.get_captured_scan_path()
            self._pending_camera_capture_path = captured_path

            # Không delete dialog.
            # Không stop camera.
            # Nạp PLY lên viewport gần như ngay lập tức.
            QTimer.singleShot(
                100,
                lambda: self._handle_load_camera_captured_scan(
                    self._pending_camera_capture_path
                )
            )
            return

        if selected_action == CameraSourceDialog.ACTION_CAPTURE_FRAME:
            mode = dialog.get_selected_mode()
            self._handle_camera_capture_frame(mode)
            return

        if selected_action == CameraSourceDialog.ACTION_HANDHELD_SCAN:
            self._handle_handheld_camera_mock()
            return

        if selected_action == CameraSourceDialog.ACTION_TURNTABLE_SCAN:
            angle_step, total_angle = dialog.get_turntable_params()
            self._handle_turntable_camera_mock(
                angle_step_deg=angle_step,
                total_angle_deg=total_angle,
            )
            return

        self.presenter.show_unknown_action(selected_action)

    def _handle_load_scan_popup_fallback(self):
        """
        Popup cũ, chỉ dùng nếu chưa gắn CameraControlPanel.
        """

        options = [
            "1. Nạp file point cloud",
            "2. Quét bằng camera cầm tay",
            "3. Quét bằng bàn xoay",
        ]

        selected, ok = QInputDialog.getItem(
            self.window,
            "Chọn nguồn dữ liệu 3D",
            "Chọn chế độ nạp / quét mẫu 3D:",
            options,
            0,
            False,
        )

        if not ok:
            self.presenter.show_source_selection_cancelled()
            return

        if selected.startswith("1."):
            self._handle_load_scan_from_file()

        elif selected.startswith("2."):
            self._handle_handheld_camera_mock()

        elif selected.startswith("3."):
            self._handle_turntable_camera_mock()

        else:
            self.presenter.show_unknown_action(selected)

    def _handle_load_scan_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Chọn file quét 3D",
            "data/pointcloud_raw",
            "Point Cloud Files (*.ply *.pcd *.xyz *.xyzn *.xyzrgb);;All Files (*)",
        )

        if not file_path:
            self.presenter.show_load_scan_cancelled()
            return

        try:
            result = self.pipeline.load_scan_from_file(file_path)
            self.presenter.show_load_scan_result(result)

            camera_panel = self._camera_panel()
            if camera_panel is not None:
                camera_panel.set_source_mode(self.MODE_FILE)
                camera_panel.set_session("FILE_POINTCLOUD")
                camera_panel.set_output_path(file_path)

        except Exception as exc:
            self.presenter.show_load_scan_error(exc)

    def _handle_load_camera_captured_scan(self, file_path: str | None):
        """
        Nạp file .ply vừa được tạo từ camera OpenNI/Astra.

        Luồng:
            CameraSourceDialog
            → CHỤP 1 FRAME
            → tạo .ply trong data/pointcloud_raw/OPENNI_...
            → QUÉT CẦM TAY
            → hàm này nạp .ply đó vào pipeline như file point cloud thường.
        """

        if not file_path:
            self.presenter.show_load_scan_error(
                RuntimeError(
                    "Chưa có file point cloud từ camera. "
                    "Hãy bấm CHỤP 1 FRAME trước."
                )
            )
            return

        try:
            result = self.pipeline.load_scan_from_file(file_path)

            # Quan trọng:
            # Hàm này đã hiển thị point cloud lên viewport rồi.
            # Không được gọi set_viewport_status() ngay sau đó,
            # vì nó sẽ ghi đè viewport 3D thành text.
            self.presenter.show_load_scan_result(result)

            self.presenter.set_top_status(
                system=("HỆ THỐNG: SẴN SÀNG", "success"),
                scan=("CAMERA OPENNI: ĐÃ NẠP POINT CLOUD", "success"),
                path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
            )

            self.presenter.runtime("set_method", "OPENNI RGB-D")
            self.presenter.runtime("set_output", "POINT CLOUD TỪ CAMERA")
            self.apply_pipeline_stage()

        except Exception as exc:
            self.presenter.show_load_scan_error(exc)

    # -------------------------------------------------
    # Camera panel actions
    # -------------------------------------------------
    def _handle_camera_connect(self, mode: str):
        """
        Kết nối camera ở mức UI/mock.

        Hiện tại chưa capture thật bằng Python.
        Hàm này chỉ chuẩn bị trạng thái UI cho CameraControlPanel.
        """

        mode = self._normalize_camera_mode(mode)
        camera_panel = self._camera_panel()

        try:
            camera_mode = "HANDHELD"

            if mode == self.MODE_TURNTABLE:
                camera_mode = "TURNTABLE"

            # Nếu CameraService hiện tại có connect() thì gọi luôn.
            camera_service = getattr(self.pipeline, "camera_service", None)
            if camera_service is not None and hasattr(camera_service, "connect"):
                camera_service.connect(camera_mode)

            if camera_panel is not None:
                camera_panel.set_camera_connected(True)
                camera_panel.set_status_text("ĐÃ KẾT NỐI CAMERA MOCK")
                camera_panel.set_session(f"{camera_mode}_MOCK")
                camera_panel.set_output_path("Chưa có point cloud thật")

            self.presenter.set_top_status(
                system=("HỆ THỐNG: SẴN SÀNG", "success"),
                scan=(f"CAMERA: {camera_mode} MOCK", "warning"),
                path=("ĐƯỜNG DẪN: CHỜ DỮ LIỆU", "muted"),
            )

            self.presenter.runtime("set_progress", 5)
            self.presenter.runtime("set_eta", "Kết nối camera mock")
            self.presenter.runtime("set_mode", f"{camera_mode} MOCK")
            self.presenter.runtime("set_points", "--")
            self.presenter.runtime("set_method", "CAMERA MOCK")
            self.presenter.runtime("set_output", "CHƯA CÓ POINT CLOUD")

            self.presenter.set_viewport_status(
                "CAMERA MOCK ĐÃ KẾT NỐI\n\n"
                f"Mode hiện tại: {camera_mode}\n\n"
                "Giai đoạn này chỉ tạo layout và luồng điều khiển camera.\n"
                "Chưa capture point cloud thật.\n\n"
                "Bạn vẫn có thể dùng nguồn FILE POINT CLOUD để chạy pipeline."
            )

        except Exception as exc:
            if camera_panel is not None:
                camera_panel.set_camera_connected(False)
                camera_panel.set_status_text("LỖI KẾT NỐI CAMERA")

            self.presenter.set_viewport_status(
                "Không thể kết nối camera mock.\n\n"
                f"Lỗi: {exc}"
            )

    def _handle_camera_disconnect(self):
        camera_panel = self._camera_panel()

        try:
            camera_service = getattr(self.pipeline, "camera_service", None)

            if camera_service is not None and hasattr(camera_service, "disconnect"):
                camera_service.disconnect()

            if camera_panel is not None:
                camera_panel.set_camera_connected(False)
                camera_panel.set_status_text("ĐÃ NGẮT CAMERA")
                camera_panel.set_session(None)
                camera_panel.set_output_path(None)

            self.presenter.set_top_status(
                system=("HỆ THỐNG: SẴN SÀNG", "success"),
                scan=("CAMERA: ĐÃ NGẮT", "muted"),
                path=("ĐƯỜNG DẪN: CHỜ", "muted"),
            )

            self.presenter.runtime("set_eta", "Đã ngắt camera")
            self.presenter.runtime("set_mode", "CHỜ")
            self.presenter.runtime("set_output", "--")

            self.presenter.set_viewport_status(
                "Đã ngắt camera.\n\n"
                "Bạn có thể chọn lại nguồn dữ liệu hoặc nạp file point cloud."
            )

        except Exception as exc:
            self.presenter.set_viewport_status(
                "Không thể ngắt camera.\n\n"
                f"Lỗi: {exc}"
            )

    def _handle_camera_capture_frame(self, mode: str):
        """
        Placeholder cho nút CHỤP 1 FRAME.

        Sau này khi có Python camera source thật thì hàm này sẽ gọi capture thật.
        """

        mode = self._normalize_camera_mode(mode)
        camera_panel = self._camera_panel()

        if camera_panel is not None and not camera_panel.is_camera_connected:
            self.presenter.set_viewport_status(
                "Camera chưa kết nối.\n\n"
                "Hãy bấm KẾT NỐI CAMERA trước khi chụp frame."
            )
            return

        self.presenter.set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("CAMERA: CHỤP FRAME MOCK", "warning"),
            path=("ĐƯỜNG DẪN: CHỜ DỮ LIỆU", "muted"),
        )

        self.presenter.runtime("set_progress", 8)
        self.presenter.runtime("set_eta", "Chụp 1 frame mock")
        self.presenter.runtime("set_mode", "FRAME MOCK")
        self.presenter.runtime("set_points", "--")
        self.presenter.runtime("set_method", "RGB-D MOCK")
        self.presenter.runtime("set_output", "CHƯA CÓ POINT CLOUD")

        self.presenter.set_viewport_status(
            "CHỤP 1 FRAME CAMERA MOCK\n\n"
            f"Mode: {mode}\n\n"
            "Hiện tại nút này chỉ kiểm tra luồng UI.\n"
            "Bước sau sẽ nối vào camera Python thật để lấy RGB/Depth frame."
        )

        if camera_panel is not None:
            camera_panel.set_status_text("ĐÃ CHỤP FRAME MOCK")
            camera_panel.set_output_path("Chưa có dữ liệu frame thật")

    # -------------------------------------------------
    # Camera mock scans
    # -------------------------------------------------
    def _handle_handheld_camera_mock(self):
        try:
            result = self.pipeline.run_handheld_camera_mock()
            self.presenter.show_handheld_camera_mock(result)

            camera_panel = self._camera_panel()
            if camera_panel is not None:
                camera_panel.set_source_mode(self.MODE_HANDHELD)
                camera_panel.set_status_text("HANDHELD MOCK HOÀN TẤT")
                camera_panel.set_session("HANDHELD_MOCK")
                camera_panel.set_output_path("Chưa có point cloud thật")

        except Exception as exc:
            self.presenter.show_handheld_camera_error(exc)

    def _handle_turntable_camera_mock(
        self,
        angle_step_deg: float = 10.0,
        total_angle_deg: float = 360.0,
    ):
        try:
            result = self.pipeline.run_turntable_camera_mock(
                angle_step_deg=angle_step_deg,
                total_angle_deg=total_angle_deg,
            )
            self.presenter.show_turntable_camera_mock(result)

            camera_panel = self._camera_panel()
            if camera_panel is not None:
                camera_panel.set_source_mode(self.MODE_TURNTABLE)
                camera_panel.set_turntable_params(
                    angle_step_deg=angle_step_deg,
                    total_angle_deg=total_angle_deg,
                )
                camera_panel.set_status_text("TURNTABLE MOCK HOÀN TẤT")
                camera_panel.set_session("TURNTABLE_MOCK")
                camera_panel.set_output_path("Chưa có point cloud thật")

        except Exception as exc:
            self.presenter.show_turntable_camera_error(exc)

    # -------------------------------------------------
    # Point cloud pipeline
    # -------------------------------------------------
    def _handle_extract_nearest_object(self):
        """
        Nút:
            TÁCH VẬT THỂ BẰNG EDGE AI

        Giai đoạn hiện tại:
            Chưa chạy Edge AI model thật.
            Dùng DepthObjectExtractor:
                - ưu tiên vật thể gần camera nhất
                - crop theo depth
                - loại mặt phẳng lớn
                - DBSCAN giữ cụm vật thể
        """

        try:
            result = self.pipeline.extract_nearest_object()

            object_cloud = result.object_cloud
            point_count_text = f"{result.output_count:,}".replace(",", ".")

            self.presenter.set_top_status(
                system=("HỆ THỐNG: SẴN SÀNG", "success"),
                scan=("VẬT THỂ: ĐÃ TÁCH", "success"),
                path=("ĐƯỜNG DẪN: CHỜ XỬ LÝ", "muted"),
            )

            self.presenter.runtime("set_progress", 20)
            self.presenter.runtime("set_eta", "Đã tách vật thể")
            self.presenter.runtime("set_mode", "OBJECT ONLY")
            self.presenter.runtime("set_points", point_count_text)
            self.presenter.runtime("set_method", "DEPTH + GEOMETRY")
            self.presenter.runtime("set_output", "OBJECT POINT CLOUD")

            viewport = getattr(self.window, "viewport", None)

            if viewport is not None and hasattr(viewport, "show_point_cloud"):
                viewport.show_point_cloud(
                    object_cloud,
                    title="OBJECT POINT CLOUD",
                    status=(
                        "Đã tách vật thể gần camera nhất | "
                        f"{point_count_text} điểm"
                    ),
                    max_points=120_000,
                    point_size=0.008,
                )
            else:
                self.presenter.set_viewport_status(
                    "Đã tách vật thể nhưng viewport chưa hỗ trợ show_point_cloud().\n\n"
                    f"{result.message}"
                )

            self.apply_pipeline_stage()

        except Exception as exc:
            self.presenter.set_top_status(
                system=("HỆ THỐNG: LỖI", "danger"),
                scan=("TÁCH VẬT THỂ: LỖI", "danger"),
                path=("ĐƯỜNG DẪN: CHỜ", "muted"),
            )

            self.presenter.runtime("set_progress", 10)
            self.presenter.runtime("set_eta", "Lỗi tách vật thể")
            self.presenter.runtime("set_mode", "LỖI")
            self.presenter.runtime("set_output", "THẤT BẠI")

            self.presenter.set_viewport_status(
                "Không thể tách vật thể từ point cloud hiện tại.\n\n"
                f"Lỗi: {exc}"
            )


    def _handle_filter_pointcloud(self):
        try:
            result = self.pipeline.filter_pointcloud()
            self.presenter.show_filter_result(result)

        except Exception as exc:
            self.presenter.show_filter_error(exc)

    def _handle_estimate_normals(self):
        try:
            result, source_name = self.pipeline.estimate_normals()
            self.presenter.show_normal_result(result, source_name)

        except Exception as exc:
            self.presenter.show_normal_error(exc)

    def _handle_build_surface_map(self):
        try:
            self.presenter.show_surface_building()

            result = self.pipeline.build_surface_map()

            normal_cloud = None
            try:
                normal_cloud = self.pipeline.get_normal_cloud()
            except Exception:
                normal_cloud = None

            self.presenter.show_surface_result(
                result=result,
                normal_cloud=normal_cloud,
            )

        except Exception as exc:
            self.presenter.show_surface_error(exc)

    def _handle_generate_zigzag(self):
        try:
            result = self.pipeline.generate_zigzag()
            self.presenter.show_zigzag_result(result)

        except Exception as exc:
            self.presenter.show_zigzag_error(exc)

    # -------------------------------------------------
    # Export
    # -------------------------------------------------
    def _handle_export_results(self):
        try:
            export_result = self.pipeline.export_results(
                object_name="SAMPLE",
                status="OK",
                include_clean_cloud=False,
                include_normal_cloud=False,
            )

            self.presenter.show_export_result(export_result)

            try:
                measurement_result = self.pipeline.measurement_service.get_last_result()
                self.presenter.set_viewport_status(
                    "ĐÃ XUẤT KẾT QUẢ PIPELINE\n\n"
                    f"{export_result.message}\n\n"
                    f"{measurement_result.to_text()}"
                )
            except Exception:
                pass

        except Exception as exc:
            self.presenter.show_export_error(exc)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _camera_panel(self):
        right_panel = getattr(self.window, "right_panel", None)

        if right_panel is None:
            return None

        return getattr(right_panel, "camera_panel", None)

    def _get_camera_source_mode(self) -> str:
        camera_panel = self._camera_panel()

        if camera_panel is None:
            return ""

        try:
            return camera_panel.get_source_mode()
        except Exception:
            return ""

    def _get_turntable_params(self) -> tuple[float, float]:
        camera_panel = self._camera_panel()

        if camera_panel is None:
            return 10.0, 360.0

        try:
            return camera_panel.get_turntable_params()
        except Exception:
            return 10.0, 360.0

    def _parse_turntable_action(self, action: str) -> tuple[float, float]:
        """
        Parse action dạng:
            camera_turntable_scan:10.0:360.0
        """

        try:
            parts = action.split(":")

            angle_step = float(parts[1])
            total_angle = float(parts[2])

            return angle_step, total_angle

        except Exception:
            return self._get_turntable_params()

    def _normalize_camera_mode(self, mode: str) -> str:
        mode = str(mode).strip().upper()

        if mode in ("FILE", "FILE_POINTCLOUD"):
            return self.MODE_FILE

        if mode in ("HANDHELD", "HANDHELD_CAMERA"):
            return self.MODE_HANDHELD

        if mode in ("TURNTABLE", "TURNTABLE_CAMERA"):
            return self.MODE_TURNTABLE

        return self.MODE_FILE