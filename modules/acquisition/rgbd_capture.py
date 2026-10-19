from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import open3d as o3d


@dataclass
class RGBDFrame:
    """
    Một frame RGB-D giả lập / thật.

    Sau này khi nối Orbbec:
        rgb_image   -> ảnh màu
        depth_image -> ảnh độ sâu
        point_cloud -> point cloud từ frame RGB-D
    """

    frame_id: int
    timestamp: str

    rgb_path: Optional[Path] = None
    depth_path: Optional[Path] = None

    point_cloud: Optional[o3d.geometry.PointCloud] = None

    message: str = "Frame RGB-D đã được tạo."


@dataclass
class HandheldScanResult:
    """
    Kết quả quét bằng camera cầm tay.
    """

    mode: str = "HANDHELD"
    frames: list[RGBDFrame] = field(default_factory=list)
    point_cloud: Optional[o3d.geometry.PointCloud] = None

    frame_count: int = 0
    point_count: int = 0

    message: str = "Chưa có dữ liệu quét cầm tay."


class HandheldRGBDCapture:
    """
    Khung quét camera cầm tay.

    Mục tiêu:
        - Sau này dùng Orbbec RGB-D stream.
        - Người dùng cầm camera quét quanh vật/người.
        - Nhiều frame RGB-D được ghép thành point cloud.

    Hiện tại:
        - Chỉ là mock/controller skeleton.
        - Chưa gọi Orbbec SDK thật.
    """

    def __init__(self):
        self.is_connected = False
        self.is_scanning = False
        self.frames: list[RGBDFrame] = []

    # -------------------------------------------------
    # Camera connection
    # -------------------------------------------------
    def connect(self) -> bool:
        """
        Kết nối camera.

        Hiện tại là mock.
        Sau này thay bằng Orbbec pipeline start.
        """

        self.is_connected = True
        return self.is_connected

    def disconnect(self):
        """
        Ngắt camera.
        """

        self.is_connected = False
        self.is_scanning = False
        self.frames.clear()

    def check_connection(self) -> bool:
        return self.is_connected

    # -------------------------------------------------
    # Scan lifecycle
    # -------------------------------------------------
    def start_scan(self):
        if not self.is_connected:
            raise RuntimeError(
                "Camera chưa kết nối. Hãy kết nối camera trước khi quét."
            )

        self.is_scanning = True
        self.frames.clear()

    def capture_frame(self) -> RGBDFrame:
        """
        Chụp 1 frame RGB-D.

        Hiện tại tạo frame mock.
        Sau này thay bằng:
            - lấy RGB frame
            - lấy Depth frame
            - convert sang point cloud
        """

        if not self.is_connected:
            raise RuntimeError("Camera chưa kết nối.")

        if not self.is_scanning:
            raise RuntimeError("Chưa bắt đầu phiên quét cầm tay.")

        frame_id = len(self.frames) + 1

        frame = RGBDFrame(
            frame_id=frame_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            point_cloud=None,
            message=f"Đã nhận frame RGB-D mock #{frame_id}.",
        )

        self.frames.append(frame)

        return frame

    def stop_scan(self) -> HandheldScanResult:
        """
        Dừng phiên quét.

        Hiện tại chưa ghép frame thành point cloud thật.
        Sau này sẽ thêm:
            - registration
            - ICP
            - merge point cloud
        """

        if not self.is_scanning:
            raise RuntimeError("Chưa có phiên quét cầm tay đang chạy.")

        self.is_scanning = False

        merged_cloud = self._merge_frames_to_point_cloud(self.frames)

        point_count = 0
        if merged_cloud is not None:
            point_count = len(merged_cloud.points)

        return HandheldScanResult(
            frames=list(self.frames),
            point_cloud=merged_cloud,
            frame_count=len(self.frames),
            point_count=point_count,
            message=(
                "Đã hoàn tất phiên quét cầm tay. "
                "Hiện tại đang dùng mock, chưa ghép point cloud thật."
            ),
        )

    # -------------------------------------------------
    # Internal
    # -------------------------------------------------
    def _merge_frames_to_point_cloud(
        self,
        frames: list[RGBDFrame],
    ) -> Optional[o3d.geometry.PointCloud]:
        """
        Placeholder ghép nhiều frame RGB-D thành point cloud.

        Sau này:
            frame RGB-D
            → point cloud từng frame
            → registration / ICP
            → merged point cloud
        """

        clouds = [
            frame.point_cloud
            for frame in frames
            if frame.point_cloud is not None
        ]

        if not clouds:
            return None

        merged = o3d.geometry.PointCloud()

        for cloud in clouds:
            merged += cloud

        return merged