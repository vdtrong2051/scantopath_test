from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import csv
import numpy as np
import open3d as o3d


@dataclass
class ZigzagParams:
    """
    Thông số sinh đường Zigzag dựa trên surface mesh.

    Bản SAFE:
        - Sinh Zigzag từ TriangleMesh, không dùng point cloud rời rạc.
        - Cắt mesh bằng các mặt phẳng song song.
        - Tách segment riêng để không nối xuyên qua lỗ rỗng.
        - Giới hạn số mặt cắt, số segment và tổng số điểm để tránh crash.
        - Có tùy chọn lọc theo hướng pháp tuyến nếu cần mô phỏng hướng phun.

    path_spacing:
        Khoảng cách giữa các dải quét. Nếu <= 0 thì tự tính theo kích thước vật thể.

    point_step:
        Khoảng cách lấy mẫu trên mỗi segment. Nếu <= 0 thì tự tính theo kích thước vật thể.

    max_gap:
        Nếu khoảng cách giữa 2 điểm liên tiếp quá lớn thì cắt segment.
    """

    # Khoảng cách giữa các dải quét
    # Giá trị càng nhỏ → càng nhiều dải Zigzag → dày hơn nhưng nặng hơn
    path_spacing: float = 0.0
    adaptive_spacing_ratio: float = 0.020

    # Khoảng cách lấy mẫu trên mỗi đường
    # Giá trị càng nhỏ → mỗi đường có nhiều điểm hơn → mượt hơn nhưng nặng hơn
    point_step: float = 0.0
    adaptive_point_step_ratio: float = 0.008

    # Ngưỡng cắt đoạn để tránh nối qua lỗ rỗng / khe hở
    # Tăng lên nếu đường bị cắt quá vụn
    # Giảm xuống nếu đường nối bậy qua vùng rỗng
    max_gap: float = 0.0
    adaptive_max_gap_ratio: float = 0.055

    # Trục cắt và trục chạy
    # Mặc định:
    #   line_axis = 1  → cắt theo Y
    #   sort_axis = 0  → đường chạy theo X
    line_axis: int = 1
    sort_axis: int = 0

    # Bỏ bớt mặt cắt sát biên bounding box để giảm nhiễu mép
    trim_boundary_ratio: float = 0.02

    # Đảo chiều xen kẽ từng dải để tạo hiệu ứng Zigzag
    alternate_direction: bool = True

    # Giới hạn an toàn để không crash app
    max_planes: int = 45
    max_triangles_for_path: int = 35_000
    max_segments: int = 220
    max_total_path_points: int = 8_000

    # Segment path
    min_points_per_segment: int = 3
    max_points_per_segment: int = 120

    # Bỏ segment quá ngắn để tránh đường vụn / gai nhỏ
    min_segment_length: float = 0.0
    adaptive_min_segment_length_ratio: float = 0.012

    # Làm mượt nhẹ từng segment
    smooth_segments: bool = True
    smooth_window: int = 5

    # Tùy chọn lọc theo hướng pháp tuyến / hướng phun
    # Để False trước cho demo, tránh mất quá nhiều path
    use_direction_filter: bool = False
    spray_direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    min_normal_dot: float = 0.15

    # Path dùng riêng cho hiển thị:
    # Nâng đường dẫn khỏi mesh một chút để không bị chìm / z-fighting.
    display_lift_offset: float = 0.0
    adaptive_display_lift_ratio: float = 0.018


@dataclass
class ZigzagPathResult:
    source_mesh: o3d.geometry.TriangleMesh

    path_points: np.ndarray
    path_normals: np.ndarray
    path_poses: np.ndarray

    path_segments: list[np.ndarray]
    normal_segments: list[np.ndarray]

    # Dùng cho viewport/thuyết trình:
    # Đây là path đã được nâng ra khỏi mesh theo normal.
    display_path_segments: list[np.ndarray]

    path_count: int
    line_count: int
    segment_count: int
    path_length: float

    path_spacing: float
    point_step: float
    max_gap: float

    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    method: str
    message: str


