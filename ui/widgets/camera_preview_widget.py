from __future__ import annotations

from typing import Optional

import numpy as np

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


class CameraFrameView(QFrame):
    """
    Một khung hiển thị frame camera.

    Dùng cho:
        - RGB Stream
        - Depth Stream
    """

    def __init__(
        self,
        title: str,
        placeholder: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.title = title
        self.placeholder = placeholder

        self.lbl_title = None
        self.lbl_image = None
        self.lbl_info = None

        self.current_pixmap: Optional[QPixmap] = None

        self._build_ui()
        self._build_layout()
        self._apply_styles()
        self.clear()

    # -------------------------------------------------
    # Build
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("CameraFrameView")
        self.setMinimumSize(320, 240)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.lbl_title = QLabel(self.title)
        self.lbl_title.setObjectName("CameraFrameTitle")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.lbl_image = QLabel()
        self.lbl_image.setObjectName("CameraFrameImage")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setMinimumSize(300, 200)
        self.lbl_image.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.lbl_info = QLabel("--")
        self.lbl_info.setObjectName("CameraFrameInfo")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        root.addWidget(self.lbl_title)
        root.addWidget(self.lbl_image, 1)
        root.addWidget(self.lbl_info)

    def _apply_styles(self):
        self.setStyleSheet("""
            QFrame#CameraFrameView {
                background-color: #15171b;
                border: 1px solid #303743;
                border-radius: 8px;
            }

            QLabel#CameraFrameTitle {
                color: #ffffff;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.6px;
            }

            QLabel#CameraFrameImage {
                background-color: #0e1013;
                border: 1px solid #262c34;
                border-radius: 6px;
                color: #6f7a89;
                font-size: 13px;
                font-weight: 600;
            }

            QLabel#CameraFrameInfo {
                color: #9ca8b8;
                font-size: 10px;
            }
        """)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_pixmap(self, pixmap: QPixmap, info: str = ""):
        if pixmap is None or pixmap.isNull():
            self.clear()
            return

        self.current_pixmap = pixmap
        self._update_scaled_pixmap()

        if info:
            self.lbl_info.setText(info)

    def set_image_array(self, image: np.ndarray, info: str = ""):
        """
        Nhận numpy image và hiển thị.

        Hỗ trợ:
            - RGB uint8: H x W x 3
            - BGR uint8: H x W x 3 nếu truyền bgr=True ở caller thì tự đổi trước
            - Grayscale / depth normalized: H x W
        """

        if image is None:
            self.clear()
            return

        image = np.asarray(image)

        if image.size <= 0:
            self.clear()
            return

        qimage = self._numpy_to_qimage(image)

        if qimage is None:
            self.clear()
            return

        self.set_pixmap(QPixmap.fromImage(qimage), info=info)

    def clear(self):
        self.current_pixmap = None
        self.lbl_image.setPixmap(self._make_placeholder_pixmap())
        self.lbl_info.setText("Chưa có frame.")

    def set_info(self, text: str):
        self.lbl_info.setText(text)

    # -------------------------------------------------
    # Conversion
    # -------------------------------------------------
    def _numpy_to_qimage(self, image: np.ndarray) -> Optional[QImage]:
        image = np.asarray(image)

        if image.ndim == 2:
            gray = self._normalize_to_uint8(image)
            h, w = gray.shape

            qimage = QImage(
                gray.data,
                w,
                h,
                gray.strides[0],
                QImage.Format.Format_Grayscale8,
            )

            return qimage.copy()

        if image.ndim == 3 and image.shape[2] >= 3:
            rgb = image[:, :, :3]

            if rgb.dtype != np.uint8:
                rgb = self._normalize_to_uint8(rgb)

            rgb = np.ascontiguousarray(rgb)
            h, w, ch = rgb.shape

            qimage = QImage(
                rgb.data,
                w,
                h,
                rgb.strides[0],
                QImage.Format.Format_RGB888,
            )

            return qimage.copy()

        return None

    def _normalize_to_uint8(self, image: np.ndarray) -> np.ndarray:
        image = np.asarray(image, dtype=np.float32)

        image = np.nan_to_num(
            image,
            nan=0.0,
            posinf=0.0,
            neginf=0.0,
        )

        min_val = float(np.min(image))
        max_val = float(np.max(image))

        if max_val - min_val < 1e-9:
            return np.zeros(image.shape, dtype=np.uint8)

        image = (image - min_val) / (max_val - min_val)
        image = image * 255.0

        return image.astype(np.uint8)

    # -------------------------------------------------
    # Resize
    # -------------------------------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self.current_pixmap is None or self.current_pixmap.isNull():
            return

        target_size = self.lbl_image.size()

        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        scaled = self.current_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.lbl_image.setPixmap(scaled)

    def _make_placeholder_pixmap(self) -> QPixmap:
        size = self.lbl_image.size()

        if size.width() <= 10 or size.height() <= 10:
            size = QSize(320, 220)

        pixmap = QPixmap(size)
        pixmap.fill(QColor("#0e1013"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QColor("#606b7a"))

        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            self.placeholder,
        )

        painter.end()

        return pixmap


class CameraPreviewWidget(QFrame):
    """
    Widget preview camera gồm 2 khung:

        1. RGB STREAM
        2. DEPTH STREAM

    Giai đoạn hiện tại:
        - Chưa tự lấy frame camera.
        - Chỉ cung cấp API để bên ngoài set frame vào.

    Sau này CameraSourceDialog hoặc CameraService sẽ gọi:
        set_rgb_frame(...)
        set_depth_frame(...)
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.lbl_title = None
        self.lbl_status = None

        self.rgb_view = None
        self.depth_view = None

        self._build_ui()
        self._build_layout()
        self._apply_styles()

        self.set_status("CHƯA KẾT NỐI CAMERA")

    # -------------------------------------------------
    # Build
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("CameraPreviewWidget")
        self.setMinimumSize(640, 520)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.lbl_title = QLabel("CAMERA PREVIEW")
        self.lbl_title.setObjectName("CameraPreviewTitle")

        self.lbl_status = QLabel("Trạng thái: --")
        self.lbl_status.setObjectName("CameraPreviewStatus")

        self.rgb_view = CameraFrameView(
            title="RGB STREAM",
            placeholder="RGB STREAM\nCHƯA CÓ TÍN HIỆU",
        )

        self.depth_view = CameraFrameView(
            title="DEPTH STREAM",
            placeholder="DEPTH STREAM\nCHƯA CÓ TÍN HIỆU",
        )

    def _build_layout(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        header.addWidget(self.lbl_title)
        header.addStretch()
        header.addWidget(self.lbl_status)

        root.addLayout(header)

        # Hai frame xếp dọc để nhìn rõ cả RGB và Depth.
        root.addWidget(self.rgb_view, 1)
        root.addWidget(self.depth_view, 1)

    def _apply_styles(self):
        self.setStyleSheet("""
            QFrame#CameraPreviewWidget {
                background-color: #111318;
                border: 1px solid #303743;
                border-radius: 10px;
            }

            QLabel#CameraPreviewTitle {
                color: #ffffff;
                font-size: 15px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }

            QLabel#CameraPreviewStatus {
                color: #8fa1b7;
                font-size: 11px;
                font-weight: 600;
            }
        """)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_status(self, text: str):
        self.lbl_status.setText(f"Trạng thái: {text}")

    def set_rgb_frame(self, frame: np.ndarray, info: str = ""):
        if info == "":
            info = self._make_frame_info(frame, prefix="RGB")

        self.rgb_view.set_image_array(frame, info=info)

    def set_depth_frame(self, frame: np.ndarray, info: str = ""):
        if info == "":
            info = self._make_frame_info(frame, prefix="DEPTH")

        self.depth_view.set_image_array(frame, info=info)

    def set_rgb_pixmap(self, pixmap: QPixmap, info: str = ""):
        self.rgb_view.set_pixmap(pixmap, info=info)

    def set_depth_pixmap(self, pixmap: QPixmap, info: str = ""):
        self.depth_view.set_pixmap(pixmap, info=info)

    def clear_rgb(self):
        self.rgb_view.clear()

    def clear_depth(self):
        self.depth_view.clear()

    def clear_all(self):
        self.rgb_view.clear()
        self.depth_view.clear()
        self.set_status("CHƯA CÓ TÍN HIỆU")

    def show_mock_frames(self):
        """
        Tạo frame giả để test layout preview.
        Sau này xóa cũng được.
        """

        rgb = self._make_mock_rgb()
        depth = self._make_mock_depth()

        self.set_rgb_frame(rgb, info="RGB MOCK | 640 x 480")
        self.set_depth_frame(depth, info="DEPTH MOCK | 640 x 480")
        self.set_status("ĐANG HIỂN THỊ MOCK FRAME")

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _make_frame_info(self, frame: np.ndarray, prefix: str) -> str:
        try:
            h, w = frame.shape[:2]
            dtype = frame.dtype
            return f"{prefix} | {w} x {h} | {dtype}"
        except Exception:
            return f"{prefix} | FRAME"

    def _make_mock_rgb(self) -> np.ndarray:
        h, w = 480, 640

        x = np.linspace(0, 255, w, dtype=np.uint8)
        y = np.linspace(0, 255, h, dtype=np.uint8)

        xx, yy = np.meshgrid(x, y)

        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        rgb[:, :, 0] = xx
        rgb[:, :, 1] = yy
        rgb[:, :, 2] = 120

        return rgb

    def _make_mock_depth(self) -> np.ndarray:
        h, w = 480, 640

        x = np.linspace(-1.0, 1.0, w, dtype=np.float32)
        y = np.linspace(-1.0, 1.0, h, dtype=np.float32)

        xx, yy = np.meshgrid(x, y)

        depth = np.sqrt(xx ** 2 + yy ** 2)
        depth = 1.0 - np.clip(depth, 0.0, 1.0)

        return depth