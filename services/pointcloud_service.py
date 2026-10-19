from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import open3d as o3d

from modules.pointcloud.pointcloud_filter import (
    PointCloudFilter,
    PointCloudFilterParams,
    PointCloudFilterResult,
)


@dataclass
class PointCloudServiceState:
    raw_point_cloud: Optional[o3d.geometry.PointCloud] = None
    clean_point_cloud: Optional[o3d.geometry.PointCloud] = None
    filter_result: Optional[PointCloudFilterResult] = None

    is_filtered: bool = False
    message: str = "Chưa xử lý point cloud."


class PointCloudService:
    """
    Service quản lý xử lý point cloud.

    Vai trò:
        - Nhận point cloud thô từ ScanService
        - Lọc nhiễu point cloud
        - Lưu point cloud sạch trong RAM
        - Cung cấp dữ liệu cho các bước sau:
            + Build Surface Map
            + Estimate Normals
            + Generate Path
    """

    def __init__(self):
        self.filter_module = PointCloudFilter()
        self.state = PointCloudServiceState()

    def filter_point_cloud(
        self,
        raw_point_cloud: o3d.geometry.PointCloud,
        params: Optional[PointCloudFilterParams] = None,
    ) -> PointCloudFilterResult:
        result = self.filter_module.filter(
            point_cloud=raw_point_cloud,
            params=params,
        )

        self.state.raw_point_cloud = raw_point_cloud
        self.state.clean_point_cloud = result.output_cloud
        self.state.filter_result = result
        self.state.is_filtered = True
        self.state.message = result.message

        return result

    def has_clean_cloud(self) -> bool:
        return (
            self.state.is_filtered
            and self.state.clean_point_cloud is not None
            and self.state.filter_result is not None
        )

    def get_clean_point_cloud(self) -> o3d.geometry.PointCloud:
        if not self.has_clean_cloud():
            raise RuntimeError(
                "Chưa có point cloud sạch. Hãy lọc nhiễu point cloud trước."
            )

        return self.state.clean_point_cloud

    def get_filter_result(self) -> PointCloudFilterResult:
        if not self.has_clean_cloud():
            raise RuntimeError(
                "Chưa có kết quả lọc point cloud."
            )

        return self.state.filter_result

    def save_clean_point_cloud(self, output_path: str | Path) -> Path:
        if not self.has_clean_cloud():
            raise RuntimeError(
                "Chưa có point cloud sạch để lưu."
            )

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        ok = o3d.io.write_point_cloud(
            str(path),
            self.state.clean_point_cloud,
        )

        if not ok:
            raise RuntimeError(f"Không thể lưu point cloud sạch: {path}")

        return path

    def reset(self):
        self.state = PointCloudServiceState(
            is_filtered=False,
            message="Đã xóa point cloud sạch hiện tại.",
        )