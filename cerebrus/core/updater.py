import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests  # type: ignore[import-untyped]

from cerebrus._version import __version__

logger = logging.getLogger(__name__)

GITHUB_REPO = "LightFuryGames/Cerebrus"
GITHUB_LATEST_RELEASE_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
)


def check_for_updates():
    """
    Checks for updates by querying GitHub Latest Release.
    Returns tuple: (is_update_available, latest_version_tag, download_url)
    """
    try:
        response = requests.get(GITHUB_LATEST_RELEASE_URL, timeout=5)
        response.raise_for_status()
        release_data = response.json()

        latest_tag = release_data.get("tag_name", "")
        if not latest_tag:
            return False, None, None

        # Normalize versions
        clean_latest = latest_tag.lstrip("v").lstrip(".")
        clean_current = __version__.lstrip("v").lstrip(".").split("-")[0]

        if clean_latest == clean_current:
            return False, latest_tag, None

        # Find installer asset
        download_url = None
        for asset in release_data.get("assets", []):
            name = asset.get("name", "").lower()
            if name.endswith(".exe") or name.endswith(".msi"):
                download_url = asset.get("browser_download_url")
                break

        return True, latest_tag, download_url

    except Exception as e:
        logger.error(f"Failed to check for updates: {e}")
        return False, None, None


def download_update(url, progress_callback=None):
    """
    Downloads the installer from the given URL.
    progress_callback(current_bytes, total_bytes)
    Returns path to downloaded file.
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        filename = url.split("/")[-1]

        # Save to temp dir
        temp_dir = Path(tempfile.gettempdir()) / "CerebrusUpdates"
        temp_dir.mkdir(exist_ok=True)
        save_path = temp_dir / filename

        downloaded_size = 0

        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded_size, total_size)

        return save_path
    except Exception as e:
        logger.error(f"Failed to download update: {e}")
        raise e


def run_installer(installer_path):
    """
    Runs the downloaded installer and exits the application.
    """
    try:
        # Close the current app is implicitly handled because we will exit after this call
        # but technically we should subprocess.Popen then sys.exit

        if str(installer_path).endswith(".msi"):
            subprocess.Popen(["msiexec", "/i", str(installer_path)])
        else:
            subprocess.Popen([str(installer_path)])

        return True
    except Exception as e:
        logger.error(f"Failed to run installer: {e}")
        return False
