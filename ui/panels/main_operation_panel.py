from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)

from ui.styles.theme import theme
from ui.panels.viewport_3d import Viewport3D
from ui.panels.right_action_panel import RightActionPanel


class MainOperationPanel(QWidget):
    """
    Main working area for Scan-to-Path.

    Layout:
        Left  -> 3D Viewport
        Right -> Scan-to-Path Action Panel

    Responsibility:
        - Hold UI containers only
        - Expose helper methods
        - No business logic
        - No backend processing
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.viewport = None
        self.actions = None

        self._build_ui()
        self._build_layout()

    # -------------------------------------------------
    # UI
    # -------------------------------------------------
    def _build_ui(self):
        self.setObjectName("main_operation_panel")

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.viewport = Viewport3D()
        self.actions = RightActionPanel()

    # -------------------------------------------------
    # Layout
    # -------------------------------------------------
    def _build_layout(self):
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            theme.spacing.SM,
            theme.spacing.SM,
            theme.spacing.SM,
            theme.spacing.SM,
        )

        layout.setSpacing(theme.spacing.SM)

        layout.addWidget(
            self.viewport,
            getattr(theme.ratios, "MAIN_LEFT", 7),
        )

        layout.addWidget(
            self.actions,
            getattr(theme.ratios, "MAIN_RIGHT", 3),
        )

    # -------------------------------------------------
    # Public API
    # -------------------------------------------------
    def reset_state(self):
        self.viewport.show_ready_state()
        self.actions.set_idle_mode()

    def set_viewport_status(self, text: str):
        self.viewport.set_viewport_status(text)

    def show_scan(self):
        self.viewport.show_scan_mode()

    def show_edge_ai(self):
        self.viewport.show_edge_ai_mode()

    def show_raw_pointcloud(self):
        self.viewport.show_raw_pointcloud_mode()

    def show_clean_pointcloud(self):
        self.viewport.show_clean_pointcloud_mode()

    def show_surface_map(self):
        self.viewport.show_surface_map_mode()

    def show_normals(self):
        self.viewport.show_normal_mode()

    def show_zigzag_path(self):
        self.viewport.show_zigzag_path_mode()

    def show_contour_path(self):
        self.viewport.show_contour_path_mode()

    def show_export(self):
        self.viewport.show_export_mode()

    def lock_controls(self):
        self.actions.lock_controls()

    def unlock_controls(self):
        self.actions.unlock_controls()