from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class NormalEstimationParams:
    """
    Thông số tính pháp tuyến bề mặt.

    Ghi chú tài nguyên / chất lượng:

        LOW_RAM:
            adaptive_radius_ratio = 0.020
            max_nn = 30
            consistent_tangent_plane_k = 20

        DEMO_STABLE:
            adaptive_radius_ratio = 0.025
            max_nn = 50
            consistent_tangent_plane_k = 50

        DETAIL_HIGH:
            adaptive_radius_ratio = 0.018
            max_nn = 80
            consistent_tangent_plane_k = 80

    Khuyến nghị hiện tại:
        Dùng DEMO_STABLE để surface reconstruction ổn hơn.
    """

    search_radius: float = 0.0
    adaptive_radius_ratio: float = 0.025
    max_nn: int = 50

    orient_normals: bool = True
    consistent_tangent_plane_k: int = 50

    normalize_normals: bool = True


@dataclass
class NormalEstimationResult:
    input_cloud: o3d.geometry.PointCloud
    output_cloud: o3d.geometry.PointCloud

    point_count: int
    normal_count: int
    has_normals: bool

    search_radius: float
    max_nn: int

    average_normal: np.ndarray
    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    message: str


def get_normal_estimation_params_preset(mode: str = "demo") -> NormalEstimationParams:
    """
    Preset nhanh để sau này đổi chất lượng normal.

    mode:
        "low_ram"
        "demo"
        "detail"
    """

    mode = mode.lower().strip()

    if mode in ("low", "low_ram", "safe"):
        return NormalEstimationParams(
            adaptive_radius_ratio=0.020,
            max_nn=30,
            orient_normals=True,
            consistent_tangent_plane_k=20,
        )

    if mode in ("detail", "high", "quality"):
        return NormalEstimationParams(
            adaptive_radius_ratio=0.018,
            max_nn=80,
            orient_normals=True,
            consistent_tangent_plane_k=80,
        )

    return NormalEstimationParams(
        adaptive_radius_ratio=0.025,
        max_nn=50,
        orient_normals=True,
        consistent_tangent_plane_k=50,
    )


class NormalEstimator:
    """
    Module ước lượng pháp tuyến bề mặt cho point cloud.

    Vai trò:
        - Nhận point cloud sạch.
        - Lọc điểm lỗi NaN/Inf.
        - Ước lượng normal vector tại từng điểm.
        - Orient normal tương đối nhất quán.
        - Trả point cloud có normal cho bước Surface Map.

    Ghi chú:
        Normal tốt là điều kiện quan trọng để Poisson/BPA dựng mesh ổn.
    """

    def __init__(self, params: Optional[NormalEstimationParams] = None):
        self.params = params or NormalEstimationParams()

    def estimate(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: Optional[NormalEstimationParams] = None,
    ) -> NormalEstimationResult:
        params = params or self.params

        self._validate_point_cloud(point_cloud)

        cloud = o3d.geometry.PointCloud(point_cloud)
        cloud = self._remove_invalid_points(cloud)

        self._validate_point_cloud(cloud)

        points = np.asarray(cloud.points, dtype=np.float64)

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        size = bounds_max - bounds_min
        center = (bounds_min + bounds_max) / 2.0

        max_size = float(np.max(size))
        if max_size <= 0:
            max_size = 1.0

        search_radius = params.search_radius

        if search_radius <= 0:
            search_radius = max_size * params.adaptive_radius_ratio

        if search_radius <= 0:
            search_radius = 1.0

        cloud.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=search_radius,
                max_nn=params.max_nn,
            )
        )

        if not cloud.has_normals():
            raise ValueError("Không thể tính pháp tuyến cho point cloud.")

        if params.orient_normals:
            try:
                cloud.orient_normals_consistent_tangent_plane(
                    params.consistent_tangent_plane_k
                )
            except Exception:
                # Nếu point cloud quá thưa/nhiễu thì bước orient có thể fail.
                # Khi đó vẫn giữ normal đã estimate để không làm vỡ pipeline.
                pass

        if params.normalize_normals:
            try:
                cloud.normalize_normals()
            except Exception:
                pass

        normals = np.asarray(cloud.normals, dtype=np.float64)

        if normals.size == 0:
            raise ValueError("Không thể tính pháp tuyến cho point cloud.")

        if len(normals) != len(cloud.points):
            raise ValueError(
                "Số lượng vector pháp tuyến không khớp với số lượng điểm."
            )

        normal_valid_mask = np.isfinite(normals).all(axis=1)

        if not normal_valid_mask.all():
            points = np.asarray(cloud.points, dtype=np.float64)
            colors = np.asarray(cloud.colors) if cloud.has_colors() else None

            points = points[normal_valid_mask]
            normals = normals[normal_valid_mask]

            cleaned = o3d.geometry.PointCloud()
            cleaned.points = o3d.utility.Vector3dVector(points)
            cleaned.normals = o3d.utility.Vector3dVector(normals)

            if colors is not None and len(colors) == len(normal_valid_mask):
                cleaned.colors = o3d.utility.Vector3dVector(
                    colors[normal_valid_mask]
                )

            cloud = cleaned

        normals = np.asarray(cloud.normals, dtype=np.float64)
        normals = self._normalize_vectors(normals)
        cloud.normals = o3d.utility.Vector3dVector(normals)

        average_normal = normals.mean(axis=0)

        avg_norm = np.linalg.norm(average_normal)
        if avg_norm > 0:
            average_normal = average_normal / avg_norm

        point_count = len(cloud.points)
        normal_count = len(cloud.normals)

        return NormalEstimationResult(
            input_cloud=point_cloud,
            output_cloud=cloud,
            point_count=point_count,
            normal_count=normal_count,
            has_normals=cloud.has_normals(),
            search_radius=search_radius,
            max_nn=params.max_nn,
            average_normal=average_normal,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            message=(
                f"Đã tính pháp tuyến bề mặt cho {point_count} điểm "
                f"với bán kính tìm kiếm {search_radius:.4f}, "
                f"max_nn={params.max_nn}."
            ),
        )

    def _validate_point_cloud(self, point_cloud: o3d.geometry.PointCloud):
        if point_cloud is None:
            raise ValueError("Point cloud đầu vào bị rỗng.")

        if not isinstance(point_cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "NormalEstimator cần đầu vào là open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(point_cloud)}"
            )

        if len(point_cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm 3D hợp lệ.")

    def _remove_invalid_points(
        self,
        cloud: o3d.geometry.PointCloud,
    ) -> o3d.geometry.PointCloud:
        points = np.asarray(cloud.points, dtype=np.float64)

        if len(points) == 0:
            return cloud

        valid_mask = np.isfinite(points).all(axis=1)

        clean = o3d.geometry.PointCloud()
        clean.points = o3d.utility.Vector3dVector(points[valid_mask])

        if cloud.has_colors():
            colors = np.asarray(cloud.colors)

            if len(colors) == len(valid_mask):
                clean.colors = o3d.utility.Vector3dVector(colors[valid_mask])

        if cloud.has_normals():
            normals = np.asarray(cloud.normals)

            if len(normals) == len(valid_mask):
                clean.normals = o3d.utility.Vector3dVector(normals[valid_mask])

        return clean

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        if len(vectors) == 0:
            return vectors

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return vectors / norms