from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QMessageBox,
)

from ui.styles.theme import theme

from ui.panels.top_status_bar import TopStatusBar
from ui.panels.progress_runtime_bar import ProgressRuntimeBar
from ui.panels.main_operation_panel import MainOperationPanel

from controllers.pipeline_controller import PipelineController
from controllers.pipeline_action_controller import PipelineActionController


class MainWindow(QMainWindow):
    """
    Cửa sổ HMI chính cho hệ thống Scan-to-Path.

    Vai trò của MainWindow:
        - Build cửa sổ chính.
        - Build các panel UI.
        - Kết nối signal từ RightActionPanel.
        - Khởi tạo PipelineController và PipelineActionController.

    MainWindow không xử lý trực tiếp:
        - Load scan
        - Filter point cloud
        - Estimate normals
        - Build surface map
        - Generate Zigzag
        - Export
        - Camera mock

    Các phần đó đã chuyển sang:
        controllers/pipeline_controller.py
        controllers/pipeline_action_controller.py
    """

    def __init__(self, config=None):
        super().__init__()

        self.config = config

        # -------------------------------------------------
        # Core controllers
        # -------------------------------------------------
        self.pipeline = PipelineController(
            export_root="data/exports",
            project_code="PJ1",
        )

        self.action_controller = None

        # -------------------------------------------------
        # UI references
        # -------------------------------------------------
        self.central = None
        self.top_bar = None
        self.runtime_bar = None
        self.main_panel = None
        self.viewport = None
        self.right_panel = None

        self._build_window()
        self._build_ui()
        self._build_layout()
        self._build_controllers()
        self._bind_events()
        self._load_defaults()

    # -------------------------------------------------
    # Window
    # -------------------------------------------------
    def _build_window(self):
        title = "Scan-to-Path | Hệ thống tái tạo bề mặt 3D"

        if self.config and hasattr(self.config, "app_name"):
            title = self.config.app_name

        self.setWindowTitle(title)

        min_width = getattr(theme.sizes, "WINDOW_MIN_WIDTH", 1280)
        min_height = getattr(theme.sizes, "WINDOW_MIN_HEIGHT", 720)

        default_width = getattr(theme.sizes, "WINDOW_DEFAULT_WIDTH", 1440)
        default_height = getattr(theme.sizes, "WINDOW_DEFAULT_HEIGHT", 900)

        self.setMinimumSize(min_width, min_height)
        self.resize(default_width, default_height)

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.central = QWidget()
        self.setCentralWidget(self.central)

        self.top_bar = TopStatusBar()
        self.runtime_bar = ProgressRuntimeBar()
        self.main_panel = MainOperationPanel()

        # Lấy tham chiếu từ MainOperationPanel
        self.viewport = self.main_panel.viewport
        self.right_panel = self.main_panel.actions

    def _build_layout(self):
        root_layout = QVBoxLayout(self.central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.top_bar)
        root_layout.addWidget(self.main_panel, 1)
        root_layout.addWidget(self.runtime_bar)

    # -------------------------------------------------
    # Controllers
    # -------------------------------------------------
    def _build_controllers(self):
        """
        Tạo controller xử lý action UI.

        PipelineActionController nhận:
            - window: để truy cập top_bar, runtime_bar, viewport, right_panel
            - pipeline: để gọi xử lý dữ liệu thật
        """

        self.action_controller = PipelineActionController(
            window=self,
            pipeline=self.pipeline,
        )

    # -------------------------------------------------
    # Events
    # -------------------------------------------------
    def _bind_events(self):
        """
        RightActionPanel phát signal action_requested(str).
        MainWindow chỉ nối signal này sang PipelineActionController.
        """

        if hasattr(self.right_panel, "action_requested"):
            self.right_panel.action_requested.connect(
                self.action_controller.handle_action
            )
            return

        print("[UI WARNING] RightActionPanel không có signal action_requested.")

    # -------------------------------------------------
    # Default State
    # -------------------------------------------------
    def _load_defaults(self):
        self._set_top_status(
            system=("HỆ THỐNG: SẴN SÀNG", "success"),
            scan=("QUÉT: CHỜ DỮ LIỆU", "muted"),
            path=("ĐƯỜNG DẪN: SẴN SÀNG", "muted"),
        )

        self._safe_call(self.runtime_bar, "set_job", "SCAN-TO-PATH")
        self._safe_call(self.runtime_bar, "set_progress", 0)
        self._safe_call(self.runtime_bar, "set_eta", "CHỜ")
        self._safe_call(self.runtime_bar, "set_idle_state")
        self._safe_call(self.runtime_bar, "set_points", "--")
        self._safe_call(self.runtime_bar, "set_method", "--")
        self._safe_call(self.runtime_bar, "set_output", "--")

        self._set_viewport_status(
            "SẴN SÀNG\n"
            "Nạp file quét 3D hoặc quét dữ liệu từ camera Orbbec Astra Mini Pro."
        )

        if self.action_controller is not None:
            self.action_controller.apply_pipeline_stage()

    # -------------------------------------------------
    # UI Helpers
    # -------------------------------------------------
    def _safe_call(self, obj, method_name: str, *args, **kwargs):
        if obj is None:
            return None

        method = getattr(obj, method_name, None)

        if callable(method):
            return method(*args, **kwargs)

        return None

    def _set_top_status(self, system=None, scan=None, path=None):
        """
        Tương thích với TopStatusBar hiện tại:
            set_machine_status(...)
            set_camera_status(...)
            set_robot_status(...)

        Ý nghĩa mới:
            machine_status -> trạng thái hệ thống
            camera_status  -> trạng thái dữ liệu quét/bề mặt
            robot_status   -> trạng thái đường dẫn
        """

        if system:
            self._safe_call(
                self.top_bar,
                "set_machine_status",
                system[0],
                system[1],
            )

        if scan:
            self._safe_call(
                self.top_bar,
                "set_camera_status",
                scan[0],
                scan[1],
            )

        if path:
            self._safe_call(
                self.top_bar,
                "set_robot_status",
                path[0],
                path[1],
            )

    def _set_viewport_status(self, message: str):
        """
        Tương thích với nhiều phiên bản Viewport3D khác nhau.
        """

        if self.viewport is None:
            print(message)
            return

        possible_methods = [
            "set_viewport_status",
            "set_status",
            "set_message",
            "show_message",
            "show_placeholder",
        ]

        for method_name in possible_methods:
            method = getattr(self.viewport, method_name, None)

            if callable(method):
                method(message)
                return

        print(f"[VIEWPORT] {message}")

    # -------------------------------------------------
    # Optional Fullscreen
    # -------------------------------------------------
    def start_fullscreen(self):
        self.showFullScreen()

    # -------------------------------------------------
    # Close confirm
    # -------------------------------------------------
    def closeEvent(self, event):
        reply = QMessageBox.question(
            self,
            "Thoát",
            "Đóng Scan-to-Path?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()