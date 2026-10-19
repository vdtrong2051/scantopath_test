from dataclasses import dataclass


@dataclass(frozen=True)
class Colors:
    """
    Color palette for Scan-to-Path HMI.

    Focus:
    - RGB-D scan
    - Edge AI mask
    - Point cloud processing
    - 3D surface map
    - Normal estimation
    - Zigzag / Contour path generation
    """

    # Background
    BG_MAIN: str = "#141517"
    BG_PANEL: str = "#1E1F22"
    BG_CARD: str = "#2B2D31"
    BG_VIEWPORT: str = "#111214"
    BG_HOVER: str = "#383A40"

    # Text
    TEXT_PRIMARY: str = "#E3E5E8"
    TEXT_SECONDARY: str = "#B5BAC1"
    TEXT_MUTED: str = "#80848E"
    TEXT_DIM: str = "#6F737D"

    # Status
    SUCCESS: str = "#23A559"
    WARNING: str = "#F0B232"
    DANGER: str = "#DA373C"
    INFO: str = "#00A8FC"

    # Border
    BORDER: str = "#313338"
    BORDER_LIGHT: str = "#4F545C"

    # Default button
    BTN_DEFAULT: str = "#313338"
    BTN_DEFAULT_HOVER: str = "#404249"

    # Primary button:
    # Generate Zigzag / Contour / Export
    BTN_PRIMARY: str = "#005C9E"
    BTN_PRIMARY_HOVER: str = "#004B82"

    # Action button:
    # Load Scan / Edge AI / Build Point Cloud / Build Surface Map
    BTN_ACTION: str = "#0D6E66"
    BTN_ACTION_HOVER: str = "#0A5751"

    # Danger button:
    # Reserved for Stop / Reset / Error later
    BTN_DANGER: str = "#B3261E"
    BTN_DANGER_HOVER: str = "#8C1D18"

    # Backward-compatible old names
    BTN_STOP: str = BTN_DANGER
    BTN_STOP_HOVER: str = BTN_DANGER_HOVER


@dataclass(frozen=True)
class Fonts:
    FAMILY: str = "Segoe UI, Inter, Arial"
    SIZE_XS: int = 11
    SIZE_SM: int = 12
    SIZE_MD: int = 14
    SIZE_LG: int = 16
    SIZE_XL: int = 20
    SIZE_XXL: int = 24


@dataclass(frozen=True)
class Spacing:
    XS: int = 4
    SM: int = 8
    MD: int = 16
    LG: int = 24
    XL: int = 32


@dataclass(frozen=True)
class Radius:
    SM: int = 4
    MD: int = 6
    LG: int = 8


@dataclass(frozen=True)
class Sizes:
    # Main bars
    TOP_BAR_HEIGHT: int = 48
    PROGRESS_BAR_HEIGHT: int = 40
    INFO_BAR_HEIGHT: int = 40
    BOTTOM_BAR_HEIGHT: int = 56

    # Buttons
    BUTTON_HEIGHT: int = 36
    BUTTON_HEIGHT_LARGE: int = 42

    # Panels
    RIGHT_PANEL_MIN_WIDTH: int = 340

    # Window
    WINDOW_MIN_WIDTH: int = 1280
    WINDOW_MIN_HEIGHT: int = 720
    WINDOW_DEFAULT_WIDTH: int = 1440
    WINDOW_DEFAULT_HEIGHT: int = 900

    # Viewport
    VIEWPORT_MIN_WIDTH: int = 760
    VIEWPORT_MIN_HEIGHT: int = 520


@dataclass(frozen=True)
class Ratios:
    # Main operation area:
    # Left = 3D viewport, Right = action panel
    MAIN_LEFT: int = 70
    MAIN_RIGHT: int = 30

    # Bottom progress/runtime bar
    PROGRESS_LEFT: int = 70
    INFO_RIGHT: int = 30


@dataclass(frozen=True)
class Pipeline:
    """
    UI constants for the Scan-to-Path processing pipeline.
    """

    APP_NAME: str = "Scan-to-Path"
    APP_SUBTITLE: str = "3D Surface Mapping System"

    STAGE_IDLE: str = "IDLE"
    STAGE_LOAD_SCAN: str = "LOAD SCAN"
    STAGE_EDGE_AI: str = "EDGE AI MASK"
    STAGE_BUILD_POINTCLOUD: str = "BUILD POINT CLOUD"
    STAGE_FILTER_POINTCLOUD: str = "FILTER POINT CLOUD"
    STAGE_SURFACE_MAP: str = "BUILD SURFACE MAP"
    STAGE_NORMALS: str = "ESTIMATE NORMALS"
    STAGE_ZIGZAG: str = "GENERATE ZIGZAG"
    STAGE_CONTOUR: str = "GENERATE CONTOUR"
    STAGE_EXPORT: str = "EXPORT RESULTS"


class Theme:
    colors = Colors()
    fonts = Fonts()
    spacing = Spacing()
    radius = Radius()
    sizes = Sizes()
    ratios = Ratios()
    pipeline = Pipeline()


theme = Theme()