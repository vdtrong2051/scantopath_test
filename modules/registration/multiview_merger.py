from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

import copy
import math

import numpy as np
import open3d as o3d


@dataclass
class MultiViewCloudItem:
    """
    Một cloud ứng với một góc nhìn.

    yaw_deg:
        Góc quay của vật/bàn xoay theo độ.

    Ví dụ 4 view:
        0, 90, 180, 270

    Ví dụ 6 view:
        0, 60, 120, 180, 240, 300
    """

    cloud: o3d.geometry.PointCloud
    yaw_deg: float

    name: str = ""
    source_path: Optional[str] = None


@dataclass
class MultiViewMergerParams:
    """
    Tham số ghép nhiều point cloud.

    Bản đầu ưu tiên ổn định:
        - transform theo góc yaw biết trước
        - merge cloud
        - voxel downsample
        - lọc nhiễu
    """

    # -----------------------------
    # Rotation
    # -----------------------------
    # Hệ cloud từ camera hiện tại thường:
    # x: ngang
    # y: dọc ảnh
    # z: chiều sâu
    #
    # Nếu vật quay trên bàn xoay, thường thử axis="Y" trước.
    # Nếu thấy xoay sai trục, đổi thành "Z".
    rotation_axis: str = "Y"

    # Chiều quay.
    # Nếu merge thấy các mặt úp sai hướng, đổi thành -1.
    yaw_direction: float = 1.0

    # Nếu True, đưa từng cloud về gần tâm trước khi xoay.
    center_each_cloud_before_rotation: bool = True

    # Nếu True, sau merge đưa cloud tổng về tâm tọa độ.
    center_merged_cloud: bool = True

    # -----------------------------
    # Optional ICP
    # -----------------------------
    # Bản đầu nên để False cho ổn định.
    use_icp_refinement: bool = False
    icp_voxel_size_m: float = 0.02
    icp_max_correspondence_distance_m: float = 0.06
    icp_max_iteration: int = 50

    # -----------------------------
    # Downsample / Cleanup
    # -----------------------------
    pre_voxel_size_m: float = 0.0
    merge_voxel_size_m: float = 0.006

    remove_statistical_outlier: bool = True
    nb_neighbors: int = 20
    std_ratio: float = 2.0

    remove_radius_outlier: bool = False
    radius_nb_points: int = 12
    radius_m: float = 0.025

    # -----------------------------
    # Safety
    # -----------------------------
    min_points_per_view: int = 30
    min_output_points: int = 50

    verbose: bool = True


@dataclass
class MultiViewMergeResult:
    merged_cloud: o3d.geometry.PointCloud

    input_view_count: int
    used_view_count: int

    input_point_count: int
    output_point_count: int

    yaw_angles_used: list[float] = field(default_factory=list)

    bounds_min: np.ndarray = field(default_factory=lambda: np.zeros(3))
    bounds_max: np.ndarray = field(default_factory=lambda: np.zeros(3))
    center: np.ndarray = field(default_factory=lambda: np.zeros(3))
    size: np.ndarray = field(default_factory=lambda: np.zeros(3))

    message: str = ""


