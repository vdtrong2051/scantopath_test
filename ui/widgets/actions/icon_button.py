from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QPushButton

from ui.styles.theme import theme


class IconButton(QPushButton):
    """
    Reusable compact HMI button with icon text.

    Current use:
        Optional toolbar / viewport mode button.

    Example:
        IconButton("📁", "LOAD")
        IconButton("🧠", "AI MASK")
        IconButton("☁", "POINT CLOUD")
        IconButton("🗺", "SURFACE")
        IconButton("↗", "NORMALS")
        IconButton("〰", "ZIGZAG")
        IconButton("◎", "CONTOUR")
        IconButton("💾", "EXPORT")
    """

    def __init__(
        self,
        icon_text: str = "•",
        text: str = "BUTTON",
        role: str = "inline",
        min_height: int = 40,
        compact: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.icon_text = icon_text
        self.button_text = text
        self.role = role
        self.compact = compact
        self.min_height = min_height

        self._build_ui()

    # -----------------------------------------
    # UI
    # -----------------------------------------
    def _build_ui(self):
        self.setObjectName("icon_button")
        self.setProperty("role", self.role)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setMinimumHeight(self.min_height)

        if self.compact:
            self.setMinimumWidth(52)
            self.setText(self.icon_text)
        else:
            self.setMinimumWidth(130)
            self.setText(f"{self.icon_text}  {self.button_text}")

        self._refresh_style()

    # -----------------------------------------
    # Public API
    # -----------------------------------------
    def set_text(self, text: str):
        self.button_text = text

        if self.compact:
            self.setText(self.icon_text)
        else:
            self.setText(f"{self.icon_text}  {self.button_text}")

    def set_icon(self, icon_text: str):
        self.icon_text = icon_text

        if self.compact:
            self.setText(self.icon_text)
        else:
            self.setText(f"{self.icon_text}  {self.button_text}")

    def set_role(self, role: str):
        self.role = role
        self.setProperty("role", role)
        self._refresh_style()

    def disable_button(self):
        self.setDisabled(True)

    def enable_button(self):
        self.setDisabled(False)

    def sizeHint(self):
        if self.compact:
            return QSize(56, self.min_height)
        return QSize(150, self.min_height)

    # -----------------------------------------
    # Helpers
    # -----------------------------------------
    def _refresh_style(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()