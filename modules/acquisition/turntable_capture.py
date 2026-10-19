from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import open3d as o3d


@dataclass
class TurntableCaptureStep:
    """
    Một bước chụp trong mode bàn xoay.

    angle_deg:
        Góc bàn xoay hiện tại.

    trigger_ok:
        True nếu camera đã chụp sau khi bàn xoay dừng.
    """

    step_id: int
    angle_deg: float
    timestamp: str
    trigger_ok: bool = False

    point_cloud: Optional[o3d.geometry.PointCloud] = None
    message: str = "Đã tạo bước chụp bàn xoay."


@dataclass
class TurntableScanResult:
    """
    Kết quả quét bằng bàn xoay.
    """

    mode: str = "TURNTABLE"
    steps: list[TurntableCaptureStep] = field(default_factory=list)
    point_cloud: Optional[o3d.geometry.PointCloud] = None

    step_count: int = 0
    point_count: int = 0

    angle_step_deg: float = 10.0
    total_angle_deg: float = 360.0

    message: str = "Chưa có dữ liệu quét bàn xoay."


class TurntableCapture:
    """
    Khung quét với cơ cấu bàn xoay.

    Luồng Stop-and-Go:
        PC gửi lệnh quay
        → Arduino quay bàn xoay
        → delay triệt tiêu dao động
        → Arduino gửi trigger đã dừng
        → Camera chụp RGB-D
        → lặp lại cho đến hết 360 độ

    Hiện tại:
        - Mock controller.
        - Chưa nối UART Arduino thật.
        - Chưa nối Orbbec SDK thật.
    """

    def __init__(
        self,
        angle_step_deg: float = 10.0,
        total_angle_deg: float = 360.0,
    ):
        self.angle_step_deg = angle_step_deg
        self.total_angle_deg = total_angle_deg

        self.is_connected = False
        self.is_scanning = False

        self.steps: list[TurntableCaptureStep] = []

    # -------------------------------------------------
    # Connection
    # -------------------------------------------------
    def connect(self) -> bool:
        """
        Kết nối camera + Arduino.

        Hiện tại là mock.
        Sau này:
            - connect Orbbec
            - open UART Arduino
        """

        self.is_connected = True
        return self.is_connected

    def disconnect(self):
        self.is_connected = False
        self.is_scanning = False
        self.steps.clear()

    def check_connection(self) -> bool:
        return self.is_connected

    # -------------------------------------------------
    # Scan lifecycle
    # -------------------------------------------------
    def start_scan(self):
        if not self.is_connected:
            raise RuntimeError(
                "Chưa kết nối camera/bàn xoay. Hãy kết nối trước khi quét."
            )

        self.is_scanning = True
        self.steps.clear()

    def capture_next_angle(self) -> TurntableCaptureStep:
        """
        Thực hiện một bước Stop-and-Go.

        Hiện tại:
            - Tính góc tiếp theo
            - Tạo step mock
            - trigger_ok=True giả lập
        """

        if not self.is_connected:
            raise RuntimeError("Chưa kết nối camera/bàn xoay.")

        if not self.is_scanning:
            raise RuntimeError("Chưa bắt đầu phiên quét bàn xoay.")

        step_id = len(self.steps) + 1
        angle_deg = (step_id - 1) * self.angle_step_deg

        if angle_deg >= self.total_angle_deg:
            raise RuntimeError("Đã quét đủ vòng bàn xoay.")

        step = TurntableCaptureStep(
            step_id=step_id,
            angle_deg=angle_deg,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trigger_ok=True,
            point_cloud=None,
            message=(
                f"Mock Stop-and-Go: bàn xoay tại góc {angle_deg:.1f}°, "
                "camera đã trigger."
            ),
        )

        self.steps.append(step)

        return step

    def stop_scan(self) -> TurntableScanResult:
        if not self.is_scanning:
            raise RuntimeError("Chưa có phiên quét bàn xoay đang chạy.")

        self.is_scanning = False

        merged_cloud = self._merge_steps_to_point_cloud(self.steps)

        point_count = 0
        if merged_cloud is not None:
            point_count = len(merged_cloud.points)

        return TurntableScanResult(
            steps=list(self.steps),
            point_cloud=merged_cloud,
            step_count=len(self.steps),
            point_count=point_count,
            angle_step_deg=self.angle_step_deg,
            total_angle_deg=self.total_angle_deg,
            message=(
                "Đã hoàn tất phiên quét bàn xoay. "
                "Hiện tại đang dùng mock, chưa ghép point cloud thật."
            ),
        )

    # -------------------------------------------------
    # Internal
    # -------------------------------------------------
    def _merge_steps_to_point_cloud(
        self,
        steps: list[TurntableCaptureStep],
    ) -> Optional[o3d.geometry.PointCloud]:
        """
        Placeholder ghép point cloud nhiều góc.

        Sau này:
            - mỗi góc có RGB-D/point cloud
            - transform theo góc bàn xoay
            - merge thành point cloud đầy đủ
        """

        clouds = [
            step.point_cloud
            for step in steps
            if step.point_cloud is not None
        ]

        if not clouds:
            return None

        merged = o3d.geometry.PointCloud()

        for cloud in clouds:
            merged += cloud

        return merged