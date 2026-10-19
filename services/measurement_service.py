from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional, Any

import numpy as np
import open3d as o3d


@dataclass
class BoundingBoxMeasurement:
    """
    Kích thước hộp bao 3D.

    Đơn vị gốc trong project đang giả định là meter.
    Nếu point cloud của bạn đang đúng scale từ depth camera:
        1.0 = 1 meter
    """

    min_x_m: float = 0.0
    min_y_m: float = 0.0
    min_z_m: float = 0.0

    max_x_m: float = 0.0
    max_y_m: float = 0.0
    max_z_m: float = 0.0

    size_x_m: float = 0.0
    size_y_m: float = 0.0
    size_z_m: float = 0.0

    center_x_m: float = 0.0
    center_y_m: float = 0.0
    center_z_m: float = 0.0

    volume_bbox_m3: float = 0.0

    @property
    def size_x_cm(self) -> float:
        return self.size_x_m * 100.0

    @property
    def size_y_cm(self) -> float:
        return self.size_y_m * 100.0

    @property
    def size_z_cm(self) -> float:
        return self.size_z_m * 100.0

    @property
    def size_x_mm(self) -> float:
        return self.size_x_m * 1000.0

    @property
    def size_y_mm(self) -> float:
        return self.size_y_m * 1000.0

    @property
    def size_z_mm(self) -> float:
        return self.size_z_m * 1000.0

    @property
    def volume_bbox_cm3(self) -> float:
        return self.volume_bbox_m3 * 1_000_000.0


@dataclass
class GeometryMeasurementResult:
    """
    Kết quả đo hình học của vật thể 3D.

    Có thể đo từ:
        - point_cloud
        - surface_mesh
        - hoặc cả hai
    """

    source_name: str = "UNKNOWN"

    point_count: int = 0
    mesh_vertex_count: int = 0
    mesh_triangle_count: int = 0

    aabb: BoundingBoxMeasurement = BoundingBoxMeasurement()
    obb: Optional[BoundingBoxMeasurement] = None

    surface_area_m2: Optional[float] = None
    surface_area_cm2: Optional[float] = None
    surface_area_mm2: Optional[float] = None

    has_point_cloud: bool = False
    has_surface_mesh: bool = False
    has_surface_area: bool = False

    unit_note: str = (
        "Đơn vị tính dựa trên scale point cloud. "
        "Nếu depth camera dùng meter thì kết quả m/cm/mm là hợp lệ."
    )

    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        if self.obb is not None:
            data["obb"] = asdict(self.obb)

        return data

    def to_text(self) -> str:
        lines = []

        lines.append("THÔNG SỐ HÌNH HỌC VẬT THỂ 3D")
        lines.append("=" * 42)
        lines.append(f"Nguồn đo: {self.source_name}")
        lines.append("")

        lines.append("1. Dữ liệu hình học")
        lines.append(f"- Số điểm point cloud: {self.point_count:,}".replace(",", "."))
        lines.append(f"- Số đỉnh mesh: {self.mesh_vertex_count:,}".replace(",", "."))
        lines.append(f"- Số mặt tam giác mesh: {self.mesh_triangle_count:,}".replace(",", "."))
        lines.append("")

        lines.append("2. Kích thước hộp bao AABB")
        lines.append(f"- Size X: {self.aabb.size_x_m:.4f} m | {self.aabb.size_x_cm:.2f} cm | {self.aabb.size_x_mm:.1f} mm")
        lines.append(f"- Size Y: {self.aabb.size_y_m:.4f} m | {self.aabb.size_y_cm:.2f} cm | {self.aabb.size_y_mm:.1f} mm")
        lines.append(f"- Size Z: {self.aabb.size_z_m:.4f} m | {self.aabb.size_z_cm:.2f} cm | {self.aabb.size_z_mm:.1f} mm")
        lines.append(f"- Thể tích hộp bao gần đúng: {self.aabb.volume_bbox_m3:.6f} m³ | {self.aabb.volume_bbox_cm3:.2f} cm³")
        lines.append("")

        if self.obb is not None:
            lines.append("3. Kích thước hộp bao định hướng OBB")
            lines.append(f"- Size X: {self.obb.size_x_m:.4f} m | {self.obb.size_x_cm:.2f} cm | {self.obb.size_x_mm:.1f} mm")
            lines.append(f"- Size Y: {self.obb.size_y_m:.4f} m | {self.obb.size_y_cm:.2f} cm | {self.obb.size_y_mm:.1f} mm")
            lines.append(f"- Size Z: {self.obb.size_z_m:.4f} m | {self.obb.size_z_cm:.2f} cm | {self.obb.size_z_mm:.1f} mm")
            lines.append(f"- Thể tích hộp bao định hướng: {self.obb.volume_bbox_m3:.6f} m³ | {self.obb.volume_bbox_cm3:.2f} cm³")
            lines.append("")

        if self.has_surface_area:
            lines.append("4. Diện tích bề mặt gần đúng")
            lines.append(f"- Diện tích: {self.surface_area_m2:.6f} m²")
            lines.append(f"- Diện tích: {self.surface_area_cm2:.2f} cm²")
            lines.append(f"- Diện tích: {self.surface_area_mm2:.2f} mm²")
            lines.append("")
        else:
            lines.append("4. Diện tích bề mặt gần đúng")
            lines.append("- Chưa có surface mesh hợp lệ nên chưa tính được diện tích bề mặt.")
            lines.append("")

        lines.append("5. Ghi chú")
        lines.append(f"- {self.unit_note}")
        lines.append("- Kích thước là kết quả gần đúng từ point cloud/mesh, không phải kích thước CAD chuẩn tuyệt đối.")
        lines.append("- File mesh/point cloud có thể chỉnh sửa trong Blender, MeshLab, CloudCompare, nhưng chưa phải CAD tham số như SolidWorks.")
        lines.append("")

        if self.message:
            lines.append("6. Trạng thái")
            lines.append(f"- {self.message}")

        return "\n".join(lines)


