from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class AstraCameraIntrinsics:
    """
    Thông số nội tại camera RGB-D.

    Đơn vị depth:
        - depth raw từ OpenNI thường là uint16 millimeter.
        - depth_scale = 0.001 nghĩa là mm → m.
    """

    width: int = 640
    height: int = 480

    fx: float = 580.0
    fy: float = 580.0
    cx: float = 320.0
    cy: float = 240.0

    depth_scale: float = 0.001


@dataclass
class AstraFrameBundle:
    """
    Gói frame RGB-D lấy từ Astra/OpenNI2.
    """

    rgb: np.ndarray
    depth: np.ndarray

    timestamp: float
    frame_id: int

    intrinsics: AstraCameraIntrinsics
    valid: bool = True

    source: str = "openni_astra"


class AstraCamera:
    """
    Camera backend dùng OpenNI2 cho Orbbec Astra / Astra Mini.

    Vai trò:
        - Nạp OpenNI2 runtime.
        - Kết nối camera.
        - Bật depth stream.
        - Bật color stream.
        - Đọc RGB frame + depth frame.
        - Trả dữ liệu dạng numpy để preview và tạo point cloud.

    Ghi chú:
        - File này chỉ xử lý acquisition.
        - Không tạo point cloud.
        - Không lọc nhiễu.
        - Không tạo surface / path.

    Dựa trên hướng code OpenNI2 cũ của bạn:
        connect()
        get_frames()
        disconnect()
    """

    _is_openni_initialized: bool = False

    def __init__(
        self,
        openni2_path: str | Path | None = None,
        *,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        mirror: bool = True,
        color_format: str = "rgb",
        enable_registration: bool = False,
        intrinsics: Optional[AstraCameraIntrinsics] = None,
    ):
        """
        Args:
            openni2_path:
                Đường dẫn OpenNI2 Redist.
                Nếu None, class sẽ thử lấy từ:
                    - biến môi trường OPENNI2_PATH
                    - config.settings.OPENNI2_PATH nếu có

            width, height, fps:
                Thông số stream mong muốn.

            mirror:
                Lật ngang ảnh RGB/Depth giống code cũ.

            color_format:
                "rgb" hoặc "bgr".
                - "rgb": hợp với CameraPreviewWidget / QImage RGB888.
                - "bgr": hợp với xử lý OpenCV cũ.

            enable_registration:
                Thử bật align depth-to-color.
                Có camera/driver hỗ trợ, có camera không.

            intrinsics:
                Thông số camera. Nếu None thì dùng mặc định.
        """

        self.openni2_path = self._resolve_openni2_path(openni2_path)

        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)

        self.mirror = bool(mirror)
        self.color_format = str(color_format).strip().lower()
        self.enable_registration = bool(enable_registration)

        self.intrinsics = intrinsics or AstraCameraIntrinsics(
            width=self.width,
            height=self.height,
            cx=self.width / 2.0,
            cy=self.height / 2.0,
        )

        self.device = None
        self.depth_stream = None
        self.color_stream = None

        self._openni2 = None

        self._connected = False
        self._streaming = False
        self._frame_id = 0

    # -------------------------------------------------
    # Lifecycle
    # -------------------------------------------------
    def connect(self) -> bool:
        """
        Khởi tạo OpenNI2 và mở camera.
        """

        self._load_openni2()

        try:
            self.device = self._openni2.Device.open_any()
        except Exception as exc:
            raise RuntimeError(
                "Không mở được thiết bị OpenNI2/Astra.\n\n"
                "Kiểm tra:\n"
                "- Camera đã cắm USB chưa\n"
                "- Driver OpenNI2 đã đúng chưa\n"
                "- OPENNI2_PATH đã trỏ đúng thư mục Redist chưa"
            ) from exc

        try:
            info = self.device.get_device_info()
            print(f"[AstraCamera] Đã kết nối thiết bị: {info.name}")
        except Exception:
            print("[AstraCamera] Đã kết nối thiết bị OpenNI2.")

        self._create_streams()
        self._connected = True

        return True

    def disconnect(self) -> None:
        """
        Dừng stream và đóng camera an toàn.
        """

        print("[AstraCamera] Đang ngắt kết nối...")

        self.stop_stream()

        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass

        self.device = None
        self.depth_stream = None
        self.color_stream = None

        self._connected = False
        self._streaming = False

        print("[AstraCamera] Đã ngắt kết nối an toàn.")

    def reset(self) -> None:
        self.disconnect()
        self._frame_id = 0

    def is_connected(self) -> bool:
        return self._connected

    def is_streaming(self) -> bool:
        return self._streaming

    # -------------------------------------------------
    # Stream
    # -------------------------------------------------
    def start_stream(self) -> None:
        """
        Bật depth + color stream.
        """

        if not self._connected:
            self.connect()

        if self.depth_stream is None or self.color_stream is None:
            self._create_streams()

        try:
            self.depth_stream.start()
        except Exception as exc:
            raise RuntimeError("Không start được depth stream.") from exc

        try:
            self.color_stream.start()
        except Exception as exc:
            try:
                self.depth_stream.stop()
            except Exception:
                pass

            raise RuntimeError("Không start được color stream.") from exc

        self._try_enable_sync_and_registration()

        self._streaming = True
        print("[AstraCamera] Đã start RGB-D stream.")

    def stop_stream(self) -> None:
        if self.depth_stream is not None:
            try:
                self.depth_stream.stop()
            except Exception:
                pass

        if self.color_stream is not None:
            try:
                self.color_stream.stop()
            except Exception:
                pass

        self._streaming = False

    # -------------------------------------------------
    # Acquisition
    # -------------------------------------------------
    def get_frames(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Lấy RGB + Depth frame.

        Returns:
            rgb_image:
                np.ndarray H x W x 3.
                Mặc định là RGB nếu color_format="rgb".

            depth_image:
                np.ndarray H x W uint16.
                Đơn vị thường là millimeter.
        """

        if not self._streaming:
            return None, None

        if self.depth_stream is None or self.color_stream is None:
            return None, None

        try:
            depth_frame = self.depth_stream.read_frame()
            color_frame = self.color_stream.read_frame()
        except Exception as exc:
            raise RuntimeError("Không đọc được frame từ OpenNI2 stream.") from exc

        depth_img = self._depth_frame_to_numpy(depth_frame)
        rgb_img = self._color_frame_to_numpy(color_frame)

        if self.mirror:
            rgb_img = cv2.flip(rgb_img, 1)
            depth_img = cv2.flip(depth_img, 1)

        if self.color_format == "bgr":
            rgb_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)

        return rgb_img.copy(), depth_img.copy()

    def get_frame_bundle(self) -> AstraFrameBundle:
        """
        Lấy frame theo dạng bundle thống nhất.
        """

        rgb, depth = self.get_frames()

        if rgb is None or depth is None:
            return AstraFrameBundle(
                rgb=np.empty((0, 0, 3), dtype=np.uint8),
                depth=np.empty((0, 0), dtype=np.uint16),
                timestamp=time.time(),
                frame_id=self._frame_id,
                intrinsics=self.intrinsics,
                valid=False,
            )

        frame = AstraFrameBundle(
            rgb=rgb,
            depth=depth,
            timestamp=time.time(),
            frame_id=self._frame_id,
            intrinsics=self.intrinsics,
            valid=True,
        )

        self._frame_id += 1

        return frame

    def get_intrinsics(self) -> AstraCameraIntrinsics:
        return self.intrinsics

    # -------------------------------------------------
    # Internal OpenNI
    # -------------------------------------------------
    def _load_openni2(self):
        """
        Import và initialize OpenNI2.
        """

        try:
            from openni import openni2
        except Exception as exc:
            raise RuntimeError(
                "Không import được openni.openni2.\n\n"
                "Cần cài package OpenNI cho Python trước.\n"
                "Ví dụ thường gặp:\n"
                "pip install primesense\n"
                "hoặc dùng package openni phù hợp môi trường của bạn."
            ) from exc

        self._openni2 = openni2

        if AstraCamera._is_openni_initialized:
            print("[AstraCamera] OpenNI2 SDK đã được nạp sẵn.")
            return

        path = self.openni2_path

        if path:
            path = str(Path(path).resolve())
            print(f"[AstraCamera] Đang nạp OpenNI2 từ: {path}")

            if hasattr(os, "add_dll_directory") and os.path.exists(path):
                os.add_dll_directory(path)

            try:
                openni2.initialize(path)
            except TypeError:
                openni2.initialize()
        else:
            print("[AstraCamera] OPENNI2_PATH chưa cấu hình, thử openni2.initialize() mặc định.")
            openni2.initialize()

        AstraCamera._is_openni_initialized = True

    def _create_streams(self):
        if self.device is None:
            raise RuntimeError("Chưa có thiết bị OpenNI2 để tạo stream.")

        try:
            self.depth_stream = self.device.create_depth_stream()
        except Exception as exc:
            raise RuntimeError("Không tạo được depth stream.") from exc

        try:
            self.color_stream = self.device.create_color_stream()
        except Exception as exc:
            raise RuntimeError("Không tạo được color stream.") from exc

        self._try_set_video_modes()

    def _try_set_video_modes(self):
        """
        Thử set video mode nếu binding hỗ trợ.
        Nếu fail thì bỏ qua, dùng mode mặc định của camera.
        """

        if self._openni2 is None:
            return

        try:
            video_mode = self._openni2.VideoMode

            depth_format = getattr(
                self._openni2,
                "PIXEL_FORMAT_DEPTH_1_MM",
                None,
            )

            rgb_format = getattr(
                self._openni2,
                "PIXEL_FORMAT_RGB888",
                None,
            )

            if depth_format is not None and self.depth_stream is not None:
                self.depth_stream.set_video_mode(
                    video_mode(
                        pixelFormat=depth_format,
                        resolutionX=self.width,
                        resolutionY=self.height,
                        fps=self.fps,
                    )
                )

            if rgb_format is not None and self.color_stream is not None:
                self.color_stream.set_video_mode(
                    video_mode(
                        pixelFormat=rgb_format,
                        resolutionX=self.width,
                        resolutionY=self.height,
                        fps=self.fps,
                    )
                )

        except Exception as exc:
            print(f"[AstraCamera] Cảnh báo: không set được video mode: {exc}")

    def _try_enable_sync_and_registration(self):
        """
        Thử bật đồng bộ depth-color nếu camera/driver hỗ trợ.
        """

        if self.device is None:
            return

        if not self.enable_registration:
            return

        try:
            self.device.set_depth_color_sync_enabled(True)
            print("[AstraCamera] Đã bật depth-color sync.")
        except Exception as exc:
            print(f"[AstraCamera] Cảnh báo: không bật được sync: {exc}")

        try:
            if self._openni2 is not None:
                self.device.set_image_registration_mode(
                    self._openni2.IMAGE_REGISTRATION_DEPTH_TO_COLOR
                )
                print("[AstraCamera] Đã bật image registration depth-to-color.")
        except Exception as exc:
            print(f"[AstraCamera] Cảnh báo: không bật được registration: {exc}")

    # -------------------------------------------------
    # Frame conversion
    # -------------------------------------------------
    def _depth_frame_to_numpy(self, depth_frame) -> np.ndarray:
        depth_data = np.frombuffer(
            depth_frame.get_buffer_as_uint16(),
            dtype=np.uint16,
        )

        height = int(depth_frame.height)
        width = int(depth_frame.width)

        expected = height * width

        if depth_data.size < expected:
            raise RuntimeError(
                f"Depth buffer thiếu dữ liệu: {depth_data.size}/{expected}"
            )

        depth_img = depth_data[:expected].reshape((height, width))

        return depth_img

    def _color_frame_to_numpy(self, color_frame) -> np.ndarray:
        color_data = np.frombuffer(
            color_frame.get_buffer_as_uint8(),
            dtype=np.uint8,
        )

        height = int(color_frame.height)
        width = int(color_frame.width)

        expected = height * width * 3

        if color_data.size < expected:
            raise RuntimeError(
                f"Color buffer thiếu dữ liệu: {color_data.size}/{expected}"
            )

        color_img = color_data[:expected].reshape((height, width, 3))

        # OpenNI trả RGB888.
        return color_img

    # -------------------------------------------------
    # Config helper
    # -------------------------------------------------
    def _resolve_openni2_path(
        self,
        openni2_path: str | Path | None,
    ) -> Optional[str]:
        if openni2_path:
            return str(openni2_path)

        env_path = os.environ.get("OPENNI2_PATH")

        if env_path:
            return env_path

        # Nếu project của bạn có config.settings.OPENNI2_PATH thì tự nhận.
        try:
            from app.config import settings

            value = getattr(settings, "OPENNI2_PATH", None)

            if value:
                return str(value)
        except Exception:
            pass

        return None

    # -------------------------------------------------
    # Context manager
    # -------------------------------------------------
    def __enter__(self):
        self.connect()
        self.start_stream()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()