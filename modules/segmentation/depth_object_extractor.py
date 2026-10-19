from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class DepthObjectExtractorParams:
    """
    Tham số tách vật thể dựa trên depth / hình học 3D.

    Ý tưởng chính:
        - Camera RGB-D tạo point cloud theo hệ tọa độ camera.
        - Trục Z thường là chiều sâu đi ra trước camera.
        - Vật thể gần camera nhất thường có Z nhỏ hơn nền/tường phía sau.
        - Ta ưu tiên giữ cụm điểm gần camera nhất.

    Lưu ý:
        Đây chưa phải Edge AI thật.
        Đây là bước tách vật thể bằng depth + geometry.
    """

    # -----------------------------
    # Depth crop
    # -----------------------------
    min_z_m: float = 0.25
    max_z_m: float = 2.50

    # Lấy percentile thấp của z để tìm vùng gần camera.
    # 3% hoặc 5% thường ổn hơn lấy min trực tiếp vì min có thể là nhiễu.
    nearest_percentile: float = 5.0

    # Sau khi tìm z_near, giữ điểm trong khoảng:
    # z_near - near_margin_m đến z_near + depth_window_m
    near_margin_m: float = 0.04
    depth_window_m: float = 0.70

    # Nếu True, dùng depth crop động theo vật gần camera nhất.
    use_nearest_depth_window: bool = True

    # -----------------------------
    # Basic cleanup
    # -----------------------------
    voxel_size_m: float = 0.006

    use_statistical_outlier: bool = True
    nb_neighbors: int = 20
    std_ratio: float = 2.0

    # -----------------------------
    # Plane removal
    # -----------------------------
    remove_large_planes: bool = True
    max_plane_removal_iterations: int = 2
    plane_distance_threshold_m: float = 0.018
    plane_ransac_n: int = 3
    plane_num_iterations: int = 800

    # Chỉ xóa plane nếu plane đủ lớn so với cloud.
    # Tránh xóa nhầm mặt phẳng nhỏ thuộc vật thể.
    plane_min_ratio: float = 0.22

    # Không xóa plane nếu tâm plane quá gần camera,
    # vì đó có thể là mặt trước của vật thể.
    protect_near_object_plane: bool = True
    protected_near_margin_m: float = 0.12

    # -----------------------------
    # Clustering
    # -----------------------------
    use_dbscan: bool = True
    dbscan_eps_m: float = 0.045
    dbscan_min_points: int = 25

    min_cluster_points: int = 80

    # Chọn cluster theo score:
    # score = point_count / z_center^power / center_offset_penalty
    nearest_score_power: float = 1.25
    center_x_penalty: float = 0.75

    # Nếu True, ưu tiên cụm nằm gần trục giữa camera hơn.
    prefer_center: bool = True

    # -----------------------------
    # Final cleanup
    # -----------------------------
    final_voxel_size_m: float = 0.004
    final_remove_outlier: bool = True

    # -----------------------------
    # Debug
    # -----------------------------
    verbose: bool = True


@dataclass
class DepthObjectExtractorResult:
    input_count: int
    after_depth_crop_count: int
    after_cleanup_count: int
    after_plane_removal_count: int
    output_count: int

    object_cloud: o3d.geometry.PointCloud

    z_near: float
    z_min_used: float
    z_max_used: float

    selected_cluster_label: Optional[int]
    selected_cluster_score: float

    message: str