class MeasurementService:
    """
    Service đo thông số hình học 3D.

    Đầu vào:
        - point cloud
        - surface mesh

    Đầu ra:
        - kích thước X/Y/Z
        - bounding box
        - số điểm
        - số mặt tam giác
        - diện tích bề mặt gần đúng nếu có mesh
    """

    def __init__(self):
        self.last_result: Optional[GeometryMeasurementResult] = None

    # -------------------------------------------------
    # Main API
    # -------------------------------------------------
    def measure_geometry(
        self,
        point_cloud: Optional[o3d.geometry.PointCloud] = None,
        surface_mesh: Optional[o3d.geometry.TriangleMesh] = None,
        source_name: str = "CURRENT_OBJECT",
    ) -> GeometryMeasurementResult:
        has_cloud = self._has_valid_cloud(point_cloud)
        has_mesh = self._has_valid_mesh(surface_mesh)

        if not has_cloud and not has_mesh:
            raise RuntimeError(
                "Không có point cloud hoặc surface mesh hợp lệ để đo kích thước."
            )

        geometry_for_bbox = self._choose_geometry_for_bbox(
            point_cloud=point_cloud,
            surface_mesh=surface_mesh,
        )

        aabb = self._measure_aabb(geometry_for_bbox)
        obb = self._measure_obb_safe(geometry_for_bbox)

        point_count = len(point_cloud.points) if has_cloud else 0
        mesh_vertex_count = len(surface_mesh.vertices) if has_mesh else 0
        mesh_triangle_count = len(surface_mesh.triangles) if has_mesh else 0

        surface_area_m2 = None
        surface_area_cm2 = None
        surface_area_mm2 = None
        has_surface_area = False

        if has_mesh and mesh_triangle_count > 0:
            surface_area_m2 = self._compute_mesh_surface_area(surface_mesh)
            surface_area_cm2 = surface_area_m2 * 10_000.0
            surface_area_mm2 = surface_area_m2 * 1_000_000.0
            has_surface_area = True

        message = (
            "Đã đo thông số hình học 3D: "
            f"X={aabb.size_x_cm:.2f} cm, "
            f"Y={aabb.size_y_cm:.2f} cm, "
            f"Z={aabb.size_z_cm:.2f} cm"
        )

        if has_surface_area:
            message += f", Area={surface_area_cm2:.2f} cm²"

        result = GeometryMeasurementResult(
            source_name=source_name,
            point_count=point_count,
            mesh_vertex_count=mesh_vertex_count,
            mesh_triangle_count=mesh_triangle_count,
            aabb=aabb,
            obb=obb,
            surface_area_m2=surface_area_m2,
            surface_area_cm2=surface_area_cm2,
            surface_area_mm2=surface_area_mm2,
            has_point_cloud=has_cloud,
            has_surface_mesh=has_mesh,
            has_surface_area=has_surface_area,
            message=message,
        )

        self.last_result = result

        print(f"[MeasurementService] {message}")

        return result

    def get_last_result(self) -> GeometryMeasurementResult:
        if self.last_result is None:
            raise RuntimeError("Chưa có kết quả đo hình học.")

        return self.last_result

    def has_result(self) -> bool:
        return self.last_result is not None

    def reset(self):
        self.last_result = None

    # -------------------------------------------------
    # Bounding box
    # -------------------------------------------------
    def _measure_aabb(
        self,
        geometry,
    ) -> BoundingBoxMeasurement:
        aabb = geometry.get_axis_aligned_bounding_box()

        min_bound = np.asarray(aabb.get_min_bound(), dtype=np.float64)
        max_bound = np.asarray(aabb.get_max_bound(), dtype=np.float64)

        size = max_bound - min_bound
        center = (min_bound + max_bound) / 2.0

        return BoundingBoxMeasurement(
            min_x_m=float(min_bound[0]),
            min_y_m=float(min_bound[1]),
            min_z_m=float(min_bound[2]),
            max_x_m=float(max_bound[0]),
            max_y_m=float(max_bound[1]),
            max_z_m=float(max_bound[2]),
            size_x_m=float(abs(size[0])),
            size_y_m=float(abs(size[1])),
            size_z_m=float(abs(size[2])),
            center_x_m=float(center[0]),
            center_y_m=float(center[1]),
            center_z_m=float(center[2]),
            volume_bbox_m3=float(abs(size[0] * size[1] * size[2])),
        )

    def _measure_obb_safe(
        self,
        geometry,
    ) -> Optional[BoundingBoxMeasurement]:
        try:
            obb = geometry.get_oriented_bounding_box()

            extent = np.asarray(obb.extent, dtype=np.float64)
            center = np.asarray(obb.center, dtype=np.float64)

            # Với OBB không có min/max trục thế giới rõ như AABB,
            # dùng center ± extent/2 để ghi gần đúng.
            min_bound = center - extent / 2.0
            max_bound = center + extent / 2.0

            return BoundingBoxMeasurement(
                min_x_m=float(min_bound[0]),
                min_y_m=float(min_bound[1]),
                min_z_m=float(min_bound[2]),
                max_x_m=float(max_bound[0]),
                max_y_m=float(max_bound[1]),
                max_z_m=float(max_bound[2]),
                size_x_m=float(abs(extent[0])),
                size_y_m=float(abs(extent[1])),
                size_z_m=float(abs(extent[2])),
                center_x_m=float(center[0]),
                center_y_m=float(center[1]),
                center_z_m=float(center[2]),
                volume_bbox_m3=float(abs(extent[0] * extent[1] * extent[2])),
            )

        except Exception as exc:
            print(f"[MeasurementService] Không tính được OBB: {exc}")
            return None

    # -------------------------------------------------
    # Surface area
    # -------------------------------------------------
    def _compute_mesh_surface_area(
        self,
        mesh: o3d.geometry.TriangleMesh,
    ) -> float:
        """
        Tính diện tích mesh.

        Ưu tiên dùng Open3D get_surface_area().
        Nếu lỗi thì tự tính bằng công thức tam giác:
            area = 0.5 * || cross(b-a, c-a) ||
        """

        try:
            area = float(mesh.get_surface_area())

            if np.isfinite(area) and area >= 0:
                return area

        except Exception:
            pass

        vertices = np.asarray(mesh.vertices, dtype=np.float64)
        triangles = np.asarray(mesh.triangles, dtype=np.int64)

        if vertices.size <= 0 or triangles.size <= 0:
            return 0.0

        tri_vertices = vertices[triangles]

        a = tri_vertices[:, 0, :]
        b = tri_vertices[:, 1, :]
        c = tri_vertices[:, 2, :]

        cross = np.cross(
            b - a,
            c - a,
        )

        areas = 0.5 * np.linalg.norm(
            cross,
            axis=1,
        )

        areas = areas[np.isfinite(areas)]

        if areas.size <= 0:
            return 0.0

        return float(np.sum(areas))

    # -------------------------------------------------
    # Geometry choice
    # -------------------------------------------------
    def _choose_geometry_for_bbox(
        self,
        point_cloud: Optional[o3d.geometry.PointCloud],
        surface_mesh: Optional[o3d.geometry.TriangleMesh],
    ):
        """
        Chọn geometry để đo bbox.

        Ưu tiên mesh nếu có mesh hợp lệ,
        vì mesh là sản phẩm bề mặt cuối.
        Nếu chưa có mesh thì dùng point cloud.
        """

        if self._has_valid_mesh(surface_mesh):
            return surface_mesh

        if self._has_valid_cloud(point_cloud):
            return point_cloud

        raise RuntimeError("Không có geometry hợp lệ để đo bounding box.")

    def _has_valid_cloud(
        self,
        point_cloud: Optional[o3d.geometry.PointCloud],
    ) -> bool:
        return (
            point_cloud is not None
            and isinstance(point_cloud, o3d.geometry.PointCloud)
            and len(point_cloud.points) > 0
        )

    def _has_valid_mesh(
        self,
        surface_mesh: Optional[o3d.geometry.TriangleMesh],
    ) -> bool:
        return (
            surface_mesh is not None
            and isinstance(surface_mesh, o3d.geometry.TriangleMesh)
            and len(surface_mesh.vertices) > 0
        )