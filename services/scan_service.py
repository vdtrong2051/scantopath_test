from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import open3d as o3d

from modules.acquisition.scan_importer import (
    ScanImporter,
    ScanImportResult,
)


@dataclass
class ScanServiceState:
    """
    Trạng thái hiện tại của dữ liệu quét trong chương trình.
    """

    current_file: Optional[Path] = None
    current_result: Optional[ScanImportResult] = None
    current_point_cloud: Optional[o3d.geometry.PointCloud] = None

    is_loaded: bool = False
    message: str = "Chưa nạp dữ liệu quét."


class ScanService:
    """
    Service quản lý bước nạp dữ liệu quét 3D.

    Vai trò:
        - Gọi ScanImporter để nạp file .ply / .pcd / .xyz
        - Lưu point cloud hiện tại vào bộ nhớ
        - Trả thông tin cho UI
        - Cung cấp dữ liệu cho các bước sau:
            + Edge AI / ROI mask
            + Filter point cloud
            + Build surface map
            + Estimate normals
            + Generate path
    """

    def __init__(self):
        self.importer = ScanImporter()
        self.state = ScanServiceState()

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def load_scan(self, file_path: str | Path) -> ScanImportResult:
        """
        Nạp dữ liệu quét 3D từ file.

        Args:
            file_path:
                Đường dẫn file .ply / .pcd / .xyz / .xyzn / .xyzrgb

        Returns:
            ScanImportResult
        """

        result = self.importer.import_scan(file_path)

        self.state.current_file = result.file_path
        self.state.current_result = result
        self.state.current_point_cloud = result.point_cloud
        self.state.is_loaded = True
        self.state.message = result.message

        return result

    def has_scan(self) -> bool:
        """
        Kiểm tra đã có dữ liệu quét chưa.
        """

        return (
            self.state.is_loaded
            and self.state.current_point_cloud is not None
            and self.state.current_result is not None
        )

    def get_current_point_cloud(self) -> o3d.geometry.PointCloud:
        """
        Lấy point cloud hiện tại.

        Raises:
            RuntimeError nếu chưa nạp scan.
        """

        if not self.has_scan():
            raise RuntimeError(
                "Chưa có dữ liệu quét. Hãy nạp file .ply/.pcd/.xyz trước."
            )

        return self.state.current_point_cloud

    def get_current_result(self) -> ScanImportResult:
        """
        Lấy kết quả nạp scan hiện tại.

        Raises:
            RuntimeError nếu chưa nạp scan.
        """

        if not self.has_scan():
            raise RuntimeError(
                "Chưa có kết quả nạp scan. Hãy nạp dữ liệu quét trước."
            )

        return self.state.current_result

    def get_summary(self) -> dict:
        """
        Trả về thông tin tóm tắt để UI hiển thị.
        """

        if not self.has_scan():
            return {
                "is_loaded": False,
                "message": self.state.message,
                "file_name": "--",
                "point_count": 0,
                "has_colors": False,
                "has_normals": False,
                "size": [0.0, 0.0, 0.0],
                "center": [0.0, 0.0, 0.0],
            }

        result = self.state.current_result

        return {
            "is_loaded": True,
            "message": result.message,
            "file_name": result.file_name,
            "file_path": str(result.file_path),
            "extension": result.extension,
            "point_count": result.point_count,
            "has_colors": result.has_colors,
            "has_normals": result.has_normals,
            "bounds_min": result.bounds_min.tolist(),
            "bounds_max": result.bounds_max.tolist(),
            "center": result.center.tolist(),
            "size": result.size.tolist(),
        }

    def reset(self):
        """
        Xóa dữ liệu scan hiện tại khỏi bộ nhớ.
        """

        self.state = ScanServiceState(
            is_loaded=False,
            message="Đã xóa dữ liệu quét hiện tại.",
        )

    def is_supported_file(self, file_path: str | Path) -> bool:
        """
        Kiểm tra file có đúng định dạng được hỗ trợ không.
        """

        return self.importer.is_supported_file(file_path)


# -------------------------------------------------
# Quick test
# -------------------------------------------------
if __name__ == "__main__":
    service = ScanService()

    sample_path = Path("data/pointcloud_raw/sample_001.ply")

    result = service.load_scan(sample_path)

    print(result.message)
    print(service.get_summary())