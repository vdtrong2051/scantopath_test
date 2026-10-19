from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv
import os


@dataclass
class Config:
    # -------------------------------------------------
    # App
    # -------------------------------------------------
    app_name: str = "Scan-to-Path | 3D Surface Mapping"
    app_version: str = "0.1.0"
    fullscreen: bool = False
    debug: bool = True

    # -------------------------------------------------
    # Project paths
    # -------------------------------------------------
    base_dir: Path = Path(__file__).resolve().parents[1]

    data_dir: str = "data"
    export_dir: str = "data/exports"

    pointcloud_raw_dir: str = "data/pointcloud_raw"
    pointcloud_clean_dir: str = "data/pointcloud_clean"

    raw_rgb_dir: str = "data/raw_rgb"
    raw_depth_dir: str = "data/raw_depth"

    masks_dir: str = "data/masks"
    normal_maps_dir: str = "data/normal_maps"
    surface_maps_dir: str = "data/surface_maps"
    surface_paths_dir: str = "data/surface_paths"

    # -------------------------------------------------
    # OpenNI / Astra Camera
    # -------------------------------------------------
    # Đây là thư mục chứa OpenNI2.dll và thư mục OpenNI2/Drivers.
    openni2_path: str = (
        "vendor/orbbec/OpenNI_2.3.0.86/"
        "Win64-Release/tools/NiViewer"
    )

    # Giữ tên viết hoa để tương thích code cũ:
    # from config import settings
    # settings.OPENNI2_PATH
    OPENNI2_PATH: str = (
        "vendor/orbbec/OpenNI_2.3.0.86/"
        "Win64-Release/tools/NiViewer"
    )

    # Camera default
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 30

    camera_fx: float = 580.0
    camera_fy: float = 580.0
    camera_cx: float = 320.0
    camera_cy: float = 240.0
    depth_scale: float = 0.001

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def abs_path(self, relative_or_absolute: str | Path) -> Path:
        path = Path(relative_or_absolute)

        if path.is_absolute():
            return path

        return self.base_dir / path

    def get_openni2_path(self) -> str:
        return str(self.abs_path(self.openni2_path))

    def ensure_data_dirs(self):
        """
        Tạo sẵn các thư mục data cần dùng.
        """

        dirs = [
            self.data_dir,
            self.export_dir,
            self.pointcloud_raw_dir,
            self.pointcloud_clean_dir,
            self.raw_rgb_dir,
            self.raw_depth_dir,
            self.masks_dir,
            self.normal_maps_dir,
            self.surface_maps_dir,
            self.surface_paths_dir,
        ]

        for folder in dirs:
            self.abs_path(folder).mkdir(parents=True, exist_ok=True)

    def apply_runtime_env(self):
        """
        Gắn OPENNI2_PATH vào biến môi trường để AstraCamera tự nhận.

        Hàm này nên được gọi lúc load config.
        """

        openni_path = self.get_openni2_path()
        os.environ["OPENNI2_PATH"] = openni_path

        if hasattr(os, "add_dll_directory") and Path(openni_path).exists():
            os.add_dll_directory(openni_path)


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def load_config() -> Config:
    load_dotenv()

    base_dir = Path(__file__).resolve().parents[1]

    default_openni2_path = (
        "vendor/orbbec/OpenNI_2.3.0.86/"
        "Win64-Release/tools/NiViewer"
    )

    openni2_path = os.getenv(
        "OPENNI2_PATH",
        default_openni2_path,
    )

    config = Config(
        app_name=os.getenv(
            "APP_NAME",
            "Scan-to-Path | 3D Surface Mapping",
        ),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        fullscreen=_to_bool(os.getenv("FULLSCREEN"), False),
        debug=_to_bool(os.getenv("DEBUG"), True),

        base_dir=base_dir,

        export_dir=os.getenv("EXPORT_DIR", "data/exports"),

        openni2_path=openni2_path,
        OPENNI2_PATH=str(base_dir / openni2_path)
        if not Path(openni2_path).is_absolute()
        else openni2_path,

        camera_width=int(os.getenv("CAMERA_WIDTH", "640")),
        camera_height=int(os.getenv("CAMERA_HEIGHT", "480")),
        camera_fps=int(os.getenv("CAMERA_FPS", "30")),

        camera_fx=float(os.getenv("CAMERA_FX", "580.0")),
        camera_fy=float(os.getenv("CAMERA_FY", "580.0")),
        camera_cx=float(os.getenv("CAMERA_CX", "320.0")),
        camera_cy=float(os.getenv("CAMERA_CY", "240.0")),
        depth_scale=float(os.getenv("DEPTH_SCALE", "0.001")),
    )

    config.ensure_data_dirs()
    config.apply_runtime_env()

    return config


# Tương thích với code cũ:
# from config import settings
settings = load_config()