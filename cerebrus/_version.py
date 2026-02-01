import os
import subprocess
import sys
from pathlib import Path


def get_version():
    # 1. Check for frozen version file (created during build)
    try:
        from ._frozen_version import __version__ as frozen_version

        return frozen_version
    except ImportError:
        pass

    # 2. Check for git tag
    try:
        # Get the directory of this file
        root_dir = Path(__file__).parent.parent

        # Ensure we are in a git repo
        if (root_dir / ".git").exists():
            cmd = ["git", "describe", "--tags", "--always", "--dirty"]
            version = (
                subprocess.check_output(cmd, cwd=root_dir, stderr=subprocess.DEVNULL)
                .decode("utf-8")
                .strip()
            )
            # Remove 'v' or 'v.' prefix if present
            if version.lower().startswith("v"):
                version = version[1:]
            if version.startswith("."):
                version = version[1:]
            return version
    except Exception:
        pass

    # 3. Fallback
    return "0.0.0-dev"


__version__ = get_version()
