from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class PointCloudFilterParams:
    voxel_size: float = 0.0
    adaptive_voxel_ratio: float = 0.01

    use_voxel_downsample: bool = True

    use_statistical_outlier: bool = True
    sor_nb_neighbors: int = 30
    sor_std_ratio: float = 2.0

    use_radius_outlier: bool = False
    ror_nb_points: int = 16
    ror_radius: float = 0.03


@dataclass
class PointCloudFilterResult:
    input_cloud: o3d.geometry.PointCloud
    output_cloud: o3d.geometry.PointCloud

    input_point_count: int
    output_point_count: int
    removed_point_count: int
    reduction_percent: float

    has_colors: bool
    has_normals: bool

    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    message: str


class PointCloudFilter:
    """
    Bộ lọc point cloud cho pipeline Scan-to-Path.

    Chức năng:
        - Giảm mật độ điểm bằng Voxel Downsample
        - Lọc điểm ngoại lai bằng Statistical Outlier Removal
        - Tùy chọn lọc điểm lẻ bằng Radius Outlier Removal

    Không làm:
        - Không tái tạo surface
        - Không tính normal
        - Không sinh path
    """

    def __init__(self, params: Optional[PointCloudFilterParams] = None):
        self.params = params or PointCloudFilterParams()

    def filter(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: Optional[PointCloudFilterParams] = None,
    ) -> PointCloudFilterResult:
        params = params or self.params

        self._validate_point_cloud(point_cloud)

        input_count = len(point_cloud.points)

        # Copy để không sửa trực tiếp cloud gốc
        filtered = o3d.geometry.PointCloud(point_cloud)

        if params.use_voxel_downsample:
            voxel_size = params.voxel_size

            if voxel_size <= 0:
                points_np = np.asarray(filtered.points)
                bounds_min = points_np.min(axis=0)
                bounds_max = points_np.max(axis=0)
                bbox_size = bounds_max - bounds_min
                max_size = float(np.max(bbox_size))

                voxel_size = max_size * params.adaptive_voxel_ratio

            if voxel_size > 0:
                filtered = filtered.voxel_down_sample(
                    voxel_size=voxel_size
                )

        if params.use_statistical_outlier and len(filtered.points) > params.sor_nb_neighbors:
            filtered, _ = filtered.remove_statistical_outlier(
                nb_neighbors=params.sor_nb_neighbors,
                std_ratio=params.sor_std_ratio,
            )

        if params.use_radius_outlier and len(filtered.points) > params.ror_nb_points:
            filtered, _ = filtered.remove_radius_outlier(
                nb_points=params.ror_nb_points,
                radius=params.ror_radius,
            )

        output_count = len(filtered.points)

        if output_count <= 0:
            raise ValueError(
                "Point cloud sau khi lọc không còn điểm hợp lệ. "
                "Hãy giảm mức lọc hoặc kiểm tra lại dữ liệu quét."
            )

        return self._build_result(
            input_cloud=point_cloud,
            output_cloud=filtered,
            input_count=input_count,
            output_count=output_count,
        )

    def _validate_point_cloud(self, point_cloud: o3d.geometry.PointCloud):
        if point_cloud is None:
            raise ValueError("Point cloud đầu vào bị rỗng.")

        if len(point_cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm 3D hợp lệ.")

    def _build_result(
        self,
        input_cloud: o3d.geometry.PointCloud,
        output_cloud: o3d.geometry.PointCloud,
        input_count: int,
        output_count: int,
    ) -> PointCloudFilterResult:
        points = np.asarray(output_cloud.points)

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        removed_count = input_count - output_count

        if input_count > 0:
            reduction_percent = removed_count / input_count * 100.0
        else:
            reduction_percent = 0.0

        return PointCloudFilterResult(
            input_cloud=input_cloud,
            output_cloud=output_cloud,
            input_point_count=input_count,
            output_point_count=output_count,
            removed_point_count=removed_count,
            reduction_percent=reduction_percent,
            has_colors=output_cloud.has_colors(),
            has_normals=output_cloud.has_normals(),
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            message=(
                f"Đã lọc point cloud: {input_count} → {output_count} điểm "
                f"({reduction_percent:.2f}% giảm)"
            ),
        )