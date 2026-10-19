from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class SurfaceMapParams:
    """
    Thông số tạo bản đồ bề mặt 3D.

    method:
        "poisson" -> ưu tiên demo / thuyết trình, mesh liền khối, dễ nhìn.
        "bpa"     -> giữ lỗ tốt hơn, nhưng dễ rỗ/mảnh nếu point cloud thưa.
        "auto"    -> thử Poisson trước, nếu lỗi thì fallback sang BPA.

    Ghi chú tài nguyên để đổi nhanh sau này:

        LOW_RAM:
            method="poisson"
            max_input_points=25_000
            poisson_depth=6
            target_triangles=25_000
            smooth_iterations=1

        DEMO_STABLE:
            method="poisson"
            max_input_points=45_000
            poisson_depth=7
            target_triangles=45_000
            smooth_iterations=1

        DETAIL_HIGH:
            method="poisson"
            max_input_points=70_000
            poisson_depth=8
            target_triangles=80_000
            smooth_iterations=1 hoặc 2

        PRESERVE_HOLES:
            method="bpa"
            max_input_points=45_000
            bpa_radius_factor_1=2.0
            bpa_radius_factor_2=3.5
            bpa_radius_factor_3=6.0

    Khuyến nghị hiện tại:
        Dùng DEMO_STABLE để thuyết trình.
    """

    # Với demo/thuyết trình: ưu tiên Poisson để mesh liền khối hơn.
    # Nếu muốn giữ lỗ mạnh hơn thì đổi thành "bpa".
    method: str = "poisson"

    # Giới hạn point cloud đầu vào để tránh crash.
    max_input_points: int = 45_000

    # Voxel downsample thích nghi.
    use_voxel_downsample: bool = True
    voxel_size: float = 0.0
    adaptive_voxel_ratio: float = 0.0035

    # Normal.
    force_recompute_normals: bool = False
    normal_radius: float = 0.0
    adaptive_normal_radius_ratio: float = 0.025
    normal_max_nn: int = 30
    orient_normals: bool = True
    orient_k: int = 20

    # BPA - Ball Pivoting.
    bpa_neighbor_sample: int = 6000
    bpa_radius_factor_1: float = 2.0
    bpa_radius_factor_2: float = 3.5
    bpa_radius_factor_3: float = 6.0

    # Poisson.
    poisson_depth: int = 7
    poisson_scale: float = 1.05
    poisson_linear_fit: bool = False
    density_quantile: float = 0.08

    # Crop mesh theo bounding box point cloud.
    crop_to_cloud_bbox: bool = True
    crop_padding_ratio: float = 0.03

    # Mesh cleanup / simplification.
    simplify_mesh: bool = True
    target_triangles: int = 45_000

    # Làm mượt nhẹ để mesh nhìn liền khối hơn.
    smooth_iterations: int = 1

    # Mặc định tắt để tránh xóa nhầm chi tiết nhỏ bị tách cụm.
    # Nếu scan có nhiều mảnh rác nhỏ thì bật True.
    keep_largest_component: bool = False
    min_component_triangle_ratio: float = 0.003


@dataclass
class SurfaceMapResult:
    input_cloud: o3d.geometry.PointCloud
    working_cloud: o3d.geometry.PointCloud
    mesh: o3d.geometry.TriangleMesh

    vertex_count: int
    triangle_count: int

    input_point_count: int
    working_point_count: int

    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    method: str
    message: str


def get_surface_map_params_preset(mode: str = "demo") -> SurfaceMapParams:
    """
    Lấy nhanh preset tài nguyên cho SurfaceMapBuilder.

    Cách dùng sau này:
        params = get_surface_map_params_preset("low_ram")
        result = surface_map_service.build_surface_map(normal_cloud, params=params)

    Các mode:
        "low_ram"
        "demo"
        "detail"
        "holes"
    """

    mode = mode.lower().strip()

    if mode in ("low", "low_ram", "safe"):
        return SurfaceMapParams(
            method="poisson",
            max_input_points=25_000,
            adaptive_voxel_ratio=0.005,
            poisson_depth=6,
            density_quantile=0.08,
            target_triangles=25_000,
            smooth_iterations=1,
            keep_largest_component=False,
        )

    if mode in ("detail", "high", "quality"):
        return SurfaceMapParams(
            method="poisson",
            max_input_points=70_000,
            adaptive_voxel_ratio=0.0025,
            poisson_depth=8,
            density_quantile=0.06,
            target_triangles=80_000,
            smooth_iterations=1,
            keep_largest_component=False,
        )

    if mode in ("holes", "bpa", "preserve_holes"):
        return SurfaceMapParams(
            method="bpa",
            max_input_points=45_000,
            adaptive_voxel_ratio=0.0035,
            bpa_radius_factor_1=2.0,
            bpa_radius_factor_2=3.5,
            bpa_radius_factor_3=6.0,
            target_triangles=45_000,
            smooth_iterations=0,
            keep_largest_component=False,
        )

    # Default: demo stable.
    return SurfaceMapParams(
        method="poisson",
        max_input_points=45_000,
        adaptive_voxel_ratio=0.0035,
        poisson_depth=7,
        density_quantile=0.08,
        target_triangles=45_000,
        smooth_iterations=1,
        keep_largest_component=False,
    )


