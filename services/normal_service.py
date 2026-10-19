from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import open3d as o3d

from modules.surface_map.normal_estimation import (
    NormalEstimator,
    NormalEstimationParams,
    NormalEstimationResult,
)


@dataclass
class NormalServiceState:
    source_cloud: Optional[o3d.geometry.PointCloud] = None
    normal_cloud: Optional[o3d.geometry.PointCloud] = None
    normal_result: Optional[NormalEstimationResult] = None
    params_used: Optional[NormalEstimationParams] = None

    is_estimated: bool = False
    message: str = "Chưa tính pháp tuyến bề mặt."


class NormalService:
    """
    Service quản lý bước tính pháp tuyến bề mặt.

    Vai trò:
        - Nhận point cloud sạch từ PointCloudService.
        - Tính normal vector cho từng điểm.
        - Lưu point cloud có normal trong RAM.
        - Cung cấp dữ liệu cho Surface Map.

    Ghi chú:
        Zigzag bản mới không sinh trực tiếp từ normal_cloud nữa.
        Zigzag sẽ dùng surface mesh tạo từ normal_cloud.
    """

    def __init__(self):
        self.estimator = NormalEstimator()
        self.state = NormalServiceState()

    def estimate_normals(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: Optional[NormalEstimationParams] = None,
    ) -> NormalEstimationResult:
        """
        Tính pháp tuyến cho point cloud.
        """

        self._validate_input_cloud(point_cloud)

        result = self.estimator.estimate(
            point_cloud=point_cloud,
            params=params,
        )

        if result.output_cloud is None:
            raise RuntimeError(
                "NormalEstimator không trả về point cloud hợp lệ."
            )

        if not result.output_cloud.has_normals():
            raise RuntimeError(
                "Point cloud sau khi tính vẫn chưa có pháp tuyến. "
                "Hãy kiểm tra normal_estimation.py."
            )

        if len(result.output_cloud.points) <= 0:
            raise RuntimeError(
                "Point cloud sau khi tính pháp tuyến bị rỗng."
            )

        if len(result.output_cloud.normals) != len(result.output_cloud.points):
            raise RuntimeError(
                "Số lượng normal không khớp với số lượng point."
            )

        self.state.source_cloud = point_cloud
        self.state.normal_cloud = result.output_cloud
        self.state.normal_result = result
        self.state.params_used = params
        self.state.is_estimated = True
        self.state.message = result.message

        return result

    def has_normals(self) -> bool:
        if not (
            self.state.is_estimated
            and self.state.normal_cloud is not None
            and self.state.normal_result is not None
        ):
            return False

        if not self.state.normal_cloud.has_normals():
            return False

        if len(self.state.normal_cloud.points) <= 0:
            return False

        if len(self.state.normal_cloud.normals) != len(self.state.normal_cloud.points):
            return False

        return True

    def get_normal_cloud(self) -> o3d.geometry.PointCloud:
        if not self.has_normals():
            raise RuntimeError(
                "Chưa có point cloud chứa pháp tuyến hợp lệ. "
                "Hãy tính pháp tuyến trước."
            )

        return self.state.normal_cloud

    def get_result(self) -> NormalEstimationResult:
        if not self.has_normals():
            raise RuntimeError("Chưa có kết quả tính pháp tuyến hợp lệ.")

        return self.state.normal_result

    def get_params_used(self) -> Optional[NormalEstimationParams]:
        return self.state.params_used

    def reset(self):
        self.state = NormalServiceState(
            is_estimated=False,
            message="Đã xóa kết quả pháp tuyến hiện tại.",
        )

    def _validate_input_cloud(self, point_cloud: o3d.geometry.PointCloud):
        if point_cloud is None:
            raise ValueError("Point cloud đầu vào bị rỗng.")

        if not isinstance(point_cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "NormalService cần đầu vào là open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(point_cloud)}"
            )

        if len(point_cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm 3D hợp lệ.")