class MultiViewMerger:
    """
    Ghép nhiều point cloud từ các góc nhìn khác nhau.

    Dùng cho mục tiêu:
        - 4 view: trước / phải / sau / trái
        - 6 view: 0 / 60 / 120 / 180 / 240 / 300

    Bản này chưa cần ICP bắt buộc.
    Ghép chính bằng yaw angle biết trước.

    Pipeline đề xuất:
        raw PLY từng góc
        → DepthObjectExtractor tách object_cloud từng góc
        → MultiViewMerger merge các object_cloud
        → filter / normal / surface / zigzag
    """

    def __init__(
        self,
        params: Optional[MultiViewMergerParams] = None,
    ):
        self.params = params or MultiViewMergerParams()

    # -------------------------------------------------
    # Main API
    # -------------------------------------------------
    def merge(
        self,
        items: Sequence[MultiViewCloudItem],
        params: Optional[MultiViewMergerParams] = None,
    ) -> MultiViewMergeResult:
        params = params or self.params

        if not items:
            raise ValueError("Danh sách view point cloud đang rỗng.")

        valid_items = self._filter_valid_items(items, params)

        if not valid_items:
            raise RuntimeError(
                "Không có point cloud view nào đủ điểm để merge."
            )

        input_point_count = sum(
            len(item.cloud.points)
            for item in valid_items
        )

        transformed_clouds: list[o3d.geometry.PointCloud] = []
        yaw_angles_used: list[float] = []

        for item in valid_items:
            cloud = self._prepare_view_cloud(
                cloud=item.cloud,
                params=params,
            )

            transformed = self._transform_cloud_by_yaw(
                cloud=cloud,
                yaw_deg=float(item.yaw_deg),
                params=params,
            )

            transformed_clouds.append(transformed)
            yaw_angles_used.append(float(item.yaw_deg))

        if params.use_icp_refinement and len(transformed_clouds) >= 2:
            transformed_clouds = self._refine_with_icp(
                transformed_clouds,
                params=params,
            )

        merged = o3d.geometry.PointCloud()

        for cloud in transformed_clouds:
            merged += cloud

        merged = self._cleanup_merged_cloud(
            merged,
            params=params,
        )

        if params.center_merged_cloud and len(merged.points) > 0:
            merged.translate(-merged.get_center())

        output_point_count = len(merged.points)

        if output_point_count < int(params.min_output_points):
            raise RuntimeError(
                "Merged cloud có quá ít điểm. "
                f"Số điểm hiện tại: {output_point_count}. "
                "Hãy nới tham số tách object hoặc giảm voxel_size."
            )

        bounds_min, bounds_max, center, size = self._compute_bounds(merged)

        message = (
            "Đã ghép point cloud nhiều góc: "
            f"{len(valid_items)}/{len(items)} view | "
            f"{input_point_count} điểm đầu vào → "
            f"{output_point_count} điểm sau merge | "
            f"góc={yaw_angles_used}"
        )

        if params.verbose:
            print(f"[MultiViewMerger] {message}")

        return MultiViewMergeResult(
            merged_cloud=merged,
            input_view_count=len(items),
            used_view_count=len(valid_items),
            input_point_count=input_point_count,
            output_point_count=output_point_count,
            yaw_angles_used=yaw_angles_used,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            message=message,
        )

    def merge_clouds(
        self,
        clouds: Sequence[o3d.geometry.PointCloud],
        yaw_angles_deg: Sequence[float],
        params: Optional[MultiViewMergerParams] = None,
    ) -> MultiViewMergeResult:
        if len(clouds) != len(yaw_angles_deg):
            raise ValueError(
                "Số lượng clouds phải bằng số lượng yaw_angles_deg."
            )

        items = [
            MultiViewCloudItem(
                cloud=cloud,
                yaw_deg=float(yaw),
                name=f"view_{idx}",
            )
            for idx, (cloud, yaw) in enumerate(
                zip(clouds, yaw_angles_deg),
                start=1,
            )
        ]

        return self.merge(items, params=params)

    def merge_files(
        self,
        file_paths: Sequence[str | Path],
        yaw_angles_deg: Sequence[float],
        params: Optional[MultiViewMergerParams] = None,
    ) -> MultiViewMergeResult:
        if len(file_paths) != len(yaw_angles_deg):
            raise ValueError(
                "Số lượng file_paths phải bằng số lượng yaw_angles_deg."
            )

        items: list[MultiViewCloudItem] = []

        for idx, (file_path, yaw) in enumerate(
            zip(file_paths, yaw_angles_deg),
            start=1,
        ):
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(f"Không tìm thấy file: {path}")

            cloud = o3d.io.read_point_cloud(str(path))

            if cloud is None or len(cloud.points) <= 0:
                raise RuntimeError(f"Không đọc được point cloud: {path}")

            items.append(
                MultiViewCloudItem(
                    cloud=cloud,
                    yaw_deg=float(yaw),
                    name=f"view_{idx}",
                    source_path=str(path),
                )
            )

        return self.merge(items, params=params)

    def merge_files_and_save(
        self,
        file_paths: Sequence[str | Path],
        yaw_angles_deg: Sequence[float],
        output_path: str | Path,
        params: Optional[MultiViewMergerParams] = None,
    ) -> MultiViewMergeResult:
        result = self.merge_files(
            file_paths=file_paths,
            yaw_angles_deg=yaw_angles_deg,
            params=params,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ok = o3d.io.write_point_cloud(
            str(output_path),
            result.merged_cloud,
            write_ascii=False,
        )

        if not ok:
            raise RuntimeError(f"Không ghi được merged cloud: {output_path}")

        return result

    # -------------------------------------------------
    # Validation / Prepare
    # -------------------------------------------------
    def _filter_valid_items(
        self,
        items: Sequence[MultiViewCloudItem],
        params: MultiViewMergerParams,
    ) -> list[MultiViewCloudItem]:
        valid_items: list[MultiViewCloudItem] = []

        for item in items:
            if item is None:
                continue

            cloud = item.cloud

            if cloud is None:
                continue

            if not isinstance(cloud, o3d.geometry.PointCloud):
                continue

            if len(cloud.points) < int(params.min_points_per_view):
                if params.verbose:
                    print(
                        "[MultiViewMerger] Bỏ view ít điểm: "
                        f"{item.name} | {len(cloud.points)} điểm"
                    )
                continue

            valid_items.append(item)

        return valid_items

    def _prepare_view_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
        params: MultiViewMergerParams,
    ) -> o3d.geometry.PointCloud:
        output = copy.deepcopy(cloud)

        output.remove_non_finite_points(
            remove_nan=True,
            remove_infinite=True,
        )

        if (
            params.pre_voxel_size_m is not None
            and float(params.pre_voxel_size_m) > 0
        ):
            output = output.voxel_down_sample(
                voxel_size=float(params.pre_voxel_size_m)
            )

        return output

    # -------------------------------------------------
    # Transform
    # -------------------------------------------------
    def _transform_cloud_by_yaw(
        self,
        cloud: o3d.geometry.PointCloud,
        yaw_deg: float,
        params: MultiViewMergerParams,
    ) -> o3d.geometry.PointCloud:
        output = copy.deepcopy(cloud)

        if len(output.points) <= 0:
            return output

        if params.center_each_cloud_before_rotation:
            output.translate(-output.get_center())

        yaw_rad = math.radians(
            float(yaw_deg) * float(params.yaw_direction)
        )

        axis = str(params.rotation_axis).strip().upper()

        if axis == "X":
            axis_angle = np.array([yaw_rad, 0.0, 0.0], dtype=np.float64)
        elif axis == "Y":
            axis_angle = np.array([0.0, yaw_rad, 0.0], dtype=np.float64)
        elif axis == "Z":
            axis_angle = np.array([0.0, 0.0, yaw_rad], dtype=np.float64)
        else:
            raise ValueError(
                "rotation_axis chỉ nhận 'X', 'Y' hoặc 'Z'. "
                f"Giá trị hiện tại: {params.rotation_axis}"
            )

        rotation_matrix = output.get_rotation_matrix_from_axis_angle(
            axis_angle
        )

        output.rotate(
            rotation_matrix,
            center=(0.0, 0.0, 0.0),
        )

        return output

    # -------------------------------------------------
    # ICP optional
    # -------------------------------------------------
    def _refine_with_icp(
        self,
        clouds: Sequence[o3d.geometry.PointCloud],
        params: MultiViewMergerParams,
    ) -> list[o3d.geometry.PointCloud]:
        """
        ICP refinement nhẹ.

        Lưu ý:
            - Bản đầu nên để use_icp_refinement=False.
            - Chỉ bật khi transform theo yaw đã tương đối đúng.
        """

        if len(clouds) <= 1:
            return list(clouds)

        refined: list[o3d.geometry.PointCloud] = []

        reference = copy.deepcopy(clouds[0])
        refined.append(reference)

        merged_reference = copy.deepcopy(reference)

        for idx in range(1, len(clouds)):
            source = copy.deepcopy(clouds[idx])
            target = copy.deepcopy(merged_reference)

            source_down = source.voxel_down_sample(
                voxel_size=float(params.icp_voxel_size_m)
            )
            target_down = target.voxel_down_sample(
                voxel_size=float(params.icp_voxel_size_m)
            )

            try:
                registration = o3d.pipelines.registration.registration_icp(
                    source_down,
                    target_down,
                    float(params.icp_max_correspondence_distance_m),
                    np.eye(4),
                    o3d.pipelines.registration.TransformationEstimationPointToPoint(),
                    o3d.pipelines.registration.ICPConvergenceCriteria(
                        max_iteration=int(params.icp_max_iteration)
                    ),
                )

                source.transform(registration.transformation)

                if params.verbose:
                    print(
                        "[MultiViewMerger] ICP view "
                        f"{idx}: fitness={registration.fitness:.4f}, "
                        f"rmse={registration.inlier_rmse:.4f}"
                    )

            except Exception as exc:
                if params.verbose:
                    print(
                        "[MultiViewMerger] ICP lỗi, dùng transform yaw gốc: "
                        f"view={idx}, error={exc}"
                    )

            refined.append(source)

            merged_reference += source
            merged_reference = merged_reference.voxel_down_sample(
                voxel_size=float(params.merge_voxel_size_m)
            )

        return refined

    # -------------------------------------------------
    # Cleanup merged cloud
    # -------------------------------------------------
    def _cleanup_merged_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
        params: MultiViewMergerParams,
    ) -> o3d.geometry.PointCloud:
        output = copy.deepcopy(cloud)

        output.remove_non_finite_points(
            remove_nan=True,
            remove_infinite=True,
        )

        if (
            params.merge_voxel_size_m is not None
            and float(params.merge_voxel_size_m) > 0
        ):
            output = output.voxel_down_sample(
                voxel_size=float(params.merge_voxel_size_m)
            )

        if (
            params.remove_statistical_outlier
            and len(output.points) > int(params.nb_neighbors)
        ):
            output, _ = output.remove_statistical_outlier(
                nb_neighbors=int(params.nb_neighbors),
                std_ratio=float(params.std_ratio),
            )

        if (
            params.remove_radius_outlier
            and len(output.points) > int(params.radius_nb_points)
        ):
            output, _ = output.remove_radius_outlier(
                nb_points=int(params.radius_nb_points),
                radius=float(params.radius_m),
            )

        return output

    # -------------------------------------------------
    # Bounds
    # -------------------------------------------------
    def _compute_bounds(
        self,
        cloud: o3d.geometry.PointCloud,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        points = np.asarray(cloud.points)

        if points.size <= 0:
            zero = np.zeros(3, dtype=np.float64)
            return zero, zero, zero, zero

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        return bounds_min, bounds_max, center, size


# -------------------------------------------------
# Convenience functions
# -------------------------------------------------
def merge_multiview_clouds(
    clouds: Sequence[o3d.geometry.PointCloud],
    yaw_angles_deg: Sequence[float],
    params: Optional[MultiViewMergerParams] = None,
) -> o3d.geometry.PointCloud:
    merger = MultiViewMerger(params=params)
    result = merger.merge_clouds(
        clouds=clouds,
        yaw_angles_deg=yaw_angles_deg,
        params=params,
    )
    return result.merged_cloud


def merge_multiview_files(
    file_paths: Sequence[str | Path],
    yaw_angles_deg: Sequence[float],
    output_path: str | Path,
    params: Optional[MultiViewMergerParams] = None,
) -> MultiViewMergeResult:
    merger = MultiViewMerger(params=params)
    return merger.merge_files_and_save(
        file_paths=file_paths,
        yaw_angles_deg=yaw_angles_deg,
        output_path=output_path,
        params=params,
    )