class DepthObjectExtractor:
    """
    Tách vật thể gần camera nhất từ point cloud thô.

    Dùng cho bước:
        TÁCH VẬT THỂ BẰNG EDGE AI

    Nhưng hiện tại chưa dùng AI model.
    Đây là bản fallback bằng hình học 3D:
        1. Depth crop theo vật gần camera nhất
        2. Lọc nhiễu
        3. Xóa mặt phẳng lớn như sàn/tường nếu cần
        4. DBSCAN cluster
        5. Giữ cụm gần camera nhất / hợp lý nhất
    """

    def __init__(
        self,
        params: Optional[DepthObjectExtractorParams] = None,
    ):
        self.params = params or DepthObjectExtractorParams()

    # -------------------------------------------------
    # Main API
    # -------------------------------------------------
    def extract(
        self,
        cloud: o3d.geometry.PointCloud,
        params: Optional[DepthObjectExtractorParams] = None,
    ) -> DepthObjectExtractorResult:
        params = params or self.params

        self._validate_cloud(cloud)

        input_count = len(cloud.points)

        work_cloud = o3d.geometry.PointCloud(cloud)
        work_cloud.remove_non_finite_points(
            remove_nan=True,
            remove_infinite=True,
        )

        if len(work_cloud.points) <= 0:
            raise RuntimeError("Point cloud sau khi bỏ NaN/Inf bị rỗng.")

        # 1. Depth crop ưu tiên vật gần camera.
        (
            depth_cloud,
            z_near,
            z_min_used,
            z_max_used,
        ) = self._crop_by_nearest_depth(work_cloud, params)

        after_depth_crop_count = len(depth_cloud.points)

        if after_depth_crop_count <= 0:
            raise RuntimeError(
                "Không còn điểm nào sau khi crop theo khoảng cách depth. "
                "Hãy nới min_z_m / max_z_m / depth_window_m."
            )

        # 2. Cleanup cơ bản.
        clean_cloud = self._basic_cleanup(depth_cloud, params)
        after_cleanup_count = len(clean_cloud.points)

        if after_cleanup_count <= 0:
            raise RuntimeError("Point cloud bị rỗng sau bước lọc nhiễu.")

        # 3. Loại mặt phẳng lớn: sàn/tường/nền.
        if params.remove_large_planes:
            no_plane_cloud = self._remove_large_planes(
                clean_cloud,
                z_near=z_near,
                params=params,
            )
        else:
            no_plane_cloud = clean_cloud

        after_plane_removal_count = len(no_plane_cloud.points)

        if after_plane_removal_count <= 0:
            # Nếu xóa plane quá tay thì quay lại cloud trước đó.
            no_plane_cloud = clean_cloud
            after_plane_removal_count = len(no_plane_cloud.points)

        # 4. DBSCAN giữ cụm vật thể gần nhất.
        if params.use_dbscan:
            object_cloud, selected_label, selected_score = self._select_nearest_cluster(
                no_plane_cloud,
                params=params,
            )
        else:
            object_cloud = no_plane_cloud
            selected_label = None
            selected_score = 0.0

        # 5. Final cleanup.
        object_cloud = self._final_cleanup(object_cloud, params)

        output_count = len(object_cloud.points)

        if output_count <= 0:
            raise RuntimeError(
                "Không tách được cụm vật thể hợp lệ. "
                "Hãy nới depth_window_m hoặc giảm dbscan_min_points."
            )

        message = (
            "Đã tách vật thể gần camera nhất: "
            f"{input_count} điểm → {output_count} điểm "
            f"| z_near={z_near:.3f} m "
            f"| z_range=[{z_min_used:.3f}, {z_max_used:.3f}] m"
        )

        if params.verbose:
            print(f"[DepthObjectExtractor] {message}")

        return DepthObjectExtractorResult(
            input_count=input_count,
            after_depth_crop_count=after_depth_crop_count,
            after_cleanup_count=after_cleanup_count,
            after_plane_removal_count=after_plane_removal_count,
            output_count=output_count,
            object_cloud=object_cloud,
            z_near=float(z_near),
            z_min_used=float(z_min_used),
            z_max_used=float(z_max_used),
            selected_cluster_label=selected_label,
            selected_cluster_score=float(selected_score),
            message=message,
        )

    def extract_from_file(
        self,
        input_path: str | Path,
        params: Optional[DepthObjectExtractorParams] = None,
    ) -> DepthObjectExtractorResult:
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file point cloud: {input_path}")

        cloud = o3d.io.read_point_cloud(str(input_path))

        if cloud is None or len(cloud.points) <= 0:
            raise RuntimeError(f"Không đọc được point cloud hợp lệ: {input_path}")

        return self.extract(cloud, params=params)

    def extract_and_save(
        self,
        input_path: str | Path,
        output_path: str | Path,
        params: Optional[DepthObjectExtractorParams] = None,
    ) -> DepthObjectExtractorResult:
        result = self.extract_from_file(
            input_path=input_path,
            params=params,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ok = o3d.io.write_point_cloud(
            str(output_path),
            result.object_cloud,
            write_ascii=False,
        )

        if not ok:
            raise RuntimeError(f"Không ghi được object point cloud: {output_path}")

        return result

    # -------------------------------------------------
    # Step 1: Depth crop
    # -------------------------------------------------
    def _crop_by_nearest_depth(
        self,
        cloud: o3d.geometry.PointCloud,
        params: DepthObjectExtractorParams,
    ) -> tuple[o3d.geometry.PointCloud, float, float, float]:
        points = np.asarray(cloud.points)

        if points.ndim != 2 or points.shape[1] != 3:
            raise RuntimeError("Point cloud không có points dạng Nx3.")

        z = points[:, 2]

        valid = np.isfinite(z)
        valid &= z > 0
        valid &= z >= float(params.min_z_m)
        valid &= z <= float(params.max_z_m)

        if not np.any(valid):
            raise RuntimeError(
                "Không có điểm nào nằm trong khoảng min_z_m/max_z_m."
            )

        valid_z = z[valid]

        z_near = float(
            np.percentile(
                valid_z,
                float(params.nearest_percentile),
            )
        )

        if params.use_nearest_depth_window:
            z_min_used = max(
                float(params.min_z_m),
                z_near - float(params.near_margin_m),
            )

            z_max_used = min(
                float(params.max_z_m),
                z_near + float(params.depth_window_m),
            )
        else:
            z_min_used = float(params.min_z_m)
            z_max_used = float(params.max_z_m)

        keep = valid.copy()
        keep &= z >= z_min_used
        keep &= z <= z_max_used

        keep_idx = np.where(keep)[0]

        if len(keep_idx) <= 0:
            raise RuntimeError(
                "Không có điểm nào sau khi crop theo nearest depth window."
            )

        cropped = cloud.select_by_index(keep_idx)

        return cropped, z_near, z_min_used, z_max_used

    # -------------------------------------------------
    # Step 2: Basic cleanup
    # -------------------------------------------------
    def _basic_cleanup(
        self,
        cloud: o3d.geometry.PointCloud,
        params: DepthObjectExtractorParams,
    ) -> o3d.geometry.PointCloud:
        output = o3d.geometry.PointCloud(cloud)

        if params.voxel_size_m and params.voxel_size_m > 0:
            output = output.voxel_down_sample(
                voxel_size=float(params.voxel_size_m)
            )

        if (
            params.use_statistical_outlier
            and len(output.points) > params.nb_neighbors
        ):
            output, _ = output.remove_statistical_outlier(
                nb_neighbors=int(params.nb_neighbors),
                std_ratio=float(params.std_ratio),
            )

        return output

    # -------------------------------------------------
    # Step 3: Plane removal
    # -------------------------------------------------
    def _remove_large_planes(
        self,
        cloud: o3d.geometry.PointCloud,
        z_near: float,
        params: DepthObjectExtractorParams,
    ) -> o3d.geometry.PointCloud:
        output = o3d.geometry.PointCloud(cloud)

        for _ in range(int(params.max_plane_removal_iterations)):
            point_count = len(output.points)

            if point_count < 300:
                break

            try:
                plane_model, inliers = output.segment_plane(
                    distance_threshold=float(params.plane_distance_threshold_m),
                    ransac_n=int(params.plane_ransac_n),
                    num_iterations=int(params.plane_num_iterations),
                )
            except Exception:
                break

            inlier_count = len(inliers)

            if inlier_count <= 0:
                break

            plane_ratio = inlier_count / max(point_count, 1)

            # Plane quá nhỏ thì không cần xóa.
            if plane_ratio < float(params.plane_min_ratio):
                break

            points = np.asarray(output.points)
            plane_points = points[inliers]
            plane_center_z = float(np.mean(plane_points[:, 2]))

            # Bảo vệ mặt gần camera nhất, tránh xóa nhầm mặt vật thể.
            if params.protect_near_object_plane:
                if plane_center_z <= z_near + float(params.protected_near_margin_m):
                    break

            output = output.select_by_index(
                inliers,
                invert=True,
            )

            if len(output.points) <= 0:
                break

        return output

    # -------------------------------------------------
    # Step 4: DBSCAN cluster
    # -------------------------------------------------
    def _select_nearest_cluster(
        self,
        cloud: o3d.geometry.PointCloud,
        params: DepthObjectExtractorParams,
    ) -> tuple[o3d.geometry.PointCloud, Optional[int], float]:
        point_count = len(cloud.points)

        if point_count < params.dbscan_min_points:
            return cloud, None, 0.0

        labels = np.asarray(
            cloud.cluster_dbscan(
                eps=float(params.dbscan_eps_m),
                min_points=int(params.dbscan_min_points),
                print_progress=False,
            )
        )

        if labels.size <= 0:
            return cloud, None, 0.0

        max_label = int(labels.max())

        if max_label < 0:
            # DBSCAN không tìm được cluster nào.
            return cloud, None, 0.0

        points = np.asarray(cloud.points)

        best_label = None
        best_score = -1.0

        for label in range(max_label + 1):
            idx = np.where(labels == label)[0]

            if len(idx) < int(params.min_cluster_points):
                continue

            cluster_points = points[idx]
            center = cluster_points.mean(axis=0)

            z_center = float(center[2])
            x_center = float(center[0])

            z_score_denominator = max(
                z_center ** float(params.nearest_score_power),
                1e-6,
            )

            score = len(idx) / z_score_denominator

            if params.prefer_center:
                # Cụm càng lệch khỏi trục giữa camera thì giảm điểm.
                center_penalty = 1.0 + abs(x_center) * float(params.center_x_penalty)
                score = score / center_penalty

            if score > best_score:
                best_score = float(score)
                best_label = int(label)

        if best_label is None:
            # Nếu cluster nào cũng nhỏ thì chọn cluster lớn nhất.
            best_label = self._largest_cluster_label(labels)
            best_score = 0.0

        if best_label is None:
            return cloud, None, 0.0

        keep_idx = np.where(labels == best_label)[0]
        object_cloud = cloud.select_by_index(keep_idx)

        return object_cloud, best_label, best_score

    def _largest_cluster_label(self, labels: np.ndarray) -> Optional[int]:
        valid_labels = labels[labels >= 0]

        if valid_labels.size <= 0:
            return None

        unique, counts = np.unique(
            valid_labels,
            return_counts=True,
        )

        best_idx = int(np.argmax(counts))

        return int(unique[best_idx])

    # -------------------------------------------------
    # Step 5: Final cleanup
    # -------------------------------------------------
    def _final_cleanup(
        self,
        cloud: o3d.geometry.PointCloud,
        params: DepthObjectExtractorParams,
    ) -> o3d.geometry.PointCloud:
        output = o3d.geometry.PointCloud(cloud)

        if params.final_voxel_size_m and params.final_voxel_size_m > 0:
            output = output.voxel_down_sample(
                voxel_size=float(params.final_voxel_size_m)
            )

        if (
            params.final_remove_outlier
            and len(output.points) > params.nb_neighbors
        ):
            output, _ = output.remove_statistical_outlier(
                nb_neighbors=int(params.nb_neighbors),
                std_ratio=float(params.std_ratio),
            )

        return output

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def _validate_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
    ):
        if cloud is None:
            raise ValueError("Point cloud đầu vào bị None.")

        if not isinstance(cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "DepthObjectExtractor cần open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(cloud)}"
            )

        if len(cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm.")
        

# -------------------------------------------------
# Convenience functions
# -------------------------------------------------
def extract_nearest_object_cloud(
    cloud: o3d.geometry.PointCloud,
    params: Optional[DepthObjectExtractorParams] = None,
) -> o3d.geometry.PointCloud:
    extractor = DepthObjectExtractor(params=params)
    result = extractor.extract(cloud)
    return result.object_cloud


def extract_nearest_object_from_file(
    input_path: str | Path,
    output_path: str | Path,
    params: Optional[DepthObjectExtractorParams] = None,
) -> DepthObjectExtractorResult:
    extractor = DepthObjectExtractor(params=params)
    return extractor.extract_and_save(
        input_path=input_path,
        output_path=output_path,
        params=params,
    )