class SurfaceMapBuilder:
    """
    Tạo bản đồ bề mặt 3D từ point cloud đã có pháp tuyến.

    Bản này ưu tiên:
        - Tạo mesh liền khối để thuyết trình rõ.
        - Không giữ point cloud/normal trong viewport.
        - Giới hạn số điểm và số tam giác để tránh crash.
        - Có thể đổi sang BPA nếu cần giữ lỗ rỗng tốt hơn.
    """

    def __init__(self, params: Optional[SurfaceMapParams] = None):
        self.params = params or SurfaceMapParams()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def build(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: Optional[SurfaceMapParams] = None,
    ) -> SurfaceMapResult:
        params = params or self.params

        self._validate_point_cloud(point_cloud)

        input_point_count = len(point_cloud.points)

        working_cloud = self._prepare_cloud(
            point_cloud=point_cloud,
            params=params,
        )

        method = params.method.lower().strip()

        if method == "auto":
            mesh, method_used = self._build_auto_mesh(
                cloud=working_cloud,
                params=params,
            )

        elif method == "poisson":
            mesh = self._build_poisson_mesh(
                cloud=working_cloud,
                params=params,
            )
            method_used = "poisson"

        elif method == "bpa":
            mesh = self._build_bpa_mesh(
                cloud=working_cloud,
                params=params,
            )
            method_used = "bpa"

        else:
            raise ValueError(
                f"Phương pháp surface map chưa hỗ trợ: {params.method}. "
                "Hỗ trợ: auto, poisson, bpa."
            )

        mesh = self._postprocess_mesh(
            mesh=mesh,
            cloud=working_cloud,
            params=params,
        )

        return self._build_result(
            input_cloud=point_cloud,
            working_cloud=working_cloud,
            mesh=mesh,
            method=method_used,
            input_point_count=input_point_count,
        )

    # -------------------------------------------------
    # Prepare cloud
    # -------------------------------------------------
    def _prepare_cloud(
        self,
        point_cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ) -> o3d.geometry.PointCloud:
        cloud = o3d.geometry.PointCloud(point_cloud)

        cloud = self._remove_invalid_points(cloud)

        if len(cloud.points) <= 0:
            raise ValueError("Point cloud sau khi loại điểm lỗi bị rỗng.")

        if params.use_voxel_downsample:
            voxel_size = params.voxel_size

            if voxel_size <= 0:
                voxel_size = self._adaptive_size(
                    cloud=cloud,
                    ratio=params.adaptive_voxel_ratio,
                )

            if voxel_size > 0:
                cloud = cloud.voxel_down_sample(voxel_size=voxel_size)

        if len(cloud.points) <= 0:
            raise ValueError("Point cloud sau voxel downsample bị rỗng.")

        if (
            params.force_recompute_normals
            or not cloud.has_normals()
            or len(cloud.normals) != len(cloud.points)
        ):
            self._estimate_normals(
                cloud=cloud,
                params=params,
            )

        if params.orient_normals:
            try:
                cloud.orient_normals_consistent_tangent_plane(params.orient_k)
            except Exception:
                pass

        try:
            cloud.normalize_normals()
        except Exception:
            pass

        if len(cloud.points) > params.max_input_points:
            cloud = self._random_sample_cloud(
                cloud=cloud,
                max_points=params.max_input_points,
            )

        return cloud

    def _remove_invalid_points(
        self,
        cloud: o3d.geometry.PointCloud,
    ) -> o3d.geometry.PointCloud:
        points = np.asarray(cloud.points)

        if len(points) == 0:
            return cloud

        valid_mask = np.isfinite(points).all(axis=1)

        points = points[valid_mask]

        clean = o3d.geometry.PointCloud()
        clean.points = o3d.utility.Vector3dVector(points)

        if cloud.has_normals():
            normals = np.asarray(cloud.normals)

            if len(normals) == len(valid_mask):
                normals = normals[valid_mask]
                normal_valid = np.isfinite(normals).all(axis=1)

                points = points[normal_valid]
                normals = normals[normal_valid]

                clean.points = o3d.utility.Vector3dVector(points)
                clean.normals = o3d.utility.Vector3dVector(normals)

        if cloud.has_colors():
            colors = np.asarray(cloud.colors)

            if len(colors) == len(valid_mask):
                colors = colors[valid_mask]

                if len(colors) == len(clean.points):
                    clean.colors = o3d.utility.Vector3dVector(colors)

        return clean

    def _estimate_normals(
        self,
        cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ):
        radius = params.normal_radius

        if radius <= 0:
            radius = self._adaptive_size(
                cloud=cloud,
                ratio=params.adaptive_normal_radius_ratio,
            )

        if radius <= 0:
            radius = 1.0

        cloud.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=radius,
                max_nn=params.normal_max_nn,
            )
        )

    def _random_sample_cloud(
        self,
        cloud: o3d.geometry.PointCloud,
        max_points: int,
    ) -> o3d.geometry.PointCloud:
        point_count = len(cloud.points)

        if point_count <= max_points:
            return cloud

        points = np.asarray(cloud.points)
        normals = np.asarray(cloud.normals)

        rng = np.random.default_rng(42)
        indices = rng.choice(
            point_count,
            size=max_points,
            replace=False,
        )

        sampled = o3d.geometry.PointCloud()
        sampled.points = o3d.utility.Vector3dVector(points[indices])

        if cloud.has_normals() and len(normals) == point_count:
            sampled.normals = o3d.utility.Vector3dVector(normals[indices])

        if cloud.has_colors():
            colors = np.asarray(cloud.colors)

            if len(colors) == point_count:
                sampled.colors = o3d.utility.Vector3dVector(colors[indices])

        return sampled

    # -------------------------------------------------
    # Mesh methods
    # -------------------------------------------------
    def _build_auto_mesh(
        self,
        cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ) -> tuple[o3d.geometry.TriangleMesh, str]:
        """
        Auto mode:
            - Thử Poisson trước để mesh liền khối, dễ nhìn.
            - Nếu Poisson lỗi thì fallback sang BPA.
        """

        poisson_error = None

        try:
            mesh = self._build_poisson_mesh(
                cloud=cloud,
                params=params,
            )

            if self._is_valid_mesh(mesh):
                return mesh, "poisson"

        except Exception as exc:
            poisson_error = exc

        try:
            mesh = self._build_bpa_mesh(
                cloud=cloud,
                params=params,
            )

            if self._is_valid_mesh(mesh):
                return mesh, "bpa"

        except Exception as bpa_error:
            raise RuntimeError(
                "Không thể tạo surface mesh bằng Poisson hoặc BPA.\n\n"
                f"Poisson error: {poisson_error}\n"
                f"BPA error: {bpa_error}"
            )

        raise RuntimeError("Không thể tạo surface mesh hợp lệ.")

    def _build_bpa_mesh(
        self,
        cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ) -> o3d.geometry.TriangleMesh:
        if not cloud.has_normals():
            raise ValueError("BPA cần point cloud có pháp tuyến.")

        avg_distance = self._estimate_average_neighbor_distance(
            cloud=cloud,
            sample_size=params.bpa_neighbor_sample,
        )

        if avg_distance <= 0:
            avg_distance = self._adaptive_size(
                cloud=cloud,
                ratio=0.003,
            )

        radii = [
            avg_distance * params.bpa_radius_factor_1,
            avg_distance * params.bpa_radius_factor_2,
            avg_distance * params.bpa_radius_factor_3,
        ]

        radii = sorted(set(float(r) for r in radii if r > 0))

        if not radii:
            raise ValueError("Không thể tính bán kính BPA hợp lệ.")

        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            cloud,
            o3d.utility.DoubleVector(radii),
        )

        if not self._is_valid_mesh(mesh):
            raise ValueError(
                "BPA không tạo được mesh hợp lệ. "
                "Hãy thử method='poisson' hoặc tăng mật độ point cloud."
            )

        return mesh

    def _build_poisson_mesh(
        self,
        cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ) -> o3d.geometry.TriangleMesh:
        if not cloud.has_normals():
            raise ValueError("Poisson cần point cloud có pháp tuyến.")

        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            cloud,
            depth=params.poisson_depth,
            scale=params.poisson_scale,
            linear_fit=params.poisson_linear_fit,
        )

        densities = np.asarray(densities)

        if len(densities) > 0 and 0.0 < params.density_quantile < 1.0:
            threshold = np.quantile(
                densities,
                params.density_quantile,
            )
            remove_mask = densities < threshold
            mesh.remove_vertices_by_mask(remove_mask)

        if not self._is_valid_mesh(mesh):
            raise ValueError(
                "Poisson không tạo được mesh hợp lệ. "
                "Hãy kiểm tra point cloud hoặc pháp tuyến."
            )

        return mesh

    # -------------------------------------------------
    # Mesh post-process
    # -------------------------------------------------
    def _postprocess_mesh(
        self,
        mesh: o3d.geometry.TriangleMesh,
        cloud: o3d.geometry.PointCloud,
        params: SurfaceMapParams,
    ) -> o3d.geometry.TriangleMesh:
        mesh = self._clean_mesh(mesh)

        if params.crop_to_cloud_bbox:
            try:
                mesh = self._crop_mesh_to_cloud_bbox(
                    mesh=mesh,
                    cloud=cloud,
                    padding_ratio=params.crop_padding_ratio,
                )
                mesh = self._clean_mesh(mesh)
            except Exception:
                pass

        if (
            params.simplify_mesh
            and len(mesh.triangles) > params.target_triangles
        ):
            mesh = mesh.simplify_quadric_decimation(
                target_number_of_triangles=params.target_triangles
            )
            mesh = self._clean_mesh(mesh)

        if params.keep_largest_component:
            mesh = self._keep_largest_components(
                mesh=mesh,
                min_ratio=params.min_component_triangle_ratio,
            )
            mesh = self._clean_mesh(mesh)

        if params.smooth_iterations > 0:
            mesh = mesh.filter_smooth_simple(
                number_of_iterations=params.smooth_iterations
            )
            mesh = self._clean_mesh(mesh)

        mesh.compute_vertex_normals()
        mesh.compute_triangle_normals()

        try:
            mesh.normalize_normals()
        except Exception:
            pass

        if not self._is_valid_mesh(mesh):
            raise ValueError(
                "Mesh sau hậu xử lý không hợp lệ. "
                "Hãy giảm mức lọc point cloud hoặc đổi method surface."
            )

        return mesh

    def _clean_mesh(
        self,
        mesh: o3d.geometry.TriangleMesh,
    ) -> o3d.geometry.TriangleMesh:
        mesh.remove_duplicated_vertices()
        mesh.remove_duplicated_triangles()
        mesh.remove_degenerate_triangles()
        mesh.remove_unreferenced_vertices()

        # Không gọi remove_non_manifold_edges mặc định.
        # Với dữ liệu scan thực tế, nó có thể làm mesh rách hoặc mất chi tiết.

        return mesh

    def _keep_largest_components(
        self,
        mesh: o3d.geometry.TriangleMesh,
        min_ratio: float = 0.01,
    ) -> o3d.geometry.TriangleMesh:
        """
        Giữ lại các cụm tam giác lớn, bỏ mảnh mesh rác nhỏ.
        """

        if mesh is None or len(mesh.triangles) <= 0:
            return mesh

        try:
            triangle_clusters, cluster_n_triangles, _ = mesh.cluster_connected_triangles()
        except Exception:
            return mesh

        triangle_clusters = np.asarray(triangle_clusters)
        cluster_n_triangles = np.asarray(cluster_n_triangles)

        if len(cluster_n_triangles) <= 0:
            return mesh

        max_triangles = int(cluster_n_triangles.max())

        if max_triangles <= 0:
            return mesh

        keep_cluster_ids = np.where(
            cluster_n_triangles >= max_triangles * min_ratio
        )[0]

        if len(keep_cluster_ids) <= 0:
            keep_cluster_ids = np.asarray([int(np.argmax(cluster_n_triangles))])

        keep_mask = np.isin(triangle_clusters, keep_cluster_ids)
        remove_mask = ~keep_mask

        cleaned_mesh = o3d.geometry.TriangleMesh(mesh)
        cleaned_mesh.remove_triangles_by_mask(remove_mask)
        cleaned_mesh.remove_unreferenced_vertices()

        return cleaned_mesh

    def _crop_mesh_to_cloud_bbox(
        self,
        mesh: o3d.geometry.TriangleMesh,
        cloud: o3d.geometry.PointCloud,
        padding_ratio: float,
    ) -> o3d.geometry.TriangleMesh:
        points = np.asarray(cloud.points)

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)

        size = bounds_max - bounds_min
        max_size = float(np.max(size))

        padding = max_size * padding_ratio

        aabb = o3d.geometry.AxisAlignedBoundingBox(
            min_bound=bounds_min - padding,
            max_bound=bounds_max + padding,
        )

        return mesh.crop(aabb)

    # -------------------------------------------------
    # Validation / result
    # -------------------------------------------------
    def _validate_point_cloud(
        self,
        point_cloud: o3d.geometry.PointCloud,
    ):
        if point_cloud is None:
            raise ValueError("Point cloud đầu vào bị rỗng.")

        if len(point_cloud.points) <= 0:
            raise ValueError("Point cloud đầu vào không có điểm 3D hợp lệ.")

        if not point_cloud.has_normals():
            raise ValueError(
                "Point cloud chưa có pháp tuyến. "
                "Hãy bấm 'TÍNH PHÁP TUYẾN BỀ MẶT' trước khi tạo surface map."
            )

    def _is_valid_mesh(
        self,
        mesh: o3d.geometry.TriangleMesh,
    ) -> bool:
        if mesh is None:
            return False

        if len(mesh.vertices) <= 0:
            return False

        if len(mesh.triangles) <= 0:
            return False

        return True

    def _build_result(
        self,
        input_cloud: o3d.geometry.PointCloud,
        working_cloud: o3d.geometry.PointCloud,
        mesh: o3d.geometry.TriangleMesh,
        method: str,
        input_point_count: int,
    ) -> SurfaceMapResult:
        vertices = np.asarray(mesh.vertices)

        bounds_min = vertices.min(axis=0)
        bounds_max = vertices.max(axis=0)
        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        vertex_count = len(mesh.vertices)
        triangle_count = len(mesh.triangles)
        working_point_count = len(working_cloud.points)

        return SurfaceMapResult(
            input_cloud=input_cloud,
            working_cloud=working_cloud,
            mesh=mesh,
            vertex_count=vertex_count,
            triangle_count=triangle_count,
            input_point_count=input_point_count,
            working_point_count=working_point_count,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            method=method,
            message=(
                f"Đã tạo bản đồ bề mặt 3D bằng {method}: "
                f"{vertex_count} đỉnh, "
                f"{triangle_count} mặt tam giác, "
                f"từ {working_point_count}/{input_point_count} điểm."
            ),
        )

    # -------------------------------------------------
    # Numeric helpers
    # -------------------------------------------------
    def _adaptive_size(
        self,
        cloud: o3d.geometry.PointCloud,
        ratio: float,
    ) -> float:
        points = np.asarray(cloud.points)

        if len(points) == 0:
            return 0.0

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        size = bounds_max - bounds_min

        max_size = float(np.max(size))

        if max_size <= 0:
            return 0.0

        return max_size * ratio

    def _estimate_average_neighbor_distance(
        self,
        cloud: o3d.geometry.PointCloud,
        sample_size: int,
    ) -> float:
        point_count = len(cloud.points)

        if point_count <= 1:
            return 0.0

        if point_count > sample_size:
            points = np.asarray(cloud.points)

            rng = np.random.default_rng(42)
            indices = rng.choice(
                point_count,
                size=sample_size,
                replace=False,
            )

            sample_cloud = o3d.geometry.PointCloud()
            sample_cloud.points = o3d.utility.Vector3dVector(points[indices])

            distances = sample_cloud.compute_nearest_neighbor_distance()
        else:
            distances = cloud.compute_nearest_neighbor_distance()

        distances = np.asarray(distances, dtype=float)

        distances = distances[np.isfinite(distances)]
        distances = distances[distances > 0]

        if len(distances) == 0:
            return 0.0

        return float(np.median(distances))