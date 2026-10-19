from __future__ import annotations

import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

import cv2
import numpy as np

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from modules.acquisition.openni_astra_camera import (
    AstraCamera,
    AstraCameraIntrinsics,
)


@dataclass
class OpenNIScanWorkerParams:
    """
    Thông số cho worker đọc camera OpenNI2/Astra.
    """

    output_root: str = "data/pointcloud_raw"

    target_fps: int = 20

    session_prefix: str = "OPENNI"

    min_depth_m: float = 0.10
    max_depth_m: float = 2.50
    stride: int = 2

    # Giữ lại field này để tương thích code cũ.
    # Bản demo-stable sẽ KHÔNG tự disconnect khi bấm QUÉT CẦM TAY.
    auto_disconnect_on_stop: bool = False

    use_center_roi: bool = True

    roi_x_min: float = 0.15
    roi_x_max: float = 0.85

    roi_y_min: float = 0.05
    roi_y_max: float = 0.95


class OpenNISaveWorker(QThread):
    """
    Worker phụ chuyên lưu RGB-D thành PLY.

    Bản này KHÔNG dùng Open3D để ghi file.
    Ghi ASCII PLY bằng numpy thuần để tránh crash native.
    """

    sig_save_done = pyqtSignal(str, float, float, int)
    sig_save_error = pyqtSignal(str)

    def __init__(
        self,
        rgb_frame: np.ndarray,
        depth_frame: np.ndarray,
        output_path: str | Path,
        intrinsics: AstraCameraIntrinsics,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
        params: Optional[OpenNIScanWorkerParams] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.rgb_frame = rgb_frame.copy()
        self.depth_frame = depth_frame.copy()
        self.output_path = Path(output_path)

        self.intrinsics = intrinsics
        self.pitch_deg = float(pitch_deg)
        self.yaw_deg = float(yaw_deg)

        self.params = params or OpenNIScanWorkerParams()

    def run(self):
        try:
            point_count = self._write_rgbd_to_ascii_ply(
                rgb_frame=self.rgb_frame,
                depth_frame=self.depth_frame,
                output_path=self.output_path,
            )

            self.sig_save_done.emit(
                str(self.output_path),
                self.pitch_deg,
                self.yaw_deg,
                int(point_count),
            )

        except Exception as exc:
            error_text = (
                "Lỗi khi lưu RGB-D thành PLY:\n"
                f"{exc}\n\n"
                f"{traceback.format_exc()}"
            )
            self.sig_save_error.emit(error_text)

    def _write_rgbd_to_ascii_ply(
        self,
        rgb_frame: np.ndarray,
        depth_frame: np.ndarray,
        output_path: Path,
    ) -> int:
        """
        Convert RGB-D sang point cloud và ghi ASCII PLY thủ công.

        RGB:
            H x W x 3, RGB uint8.

        Depth:
            H x W, thường là uint16 millimeter.
        """

        output_path.parent.mkdir(parents=True, exist_ok=True)

        rgb = np.asarray(rgb_frame)
        depth = np.asarray(depth_frame)

        if rgb.ndim != 3 or rgb.shape[2] < 3:
            raise ValueError(f"RGB frame không hợp lệ: shape={rgb.shape}")

        if depth.ndim != 2:
            raise ValueError(f"Depth frame không hợp lệ: shape={depth.shape}")

        rgb = rgb[:, :, :3].astype(np.uint8)

        depth_m = depth.astype(np.float32)

        # OpenNI thường trả depth uint16 millimeter.
        if depth_m.max(initial=0) > 20.0:
            depth_m = depth_m * float(self.intrinsics.depth_scale)

        h, w = depth_m.shape

        # Resize RGB nếu lệch kích thước depth.
        if rgb.shape[0] != h or rgb.shape[1] != w:
            rgb = self._resize_rgb_nearest(rgb, h, w)

        stride = max(1, int(self.params.stride))

        depth_s = depth_m[::stride, ::stride]
        rgb_s = rgb[::stride, ::stride]

        hs, ws = depth_s.shape

        jj, ii = np.meshgrid(
            np.arange(ws, dtype=np.float32),
            np.arange(hs, dtype=np.float32),
        )

        # Quy đổi lại index pixel thật khi stride > 1.
        jj = jj * stride
        ii = ii * stride

        valid = np.isfinite(depth_s)
        valid &= depth_s >= float(self.params.min_depth_m)
        valid &= depth_s <= float(self.params.max_depth_m)
        valid &= depth_s > 0

        # Crop vùng giữa ảnh để loại bớt tường/sàn/nền.
        # jj, ii đang là tọa độ pixel gốc sau khi đã nhân stride.
        if self.params.use_center_roi:
            x_min = float(w) * float(self.params.roi_x_min)
            x_max = float(w) * float(self.params.roi_x_max)

            y_min = float(h) * float(self.params.roi_y_min)
            y_max = float(h) * float(self.params.roi_y_max)

            valid &= jj >= x_min
            valid &= jj <= x_max
            valid &= ii >= y_min
            valid &= ii <= y_max

        if not np.any(valid):
            raise RuntimeError("Không có điểm depth hợp lệ để tạo PLY.")

        z = depth_s[valid].astype(np.float64)
        x = (jj[valid].astype(np.float64) - float(self.intrinsics.cx)) * z / float(self.intrinsics.fx)
        y = (ii[valid].astype(np.float64) - float(self.intrinsics.cy)) * z / float(self.intrinsics.fy)

        points = np.stack((x, y, z), axis=1)

        colors = rgb_s[valid].astype(np.uint8)

        # Header PLY ASCII.
        point_count = int(points.shape[0])

        header = [
            "ply",
            "format ascii 1.0",
            f"element vertex {point_count}",
            "property float x",
            "property float y",
            "property float z",
            "property uchar red",
            "property uchar green",
            "property uchar blue",
            "end_header",
        ]

        data = np.hstack(
            [
                points.astype(np.float64),
                colors.astype(np.uint8),
            ]
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(header) + "\n")
            np.savetxt(
                f,
                data,
                fmt="%.6f %.6f %.6f %d %d %d",
            )

        return point_count

    def _resize_rgb_nearest(
        self,
        rgb: np.ndarray,
        target_h: int,
        target_w: int,
    ) -> np.ndarray:
        src_h, src_w = rgb.shape[:2]

        y_idx = np.linspace(0, src_h - 1, target_h).astype(np.int32)
        x_idx = np.linspace(0, src_w - 1, target_w).astype(np.int32)

        return rgb[y_idx][:, x_idx]


class OpenNIScanWorker(QThread):
    """
    QThread đọc camera Astra/OpenNI2 liên tục.

    Pattern cố định theo mã cũ đã chạy ổn:
        - Worker camera chỉ đọc frame + emit preview.
        - Bấm CHỤP 1 FRAME thì tạo SaveWorker phụ.
        - SaveWorker ghi PLY xong emit path.
        - KHÔNG stop camera khi bấm QUÉT CẦM TAY.
    """

    # Preview dùng QImage.copy() để tránh lỗi vùng nhớ numpy/Qt.
    sig_frame_ready = pyqtSignal(QImage, QImage)

    sig_status = pyqtSignal(str, str)

    sig_capture_success = pyqtSignal(str, float, float, int)
    sig_capture_error = pyqtSignal(str)

    sig_error = pyqtSignal(str)

    def __init__(
        self,
        camera: Optional[AstraCamera] = None,
        params: Optional[OpenNIScanWorkerParams] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.params = params or OpenNIScanWorkerParams()

        self.camera = camera or AstraCamera(
            color_format="rgb",
            mirror=True,
            enable_registration=False,
        )

        self.session_id = self._make_session_id()
        self.session_dir = Path(self.params.output_root) / self.session_id

        self._running = False
        self._saving = False

        self._frame_id = 0

        self._latest_rgb: Optional[np.ndarray] = None
        self._latest_depth: Optional[np.ndarray] = None

        self._capture_requested = False
        self._capture_pitch_deg = 0.0
        self._capture_yaw_deg = 0.0

        self._last_capture_path: Optional[Path] = None

        self._lock = Lock()

        self._active_save_worker: Optional[OpenNISaveWorker] = None
        self._retired_save_workers: list[OpenNISaveWorker] = []

    # -------------------------------------------------
    # Thread lifecycle
    # -------------------------------------------------
    def run(self):
        self._running = True

        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)

            self.sig_status.emit(
                "Đang kết nối camera OpenNI/Astra...",
                "info",
            )

            if not self.camera.is_connected():
                self.camera.connect()

            if not self.camera.is_streaming():
                self.camera.start_stream()

            self.sig_status.emit(
                "Camera đã kết nối. Đang stream RGB-D.",
                "success",
            )

            frame_interval = 1.0 / max(1, int(self.params.target_fps))

            while self._running:
                loop_start = time.time()

                try:
                    rgb, depth = self.camera.get_frames()

                    if rgb is None or depth is None:
                        self._sleep_remaining(loop_start, frame_interval)
                        continue

                    with self._lock:
                        self._latest_rgb = rgb.copy()
                        self._latest_depth = depth.copy()
                        frame_id = self._frame_id
                        self._frame_id += 1

                    qt_rgb, qt_depth = self._make_preview_qimages(
                        rgb=rgb,
                        depth=depth,
                    )

                    self.sig_frame_ready.emit(qt_rgb, qt_depth)

                    if self._should_capture_now():
                        self._start_save_worker(
                            rgb_frame=rgb,
                            depth_frame=depth,
                            frame_id=frame_id,
                        )

                except Exception as exc:
                    self.sig_error.emit(
                        f"Lỗi luồng camera OpenNI/Astra: {exc}"
                    )
                    self._running = False
                    break

                self._sleep_remaining(loop_start, frame_interval)

        finally:
            # Chỉ cleanup khi thật sự request_stop.
            # Trong luồng demo, bấm QUÉT CẦM TAY không gọi request_stop.
            self._cleanup_camera()

    def request_stop(self):
        """
        Dừng worker nếu thật sự cần.

        KHÔNG dùng khi bấm QUÉT CẦM TAY.
        """

        self._running = False

    def stop(self, timeout_ms: int = 3000):
        self._running = False

        if self.isRunning():
            self.wait(timeout_ms)

    # -------------------------------------------------
    # Capture API
    # -------------------------------------------------
    def trigger_capture(
        self,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
    ):
        with self._lock:
            if self._saving:
                self.sig_status.emit(
                    "Đang lưu point cloud, vui lòng chờ...",
                    "warning",
                )
                return

            if self._latest_rgb is None or self._latest_depth is None:
                self.sig_capture_error.emit(
                    "Chưa có RGB-D frame hợp lệ để lưu."
                )
                return

            self._capture_pitch_deg = float(pitch_deg)
            self._capture_yaw_deg = float(yaw_deg)
            self._capture_requested = True

        self.sig_status.emit(
            (
                "Đã nhận lệnh chụp. "
                f"Pitch={pitch_deg:.1f}°, Yaw={yaw_deg:.1f}°"
            ),
            "warning",
        )

    def capture_latest_now(
        self,
        pitch_deg: float = 0.0,
        yaw_deg: float = 0.0,
    ) -> bool:
        """
        API tương thích với code dialog hiện tại.
        """

        with self._lock:
            if self._saving:
                self.sig_status.emit(
                    "Đang lưu point cloud, vui lòng chờ...",
                    "warning",
                )
                return False

            if self._latest_rgb is None or self._latest_depth is None:
                self.sig_capture_error.emit(
                    "Chưa có RGB-D frame hợp lệ để lưu."
                )
                return False

            self._capture_pitch_deg = float(pitch_deg)
            self._capture_yaw_deg = float(yaw_deg)
            self._capture_requested = True

        self.sig_status.emit(
            (
                "Đã nhận lệnh chụp. "
                f"Pitch={pitch_deg:.1f}°, Yaw={yaw_deg:.1f}°"
            ),
            "warning",
        )

        return True

    def get_last_capture_path(self) -> Optional[Path]:
        return self._last_capture_path

    def get_session_dir(self) -> Path:
        return self.session_dir

    def get_session_id(self) -> str:
        return self.session_id

    # -------------------------------------------------
    # Internal capture
    # -------------------------------------------------
    def _should_capture_now(self) -> bool:
        with self._lock:
            if not self._capture_requested:
                return False

            if self._saving:
                return False

            self._capture_requested = False
            return True

    def _start_save_worker(
        self,
        rgb_frame: np.ndarray,
        depth_frame: np.ndarray,
        frame_id: int,
    ):
        with self._lock:
            if self._saving:
                return

            self._saving = True
            pitch = float(self._capture_pitch_deg)
            yaw = float(self._capture_yaw_deg)

        output_path = self._make_capture_path(
            frame_id=frame_id,
            pitch_deg=pitch,
            yaw_deg=yaw,
        )

        self.sig_status.emit(
            f"Đang tạo point cloud PLY: {output_path.name}",
            "warning",
        )

        worker = OpenNISaveWorker(
            rgb_frame=rgb_frame,
            depth_frame=depth_frame,
            output_path=output_path,
            intrinsics=self.camera.get_intrinsics(),
            pitch_deg=pitch,
            yaw_deg=yaw,
            params=self.params,
        )

        worker.sig_save_done.connect(self._on_save_done)
        worker.sig_save_error.connect(self._on_save_error)
        worker.finished.connect(
            lambda w=worker: self._retire_save_worker(w)
        )

        self._active_save_worker = worker
        worker.start()

    def _on_save_done(
        self,
        file_path: str,
        pitch_deg: float,
        yaw_deg: float,
        point_count: int,
    ):
        with self._lock:
            self._saving = False
            self._last_capture_path = Path(file_path)

        self.sig_status.emit(
            f"Đã tạo point cloud từ RGB-D thành công ({point_count} điểm).",
            "success",
        )

        self.sig_capture_success.emit(
            file_path,
            float(pitch_deg),
            float(yaw_deg),
            int(point_count),
        )

    def _on_save_error(self, error_text: str):
        with self._lock:
            self._saving = False

        self.sig_status.emit(
            "Lỗi khi tạo point cloud từ RGB-D.",
            "error",
        )

        self.sig_capture_error.emit(error_text)

    def _retire_save_worker(self, worker: OpenNISaveWorker):
        self._retired_save_workers.append(worker)

        if self._active_save_worker is worker:
            self._active_save_worker = None

    # -------------------------------------------------
    # Preview conversion
    # -------------------------------------------------
    def _make_preview_qimages(
        self,
        rgb: np.ndarray,
        depth: np.ndarray,
    ) -> tuple[QImage, QImage]:
        """
        Tạo QImage.copy() giống pattern code cũ.
        """

        rgb_display = np.asarray(rgb)

        if rgb_display.ndim != 3 or rgb_display.shape[2] < 3:
            raise RuntimeError("RGB frame không hợp lệ để preview.")

        rgb_display = rgb_display[:, :, :3].astype(np.uint8)

        # Depth colormap.
        depth_colored = cv2.applyColorMap(
            cv2.convertScaleAbs(depth, alpha=0.05),
            cv2.COLORMAP_JET,
        )

        depth_rgb = cv2.cvtColor(depth_colored, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb_display.shape
        bytes_per_line = ch * w

        qt_rgb = QImage(
            rgb_display.data,
            w,
            h,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()

        hd, wd, chd = depth_rgb.shape
        depth_bytes_per_line = chd * wd

        qt_depth = QImage(
            depth_rgb.data,
            wd,
            hd,
            depth_bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()

        return qt_rgb, qt_depth

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _make_capture_path(
        self,
        frame_id: int,
        pitch_deg: float,
        yaw_deg: float,
    ) -> Path:
        timestamp = datetime.now().strftime("%H%M%S")

        safe_pitch = self._format_angle_for_filename(pitch_deg)
        safe_yaw = self._format_angle_for_filename(yaw_deg)

        file_name = (
            f"scan_P{safe_pitch}_Y{safe_yaw}_"
            f"F{frame_id:06d}_{timestamp}.ply"
        )

        return self.session_dir / file_name

    def _format_angle_for_filename(self, value: float) -> str:
        text = f"{float(value):.1f}"
        text = text.replace("-", "m")
        text = text.replace(".", "p")
        return text

    def _make_session_id(self) -> str:
        return (
            f"{self.params.session_prefix}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

    def _sleep_remaining(
        self,
        loop_start: float,
        frame_interval: float,
    ):
        elapsed = time.time() - loop_start
        remaining = frame_interval - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def _cleanup_camera(self):
        """
        Cleanup chỉ chạy nếu worker bị request_stop.
        Không liên quan nút QUÉT CẦM TAY.
        """

        try:
            time.sleep(0.2)

            if self.params.auto_disconnect_on_stop:
                self.camera.disconnect()
            else:
                self.camera.stop_stream()

        except Exception:
            pass