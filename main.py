import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


@dataclass
class AppConfig:
    app_name: str = "Scan-to-Path | 3D Surface Mapping"
    fullscreen: bool = False
    debug: bool = True


def load_app_config() -> AppConfig:
    """
    Load config safely.

    Priority:
        1. Try app.config.load_config()
        2. Fallback to default AppConfig
    """

    try:
        from app.config import load_config

        config = load_config()

        # Ensure required fields exist
        if not hasattr(config, "app_name"):
            config.app_name = "Scan-to-Path | 3D Surface Mapping"

        if not hasattr(config, "fullscreen"):
            config.fullscreen = False

        return config

    except Exception as exc:
        print("[MAIN] Cannot load app.config, using fallback config.")
        print("[MAIN] Reason:", exc)
        return AppConfig()


def load_stylesheet(app: QApplication):
    """
    Load QSS theme if exists.
    """

    base_dir = Path(__file__).resolve().parent
    qss_path = base_dir / "ui" / "styles" / "dark_hmi.qss"

    if not qss_path.exists():
        print(f"[MAIN] QSS file not found: {qss_path}")
        return

    try:
        qss = qss_path.read_text(encoding="utf-8")
        app.setStyleSheet(qss)
        print(f"[MAIN] Loaded stylesheet: {qss_path}")

    except Exception as exc:
        print("[MAIN] Cannot load stylesheet:", exc)


def apply_app_meta(app: QApplication, config):
    """
    Set application metadata.
    """

    app.setApplicationName(config.app_name)
    app.setOrganizationName("Scan-to-Path")
    app.setOrganizationDomain("local")


def create_window(config) -> MainWindow:
    """
    Build and show main window.
    """

    window = MainWindow(config)

    if getattr(config, "fullscreen", False):
        window.start_fullscreen()
    else:
        window.show()

    return window


def main():
    """
    Application entrypoint.
    """

    config = load_app_config()

    app = QApplication(sys.argv)

    apply_app_meta(app, config)
    load_stylesheet(app)

    window = create_window(config)

    # Keep reference to prevent garbage collection
    app.main_window = window

    sys.exit(app.exec())


if __name__ == "__main__":
    main()