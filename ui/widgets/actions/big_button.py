from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QPushButton, QSizePolicy

from ui.styles.theme import theme


class BigButton(QPushButton):
    """
    Reusable large HMI button for Scan-to-Path UI.

    Roles:
        action      - Load Scan, Edge AI, Point Cloud, Surface Map
        primary     - Zigzag, Contour, Export
        danger      - Stop / Reset / Error if needed
        nav         - Optional navigation
        nav_active  - Optional active navigation
        inline      - Small inline button
    """

    clicked_label = pyqtSignal(str)

    def __init__(
        self,
        text: str,
        role: str = "primary",
        height: int | None = None,
        checkable: bool = False,
        parent=None,
    ):
        super().__init__(text, parent)

        self.role = role
        self.button_height = height or theme.sizes.BUTTON_HEIGHT

        self.setCheckable(checkable)

        self._build_ui()
        self._bind_events()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------
    def _build_ui(self):
        self.setProperty("role", self.role)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(self.button_height)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._refresh_style()

    # --------------------------------------------------
    # Events
    # --------------------------------------------------
    def _bind_events(self):
        self.clicked.connect(self._emit_clicked_label)

    def _emit_clicked_label(self):
        self.clicked_label.emit(self.text())

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    def set_role(self, role: str):
        self.role = role
        self.setProperty("role", role)
        self._refresh_style()

    def set_big(self):
        self.button_height = theme.sizes.BUTTON_HEIGHT_LARGE
        self.setFixedHeight(self.button_height)
        self._refresh_style()

    def set_normal(self):
        self.button_height = theme.sizes.BUTTON_HEIGHT
        self.setFixedHeight(self.button_height)
        self._refresh_style()

    def set_text(self, text: str):
        self.setText(text)

    def disable_button(self):
        self.setDisabled(True)

    def enable_button(self):
        self.setDisabled(False)

    def set_enabled(self, enabled: bool):
        self.setEnabled(enabled)

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def _refresh_style(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()