from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from services.scan_service import ScanService
from services.pointcloud_service import PointCloudService
from services.normal_service import NormalService
from services.surface_map_service import SurfaceMapService
from services.path_generation_service import PathGenerationService
from services.export_service import ExportService, ExportResult
from services.camera_service import CameraService
from services.object_extraction_service import ObjectExtractionService
from services.measurement_service import MeasurementService

from controllers.pipeline_state import (
    PipelineStage,
    PipelineStateManager,
    PipelineActionState,
)


@dataclass
class CameraMockResult:
    """
    Kết quả mock camera trả về cho MainWindow hiển thị.

    Controller không hiển thị QMessageBox,
    không cập nhật viewport, chỉ trả dữ liệu/message.
    """

    mode: str
    message: str

    frame_count: int = 0
    step_count: int = 0
    angle_step_deg: float = 0.0


class PipelineController:
    """
    Controller điều phối pipeline Scan-to-Path.

    Vai trò:
        - Giữ toàn bộ service xử lý dữ liệu.
        - Quản lý stage pipeline.
        - Reset service theo đúng luồng.
        - Gọi xử lý thật: load, filter, normal, surface, zigzag, export.
        - Chạy mock camera 2 mode.

    Không làm:
        - Không gọi QMessageBox.
        - Không cập nhật viewport.
        - Không cập nhật top bar/runtime bar.
        - Không đụng trực tiếp UI widget.

    MainWindow chỉ nên:
        - Nhận action từ RightActionPanel.
        - Gọi hàm tương ứng trong PipelineController.
        - Lấy result để hiển thị lên UI.
    """

    INPUT_IDLE = "IDLE"
    INPUT_FILE = "FILE"
    INPUT_HANDHELD = "HANDHELD"
    INPUT_TURNTABLE = "TURNTABLE"

    def __init__(
        self,
        export_root: str | Path = "data/exports",
        project_code: str = "PJ1",
    ):
        # -------------------------------------------------
        # Core services
        # -------------------------------------------------
        self.scan_service = ScanService()
        self.pointcloud_service = PointCloudService()
        self.normal_service = NormalService()
        self.surface_map_service = SurfaceMapService()
        self.path_generation_service = PathGenerationService()

        self.export_service = ExportService(
            export_root=export_root,
            project_code=project_code,
        )

        self.camera_service = CameraService()
        self.object_extraction_service = ObjectExtractionService()
        self.measurement_service = MeasurementService()

        # -------------------------------------------------
        # Pipeline state
        # -------------------------------------------------
        self.state_manager = PipelineStateManager()
        self.current_stage = PipelineStage.IDLE

        self.current_input_mode = self.INPUT_IDLE
        self.has_exported_result = False

    # -------------------------------------------------
    # Stage / action state
    # -------------------------------------------------
    def get_current_stage(self) -> PipelineStage:
        return self.current_stage

    def set_stage(self, stage: PipelineStage | str) -> PipelineStage:
        self.current_stage = self.state_manager.normalize_stage(stage)
        return self.current_stage

    def get_action_state(self) -> PipelineActionState:
        return self.state_manager.get_action_state(self.current_stage)

    def can_run_action(self, action_name: str) -> bool:
        return self.state_manager.can_run_action(
            self.current_stage,
            action_name,
        )

    def refresh_stage(self) -> PipelineStage:
        """
        Tự suy ra stage hiện tại từ trạng thái các service.

        Đây là điểm quan trọng để MainWindow không phải tự gắn stage
        thủ công trong từng hàm handler.
        """

        # Camera mock hiện chưa tạo point cloud thật.
        # Nếu đang ở mode camera mock thì khóa pipeline 3D.
        if self.current_input_mode in (
            self.INPUT_HANDHELD,
            self.INPUT_TURNTABLE,
        ):
            if not self.camera_service.has_point_cloud():
                return self.set_stage(PipelineStage.CAMERA_MOCK)

        if self.path_generation_service.has_zigzag():
            if self.has_exported_result:
                return self.set_stage(PipelineStage.EXPORTED)

            return self.set_stage(PipelineStage.PATH_READY)

        # Nếu mất path thì export cũ không còn hợp lệ.
        self.has_exported_result = False

        if self.surface_map_service.has_surface_map():
            return self.set_stage(PipelineStage.SURFACE_READY)

        if self.normal_service.has_normals():
            return self.set_stage(PipelineStage.NORMAL_READY)

        if self.object_extraction_service.has_object_cloud():
            return self.set_stage(PipelineStage.FILTERED)

        if self.pointcloud_service.has_clean_cloud():
            return self.set_stage(PipelineStage.FILTERED)

        if self.scan_service.has_scan():
            return self.set_stage(PipelineStage.SCAN_LOADED)

        return self.set_stage(PipelineStage.IDLE)

    # -------------------------------------------------
    # Reset helpers
    # -------------------------------------------------
    def reset_all(self):
        """
        Reset toàn bộ pipeline.

        Dùng khi muốn quay về trạng thái ban đầu.
        """

        self._safe_reset(self.scan_service)
        self._safe_reset(self.pointcloud_service)
        self._safe_reset(self.normal_service)
        self._safe_reset(self.surface_map_service)
        self._safe_reset(self.path_generation_service)
        self._safe_reset(self.camera_service)
        self._safe_reset(self.object_extraction_service)
        self._safe_reset(self.measurement_service)

        self.current_input_mode = self.INPUT_IDLE
        self.has_exported_result = False

        self.set_stage(PipelineStage.IDLE)

    def reset_after_new_scan(self):
        """
        Khi nạp nguồn dữ liệu mới:
            - giữ scan mới sẽ được load lại bởi ScanService
            - xóa toàn bộ kết quả xử lý phía sau
        """

        self._safe_reset(self.pointcloud_service)
        self._safe_reset(self.object_extraction_service)
        self._safe_reset(self.normal_service)
        self._safe_reset(self.surface_map_service)
        self._safe_reset(self.path_generation_service)
        self._safe_reset(self.measurement_service)

        self.has_exported_result = False

    def reset_after_filter(self):
        """
        Sau khi lọc point cloud:
            - giữ clean point cloud
            - xóa normal/surface/path cũ
        """

        self._safe_reset(self.object_extraction_service)
        self._safe_reset(self.normal_service)
        self._safe_reset(self.surface_map_service)
        self._safe_reset(self.path_generation_service)
        self._safe_reset(self.measurement_service)

        self.has_exported_result = False

    def reset_after_normals(self):
        """
        Sau khi tính normal:
            - giữ normal cloud
            - xóa surface/path cũ
        """

        self._safe_reset(self.surface_map_service)
        self._safe_reset(self.path_generation_service)
        self._safe_reset(self.measurement_service)

        self.has_exported_result = False

    def reset_after_surface(self):
        """
        Sau khi tạo surface mesh:
            - giữ surface mesh
            - xóa path cũ
        """

        self._safe_reset(self.path_generation_service)
        self._safe_reset(self.measurement_service)

        self.has_exported_result = False

    # -------------------------------------------------
    # Input: file point cloud
    # -------------------------------------------------
    def load_scan_from_file(self, file_path: str | Path):
        """
        Nạp point cloud từ file.

        Returns:
            ScanImportResult / ScanService result
        """

        if not file_path:
            raise ValueError("Đường dẫn file quét 3D không hợp lệ.")

        self.reset_after_new_scan()

        result = self.scan_service.load_scan(str(file_path))

        self.current_input_mode = self.INPUT_FILE
        self.has_exported_result = False

        self.refresh_stage()

        return result

    # -------------------------------------------------
    # Input: camera mock
    # -------------------------------------------------
    def run_handheld_camera_mock(self) -> CameraMockResult:
        """
        Mock chế độ camera cầm tay.

        Hiện tại:
            - Chạy thử workflow camera service.
            - Chưa tạo point cloud thật.
            - Pipeline 3D bị khóa sau khi chọn mode này.
        """

        self.reset_after_new_scan()

        self.camera_service.start_handheld_scan()
        frame = self.camera_service.capture_handheld_frame()
        result = self.camera_service.stop_handheld_scan()

        self.current_input_mode = self.INPUT_HANDHELD
        self.has_exported_result = False

        self.refresh_stage()

        return CameraMockResult(
            mode=self.INPUT_HANDHELD,
            frame_count=result.frame_count,
            message=(
                f"{frame.message}\n"
                f"Số frame mock: {result.frame_count}\n"
                "Chưa tạo point cloud thật từ camera."
            ),
        )

    def run_turntable_camera_mock(
        self,
        angle_step_deg: float = 10.0,
        total_angle_deg: float = 360.0,
    ) -> CameraMockResult:
        """
        Mock chế độ bàn xoay Stop-and-Go.

        Hiện tại:
            - Chạy thử workflow bàn xoay.
            - Chưa nối UART Arduino thật.
            - Chưa tạo point cloud thật.
            - Pipeline 3D bị khóa sau khi chọn mode này.
        """

        self.reset_after_new_scan()

        self.camera_service.start_turntable_scan(
            angle_step_deg=angle_step_deg,
            total_angle_deg=total_angle_deg,
        )

        step = self.camera_service.capture_turntable_step()
        result = self.camera_service.stop_turntable_scan()

        self.current_input_mode = self.INPUT_TURNTABLE
        self.has_exported_result = False

        self.refresh_stage()

        return CameraMockResult(
            mode=self.INPUT_TURNTABLE,
            step_count=result.step_count,
            angle_step_deg=result.angle_step_deg,
            message=(
                f"{step.message}\n"
                f"Số bước mock: {result.step_count}\n"
                f"Bước góc: {result.angle_step_deg:.1f}°\n"
                "Chưa nối UART Arduino thật.\n"
                "Chưa tạo point cloud thật từ camera."
            ),
        )

    # -------------------------------------------------
    # Point cloud processing
    # -------------------------------------------------
    def filter_pointcloud(self):
        """
        Lọc nhiễu point cloud.

        Ưu tiên nguồn lọc:
            1. clean cloud nếu đã có và muốn lọc lại
            2. object cloud nếu đã tách vật thể
            3. raw cloud nếu chỉ mới nạp/quét dữ liệu

        Như vậy:
            NẠP/QUÉT → TÁCH VẬT THỂ → LỌC NHIỄU
        sẽ lọc trên object cloud, không quay lại raw cloud.
        """

        source_cloud, source_name = self._get_pointcloud_source_for_filter()

        # Xóa các kết quả phía sau trước khi lọc lại.
        # Lưu ý:
        # object_extraction_service có thể bị reset ở đây cũng được,
        # vì source_cloud đã lấy ra biến riêng rồi.
        # Sau lọc, clean_cloud sẽ là dữ liệu chính.
        self.reset_after_filter()

        result = self.pointcloud_service.filter_point_cloud(source_cloud)

        self.refresh_stage()

        return result
    
    def _get_pointcloud_source_for_filter(self):
        """
        Chọn point cloud nguồn cho bước lọc nhiễu.

        Thứ tự ưu tiên:
            1. clean cloud: nếu người dùng bấm lọc lại
            2. object cloud: nếu đã tách vật thể bằng Edge AI/depth geometry
            3. raw cloud: nếu chưa tách vật thể
        """

        if self.pointcloud_service.has_clean_cloud():
            return (
                self.pointcloud_service.get_clean_point_cloud(),
                "POINT CLOUD ĐÃ LỌC",
            )

        if self.object_extraction_service.has_object_cloud():
            return (
                self.object_extraction_service.get_object_cloud(),
                "POINT CLOUD VẬT THỂ",
            )

        if self.scan_service.has_scan():
            return (
                self.scan_service.get_current_point_cloud(),
                "POINT CLOUD THÔ",
            )

        raise RuntimeError(
            "Chưa có dữ liệu quét. "
            "Hãy nạp/quét mẫu 3D trước khi lọc nhiễu point cloud."
        )
    
    def extract_nearest_object(self):
        """
        Tách vật thể gần camera nhất từ point cloud hiện tại.

        Nút UI:
            TÁCH VẬT THỂ BẰNG EDGE AI

        Giai đoạn hiện tại:
            Chưa dùng AI model thật.
            Dùng depth + geometry:
                - ưu tiên vật thể gần camera
                - loại mặt phẳng lớn
                - DBSCAN giữ cụm vật thể gần nhất
        """

        if not self.scan_service.has_scan():
            raise RuntimeError(
                "Chưa có dữ liệu quét. "
                "Hãy nạp/quét mẫu 3D trước khi tách vật thể."
            )

        raw_cloud = self.scan_service.get_current_point_cloud()

        # Tách object từ point cloud thô hiện tại.
        result = self.object_extraction_service.extract_nearest_object(
            source_cloud=raw_cloud,
        )

        # Sau khi tách vật thể, các kết quả sau đó không còn hợp lệ.
        self._safe_reset(self.normal_service)
        self._safe_reset(self.surface_map_service)
        self._safe_reset(self.path_generation_service)

        self.has_exported_result = False

        self.refresh_stage()

        return result

    def estimate_normals(self):
        """
        Tính pháp tuyến.

        Ưu tiên:
            clean point cloud nếu đã lọc
            nếu chưa lọc thì dùng point cloud thô
        """

        if self.object_extraction_service.has_object_cloud():
            source_cloud = self.object_extraction_service.get_object_cloud()
            source_name = "POINT CLOUD VẬT THỂ"

        elif self.pointcloud_service.has_clean_cloud():
            source_cloud = self.pointcloud_service.get_clean_point_cloud()
            source_name = "POINT CLOUD SẠCH"

        elif self.object_extraction_service.has_object_cloud():
            source_cloud = self.object_extraction_service.get_object_cloud()
            source_name = "POINT CLOUD VẬT THỂ"

        elif self.scan_service.has_scan():
            source_cloud = self.scan_service.get_current_point_cloud()
            source_name = "POINT CLOUD THÔ"

        else:
            raise RuntimeError(
                "Chưa có dữ liệu. "
                "Hãy nạp file quét 3D trước khi tính pháp tuyến."
            )

        # Xóa surface/path cũ trước khi tính lại normal
        self.reset_after_normals()

        result = self.normal_service.estimate_normals(source_cloud)

        self.refresh_stage()

        return result, source_name

    def build_surface_map(self):
        """
        Tạo surface mesh từ point cloud đã có normal.
        """

        if not self.normal_service.has_normals():
            raise RuntimeError(
                "Chưa có pháp tuyến. "
                "Hãy tính pháp tuyến bề mặt trước khi tạo bản đồ bề mặt 3D."
            )

        normal_cloud = self.normal_service.get_normal_cloud()

        # Xóa path cũ trước khi tạo lại surface
        self.reset_after_surface()

        result = self.surface_map_service.build_surface_map(normal_cloud)

        self.refresh_stage()

        return result

    def generate_zigzag(self):
        """
        Sinh đường Zigzag từ surface mesh.
        """

        if not self.surface_map_service.has_surface_map():
            raise RuntimeError(
                "Chưa có bản đồ bề mặt 3D. "
                "Hãy tạo surface mesh trước khi sinh đường Zigzag."
            )

        surface_mesh = self.surface_map_service.get_surface_mesh()

        result = self.path_generation_service.generate_zigzag(
            surface_mesh=surface_mesh,
        )

        self.has_exported_result = False

        self.refresh_stage()

        return result
    
    def measure_current_geometry(self):
        """
        Đo thông số hình học hiện tại.

        Ưu tiên:
            1. surface mesh nếu đã tạo surface
            2. clean/object cloud nếu có
            3. raw cloud nếu mới nạp/quét
        """

        point_cloud = None
        surface_mesh = None
        source_name = "UNKNOWN"

        if self.surface_map_service.has_surface_map():
            surface_mesh = self.surface_map_service.get_surface_mesh()
            source_name = "SURFACE MESH"

            if self.pointcloud_service.has_clean_cloud():
                point_cloud = self.pointcloud_service.get_clean_point_cloud()
            elif self.object_extraction_service.has_object_cloud():
                point_cloud = self.object_extraction_service.get_object_cloud()
            elif self.scan_service.has_scan():
                point_cloud = self.scan_service.get_current_point_cloud()

        elif self.pointcloud_service.has_clean_cloud():
            point_cloud = self.pointcloud_service.get_clean_point_cloud()
            source_name = "POINT CLOUD SẠCH"

        elif self.object_extraction_service.has_object_cloud():
            point_cloud = self.object_extraction_service.get_object_cloud()
            source_name = "POINT CLOUD VẬT THỂ"

        elif self.scan_service.has_scan():
            point_cloud = self.scan_service.get_current_point_cloud()
            source_name = "POINT CLOUD THÔ"

        else:
            raise RuntimeError(
                "Chưa có dữ liệu 3D để đo thông số hình học."
            )

        return self.measurement_service.measure_geometry(
            point_cloud=point_cloud,
            surface_mesh=surface_mesh,
            source_name=source_name,
        )

    # -------------------------------------------------
    # Export
    # -------------------------------------------------
    def export_results(
        self,
        object_name: str = "SAMPLE",
        status: str = "OK",
        include_clean_cloud: bool = False,
        include_normal_cloud: bool = False,
    ) -> ExportResult:
        """
        Xuất kết quả pipeline hiện tại ra data/exports.

        Yêu cầu:
            - đã có surface mesh
            - đã có Zigzag path
        """

        if not self.surface_map_service.has_surface_map():
            raise RuntimeError(
                "Chưa có bản đồ bề mặt 3D để xuất."
            )

        if not self.path_generation_service.has_zigzag():
            raise RuntimeError(
                "Chưa có đường Zigzag để xuất."
            )

        surface_result = self.surface_map_service.get_result()
        zigzag_result = self.path_generation_service.get_zigzag_result()

        clean_cloud = None
        normal_cloud = None

        if self.pointcloud_service.has_clean_cloud():
            clean_cloud = self.pointcloud_service.get_clean_point_cloud()

        if self.normal_service.has_normals():
            normal_cloud = self.normal_service.get_normal_cloud()
        elif self.object_extraction_service.has_object_cloud():
            clean_cloud = self.object_extraction_service.get_object_cloud()

        input_mode = self.current_input_mode

        if input_mode == self.INPUT_IDLE:
            input_mode = self.INPUT_FILE

        measurement_result = self.measure_current_geometry()

        export_result = self.export_service.export_pipeline_result(
            surface_result=surface_result,
            zigzag_result=zigzag_result,
            clean_cloud=clean_cloud,
            normal_cloud=normal_cloud,
            input_mode=input_mode,
            object_name=object_name,
            status=status,
            include_clean_cloud=include_clean_cloud,
            include_normal_cloud=include_normal_cloud,
            measurement_result=measurement_result,
        )

        self.has_exported_result = True

        self.refresh_stage()

        return export_result

    # -------------------------------------------------
    # Data access helpers for MainWindow
    # -------------------------------------------------
    def has_scan(self) -> bool:
        return self.scan_service.has_scan()

    def has_clean_cloud(self) -> bool:
        return (
            self.pointcloud_service.has_clean_cloud()
            or self.object_extraction_service.has_object_cloud()
        )

    def has_normals(self) -> bool:
        return self.normal_service.has_normals()

    def has_surface_map(self) -> bool:
        return self.surface_map_service.has_surface_map()

    def has_zigzag(self) -> bool:
        return self.path_generation_service.has_zigzag()

    def get_current_point_cloud(self):
        return self.scan_service.get_current_point_cloud()

    def get_clean_point_cloud(self):
        if self.pointcloud_service.has_clean_cloud():
            return self.pointcloud_service.get_clean_point_cloud()

        if self.object_extraction_service.has_object_cloud():
            return self.object_extraction_service.get_object_cloud()

        return self.pointcloud_service.get_clean_point_cloud()
    
    def get_object_cloud(self):
        return self.object_extraction_service.get_object_cloud()

    def get_normal_cloud(self):
        return self.normal_service.get_normal_cloud()

    def get_surface_mesh(self):
        return self.surface_map_service.get_surface_mesh()

    def get_surface_result(self):
        return self.surface_map_service.get_result()

    def get_zigzag_result(self):
        return self.path_generation_service.get_zigzag_result()

    # -------------------------------------------------
    # Internal
    # -------------------------------------------------
    def _safe_reset(self, service):
        """
        Gọi reset() nếu service có hỗ trợ.
        """

        reset = getattr(service, "reset", None)

        if callable(reset):
            reset()