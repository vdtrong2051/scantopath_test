from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import open3d as o3d

from modules.path_generation.zigzag_generator import (
    ZigzagGenerator,
    ZigzagParams,
    ZigzagPathResult,
)


@dataclass
class PathGenerationServiceState:
    source_mesh: Optional[o3d.geometry.TriangleMesh] = None

    zigzag_result: Optional[ZigzagPathResult] = None
    params_used: Optional[ZigzagParams] = None

    is_zigzag_generated: bool = False

    message: str = "Chưa sinh đường dẫn."


class PathGenerationService:
    """
    Service quản lý sinh đường dẫn bề mặt.

    Bản hiện tại:
        - Sinh Zigzag từ surface mesh.
        - Không sinh trực tiếp từ point cloud nữa.
        - Đầu vào bắt buộc là open3d.geometry.TriangleMesh.
    """

    def __init__(self):
        self.zigzag_generator = ZigzagGenerator()
        self.state = PathGenerationServiceState()

    # -------------------------------------------------
    # Zigzag
    # -------------------------------------------------
    def generate_zigzag(
        self,
        surface_mesh: o3d.geometry.TriangleMesh,
        params: Optional[ZigzagParams] = None,
    ) -> ZigzagPathResult:
        """
        Sinh đường Zigzag từ surface mesh.

        Args:
            surface_mesh:
                Mesh bề mặt đã được tạo từ SurfaceMapService.
            params:
                Thông số sinh Zigzag. Nếu None thì dùng mặc định trong ZigzagGenerator.

        Returns:
            ZigzagPathResult
        """

        self._validate_surface_mesh(surface_mesh)

        result = self.zigzag_generator.generate_from_mesh(
            mesh=surface_mesh,
            params=params,
        )

        self.state.source_mesh = result.source_mesh
        self.state.zigzag_result = result
        self.state.params_used = params
        self.state.is_zigzag_generated = True
        self.state.message = result.message

        return result

    def generate_zigzag_from_mesh(
        self,
        surface_mesh: o3d.geometry.TriangleMesh,
        params: Optional[ZigzagParams] = None,
    ) -> ZigzagPathResult:
        """
        Alias rõ nghĩa hơn cho generate_zigzag().
        """

        return self.generate_zigzag(
            surface_mesh=surface_mesh,
            params=params,
        )

    def has_zigzag(self) -> bool:
        return (
            self.state.is_zigzag_generated
            and self.state.zigzag_result is not None
        )

    def get_zigzag_result(self) -> ZigzagPathResult:
        if not self.has_zigzag():
            raise RuntimeError(
                "Chưa có đường Zigzag. "
                "Hãy tạo bản đồ bề mặt 3D rồi sinh Zigzag trước."
            )

        return self.state.zigzag_result

    def get_source_mesh(self) -> o3d.geometry.TriangleMesh:
        if self.state.source_mesh is None:
            raise RuntimeError(
                "Chưa có surface mesh nguồn cho bước sinh đường dẫn."
            )

        return self.state.source_mesh
    
    def get_params_used(self) -> Optional[ZigzagParams]:
        return self.state.params_used

    def save_zigzag_csv(self, output_path: str | Path) -> Path:
        """
        Xuất đường Zigzag ra CSV.

        CSV gồm:
            segment_id, point_id, x, y, z, nx, ny, nz
        """

        result = self.get_zigzag_result()

        return self.zigzag_generator.export_csv(
            result=result,
            output_path=output_path,
        )

    # -------------------------------------------------
    # Reset
    # -------------------------------------------------
    def reset(self):
        self.state = PathGenerationServiceState(
            message="Đã xóa đường dẫn hiện tại.",
        )

    # -------------------------------------------------
    # Internal validation
    # -------------------------------------------------
    def _validate_surface_mesh(
        self,
        surface_mesh: o3d.geometry.TriangleMesh,
    ):
        if surface_mesh is None:
            raise RuntimeError(
                "Chưa có surface mesh để sinh Zigzag. "
                "Hãy bấm 'TẠO BẢN ĐỒ BỀ MẶT 3D' trước."
            )

        if not isinstance(surface_mesh, o3d.geometry.TriangleMesh):
            raise TypeError(
                "Zigzag mesh-based cần đầu vào là TriangleMesh, "
                f"nhưng nhận được: {type(surface_mesh)}.\n\n"
                "Kiểm tra lại main_window.py: "
                "không được truyền normal_cloud hoặc point_cloud vào generate_zigzag(). "
                "Phải truyền surface_map_service.get_surface_mesh()."
            )

        if len(surface_mesh.vertices) <= 0:
            raise ValueError(
                "Surface mesh không có vertex. "
                "Hãy tạo lại bản đồ bề mặt 3D."
            )

        if len(surface_mesh.triangles) <= 0:
            raise ValueError(
                "Surface mesh không có triangle. "
                "Hãy kiểm tra bước tạo surface map."
            )