class ZigzagGenerator:
    """
    Safe Mesh-based Zigzag Generator.

    Luồng:
        TriangleMesh
        → simplify nếu mesh quá nặng
        → cắt mesh bằng nhiều mặt phẳng song song
        → lấy giao tuyến trên surface
        → sort theo trục chạy
        → tách segment nếu gặp gap/lỗ rỗng
        → resample segment
        → giới hạn tổng số điểm để app không crash

    Đầu ra mỗi điểm path:
        x, y, z, nx, ny, nz
    """

    def __init__(self, params: Optional[ZigzagParams] = None):
        self.params = params or ZigzagParams()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def generate(
        self,
        mesh: Optional[o3d.geometry.TriangleMesh] = None,
        params: Optional[ZigzagParams] = None,
        point_cloud=None,
    ) -> ZigzagPathResult:
        """
        Giữ hàm generate để tương thích code cũ.

        Bản mới yêu cầu TriangleMesh.
        point_cloud chỉ giữ lại để tránh vỡ chữ ký hàm.
        """

        if mesh is None and isinstance(point_cloud, o3d.geometry.TriangleMesh):
            mesh = point_cloud

        if mesh is None:
            raise ValueError(
                "Mesh-based Zigzag cần đầu vào là TriangleMesh. "
                "Hãy tạo bản đồ bề mặt 3D trước khi sinh Zigzag."
            )

        return self.generate_from_mesh(mesh=mesh, params=params)

    def generate_from_mesh(
        self,
        mesh: o3d.geometry.TriangleMesh,
        params: Optional[ZigzagParams] = None,
    ) -> ZigzagPathResult:
        params = params or self.params

        working_mesh = self._prepare_mesh(mesh, params)
        self._validate_mesh(working_mesh)

        vertices = np.asarray(working_mesh.vertices, dtype=np.float64)
        triangles = np.asarray(working_mesh.triangles, dtype=np.int32)
        vertex_normals = np.asarray(working_mesh.vertex_normals, dtype=np.float64)

        bounds_min = vertices.min(axis=0)
        bounds_max = vertices.max(axis=0)
        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        max_size = float(np.max(size))
        if max_size <= 0:
            max_size = 1.0

        path_spacing = self._resolve_adaptive_value(
            value=params.path_spacing,
            ratio=params.adaptive_spacing_ratio,
            max_size=max_size,
        )

        point_step = self._resolve_adaptive_value(
            value=params.point_step,
            ratio=params.adaptive_point_step_ratio,
            max_size=max_size,
        )

        max_gap = self._resolve_adaptive_value(
            value=params.max_gap,
            ratio=params.adaptive_max_gap_ratio,
            max_size=max_size,
        )

        min_segment_length = self._resolve_adaptive_value(
            value=params.min_segment_length,
            ratio=params.adaptive_min_segment_length_ratio,
            max_size=max_size,
        )

        display_lift_offset = self._resolve_adaptive_value(
            value=params.display_lift_offset,
            ratio=params.adaptive_display_lift_ratio,
            max_size=max_size,
        )

        if path_spacing <= 0:
            raise ValueError("path_spacing không hợp lệ.")

        if point_step <= 0:
            raise ValueError("point_step không hợp lệ.")

        line_axis = params.line_axis
        sort_axis = params.sort_axis

        axis_min = bounds_min[line_axis]
        axis_max = bounds_max[line_axis]
        axis_range = axis_max - axis_min

        trim = axis_range * params.trim_boundary_ratio
        slice_min = axis_min + trim
        slice_max = axis_max - trim

        if slice_max <= slice_min:
            slice_min = axis_min
            slice_max = axis_max

        plane_values = self._build_plane_values(
            slice_min=slice_min,
            slice_max=slice_max,
            spacing=path_spacing,
            max_planes=params.max_planes,
        )

        path_segments: list[np.ndarray] = []
        normal_segments: list[np.ndarray] = []

        valid_line_count = 0
        reverse_line = False

        for plane_value in plane_values:
            line_segments, line_normal_segments = self._slice_mesh_into_ordered_paths(
                vertices=vertices,
                triangles=triangles,
                vertex_normals=vertex_normals,
                plane_axis=line_axis,
                plane_value=plane_value,
                sort_axis=sort_axis,
                reverse=reverse_line,
                params=params,
                point_step=point_step,
                max_gap=max_gap,
                min_segment_length=min_segment_length,
            )

            if not line_segments:
                continue

            path_segments.extend(line_segments)
            normal_segments.extend(line_normal_segments)

            valid_line_count += 1

            if params.alternate_direction:
                reverse_line = not reverse_line

        if not path_segments:
            raise ValueError(
                "Không thể sinh đường Zigzag từ surface mesh. "
                "Hãy kiểm tra mesh hoặc giảm path_spacing."
            )

        path_segments, normal_segments = self._enforce_global_limits(
            path_segments=path_segments,
            normal_segments=normal_segments,
            max_segments=params.max_segments,
            max_total_points=params.max_total_path_points,
            min_points=params.min_points_per_segment,
        )

        # Path gốc dùng để export / tính toán
        path_points = np.vstack(path_segments)
        path_normals = np.vstack(normal_segments)
        path_normals = self._normalize_vectors(path_normals)

        path_poses = np.hstack([path_points, path_normals])
        path_length = self._compute_segments_length(path_segments)

        # Path đã nâng khỏi mesh để hiển thị rõ trên viewport
        display_path_segments = self._build_display_path_segments(
            path_segments=path_segments,
            normal_segments=normal_segments,
            lift_offset=display_lift_offset,
        )

        return ZigzagPathResult(
            source_mesh=working_mesh,
            path_points=path_points,
            path_normals=path_normals,
            path_poses=path_poses,
            path_segments=path_segments,
            normal_segments=normal_segments,
            display_path_segments=display_path_segments,
            path_count=len(path_points),
            line_count=valid_line_count,
            segment_count=len(path_segments),
            path_length=path_length,
            path_spacing=path_spacing,
            point_step=point_step,
            max_gap=max_gap,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            method="safe_mesh_slicing",
            message=(
                f"Đã sinh Zigzag an toàn từ surface mesh: "
                f"{len(path_points)} điểm, "
                f"{valid_line_count} dải quét, "
                f"{len(path_segments)} đoạn, "
                f"L = {path_length:.3f}."
            ),
        )

    def export_csv(
        self,
        result: ZigzagPathResult,
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            writer.writerow([
                "segment_id",
                "point_id",
                "x", "y", "z",
                "nx", "ny", "nz",
            ])

            for seg_idx, (seg_points, seg_normals) in enumerate(
                zip(result.path_segments, result.normal_segments)
            ):
                seg_normals = self._normalize_vectors(seg_normals)

                for point_idx, (point, normal) in enumerate(
                    zip(seg_points, seg_normals)
                ):
                    writer.writerow([
                        seg_idx,
                        point_idx,
                        float(point[0]),
                        float(point[1]),
                        float(point[2]),
                        float(normal[0]),
                        float(normal[1]),
                        float(normal[2]),
                    ])

        return path

    # -------------------------------------------------
    # Mesh preparation
    # -------------------------------------------------
    def _prepare_mesh(
        self,
        mesh: o3d.geometry.TriangleMesh,
        params: ZigzagParams,
    ) -> o3d.geometry.TriangleMesh:
        working_mesh = o3d.geometry.TriangleMesh(mesh)

        if len(working_mesh.vertices) <= 0:
            raise ValueError("Surface mesh không có vertex.")

        if len(working_mesh.triangles) <= 0:
            raise ValueError("Surface mesh không có triangle.")

        working_mesh.remove_duplicated_vertices()
        working_mesh.remove_duplicated_triangles()
        working_mesh.remove_degenerate_triangles()
        working_mesh.remove_unreferenced_vertices()

        if len(working_mesh.triangles) > params.max_triangles_for_path:
            working_mesh = working_mesh.simplify_quadric_decimation(
                target_number_of_triangles=params.max_triangles_for_path
            )

            working_mesh.remove_duplicated_vertices()
            working_mesh.remove_duplicated_triangles()
            working_mesh.remove_degenerate_triangles()
            working_mesh.remove_unreferenced_vertices()

        working_mesh.compute_vertex_normals()
        working_mesh.compute_triangle_normals()

        try:
            working_mesh.normalize_normals()
        except Exception:
            pass

        return working_mesh

    def _validate_mesh(self, mesh: o3d.geometry.TriangleMesh):
        if mesh is None:
            raise ValueError("Surface mesh đầu vào bị rỗng.")

        if len(mesh.vertices) <= 0:
            raise ValueError("Surface mesh không có vertex.")

        if len(mesh.triangles) <= 0:
            raise ValueError("Surface mesh không có triangle.")

        if not mesh.has_vertex_normals():
            raise ValueError("Surface mesh chưa có vertex normals.")

    # -------------------------------------------------
    # Plane slicing
    # -------------------------------------------------
    def _intersect_mesh_with_plane(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        vertex_normals: np.ndarray,
        plane_axis: int,
        plane_value: float,
        params: ZigzagParams,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Cắt mesh bằng mặt phẳng coordinate[plane_axis] = plane_value.

        Bản này dùng xử lý vectorized theo từng edge để nhẹ hơn
        so với loop từng triangle quá sâu.
        """

        tri_vertices = vertices[triangles]          # (T, 3, 3)
        tri_normals = vertex_normals[triangles]    # (T, 3, 3)

        all_points = []
        all_normals = []
        all_tri_ids = []

        edges = (
            (0, 1),
            (1, 2),
            (2, 0),
        )

        for edge_start, edge_end in edges:
            p0 = tri_vertices[:, edge_start, :]
            p1 = tri_vertices[:, edge_end, :]

            n0 = tri_normals[:, edge_start, :]
            n1 = tri_normals[:, edge_end, :]

            d0 = p0[:, plane_axis] - plane_value
            d1 = p1[:, plane_axis] - plane_value

            # Chỉ lấy edge thật sự cắt mặt phẳng.
            # Bỏ trường hợp nằm đúng trên plane để tránh trùng/lỗi nhiễu.
            mask = d0 * d1 < 0.0

            if not np.any(mask):
                continue

            t = d0[mask] / (d0[mask] - d1[mask])

            p = p0[mask] + t[:, None] * (p1[mask] - p0[mask])
            n = n0[mask] + t[:, None] * (n1[mask] - n0[mask])

            tri_ids = np.nonzero(mask)[0]

            all_points.append(p)
            all_normals.append(n)
            all_tri_ids.append(tri_ids)

        if not all_points:
            return (
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 3), dtype=np.float64),
            )

        points = np.vstack(all_points)
        normals = np.vstack(all_normals)
        tri_ids = np.concatenate(all_tri_ids)

        # Mỗi triangle cắt plane thường tạo 2 điểm.
        # Ta gom theo triangle rồi lấy cặp giao điểm xa nhất.
        order = np.argsort(tri_ids)
        tri_ids = tri_ids[order]
        points = points[order]
        normals = normals[order]

        unique_ids, start_indices, counts = np.unique(
            tri_ids,
            return_index=True,
            return_counts=True,
        )

        segment_points = []
        segment_normals = []

        spray_dir = np.asarray(params.spray_direction, dtype=np.float64)
        spray_norm = np.linalg.norm(spray_dir)

        if spray_norm > 0:
            spray_dir = spray_dir / spray_norm
        else:
            spray_dir = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        for start, count in zip(start_indices, counts):
            if count < 2:
                continue

            group_points = points[start:start + count]
            group_normals = normals[start:start + count]

            p_a, n_a, p_b, n_b = self._pick_farthest_pair(
                points=group_points,
                normals=group_normals,
            )

            avg_normal = self._normalize_vector((n_a + n_b) * 0.5)

            if params.use_direction_filter:
                normal_dot = float(np.dot(avg_normal, spray_dir))

                if normal_dot < params.min_normal_dot:
                    continue

            segment_points.append(p_a)
            segment_points.append(p_b)

            segment_normals.append(n_a)
            segment_normals.append(n_b)

        if not segment_points:
            return (
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 3), dtype=np.float64),
            )

        segment_points = np.asarray(segment_points, dtype=np.float64)
        segment_normals = np.asarray(segment_normals, dtype=np.float64)

        segment_points, segment_normals = self._deduplicate_points(
            segment_points,
            segment_normals,
        )

        return segment_points, self._normalize_vectors(segment_normals)

    # -------------------------------------------------
    # Segment processing
    # -------------------------------------------------
    def _sort_split_and_sample(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        sort_axis: int,
        reverse: bool,
        max_gap: float,
        point_step: float,
        min_points: int,
        max_points: int,
        min_segment_length: float,
        smooth: bool,
        smooth_window: int,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        if len(points) < min_points:
            return [], []

        order = np.argsort(points[:, sort_axis])

        if reverse:
            order = order[::-1]

        points = points[order]
        normals = normals[order]

        diff = np.diff(points, axis=0)
        dist = np.linalg.norm(diff, axis=1)

        split_indices = np.where(dist > max_gap)[0] + 1

        point_segments = np.split(points, split_indices)
        normal_segments = np.split(normals, split_indices)

        valid_point_segments = []
        valid_normal_segments = []

        for seg_points, seg_normals in zip(point_segments, normal_segments):
            if len(seg_points) < min_points:
                continue

            length = self._compute_polyline_length(seg_points)

            if length < min_segment_length:
                continue

            seg_points, seg_normals = self._resample_polyline(
                points=seg_points,
                normals=seg_normals,
                point_step=point_step,
                max_points=max_points,
            )

            if len(seg_points) < min_points:
                continue

            if smooth:
                seg_points = self._smooth_segment(
                    points=seg_points,
                    window=smooth_window,
                )

            seg_normals = self._normalize_vectors(seg_normals)

            valid_point_segments.append(
                np.ascontiguousarray(seg_points, dtype=np.float64)
            )
            valid_normal_segments.append(
                np.ascontiguousarray(seg_normals, dtype=np.float64)
            )

        return valid_point_segments, valid_normal_segments

    def _resample_polyline(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        point_step: float,
        max_points: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(points) <= 1:
            return points, normals

        diff = np.diff(points, axis=0)
        dist = np.linalg.norm(diff, axis=1)

        cumulative = np.concatenate([[0.0], np.cumsum(dist)])
        total_length = float(cumulative[-1])

        if total_length <= 1e-9:
            return points[:1], normals[:1]

        target_count = max(2, int(np.ceil(total_length / point_step)) + 1)
        target_count = min(target_count, max_points)

        sample_distances = np.linspace(0.0, total_length, target_count)

        sampled_points = np.zeros((target_count, 3), dtype=np.float64)
        sampled_normals = np.zeros((target_count, 3), dtype=np.float64)

        for axis in range(3):
            sampled_points[:, axis] = np.interp(
                sample_distances,
                cumulative,
                points[:, axis],
            )

            sampled_normals[:, axis] = np.interp(
                sample_distances,
                cumulative,
                normals[:, axis],
            )

        sampled_normals = self._normalize_vectors(sampled_normals)

        return sampled_points, sampled_normals

    def _smooth_segment(
        self,
        points: np.ndarray,
        window: int,
    ) -> np.ndarray:
        if window <= 1:
            return points

        if len(points) < window:
            return points

        if window % 2 == 0:
            window += 1

        pad = window // 2
        kernel = np.ones(window, dtype=np.float64) / window

        padded = np.pad(
            points,
            pad_width=((pad, pad), (0, 0)),
            mode="edge",
        )

        smoothed = np.zeros_like(points)

        for axis in range(3):
            smoothed[:, axis] = np.convolve(
                padded[:, axis],
                kernel,
                mode="valid",
            )

        # Giữ đầu/cuối để không co đường quá mức
        smoothed[0] = points[0]
        smoothed[-1] = points[-1]

        return smoothed

    def _enforce_global_limits(
        self,
        path_segments: list[np.ndarray],
        normal_segments: list[np.ndarray],
        max_segments: int,
        max_total_points: int,
        min_points: int,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """
        Giới hạn tổng số segment và tổng số điểm để tránh crash viewport.
        """

        if not path_segments:
            return path_segments, normal_segments

        # Giới hạn số segment, lấy đều trên toàn bộ danh sách để giữ coverage.
        if len(path_segments) > max_segments:
            keep_indices = np.linspace(
                0,
                len(path_segments) - 1,
                max_segments,
                dtype=int,
            )

            path_segments = [path_segments[i] for i in keep_indices]
            normal_segments = [normal_segments[i] for i in keep_indices]

        total_points = sum(len(seg) for seg in path_segments)

        if total_points <= max_total_points:
            return path_segments, normal_segments

        segment_count = len(path_segments)
        points_per_segment = max(
            min_points,
            max_total_points // max(segment_count, 1),
        )

        limited_segments = []
        limited_normals = []

        for seg_points, seg_normals in zip(path_segments, normal_segments):
            if len(seg_points) <= points_per_segment:
                limited_segments.append(seg_points)
                limited_normals.append(seg_normals)
                continue

            indices = np.linspace(
                0,
                len(seg_points) - 1,
                points_per_segment,
                dtype=int,
            )

            limited_segments.append(seg_points[indices])
            limited_normals.append(seg_normals[indices])

        return limited_segments, limited_normals

    # -------------------------------------------------
    # Export / math helpers
    # -------------------------------------------------
    def _build_plane_values(
        self,
        slice_min: float,
        slice_max: float,
        spacing: float,
        max_planes: int,
    ) -> np.ndarray:
        if slice_max <= slice_min:
            return np.asarray([slice_min], dtype=np.float64)

        estimated_count = int(np.floor((slice_max - slice_min) / spacing)) + 1
        estimated_count = max(2, estimated_count)

        if estimated_count > max_planes:
            return np.linspace(
                slice_min,
                slice_max,
                max_planes,
                dtype=np.float64,
            )

        return np.arange(
            slice_min,
            slice_max + spacing,
            spacing,
            dtype=np.float64,
        )

    def _resolve_adaptive_value(
        self,
        value: float,
        ratio: float,
        max_size: float,
    ) -> float:
        if value > 0:
            return float(value)

        return float(max_size * ratio)

    def _deduplicate_points(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        decimals: int = 6,
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(points) == 0:
            return points, normals

        rounded = np.round(points, decimals=decimals)

        _, unique_indices = np.unique(
            rounded,
            axis=0,
            return_index=True,
        )

        unique_indices = np.sort(unique_indices)

        return points[unique_indices], normals[unique_indices]

    def _pick_farthest_pair(
        self,
        points: np.ndarray,
        normals: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        count = len(points)

        if count == 2:
            return points[0], normals[0], points[1], normals[1]

        max_dist = -1.0
        best_i = 0
        best_j = 1

        for i in range(count):
            for j in range(i + 1, count):
                dist = float(np.linalg.norm(points[j] - points[i]))

                if dist > max_dist:
                    max_dist = dist
                    best_i = i
                    best_j = j

        return (
            points[best_i],
            normals[best_i],
            points[best_j],
            normals[best_j],
        )

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        norm = float(np.linalg.norm(vector))

        if norm <= 1e-12:
            return vector

        return vector / norm

    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        if len(vectors) == 0:
            return vectors

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0

        return vectors / norms

    def _compute_polyline_length(self, points: np.ndarray) -> float:
        if len(points) < 2:
            return 0.0

        diff = np.diff(points, axis=0)
        dist = np.linalg.norm(diff, axis=1)

        return float(dist.sum())

    def _compute_segments_length(
        self,
        path_segments: list[np.ndarray],
    ) -> float:
        total = 0.0

        for segment in path_segments:
            total += self._compute_polyline_length(segment)

        return total
    
    def _build_display_path_segments(
        self,
        path_segments: list[np.ndarray],
        normal_segments: list[np.ndarray],
        lift_offset: float,
    ) -> list[np.ndarray]:
        """
        Tạo path riêng cho hiển thị.

        Mục đích:
            - Path gốc vẫn nằm đúng trên surface để export.
            - Path hiển thị được nâng lên theo normal để không bị chìm trong mesh.
        """

        display_segments = []

        for seg_points, seg_normals in zip(path_segments, normal_segments):
            if seg_points is None or len(seg_points) < 2:
                continue

            points = np.asarray(seg_points, dtype=np.float64)
            normals = np.asarray(seg_normals, dtype=np.float64)

            if normals.ndim != 2 or normals.shape[1] != 3:
                display_segments.append(points)
                continue

            if len(normals) != len(points):
                display_segments.append(points)
                continue

            normals = self._normalize_vectors(normals)

            lifted_points = points + normals * float(lift_offset)

            display_segments.append(
                np.ascontiguousarray(lifted_points, dtype=np.float64)
            )

        return display_segments
    
    def _slice_mesh_into_ordered_paths(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        vertex_normals: np.ndarray,
        plane_axis: int,
        plane_value: float,
        sort_axis: int,
        reverse: bool,
        params: ZigzagParams,
        point_step: float,
        max_gap: float,
        min_segment_length: float,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """
        Cắt mesh bằng 1 mặt phẳng và tạo các polyline liên tục.

        Khác với cách cũ:
            - Không sort toàn bộ điểm giao một cách thô.
            - Mỗi triangle tạo 1 đoạn giao tuyến.
            - Các đoạn giao tuyến được nối lại theo endpoint chung.
            - Kết quả là các đường path liên tục, ít rối hơn.
        """

        raw_segments, raw_normal_segments = self._intersect_mesh_with_plane_as_segments(
            vertices=vertices,
            triangles=triangles,
            vertex_normals=vertex_normals,
            plane_axis=plane_axis,
            plane_value=plane_value,
            params=params,
        )

        if len(raw_segments) <= 0:
            return [], []

        polylines, normal_polylines = self._chain_intersection_segments(
            segment_points=raw_segments,
            segment_normals=raw_normal_segments,
            decimals=6,
        )

        if not polylines:
            return [], []

        final_segments = []
        final_normals = []

        for points, normals in zip(polylines, normal_polylines):
            if len(points) < params.min_points_per_segment:
                continue

            points, normals = self._orient_polyline(
                points=points,
                normals=normals,
                sort_axis=sort_axis,
                reverse=reverse,
            )

            split_segments, split_normals = self._split_resample_smooth_polyline(
                points=points,
                normals=normals,
                max_gap=max_gap,
                point_step=point_step,
                min_points=params.min_points_per_segment,
                max_points=params.max_points_per_segment,
                min_segment_length=min_segment_length,
                smooth=params.smooth_segments,
                smooth_window=params.smooth_window,
            )

            final_segments.extend(split_segments)
            final_normals.extend(split_normals)

        return final_segments, final_normals


    def _intersect_mesh_with_plane_as_segments(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        vertex_normals: np.ndarray,
        plane_axis: int,
        plane_value: float,
        params: ZigzagParams,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Trả về các đoạn giao tuyến nhỏ của từng triangle với mặt phẳng.

        Output:
            segment_points:  shape (M, 2, 3)
            segment_normals: shape (M, 2, 3)
        """

        tri_vertices = vertices[triangles]
        tri_normals = vertex_normals[triangles]

        all_points = []
        all_normals = []
        all_tri_ids = []

        edges = (
            (0, 1),
            (1, 2),
            (2, 0),
        )

        for edge_start, edge_end in edges:
            p0 = tri_vertices[:, edge_start, :]
            p1 = tri_vertices[:, edge_end, :]

            n0 = tri_normals[:, edge_start, :]
            n1 = tri_normals[:, edge_end, :]

            d0 = p0[:, plane_axis] - plane_value
            d1 = p1[:, plane_axis] - plane_value

            mask = d0 * d1 < 0.0

            if not np.any(mask):
                continue

            t = d0[mask] / (d0[mask] - d1[mask])

            p = p0[mask] + t[:, None] * (p1[mask] - p0[mask])
            n = n0[mask] + t[:, None] * (n1[mask] - n0[mask])

            tri_ids = np.nonzero(mask)[0]

            all_points.append(p)
            all_normals.append(n)
            all_tri_ids.append(tri_ids)

        if not all_points:
            return (
                np.empty((0, 2, 3), dtype=np.float64),
                np.empty((0, 2, 3), dtype=np.float64),
            )

        points = np.vstack(all_points)
        normals = np.vstack(all_normals)
        tri_ids = np.concatenate(all_tri_ids)

        order = np.argsort(tri_ids)
        tri_ids = tri_ids[order]
        points = points[order]
        normals = normals[order]

        _, start_indices, counts = np.unique(
            tri_ids,
            return_index=True,
            return_counts=True,
        )

        spray_dir = np.asarray(params.spray_direction, dtype=np.float64)
        spray_norm = np.linalg.norm(spray_dir)

        if spray_norm > 0:
            spray_dir = spray_dir / spray_norm
        else:
            spray_dir = np.array([0.0, 0.0, 1.0], dtype=np.float64)

        segment_points = []
        segment_normals = []

        for start, count in zip(start_indices, counts):
            if count < 2:
                continue

            group_points = points[start:start + count]
            group_normals = normals[start:start + count]

            p_a, n_a, p_b, n_b = self._pick_farthest_pair(
                points=group_points,
                normals=group_normals,
            )

            if float(np.linalg.norm(p_b - p_a)) <= 1e-12:
                continue

            avg_normal = self._normalize_vector((n_a + n_b) * 0.5)

            if params.use_direction_filter:
                normal_dot = float(np.dot(avg_normal, spray_dir))

                if normal_dot < params.min_normal_dot:
                    continue

            segment_points.append([p_a, p_b])
            segment_normals.append([n_a, n_b])

        if not segment_points:
            return (
                np.empty((0, 2, 3), dtype=np.float64),
                np.empty((0, 2, 3), dtype=np.float64),
            )

        return (
            np.asarray(segment_points, dtype=np.float64),
            self._normalize_vectors(
                np.asarray(segment_normals, dtype=np.float64).reshape(-1, 3)
            ).reshape(-1, 2, 3),
        )


    def _chain_intersection_segments(
        self,
        segment_points: np.ndarray,
        segment_normals: np.ndarray,
        decimals: int = 6,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """
        Nối các đoạn giao tuyến nhỏ thành polyline liên tục.

        Đây là phần quan trọng để đường Zigzag không bị rối.
        """

        if len(segment_points) == 0:
            return [], []

        node_index = {}
        node_points = []
        node_normals = []
        node_counts = []

        edges = []

        def get_node(point: np.ndarray, normal: np.ndarray) -> int:
            key = tuple(np.round(point, decimals=decimals))

            if key not in node_index:
                idx = len(node_points)
                node_index[key] = idx
                node_points.append(np.asarray(point, dtype=np.float64))
                node_normals.append(np.asarray(normal, dtype=np.float64))
                node_counts.append(1)
                return idx

            idx = node_index[key]
            node_points[idx] += point
            node_normals[idx] += normal
            node_counts[idx] += 1
            return idx

        for seg_points, seg_normals in zip(segment_points, segment_normals):
            a = get_node(seg_points[0], seg_normals[0])
            b = get_node(seg_points[1], seg_normals[1])

            if a != b:
                edges.append((a, b))

        if not edges:
            return [], []

        node_points = np.asarray(
            [p / c for p, c in zip(node_points, node_counts)],
            dtype=np.float64,
        )

        node_normals = np.asarray(
            [n / c for n, c in zip(node_normals, node_counts)],
            dtype=np.float64,
        )
        node_normals = self._normalize_vectors(node_normals)

        adjacency: dict[int, list[tuple[int, int]]] = {
            i: [] for i in range(len(node_points))
        }

        for edge_id, (a, b) in enumerate(edges):
            adjacency[a].append((edge_id, b))
            adjacency[b].append((edge_id, a))

        used_edges = set()

        def trace_from(start_node: int) -> list[int]:
            chain = [start_node]
            current = start_node

            while True:
                candidates = [
                    (edge_id, next_node)
                    for edge_id, next_node in adjacency[current]
                    if edge_id not in used_edges
                ]

                if not candidates:
                    break

                edge_id, next_node = candidates[0]
                used_edges.add(edge_id)

                current = next_node
                chain.append(current)

                # Đóng vòng thì dừng.
                if current == start_node and len(chain) > 2:
                    break

            return chain

        polylines = []
        normal_polylines = []

        # Ưu tiên đi từ đầu hở để tạo line-strip dễ hiểu.
        open_nodes = [
            node_id
            for node_id, items in adjacency.items()
            if len(items) == 1
        ]

        for node_id in open_nodes:
            has_unused = any(
                edge_id not in used_edges
                for edge_id, _ in adjacency[node_id]
            )

            if not has_unused:
                continue

            chain = trace_from(node_id)

            if len(chain) >= 2:
                polylines.append(node_points[chain])
                normal_polylines.append(node_normals[chain])

        # Xử lý các vòng kín còn lại.
        for edge_id, (a, _) in enumerate(edges):
            if edge_id in used_edges:
                continue

            chain = trace_from(a)

            if len(chain) >= 2:
                polylines.append(node_points[chain])
                normal_polylines.append(node_normals[chain])

        return polylines, normal_polylines


    def _orient_polyline(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        sort_axis: int,
        reverse: bool,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Định hướng polyline theo trục chạy.
        """

        if len(points) < 2:
            return points, normals

        # Với vòng kín, xoay điểm bắt đầu về phía min sort_axis.
        if np.linalg.norm(points[0] - points[-1]) < 1e-8 and len(points) > 3:
            points_no_dup = points[:-1]
            normals_no_dup = normals[:-1]

            start_idx = int(np.argmin(points_no_dup[:, sort_axis]))

            points = np.concatenate([
                points_no_dup[start_idx:],
                points_no_dup[:start_idx],
                points_no_dup[start_idx:start_idx + 1],
            ])

            normals = np.concatenate([
                normals_no_dup[start_idx:],
                normals_no_dup[:start_idx],
                normals_no_dup[start_idx:start_idx + 1],
            ])

        if points[0, sort_axis] > points[-1, sort_axis]:
            points = points[::-1]
            normals = normals[::-1]

        if reverse:
            points = points[::-1]
            normals = normals[::-1]

        return points, normals


    def _split_resample_smooth_polyline(
        self,
        points: np.ndarray,
        normals: np.ndarray,
        max_gap: float,
        point_step: float,
        min_points: int,
        max_points: int,
        min_segment_length: float,
        smooth: bool,
        smooth_window: int,
    ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """
        Cắt polyline theo gap lớn, rồi resample và smooth.
        Không sort lại điểm, vì thứ tự đã được nối theo topology mesh.
        """

        if len(points) < min_points:
            return [], []

        diff = np.diff(points, axis=0)
        dist = np.linalg.norm(diff, axis=1)

        split_indices = np.where(dist > max_gap)[0] + 1

        point_segments = np.split(points, split_indices)
        normal_segments = np.split(normals, split_indices)

        valid_point_segments = []
        valid_normal_segments = []

        for seg_points, seg_normals in zip(point_segments, normal_segments):
            if len(seg_points) < min_points:
                continue

            length = self._compute_polyline_length(seg_points)

            if length < min_segment_length:
                continue

            seg_points, seg_normals = self._resample_polyline(
                points=seg_points,
                normals=seg_normals,
                point_step=point_step,
                max_points=max_points,
            )

            if len(seg_points) < min_points:
                continue

            if smooth:
                seg_points = self._smooth_segment(
                    points=seg_points,
                    window=smooth_window,
                )

            seg_normals = self._normalize_vectors(seg_normals)

            valid_point_segments.append(
                np.ascontiguousarray(seg_points, dtype=np.float64)
            )
            valid_normal_segments.append(
                np.ascontiguousarray(seg_normals, dtype=np.float64)
            )

        return valid_point_segments, valid_normal_segments