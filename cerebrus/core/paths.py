import os
import sys
from pathlib import Path


def get_app_data_dir() -> Path:
    """Gets the user-writable data directory for the application."""
    if sys.platform == "win32":
        # Use Local AppData on Windows
        base_dir = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        )
        data_dir = base_dir / "Cerebrus"
    else:
        # Use home directory on other platforms
        data_dir = Path.home() / ".cerebrus"

    return data_dir


def get_debug_dir() -> Path:
    """Gets the directory for debug logs and info."""
    # To maintain consistency, we'll put it in the app data dir
    debug_dir = get_app_data_dir() / "DebugInfo"
    return debug_dir
