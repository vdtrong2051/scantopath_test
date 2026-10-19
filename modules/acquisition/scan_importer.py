from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d


SUPPORTED_SCAN_EXTENSIONS = {
    ".ply",
    ".pcd",
    ".xyz",
    ".xyzn",
    ".xyzrgb",
}


@dataclass
class ScanImportResult:
    """
    Kết quả sau khi nạp dữ liệu quét 3D.
    """

    file_path: Path
    file_name: str
    extension: str

    point_cloud: o3d.geometry.PointCloud

    point_count: int
    has_colors: bool
    has_normals: bool

    bounds_min: np.ndarray
    bounds_max: np.ndarray
    center: np.ndarray
    size: np.ndarray

    is_valid: bool
    message: str


class ScanImporter:
    """
    Module nạp dữ liệu quét 3D cho pipeline Scan-to-Path.

    Vai trò:
        - Nạp file .ply / .pcd / .xyz / .xyzn / .xyzrgb
        - Kiểm tra point cloud có hợp lệ không
        - Tính thông tin cơ bản: số điểm, bounding box, tâm, kích thước
        - Trả về ScanImportResult để UI/service dùng tiếp

    Chưa làm:
        - Không xử lý lọc nhiễu
        - Không tái tạo bề mặt
        - Không tính pháp tuyến
        - Không sinh đường dẫn
    """

    def __init__(self):
        pass

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def import_scan(self, file_path: str | Path) -> ScanImportResult:
        """
        Nạp một file quét 3D.

        Args:
            file_path:
                Đường dẫn tới file .ply / .pcd / .xyz / .xyzn / .xyzrgb

        Returns:
            ScanImportResult
        """

        path = Path(file_path).resolve()

        self._validate_path(path)

        extension = path.suffix.lower()

        if extension in {".ply", ".pcd"}:
            point_cloud = self._load_open3d_file(path)

        elif extension in {".xyz", ".xyzn", ".xyzrgb"}:
            point_cloud = self._load_xyz_like_file(path)

        else:
            raise ValueError(
                f"Định dạng không hỗ trợ: {extension}. "
                f"Hỗ trợ: {sorted(SUPPORTED_SCAN_EXTENSIONS)}"
            )

        self._validate_point_cloud(point_cloud, path)

        return self._build_result(path, point_cloud)

    def is_supported_file(self, file_path: str | Path) -> bool:
        path = Path(file_path)
        return path.suffix.lower() in SUPPORTED_SCAN_EXTENSIONS

    # -------------------------------------------------
    # Loaders
    # -------------------------------------------------
    def _load_open3d_file(self, path: Path) -> o3d.geometry.PointCloud:
        """
        Nạp .ply hoặc .pcd bằng Open3D.
        """

        point_cloud = o3d.io.read_point_cloud(str(path))

        return point_cloud

    def _load_xyz_like_file(self, path: Path) -> o3d.geometry.PointCloud:
        """
        Nạp các file dạng text:
            .xyz     -> x y z
            .xyzn    -> x y z nx ny nz
            .xyzrgb  -> x y z r g b

        Quy ước:
            - Dòng bắt đầu bằng # sẽ bị bỏ qua
            - Dữ liệu cách nhau bằng khoảng trắng hoặc dấu phẩy
        """

        try:
            data = np.genfromtxt(
                path,
                comments="#",
                delimiter=None,
                dtype=float,
            )

        except Exception:
            data = np.genfromtxt(
                path,
                comments="#",
                delimiter=",",
                dtype=float,
            )

        if data.ndim == 1:
            data = data.reshape(1, -1)

        if data.shape[1] < 3:
            raise ValueError(
                f"File {path.name} không đủ cột tọa độ. "
                "Tối thiểu cần 3 cột: x y z."
            )

        points = data[:, 0:3]

        valid_mask = np.isfinite(points).all(axis=1)
        points = points[valid_mask]

        point_cloud = o3d.geometry.PointCloud()
        point_cloud.points = o3d.utility.Vector3dVector(points)

        # Nếu có normal: x y z nx ny nz
        if path.suffix.lower() == ".xyzn" and data.shape[1] >= 6:
            normals = data[:, 3:6]
            normals = normals[valid_mask]

            if len(normals) == len(points):
                point_cloud.normals = o3d.utility.Vector3dVector(normals)

        # Nếu có RGB: x y z r g b
        if path.suffix.lower() == ".xyzrgb" and data.shape[1] >= 6:
            colors = data[:, 3:6]
            colors = colors[valid_mask]

            # Nếu màu đang ở 0-255 thì đưa về 0-1
            if colors.max() > 1.0:
                colors = colors / 255.0

            colors = np.clip(colors, 0.0, 1.0)

            if len(colors) == len(points):
                point_cloud.colors = o3d.utility.Vector3dVector(colors)

        return point_cloud

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------
    def _validate_path(self, path: Path):
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file quét 3D: {path}")

        if not path.is_file():
            raise ValueError(f"Đường dẫn không phải file: {path}")

        if path.suffix.lower() not in SUPPORTED_SCAN_EXTENSIONS:
            raise ValueError(
                f"Định dạng không hỗ trợ: {path.suffix}. "
                f"Hỗ trợ: {sorted(SUPPORTED_SCAN_EXTENSIONS)}"
            )

    def _validate_point_cloud(
        self,
        point_cloud: o3d.geometry.PointCloud,
        path: Path,
    ):
        if point_cloud is None:
            raise ValueError(f"Không thể nạp point cloud từ file: {path.name}")

        point_count = len(point_cloud.points)

        if point_count <= 0:
            raise ValueError(
                f"File {path.name} không có điểm 3D hợp lệ."
            )

    # -------------------------------------------------
    # Result builder
    # -------------------------------------------------
    def _build_result(
        self,
        path: Path,
        point_cloud: o3d.geometry.PointCloud,
    ) -> ScanImportResult:
        points = np.asarray(point_cloud.points)

        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)

        center = (bounds_min + bounds_max) / 2.0
        size = bounds_max - bounds_min

        point_count = len(points)
        has_colors = point_cloud.has_colors()
        has_normals = point_cloud.has_normals()

        return ScanImportResult(
            file_path=path,
            file_name=path.name,
            extension=path.suffix.lower(),
            point_cloud=point_cloud,
            point_count=point_count,
            has_colors=has_colors,
            has_normals=has_normals,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            center=center,
            size=size,
            is_valid=True,
            message=(
                f"Đã nạp dữ liệu quét thành công: {path.name} "
                f"({point_count} điểm)"
            ),
        )


