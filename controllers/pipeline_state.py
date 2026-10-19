from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PipelineStage(str, Enum):
    """
    Các trạng thái chính của pipeline Scan-to-Path.

    Mục tiêu:
        - Không để MainWindow phải tự quyết định nút nào bật/tắt.
        - RightActionPanel chỉ nhận ActionState rồi apply lên UI.
    """

    IDLE = "idle"

    # Đã có dữ liệu đầu vào
    SCAN_LOADED = "scan_loaded"

    # Đã lọc point cloud
    FILTERED = "filtered"

    # Đã tính pháp tuyến
    NORMAL_READY = "normal_ready"

    # Đã tạo surface mesh
    SURFACE_READY = "surface_ready"

    # Đã sinh đường Zigzag
    PATH_READY = "path_ready"

    # Đã xuất kết quả
    EXPORTED = "exported"

    # Chọn camera mock nhưng chưa có point cloud thật
    CAMERA_MOCK = "camera_mock"

    # Lỗi pipeline
    ERROR = "error"


@dataclass(frozen=True)
class PipelineActionState:
    """
    Trạng thái bật/tắt của từng action button trên RightActionPanel.

    Tên field bám theo action trong MainWindow:
        load_scan
        edge_ai_mask
        build_pointcloud
        filter_pointcloud
        estimate_normals
        build_surface_map
        generate_zigzag
        generate_contour
        export_results
    """

    load_scan: bool = False
    edge_ai_mask: bool = False
    build_pointcloud: bool = False
    filter_pointcloud: bool = False
    estimate_normals: bool = False
    build_surface_map: bool = False
    generate_zigzag: bool = False
    generate_contour: bool = False
    export_results: bool = False


class PipelineStateManager:
    """
    Quản lý logic stage nào thì action nào được bật.

    MainWindow chỉ cần gọi:
        action_state = manager.get_action_state(stage)
        right_panel.apply_action_state(action_state)
    """

    def __init__(self):
        self._stage_map = self._build_stage_map()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def get_action_state(
        self,
        stage: PipelineStage | str,
    ) -> PipelineActionState:
        stage = self.normalize_stage(stage)

        return self._stage_map.get(
            stage,
            self._stage_map[PipelineStage.IDLE],
        )

    def normalize_stage(
        self,
        stage: PipelineStage | str,
    ) -> PipelineStage:
        if isinstance(stage, PipelineStage):
            return stage

        text = str(stage).strip().lower()

        for item in PipelineStage:
            if text == item.value:
                return item

        return PipelineStage.IDLE

    def can_run_action(
        self,
        stage: PipelineStage | str,
        action_name: str,
    ) -> bool:
        """
        Optional helper.
        Sau này nếu muốn MainWindow chặn action sai stage thì dùng hàm này.
        """

        action_state = self.get_action_state(stage)
        action_name = str(action_name).strip()

        return bool(getattr(action_state, action_name, False))

    # -------------------------------------------------
    # Stage map
    # -------------------------------------------------
    def _build_stage_map(self) -> dict[PipelineStage, PipelineActionState]:
        return {
            # -------------------------------------------------
            # Mở app, chưa có dữ liệu
            # -------------------------------------------------
            PipelineStage.IDLE: PipelineActionState(
                load_scan=True,
                edge_ai_mask=False,
                build_pointcloud=False,
                filter_pointcloud=False,
                estimate_normals=False,
                build_surface_map=False,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),

            # -------------------------------------------------
            # Đã nạp file point cloud
            # Cho phép:
            #   - nạp lại mẫu khác
            #   - lọc nhiễu
            #   - tính normal trực tiếp nếu muốn bỏ qua lọc
            # -------------------------------------------------
            PipelineStage.SCAN_LOADED: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=False,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),

            # -------------------------------------------------
            # Đã lọc point cloud
            # Bước tiếp theo chính: tính pháp tuyến
            # -------------------------------------------------
            PipelineStage.FILTERED: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=False,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),

            # -------------------------------------------------
            # Đã có normal
            # Bước tiếp theo chính: tạo surface mesh
            # -------------------------------------------------
            PipelineStage.NORMAL_READY: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=True,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),

            # -------------------------------------------------
            # Đã có surface mesh
            # Bật Zigzag và giữ Contour để build sau
            # -------------------------------------------------
            PipelineStage.SURFACE_READY: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=True,
                generate_zigzag=True,
                generate_contour=True,
                export_results=False,
            ),

            # -------------------------------------------------
            # Đã có Zigzag path
            # Có thể xuất kết quả
            # Contour vẫn giữ để build sau
            # -------------------------------------------------
            PipelineStage.PATH_READY: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=True,
                generate_zigzag=True,
                generate_contour=True,
                export_results=True,
            ),

            # -------------------------------------------------
            # Đã export
            # Cho phép nạp mẫu mới hoặc xuất lại
            # -------------------------------------------------
            PipelineStage.EXPORTED: PipelineActionState(
                load_scan=True,
                edge_ai_mask=True,
                build_pointcloud=False,
                filter_pointcloud=True,
                estimate_normals=True,
                build_surface_map=True,
                generate_zigzag=True,
                generate_contour=True,
                export_results=True,
            ),

            # -------------------------------------------------
            # Camera mock chưa tạo point cloud thật
            # Không cho chạy pipeline 3D để tránh hiểu nhầm
            # -------------------------------------------------
            PipelineStage.CAMERA_MOCK: PipelineActionState(
                load_scan=True,
                edge_ai_mask=False,
                build_pointcloud=False,
                filter_pointcloud=False,
                estimate_normals=False,
                build_surface_map=False,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),

            # -------------------------------------------------
            # Lỗi
            # Chỉ cho nạp lại dữ liệu
            # -------------------------------------------------
            PipelineStage.ERROR: PipelineActionState(
                load_scan=True,
                edge_ai_mask=False,
                build_pointcloud=False,
                filter_pointcloud=False,
                estimate_normals=False,
                build_surface_map=False,
                generate_zigzag=False,
                generate_contour=False,
                export_results=False,
            ),
        }