from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import open3d as o3d

from modules.segmentation.depth_object_extractor import (
    DepthObjectExtractor,
    DepthObjectExtractorParams,
    DepthObjectExtractorResult,
)

from modules.registration.multiview_merger import (
    MultiViewCloudItem,
    MultiViewMerger,
    MultiViewMergerParams,
    MultiViewMergeResult,
)


@dataclass
class MultiViewScanParams:
    """
    Tham số session quét nhiều góc.

    view_count:
        4 view  -> 0, 90, 180, 270
        6 view  -> 0, 60, 120, 180, 240, 300

    yaw_angles_deg:
        Nếu None thì tự sinh theo view_count.
        Nếu truyền list thì dùng list đó.

    auto_extract_object:
        True:
            raw cloud từng góc sẽ được tách vật thể gần camera nhất
            trước khi merge.

        False:
            merge trực tiếp raw cloud.
    """

    view_count: int = 4
    yaw_angles_deg: Optional[list[float]] = None

    output_root: str = "data/pointcloud_clean/multiview"
    session_prefix: str = "MULTIVIEW"

    auto_extract_object: bool = True

    save_each_object_view: bool = True
    save_merged_cloud: bool = True

    object_filename_prefix: str = "object_view"
    merged_filename: str = "merged_multiview.ply"
    summary_filename: str = "multiview_summary.json"

    extractor_params: DepthObjectExtractorParams = field(
        default_factory=lambda: DepthObjectExtractorParams(
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
    )

    merger_params: MultiViewMergerParams = field(
        default_factory=lambda: MultiViewMergerParams(
            rotation_axis="Y",
            yaw_direction=1.0,
            center_each_cloud_before_rotation=True,
            center_merged_cloud=True,

            use_icp_refinement=False,

            pre_voxel_size_m=0.0,
            merge_voxel_size_m=0.006,

            remove_statistical_outlier=True,
            nb_neighbors=20,
            std_ratio=2.0,

            remove_radius_outlier=False,

            min_points_per_view=30,
            min_output_points=50,
            verbose=True,
        )
    )


@dataclass
class MultiViewScanView:
    """
    Một view trong session quét nhiều góc.
    """

    index: int
    yaw_deg: float

    raw_cloud: Optional[o3d.geometry.PointCloud] = None
    object_cloud: Optional[o3d.geometry.PointCloud] = None

    raw_path: Optional[str] = None
    object_path: Optional[str] = None

    raw_point_count: int = 0
    object_point_count: int = 0

    extractor_result: Optional[DepthObjectExtractorResult] = None

    name: str = ""


@dataclass
class MultiViewScanResult:
    """
    Kết quả sau khi merge nhiều view.
    """

    session_id: str
    session_dir: Path

    view_count: int
    used_view_count: int

    views: list[MultiViewScanView]

    merged_cloud: o3d.geometry.PointCloud
    merged_path: Optional[Path]

    merge_result: MultiViewMergeResult

    message: str


class MultiViewScanService:
    """
    Service quản lý quét nhiều góc.

    Vai trò:
        - Lưu danh sách view đã chụp.
        - Tự gán góc yaw cho từng view.
        - Tách vật thể gần camera nhất cho từng view.
        - Gọi MultiViewMerger để merge các view.
        - Lưu merged cloud ra file.

    Giai đoạn này chưa tự điều khiển camera.
    Camera dialog / pipeline sẽ gọi service này sau mỗi lần có PLY/object cloud.
    """

    def __init__(
        self,
        params: Optional[MultiViewScanParams] = None,
    ):
        self.params = params or MultiViewScanParams()

        self.extractor = DepthObjectExtractor(
            params=self.params.extractor_params
        )

        self.merger = MultiViewMerger(
            params=self.params.merger_params
        )

        self.session_id = self._make_session_id()
        self.session_dir = Path(self.params.output_root) / self.session_id

        self.views: list[MultiViewScanView] = []
        self.merge_result: Optional[MultiViewMergeResult] = None
        self.merged_cloud: Optional[o3d.geometry.PointCloud] = None
        self.merged_path: Optional[Path] = None

        self.session_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------
    # Session
    # -------------------------------------------------
    def reset(
        self,
        params: Optional[MultiViewScanParams] = None,
    ):
        if params is not None:
            self.params = params
            self.extractor = DepthObjectExtractor(
                params=self.params.extractor_params
            )
            self.merger = MultiViewMerger(
                params=self.params.merger_params
            )

        self.session_id = self._make_session_id()
        self.session_dir = Path(self.params.output_root) / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.views = []
        self.merge_result = None
        self.merged_cloud = None
        self.merged_path = None

    def has_views(self) -> bool:
        return len(self.views) > 0

    def has_enough_views(self) -> bool:
        return len(self.views) >= int(self.params.view_count)

    def has_merged_cloud(self) -> bool:
        return (
            self.merged_cloud is not None
            and len(self.merged_cloud.points) > 0
        )

    def get_session_id(self) -> str:
        return self.session_id

    def get_session_dir(self) -> Path:
        return self.session_dir

    # -------------------------------------------------
    # Angle helpers
    # -------------------------------------------------
    def get_yaw_angles(self) -> list[float]:
        if self.params.yaw_angles_deg:
            return [float(v) for v in self.params.yaw_angles_deg]

        view_count = max(1, int(self.params.view_count))
        step = 360.0 / float(view_count)

        return [
            round(i * step, 6)
            for i in range(view_count)
        ]

    def get_next_view_index(self) -> int:
        return len(self.views) + 1

    def get_next_yaw_deg(self) -> float:
        angles = self.get_yaw_angles()
        index = len(self.views)

        if index < len(angles):
            return float(angles[index])

        # Nếu chụp quá số view mặc định thì vẫn cho tiếp,
        # quay vòng theo step.
        view_count = max(1, int(self.params.view_count))
        step = 360.0 / float(view_count)

        return float(index * step)

    def get_progress_text(self) -> str:
        return f"{len(self.views)}/{int(self.params.view_count)} view"

    # -------------------------------------------------
    # Add view
    # -------------------------------------------------
    def add_raw_cloud_view(
        self,
        raw_cloud: o3d.geometry.PointCloud,
        yaw_deg: Optional[float] = None,
        raw_path: Optional[str | Path] = None,
        name: str = "",
    ) -> MultiViewScanView:
        """
        Thêm một view từ raw cloud.

        Nếu auto_extract_object=True:
            raw cloud sẽ được tách vật thể trước khi lưu vào view.
        """

        self._validate_cloud(raw_cloud)

        view_index = self.get_next_view_index()

        if yaw_deg is None:
            yaw_deg = self.get_next_yaw_deg()

        raw_copy = copy.deepcopy(raw_cloud)

        view = MultiViewScanView(
            index=view_index,
            yaw_deg=float(yaw_deg),
            raw_cloud=raw_copy,
            raw_path=str(raw_path) if raw_path is not None else None,
            raw_point_count=len(raw_copy.points),
            name=name or f"view_{view_index:02d}_{float(yaw_deg):.1f}deg",
        )

        if self.params.auto_extract_object:
            extractor_result = self.extractor.extract(
                cloud=raw_copy,
                params=self.params.extractor_params,
            )

            object_cloud = extractor_result.object_cloud

            view.object_cloud = copy.deepcopy(object_cloud)
            view.object_point_count = len(object_cloud.points)
            view.extractor_result = extractor_result

            if self.params.save_each_object_view:
                object_path = self._make_object_view_path(
                    view_index=view_index,
                    yaw_deg=float(yaw_deg),
                )

                self._write_cloud(
                    cloud=object_cloud,
                    output_path=object_path,
                )

                view.object_path = str(object_path)

        else:
            view.object_cloud = copy.deepcopy(raw_copy)
            view.object_point_count = len(raw_copy.points)

        self.views.append(view)

        print(
            "[MultiViewScanService] Đã thêm view "
            f"{view.index} | yaw={view.yaw_deg:.1f}° | "
            f"raw={view.raw_point_count} điểm | "
            f"object={view.object_point_count} điểm"
        )

        return view

    def add_raw_file_view(
        self,
        file_path: str | Path,
        yaw_deg: Optional[float] = None,
        name: str = "",
    ) -> MultiViewScanView:
        """
        Thêm một view từ file PLY/PCD.
        """

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file point cloud: {file_path}")

        cloud = o3d.io.read_point_cloud(str(file_path))

        if cloud is None or len(cloud.points) <= 0:
            raise RuntimeError(f"Không đọc được point cloud hợp lệ: {file_path}")

        return self.add_raw_cloud_view(
            raw_cloud=cloud,
            yaw_deg=yaw_deg,
            raw_path=file_path,
            name=name or file_path.stem,
        )

    def add_object_cloud_view(
        self,
        object_cloud: o3d.geometry.PointCloud,
        yaw_deg: Optional[float] = None,
        object_path: Optional[str | Path] = None,
        name: str = "",
    ) -> MultiViewScanView:
        """
        Thêm trực tiếp object cloud đã tách sẵn.
        """

        self._validate_cloud(object_cloud)

        view_index = self.get_next_view_index()

        if yaw_deg is None:
            yaw_deg = self.get_next_yaw_deg()

        object_copy = copy.deepcopy(object_cloud)

        view = MultiViewScanView(
            index=view_index,
            yaw_deg=float(yaw_deg),
            object_cloud=object_copy,
            object_path=str(object_path) if object_path is not None else None,
            raw_cloud=None,
            raw_path=None,
            raw_point_count=0,
            object_point_count=len(object_copy.points),
            name=name or f"object_view_{view_index:02d}_{float(yaw_deg):.1f}deg",
        )

        if self.params.save_each_object_view and object_path is None:
            output_path = self._make_object_view_path(
                view_index=view_index,
                yaw_deg=float(yaw_deg),
            )

            self._write_cloud(
                cloud=object_copy,
                output_path=output_path,
            )

            view.object_path = str(output_path)

        self.views.append(view)

        print(
            "[MultiViewScanService] Đã thêm object view "
            f"{view.index} | yaw={view.yaw_deg:.1f}° | "
            f"{view.object_point_count} điểm"
        )

        return view

    # -------------------------------------------------
    # Merge
    # -------------------------------------------------
    def merge_views(
        self,
        save_output: Optional[bool] = None,
    ) -> MultiViewScanResult:
        """
        Merge các view hiện tại.

        Mặc định:
            - dùng object_cloud nếu có
            - nếu không có object_cloud thì dùng raw_cloud
        """

        if not self.views:
            raise RuntimeError(
                "Chưa có view nào để merge. "
                "Hãy chụp/thêm ít nhất 2 view."
            )

        items: list[MultiViewCloudItem] = []

        for view in self.views:
            cloud = view.object_cloud or view.raw_cloud

            if cloud is None or len(cloud.points) <= 0:
                continue

            items.append(
                MultiViewCloudItem(
                    cloud=cloud,
                    yaw_deg=float(view.yaw_deg),
                    name=view.name,
                    source_path=view.object_path or view.raw_path,
                )
            )

        if len(items) < 2:
            raise RuntimeError(
                "Cần ít nhất 2 view hợp lệ để merge nhiều góc."
            )

        merge_result = self.merger.merge(
            items=items,
            params=self.params.merger_params,
        )

        self.merge_result = merge_result
        self.merged_cloud = merge_result.merged_cloud

        should_save = (
            self.params.save_merged_cloud
            if save_output is None
            else bool(save_output)
        )

        output_path = None

        if should_save:
            output_path = self.session_dir / self.params.merged_filename

            self._write_cloud(
                cloud=merge_result.merged_cloud,
                output_path=output_path,
            )

            self.merged_path = output_path

        self._write_summary()

        result = MultiViewScanResult(
            session_id=self.session_id,
            session_dir=self.session_dir,
            view_count=len(self.views),
            used_view_count=merge_result.used_view_count,
            views=self.views,
            merged_cloud=merge_result.merged_cloud,
            merged_path=output_path,
            merge_result=merge_result,
            message=merge_result.message,
        )

        print(f"[MultiViewScanService] {result.message}")

        return result

    def merge_files(
        self,
        file_paths: list[str | Path],
        yaw_angles_deg: Optional[list[float]] = None,
        reset_before: bool = True,
    ) -> MultiViewScanResult:
        """
        Tiện ích test nhanh:
            truyền vào list file PLY và list góc yaw
            service tự add view rồi merge.
        """

        if reset_before:
            self.reset()

        if yaw_angles_deg is None:
            yaw_angles_deg = self.get_yaw_angles()

        if len(file_paths) != len(yaw_angles_deg):
            raise ValueError(
                "Số lượng file_paths phải bằng số lượng yaw_angles_deg."
            )

        for file_path, yaw in zip(file_paths, yaw_angles_deg):
            self.add_raw_file_view(
                file_path=file_path,
                yaw_deg=float(yaw),
            )

        return self.merge_views(save_output=True)

    # -------------------------------------------------
    # Getters
    # -------------------------------------------------
    def get_views(self) -> list[MultiViewScanView]:
        return self.views

    def get_last_view(self) -> Optional[MultiViewScanView]:
        if not self.views:
            return None

        return self.views[-1]

    def get_merged_cloud(self) -> o3d.geometry.PointCloud:
        if not self.has_merged_cloud():
            raise RuntimeError("Chưa có merged cloud. Hãy chạy merge_views() trước.")

        return self.merged_cloud

    def get_merged_path(self) -> Optional[Path]:
        return self.merged_path

    def get_merge_result(self) -> MultiViewMergeResult:
        if self.merge_result is None:
            raise RuntimeError("Chưa có kết quả merge.")

        return self.merge_result

    # -------------------------------------------------
    # Save helpers
    # -------------------------------------------------
    def _make_object_view_path(
        self,
        view_index: int,
        yaw_deg: float,
    ) -> Path:
        safe_yaw = self._format_angle(yaw_deg)

        file_name = (
            f"{self.params.object_filename_prefix}_"
            f"{view_index:02d}_Y{safe_yaw}.ply"
        )

        return self.session_dir / file_name

    def _write_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
        output_path: str | Path,
    ):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ok = o3d.io.write_point_cloud(
            str(output_path),
            cloud,
            write_ascii=False,
        )

        if not ok:
            raise RuntimeError(f"Không ghi được point cloud: {output_path}")

    def _write_summary(self):
        summary_path = self.session_dir / self.params.summary_filename

        data = {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "view_count": len(self.views),
            "target_view_count": int(self.params.view_count),
            "yaw_angles_deg": self.get_yaw_angles(),
            "merged_path": str(self.merged_path) if self.merged_path else None,
            "views": [
                {
                    "index": view.index,
                    "yaw_deg": view.yaw_deg,
                    "name": view.name,
                    "raw_path": view.raw_path,
                    "object_path": view.object_path,
                    "raw_point_count": view.raw_point_count,
                    "object_point_count": view.object_point_count,
                }
                for view in self.views
            ],
        }

        if self.merge_result is not None:
            data["merge"] = {
                "input_view_count": self.merge_result.input_view_count,
                "used_view_count": self.merge_result.used_view_count,
                "input_point_count": self.merge_result.input_point_count,
                "output_point_count": self.merge_result.output_point_count,
                "yaw_angles_used": self.merge_result.yaw_angles_used,
                "message": self.merge_result.message,
            }

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

    # -------------------------------------------------
    # Internal helpers
    # -------------------------------------------------
    def _make_session_id(self) -> str:
        return (
            f"{self.params.session_prefix}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    def _format_angle(self, value: float) -> str:
        text = f"{float(value):.1f}"
        text = text.replace("-", "m")
        text = text.replace(".", "p")
        return text

    def _validate_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
    ):
        if cloud is None:
            raise ValueError("Point cloud bị None.")

        if not isinstance(cloud, o3d.geometry.PointCloud):
            raise TypeError(
                "MultiViewScanService cần open3d.geometry.PointCloud, "
                f"nhưng nhận được: {type(cloud)}"
            )

        if len(cloud.points) <= 0:
            raise ValueError("Point cloud không có điểm hợp lệ.")