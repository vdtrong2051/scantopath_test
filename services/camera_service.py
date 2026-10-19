from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import open3d as o3d

from modules.acquisition.rgbd_capture import (
    HandheldRGBDCapture,
    HandheldScanResult,
    RGBDFrame,
)

from modules.acquisition.turntable_capture import (
    TurntableCapture,
    TurntableScanResult,
    TurntableCaptureStep,
)


@dataclass
class CameraServiceState:
    current_mode: str = "IDLE"

    is_connected: bool = False
    is_scanning: bool = False

    last_handheld_result: Optional[HandheldScanResult] = None
    last_turntable_result: Optional[TurntableScanResult] = None

    current_point_cloud: Optional[o3d.geometry.PointCloud] = None

    message: str = "Camera chưa kết nối."


class CameraService:
    """
    Service quản lý camera 3D cho Scan-to-Path.

    Hỗ trợ 2 mode:

        HANDHELD:
            Cầm camera quét quanh vật thể/người.

        TURNTABLE:
            Camera cố định + bàn xoay Stop-and-Go.

    Hiện tại:
        - Mock/skeleton.
        - Chưa nối Orbbec SDK thật.
        - Chưa nối Arduino UART thật.
    """

    MODE_IDLE = "IDLE"
    MODE_HANDHELD = "HANDHELD"
    MODE_TURNTABLE = "TURNTABLE"

    def __init__(self):
        self.handheld_capture = HandheldRGBDCapture()
        self.turntable_capture = TurntableCapture(
            angle_step_deg=10.0,
            total_angle_deg=360.0,
        )

        self.state = CameraServiceState()

    # -------------------------------------------------
    # Connection
    # -------------------------------------------------
    def connect(self, mode: str = MODE_HANDHELD) -> bool:
        mode = self._normalize_mode(mode)

        if mode == self.MODE_HANDHELD:
            ok = self.handheld_capture.connect()

        elif mode == self.MODE_TURNTABLE:
            ok = self.turntable_capture.connect()

        else:
            raise ValueError(f"Mode camera không hợp lệ: {mode}")

        self.state.current_mode = mode
        self.state.is_connected = ok
        self.state.is_scanning = False
        self.state.message = f"Camera đã kết nối ở mode {mode}."

        return ok

    def disconnect(self):
        self.handheld_capture.disconnect()
        self.turntable_capture.disconnect()

        self.state = CameraServiceState(
            current_mode=self.MODE_IDLE,
            is_connected=False,
            is_scanning=False,
            message="Đã ngắt camera.",
        )

    def is_connected(self) -> bool:
        return self.state.is_connected

    # -------------------------------------------------
    # Handheld mode
    # -------------------------------------------------
    def start_handheld_scan(self):
        self.connect(self.MODE_HANDHELD)

        self.handheld_capture.start_scan()

        self.state.current_mode = self.MODE_HANDHELD
        self.state.is_scanning = True
        self.state.message = "Đang quét bằng camera cầm tay."

    def capture_handheld_frame(self) -> RGBDFrame:
        if self.state.current_mode != self.MODE_HANDHELD:
            raise RuntimeError("Camera hiện không ở mode HANDHELD.")

        frame = self.handheld_capture.capture_frame()

        self.state.message = frame.message

        return frame

    def stop_handheld_scan(self) -> HandheldScanResult:
        if self.state.current_mode != self.MODE_HANDHELD:
            raise RuntimeError("Camera hiện không ở mode HANDHELD.")

        result = self.handheld_capture.stop_scan()

        self.state.last_handheld_result = result
        self.state.current_point_cloud = result.point_cloud
        self.state.is_scanning = False
        self.state.message = result.message

        return result

    # -------------------------------------------------
    # Turntable mode
    # -------------------------------------------------
    def start_turntable_scan(
        self,
        angle_step_deg: float = 10.0,
        total_angle_deg: float = 360.0,
    ):
        self.turntable_capture = TurntableCapture(
            angle_step_deg=angle_step_deg,
            total_angle_deg=total_angle_deg,
        )

        self.connect(self.MODE_TURNTABLE)

        self.turntable_capture.start_scan()

        self.state.current_mode = self.MODE_TURNTABLE
        self.state.is_scanning = True
        self.state.message = (
            f"Đang quét bằng bàn xoay | "
            f"bước góc {angle_step_deg:.1f}°."
        )

    def capture_turntable_step(self) -> TurntableCaptureStep:
        if self.state.current_mode != self.MODE_TURNTABLE:
            raise RuntimeError("Camera hiện không ở mode TURNTABLE.")

        step = self.turntable_capture.capture_next_angle()

        self.state.message = step.message

        return step

    def stop_turntable_scan(self) -> TurntableScanResult:
        if self.state.current_mode != self.MODE_TURNTABLE:
            raise RuntimeError("Camera hiện không ở mode TURNTABLE.")

        result = self.turntable_capture.stop_scan()

        self.state.last_turntable_result = result
        self.state.current_point_cloud = result.point_cloud
        self.state.is_scanning = False
        self.state.message = result.message

        return result

    # -------------------------------------------------
    # Query
    # -------------------------------------------------
    def has_point_cloud(self) -> bool:
        return (
            self.state.current_point_cloud is not None
            and len(self.state.current_point_cloud.points) > 0
        )

    def get_current_point_cloud(self) -> o3d.geometry.PointCloud:
        if not self.has_point_cloud():
            raise RuntimeError(
                "CameraService chưa có point cloud hợp lệ. "
                "Hiện tại mock camera chưa tạo point cloud thật."
            )

        return self.state.current_point_cloud

    def get_state(self) -> CameraServiceState:
        return self.state

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _normalize_mode(self, mode: str) -> str:
        mode = str(mode).upper().strip()

        if mode in ("HAND", "HANDHELD", "FREEHAND"):
            return self.MODE_HANDHELD

        if mode in ("TURN", "TURNTABLE", "STOP_AND_GO"):
            return self.MODE_TURNTABLE

        if mode in ("IDLE", "NONE"):
            return self.MODE_IDLE

        raise ValueError(
            f"Mode không hỗ trợ: {mode}. "
            "Hỗ trợ: HANDHELD, TURNTABLE."
        )