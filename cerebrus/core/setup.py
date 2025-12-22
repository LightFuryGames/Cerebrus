import logging
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def check_and_setup_environment(log_callback=None):
    """
    Check for ADB and Python environment.
    If ADB is missing, attempt to download and install it.
    """
    _log(log_callback, "INFO", "Checking environment dependencies...")

    # Check Python (Implicitly checked since we are running, but good to log)
    _log(log_callback, "INFO", f"Python: {sys.executable}")

    # Check ADB
    adb_path = shutil.which("adb")
    if adb_path:
        _log(log_callback, "INFO", f"ADB found at: {adb_path}")
        # Check version
        try:
            result = subprocess.run(["adb", "version"], capture_output=True, text=True)
            _log(log_callback, "INFO", f"ADB Version: {result.stdout.splitlines()[0]}")
        except Exception as e:
            _log(log_callback, "WARNING", f"Failed to get ADB version: {e}")
    else:
        _log(log_callback, "WARNING", "ADB not found in PATH. Attempting to install...")
        if _install_adb(log_callback):
            _log(log_callback, "SUCCESS", "ADB installed successfully.")
        else:
            _log(
                log_callback,
                "ERROR",
                "Failed to install ADB. Please install Android Platform Tools manually.",
            )


def _install_adb(log_callback=None) -> bool:
    """Download and install platform-tools."""
    try:
        # Define install location: cerebrus/bin/platform-tools
        if getattr(sys, "frozen", False):
            base_path = Path(getattr(sys, "_MEIPASS"))
        else:
            base_path = Path(__file__).resolve().parent.parent.parent

        bin_dir = base_path / "cerebrus" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)

        platform_tools_dir = bin_dir / "platform-tools"
        adb_exe = platform_tools_dir / "adb.exe"

        # Check if already exists locally but not in PATH
        if adb_exe.exists():
            _log(log_callback, "INFO", f"Found local ADB at {adb_exe}")
            _add_to_path(str(platform_tools_dir))
            return True

        # Download
        url = (
            "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        )
        zip_path = bin_dir / "platform-tools.zip"

        _log(log_callback, "INFO", f"Downloading ADB from {url}...")
        urllib.request.urlretrieve(url, zip_path)

        # Extract
        _log(log_callback, "INFO", "Extracting platform-tools...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(bin_dir)

        # Cleanup zip
        zip_path.unlink()

        if adb_exe.exists():
            _add_to_path(str(platform_tools_dir))
            return True
        else:
            return False

    except Exception as e:
        _log(log_callback, "ERROR", f"Exception during ADB install: {e}")
        return False


def _add_to_path(path: str):
    """Add path to environment PATH for this process."""
    os.environ["PATH"] += os.pathsep + path
    # Also try to set it permanently? No, that requires admin. Just for this session.


def _log(callback, level, message):
    if callback:
        callback(level, message)
    else:
        print(f"[{level}] {message}")
