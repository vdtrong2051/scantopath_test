from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import open3d as o3d

from modules.segmentation.depth_object_extractor import (
    DepthObjectExtractor,
    DepthObjectExtractorParams,
    DepthObjectExtractorResult,
)


@dataclass
class ObjectExtractionServiceState:
    source_cloud: Optional[o3d.geometry.PointCloud] = None
    object_cloud: Optional[o3d.geometry.PointCloud] = None
    extractor_result: Optional[DepthObjectExtractorResult] = None
    params_used: Optional[DepthObjectExtractorParams] = None

    is_extracted: bool = False
    message: str = "Chưa tách vật thể."


class ObjectExtractionService:
    """
    Service tách vật thể từ point cloud thô.

    Giai đoạn hiện tại:
        - Chưa dùng Edge AI model thật.
        - Dùng depth + geometry:
            + ưu tiên vật thể gần camera nhất
            + crop theo depth
            + loại mặt phẳng lớn
            + DBSCAN giữ cụm gần nhất/lớn nhất

    Sau này có thể thay lõi bằng Edge AI segmentation.
    """

    def __init__(self):
        self.extractor = DepthObjectExtractor()
        self.state = ObjectExtractionServiceState()

    def extract_nearest_object(
        self,
        source_cloud: o3d.geometry.PointCloud,
        params: Optional[DepthObjectExtractorParams] = None,
    ) -> DepthObjectExtractorResult:
        self._validate_input_cloud(source_cloud)

        params = params or DepthObjectExtractorParams(
            min_z_m=0.25,
            max_z_m=2.50,
            nearest_percentile=5.0,
            near_margin_m=0.04,
            depth_window_m=0.90,
            use_nearest_depth_window=True,

            voxel_size_m=0.004,
            use_statistical_outlier=True,
            nb_neighbors=20,
            std_ratio=2.0,

            remove_large_planes=True,
            max_plane_removal_iterations=2,
            plane_distance_threshold_m=0.018,
            plane_min_ratio=0.22,
            protect_near_object_plane=True,

            use_dbscan=True,
            dbscan_eps_m=0.055,
            dbscan_min_points=20,
            min_cluster_points=40,

            final_voxel_size_m=0.003,
            final_remove_outlier=True,
            verbose=True,
        )

        result = self.extractor.extract(
            cloud=source_cloud,
            params=params,
        )

        if result.object_cloud is None:
            raise RuntimeError("DepthObjectExtractor không trả về object_cloud.")

        if len(result.object_cloud.points) <= 0:
            raise RuntimeError("Object cloud sau khi tách bị rỗng.")

        self.state.source_cloud = source_cloud
        self.state.object_cloud = result.object_cloud
        self.state.extractor_result = result
        self.state.params_used = params
        self.state.is_extracted = True
        self.state.message = result.message

        return result

    def has_object_cloud(self) -> bool:
        return (
            self.state.is_extracted
            and self.state.object_cloud is not None
            and len(self.state.object_cloud.points) > 0
        )

    def get_object_cloud(self) -> o3d.geometry.PointCloud:
        if not self.has_object_cloud():
            raise RuntimeError(
                "Chưa có point cloud vật thể hợp lệ. "
                "Hãy chạy tách vật thể trước."
            )

        return self.state.object_cloud

    def get_result(self) -> DepthObjectExtractorResult:
        if not self.has_object_cloud():
            raise RuntimeError("Chưa có kết quả tách vật thể hợp lệ.")

        return self.state.extractor_result

    def reset(self):
        self.state = ObjectExtractionServiceState(
            is_extracted=False,
            message="Đã xóa kết quả tách vật thể hiện tại.",
        )

    def _validate_input_cloud(self, cloud: o3d.geometry.PointCloud):
        if cloud is None:
            raise ValueError("Point cloud đầu vào bị None.")

        if not isinstance(cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "ObjectExtractionService cần open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(cloud)}"
            )

        if len(cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm.")