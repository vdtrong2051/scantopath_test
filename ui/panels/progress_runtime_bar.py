from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QWidget,
    QLabel,
    QHBoxLayout,
    QProgressBar,
    QSizePolicy,
)

from ui.styles.theme import theme


class ProgressRuntimeBar(QFrame):
    """
    Thanh tiến trình dưới cùng cho quy trình Scan-to-Path.

    Bên trái:
        Tên pipeline + thanh tiến trình + bước hiện tại

    Bên phải:
        Chế độ + số điểm + phương pháp + trạng thái đầu ra

    Giữ lại một số tên hàm cũ để tương thích với MainWindow:
        set_job()
        set_progress()
        set_eta()
        set_mode()
        set_speed()
        set_flow()
        set_temp()
        set_running_state()
        set_idle_state()
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl_job = None
        self.progress = None
        self.lbl_stage = None

        self.lbl_mode = None
        self.lbl_points = None
        self.lbl_method = None
        self.lbl_output = None

        self._build_ui()
        self._build_layout()
        self.set_idle_state()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("progress_runtime_bar")
        self.setProperty("role", "flat")

        self.setFixedHeight(theme.sizes.PROGRESS_BAR_HEIGHT + 14)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # Left section
        self.lbl_job = QLabel("SCAN-TO-PATH")
        self.lbl_job.setStyleSheet("font-weight: 700;")
        self.lbl_job.setMinimumWidth(110)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("%p%")

        self.lbl_stage = QLabel("BƯỚC: CHỜ")
        self.lbl_stage.setProperty("role", "muted")
        self.lbl_stage.setMinimumWidth(180)

        # Right section
        self.lbl_mode = QLabel("CHẾ ĐỘ: CHỜ")
        self.lbl_points = QLabel("ĐIỂM: --")
        self.lbl_method = QLabel("P.PHÁP: --")
        self.lbl_output = QLabel("ĐẦU RA: --")

        for label in (
            self.lbl_mode,
            self.lbl_points,
            self.lbl_method,
            self.lbl_output,
        ):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_mode.setFixedWidth(110)
        self.lbl_points.setFixedWidth(100)
        self.lbl_method.setFixedWidth(125)
        self.lbl_output.setFixedWidth(115)

        for label in (
            self.lbl_mode,
            self.lbl_points,
            self.lbl_method,
            self.lbl_output,
        ):
            label.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )

    def _build_layout(self):
        root = QHBoxLayout(self)

        root.setContentsMargins(
            theme.spacing.MD,
            theme.spacing.SM,
            theme.spacing.MD,
            theme.spacing.SM,
        )

        root.setSpacing(theme.spacing.MD)

        # ---------------------------------------------
        # Left section
        # ---------------------------------------------
        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(theme.spacing.SM)

        left_layout.addWidget(self.lbl_job, 1)
        left_layout.addWidget(self.progress, 6)
        left_layout.addWidget(self.lbl_stage, 2)

        # ---------------------------------------------
        # Right section
        # ---------------------------------------------
        right = QWidget()
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(theme.spacing.SM)

        def _v_line():
            line = QFrame()
            line.setFixedWidth(1)
            line.setStyleSheet(
                "background-color: #313338; "
                "margin-top: 6px; "
                "margin-bottom: 6px;"
            )
            return line

        right_layout.addWidget(self.lbl_mode)
        right_layout.addWidget(_v_line())
        right_layout.addWidget(self.lbl_points)
        right_layout.addWidget(_v_line())
        right_layout.addWidget(self.lbl_method)
        right_layout.addWidget(_v_line())
        right_layout.addWidget(self.lbl_output)

        # ---------------------------------------------
        # Root
        # ---------------------------------------------
        progress_left = getattr(theme.ratios, "PROGRESS_LEFT", 58)
        info_right = getattr(theme.ratios, "INFO_RIGHT", 42)

        root.addWidget(left, progress_left)
        root.addWidget(right, info_right)

    # -------------------------------------------------
    # Public API - Progress
    # -------------------------------------------------
    def set_job(self, text: str):
        self.lbl_job.setText(text)

    def set_progress(self, value: int):
        value = max(0, min(100, int(value)))
        self.progress.setValue(value)

    def set_stage(self, text: str):
        clean_text = self._clean_stage_text(text)
        short_text = self._compact_text(clean_text, max_chars=26)

        self.lbl_stage.setText(f"BƯỚC: {short_text}")
        self.lbl_stage.setToolTip(clean_text)

    def set_eta(self, text: str):
        """
        Tên hàm cũ giữ lại để tương thích.

        Ý nghĩa mới:
            Hiển thị bước xử lý hiện tại.
        """
        self.set_stage(text)

    # -------------------------------------------------
    # Public API - Runtime info
    # -------------------------------------------------
    def set_mode(self, text: str):
        self._set_runtime_text(
            self.lbl_mode,
            prefix="CĐ",
            text=text,
            max_chars=12,
        )

    def set_points(self, value):
        self._set_runtime_text(
            self.lbl_points,
            prefix="ĐIỂM",
            text=value,
            max_chars=10,
        )

    def set_method(self, text: str):
        self._set_runtime_text(
            self.lbl_method,
            prefix="PP",
            text=text,
            max_chars=13,
        )

    def set_output(self, text: str):
        self._set_runtime_text(
            self.lbl_output,
            prefix="RA",
            text=text,
            max_chars=12,
        )

    # -------------------------------------------------
    # Backward-compatible API
    # -------------------------------------------------
    def set_speed(self, value: int | float):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            Hiển thị số điểm point cloud.
        """
        self.set_points(value)

    def set_flow(self, text: str):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            Hiển thị phương pháp xử lý.
        """
        self.set_method(text)

    def set_temp(self, value):
        """
        Tên cũ giữ lại để tương thích.

        Ý nghĩa mới:
            Hiển thị trạng thái đầu ra.
        """
        self.set_output(value)

    # -------------------------------------------------
    # Presets
    # -------------------------------------------------
    def set_running_state(self):
        self.set_mode("ĐANG XỬ LÝ")
        self.set_method("ĐANG CHẠY")
        self.set_output("CHỜ XUẤT")

    def set_idle_state(self):
        self.set_mode("CHỜ")
        self.set_points("--")
        self.set_method("--")
        self.set_output("--")

    def set_result_ready_state(self):
        self.set_mode("SẴN SÀNG")
        self.set_method("SCAN-TO-PATH")
        self.set_output("ĐÃ XUẤT")

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _clean_stage_text(self, text: str) -> str:
        """
        Xóa các tiền tố tiếng Anh cũ nếu MainWindow truyền vào dạng:
            Stage: Filter Point Cloud
            STAGE: Exported
        """
        if text is None:
            return "CHỜ"

        clean_text = str(text).strip()

        prefixes = (
            "Stage:",
            "STAGE:",
            "stage:",
            "ETA:",
            "eta:",
        )

        for prefix in prefixes:
            if clean_text.startswith(prefix):
                clean_text = clean_text[len(prefix):].strip()

        return clean_text or "CHỜ"
    
    def _set_runtime_text(
        self,
        label: QLabel,
        prefix: str,
        text,
        max_chars: int = 12,
    ):
        """
        Set text cho các ô runtime bên phải.

        Có 2 mục tiêu:
            - Hiển thị ngắn để không bị khuất.
            - Giữ tooltip đầy đủ để rê chuột vẫn xem được nội dung gốc.
        """

        raw_text = "--" if text is None else str(text).strip()
        display_text = self._compact_text(raw_text, max_chars=max_chars)

        label.setText(f"{prefix}: {display_text}")
        label.setToolTip(raw_text)


    def _compact_text(self, text: str, max_chars: int = 12) -> str:
        """
        Rút gọn text dài để runtime bar không bị tràn.
        """

        if text is None:
            return "--"

        text = str(text).strip()

        if not text:
            return "--"

        replacements = {
            "ĐANG XỬ LÝ": "ĐANG XL",
            "ĐÃ XỬ LÝ": "ĐÃ XL",
            "HOÀN TẤT": "XONG",
            "CHỜ XỬ LÝ": "CHỜ XL",
            "POINT CLOUD": "PC",
            "POINT CLOUD THÔ": "PC THÔ",
            "POINT CLOUD SẠCH": "PC SẠCH",
            "CHƯA CÓ POINT CLOUD": "CHƯA CÓ PC",
            "SURFACE MESH": "MESH",
            "NORMAL FIELD": "NORMAL",
            "ZIGZAG PATH": "ZIGZAG",
            "CONTOUR PATH": "CONTOUR",
            "RGB-D HANDHELD": "RGB-D HAND",
            "TURNTABLE MOCK": "TURNTABLE",
            "HANDHELD MOCK": "HANDHELD",
            "VOXEL / OUTLIER": "VOXEL",
            "KD-TREE / PCA": "KD/PCA",
            "SAFE_MESH_SLICING": "MESH SLICE",
            "STOP-AND-GO": "STOP-GO",
        }

        upper_text = text.upper()

        for old, new in replacements.items():
            upper_text = upper_text.replace(old, new)

        if len(upper_text) <= max_chars:
            return upper_text

        return upper_text[: max_chars - 1] + "…"