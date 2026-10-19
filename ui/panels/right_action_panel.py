from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
)

from ui.styles.theme import theme
from ui.widgets.actions.big_button import BigButton
from controllers.pipeline_state import PipelineActionState

class RightActionPanel(QFrame):
    """
    Bảng thao tác bên phải cho quy trình Scan-to-Path.

    Các bước chính:
        1. Nạp / quét mẫu 3D
        2. Tách vật thể bằng Edge AI
        3. Tạo và xử lý đám mây điểm
        4. Tính pháp tuyến bề mặt
        5. Tạo bản đồ bề mặt 3D
        6. Sinh đường Zigzag / Contour
        7. Xuất kết quả

    Lưu ý:
        Panel này chỉ phát tín hiệu UI.
        Không xử lý thuật toán trực tiếp tại đây.
    """

    action_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.lbl_title = None
        self.lbl_input = None
        self.lbl_processing = None
        self.lbl_path = None
        self.lbl_output = None

        self.btn_load_scan = None
        self.btn_edge_ai_mask = None
        self.btn_build_pointcloud = None
        self.btn_filter_pointcloud = None
        self.btn_build_surface_map = None
        self.btn_estimate_normals = None
        self.btn_generate_zigzag = None
        self.btn_generate_contour = None
        self.btn_export_results = None

        self._build_ui()
        self._build_layout()
        self._bind_events()

        self.set_idle_mode()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("right_action_panel")
        self.setProperty("role", "flat")

        self.setMinimumWidth(theme.sizes.RIGHT_PANEL_MIN_WIDTH)

        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )

        self.lbl_title = QLabel("QUY TRÌNH SCAN-TO-PATH")
        self.lbl_title.setObjectName("panel_title")

        self.lbl_input = QLabel("1. DỮ LIỆU VÀ EDGE AI")
        self.lbl_input.setObjectName("section_label")

        self.lbl_processing = QLabel("2. XỬ LÝ DỮ LIỆU 3D")
        self.lbl_processing.setObjectName("section_label")

        self.lbl_path = QLabel("3. SINH ĐƯỜNG DẪN")
        self.lbl_path.setObjectName("section_label")

        self.lbl_output = QLabel("4. KẾT QUẢ")
        self.lbl_output.setObjectName("section_label")

        self.btn_load_scan = BigButton(
            "NẠP / QUÉT MẪU 3D",
            role="action",
        )

        self.btn_edge_ai_mask = BigButton(
            "TÁCH VẬT THỂ BẰNG EDGE AI",
            role="action",
        )

        self.btn_build_pointcloud = BigButton(
            "TẠO ĐÁM MÂY ĐIỂM",
            role="action",
        )

        self.btn_filter_pointcloud = BigButton(
            "LỌC NHIỄU ĐÁM MÂY ĐIỂM",
            role="action",
        )

        self.btn_build_surface_map = BigButton(
            "TẠO BẢN ĐỒ BỀ MẶT 3D",
            role="action",
        )

        self.btn_estimate_normals = BigButton(
            "TÍNH PHÁP TUYẾN BỀ MẶT",
            role="action",
        )

        self.btn_generate_zigzag = BigButton(
            "SINH ĐƯỜNG ZIGZAG",
            role="primary",
        )

        self.btn_generate_contour = BigButton(
            "SINH ĐƯỜNG CONTOUR",
            role="primary",
        )

        self.btn_export_results = BigButton(
            "XUẤT KẾT QUẢ",
            role="primary",
            height=theme.sizes.BUTTON_HEIGHT_LARGE,
        )

    # -------------------------------------------------
    # Layout
    # -------------------------------------------------
    def _build_layout(self):
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            theme.spacing.SM,
            theme.spacing.SM,
            theme.spacing.SM,
            theme.spacing.SM,
        )

        layout.setSpacing(5)

        layout.addWidget(self.lbl_title)
        layout.addSpacing(4)

        # 1. Input / Edge AI
        layout.addWidget(self.lbl_input)
        layout.addWidget(self.btn_load_scan)
        layout.addWidget(self.btn_edge_ai_mask)

        layout.addSpacing(6)

        # 2. 3D processing
        layout.addWidget(self.lbl_processing)
        layout.addWidget(self.btn_build_pointcloud)
        layout.addWidget(self.btn_filter_pointcloud)
        layout.addWidget(self.btn_estimate_normals)
        layout.addWidget(self.btn_build_surface_map)

        layout.addSpacing(6)

        # 3. Path generation
        layout.addWidget(self.lbl_path)
        layout.addWidget(self.btn_generate_zigzag)
        layout.addWidget(self.btn_generate_contour)

        layout.addSpacing(6)

        # 4. Output
        layout.addWidget(self.lbl_output)
        layout.addWidget(self.btn_export_results)

        layout.addStretch()

    # -------------------------------------------------
    # Events
    # -------------------------------------------------
    def _bind_events(self):
        self.btn_load_scan.clicked.connect(
            lambda: self._emit_action("load_scan")
        )

        self.btn_edge_ai_mask.clicked.connect(
            lambda: self._emit_action("edge_ai_mask")
        )

        self.btn_build_pointcloud.clicked.connect(
            lambda: self._emit_action("build_pointcloud")
        )

        self.btn_filter_pointcloud.clicked.connect(
            lambda: self._emit_action("filter_pointcloud")
        )

        self.btn_build_surface_map.clicked.connect(
            lambda: self._emit_action("build_surface_map")
        )

        self.btn_estimate_normals.clicked.connect(
            lambda: self._emit_action("estimate_normals")
        )

        self.btn_generate_zigzag.clicked.connect(
            lambda: self._emit_action("generate_zigzag")
        )

        self.btn_generate_contour.clicked.connect(
            lambda: self._emit_action("generate_contour")
        )

        self.btn_export_results.clicked.connect(
            lambda: self._emit_action("export_results")
        )

    def _emit_action(self, name: str):
        self.action_requested.emit(name)

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def set_idle_mode(self):
        """
        Trạng thái ban đầu:
            - Chỉ cho phép NẠP / QUÉT MẪU 3D.
            - Các bước sau khóa lại cho đến khi pipeline có dữ liệu.
        """

        self.lock_controls()
        self.set_load_enabled(True)

    def set_scan_loaded_mode(self):
        self.unlock_controls()

    def set_processing_mode(self):
        self.unlock_controls()
        self.btn_load_scan.disable_button()

    def set_result_ready_mode(self):
        self.unlock_controls()
        self.btn_export_results.enable_button()

    def lock_controls(self):
        for btn in self._all_buttons():
            btn.disable_button()

    def unlock_controls(self):
        for btn in self._all_buttons():
            btn.enable_button()

    def set_load_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_load_scan, enabled)

        if not enabled and self.camera_panel is not None:
            self.camera_panel.setVisible(False)

    def set_edge_ai_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_edge_ai_mask, enabled)

    def set_pointcloud_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_build_pointcloud, enabled)

    def set_filter_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_filter_pointcloud, enabled)

    def set_surface_map_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_build_surface_map, enabled)

    def set_normals_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_estimate_normals, enabled)

    def set_zigzag_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_generate_zigzag, enabled)


    def set_contour_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_generate_contour, enabled)


    def set_path_enabled(self, enabled: bool):
        """
        Giữ lại để tương thích code cũ.
        Bật/tắt cả Zigzag và Contour.
        """

        self.set_zigzag_enabled(enabled)
        self.set_contour_enabled(enabled)

    def set_export_enabled(self, enabled: bool):
        self._set_button_enabled(self.btn_export_results, enabled)

    def apply_action_state(self, state: PipelineActionState):
        """
        Nhận trạng thái action từ PipelineStateManager
        và áp dụng lên các nút trong RightActionPanel.
        """

        self.set_load_enabled(state.load_scan)
        self.set_edge_ai_enabled(state.edge_ai_mask)
        self.set_pointcloud_enabled(state.build_pointcloud)
        self.set_filter_enabled(state.filter_pointcloud)
        self.set_normals_enabled(state.estimate_normals)
        self.set_surface_map_enabled(state.build_surface_map)
        self.set_zigzag_enabled(state.generate_zigzag)
        self.set_contour_enabled(state.generate_contour)
        self.set_export_enabled(state.export_results)

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def _set_button_enabled(self, button, enabled: bool):
        if enabled:
            button.enable_button()
        else:
            button.disable_button()

    def _all_buttons(self):
        return [
            self.btn_load_scan,
            self.btn_edge_ai_mask,
            self.btn_build_pointcloud,
            self.btn_filter_pointcloud,
            self.btn_estimate_normals,
            self.btn_build_surface_map,
            self.btn_generate_zigzag,
            self.btn_generate_contour,
            self.btn_export_results,
        ]