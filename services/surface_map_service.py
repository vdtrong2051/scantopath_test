from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import open3d as o3d

from modules.surface_map.surface_map_builder import (
    SurfaceMapBuilder,
    SurfaceMapParams,
    SurfaceMapResult,
    get_surface_map_params_preset,
)


@dataclass
class SurfaceMapServiceState:
    source_cloud: Optional[o3d.geometry.PointCloud] = None
    surface_mesh: Optional[o3d.geometry.TriangleMesh] = None
    surface_result: Optional[SurfaceMapResult] = None
    params_used: Optional[SurfaceMapParams] = None

    is_built: bool = False
    message: str = "Chưa tạo bản đồ bề mặt 3D."


class SurfaceMapService:
    """
    Service quản lý bước tạo bản đồ bề mặt 3D.

    Vai trò:
        - Nhận point cloud đã có pháp tuyến
        - Tạo mesh / surface map 3D
        - Lưu kết quả trong RAM
        - Cung cấp mesh cho bước sinh Zigzag / Contour

    Hỗ trợ preset:
        low_ram
        demo
        detail
        holes
    """

    def __init__(self):
        self.builder = SurfaceMapBuilder()
        self.state = SurfaceMapServiceState()

    # -------------------------------------------------
    # Build surface map
    # -------------------------------------------------
    def build_surface_map(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: Optional[SurfaceMapParams] = None,
    ) -> SurfaceMapResult:
        """
        Tạo surface mesh từ point cloud có pháp tuyến.

        Nếu params=None thì dùng default trong SurfaceMapBuilder.
        """

        self._validate_point_cloud(point_cloud)

        result = self.builder.build(
            point_cloud=point_cloud,
            params=params,
        )

        self.state.source_cloud = point_cloud
        self.state.surface_mesh = result.mesh
        self.state.surface_result = result
        self.state.params_used = params
        self.state.is_built = True
        self.state.message = result.message

        return result

    def build_surface_map_with_preset(
        self,
        point_cloud: o3d.geometry.PointCloud,
        preset: str = "demo",
    ) -> SurfaceMapResult:
        """
        Tạo surface map theo preset tài nguyên.

        Preset khả dụng:
            low_ram  -> máy yếu, ít RAM
            demo     -> cân bằng, dùng để thuyết trình
            detail   -> chất lượng cao hơn, nặng hơn
            holes    -> ưu tiên giữ lỗ, dùng BPA

        Ví dụ:
            result = surface_map_service.build_surface_map_with_preset(
                normal_cloud,
                preset="demo"
            )
        """

        params = get_surface_map_params_preset(preset)

        result = self.build_surface_map(
            point_cloud=point_cloud,
            params=params,
        )

        self.state.params_used = params

        return result

    # -------------------------------------------------
    # Query state
    # -------------------------------------------------
    def has_surface_map(self) -> bool:
        return (
            self.state.is_built
            and self.state.surface_mesh is not None
            and self.state.surface_result is not None
        )

    def get_surface_mesh(self) -> o3d.geometry.TriangleMesh:
        if not self.has_surface_map():
            raise RuntimeError(
                "Chưa có bản đồ bề mặt 3D. "
                "Hãy tạo surface map trước."
            )

        return self.state.surface_mesh

    def get_result(self) -> SurfaceMapResult:
        if not self.has_surface_map():
            raise RuntimeError("Chưa có kết quả tạo bản đồ bề mặt 3D.")

        return self.state.surface_result

    def get_params_used(self) -> Optional[SurfaceMapParams]:
        return self.state.params_used

    # -------------------------------------------------
    # Save
    # -------------------------------------------------
    def save_surface_mesh(self, output_path: str | Path) -> Path:
        if not self.has_surface_map():
            raise RuntimeError("Chưa có surface mesh để lưu.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        ok = o3d.io.write_triangle_mesh(
            str(path),
            self.state.surface_mesh,
        )

        if not ok:
            raise RuntimeError(f"Không thể lưu surface mesh: {path}")

        return path

    # -------------------------------------------------
    # Reset
    # -------------------------------------------------
    def reset(self):
        self.state = SurfaceMapServiceState(
            is_built=False,
            message="Đã xóa bản đồ bề mặt 3D hiện tại.",
        )

    # -------------------------------------------------
    # Internal validation
    # -------------------------------------------------
    def _validate_point_cloud(self, point_cloud: o3d.geometry.PointCloud):
        if point_cloud is None:
            raise ValueError("Point cloud đầu vào bị rỗng.")

        if not isinstance(point_cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "SurfaceMapService cần đầu vào là open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(point_cloud)}"
            )

        if len(point_cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm 3D hợp lệ.")

        if not point_cloud.has_normals():
            raise ValueError(
                "Point cloud chưa có pháp tuyến. "
                "Hãy bấm 'TÍNH PHÁP TUYẾN BỀ MẶT' trước khi tạo surface map."
            )