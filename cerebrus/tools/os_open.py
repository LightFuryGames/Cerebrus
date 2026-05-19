"""Cross-platform shell-out for opening folders / files in the OS GUI.

Kept in ``cerebrus/tools`` per ``CODE_STANDARDS.md §2``: ``cerebrus/ui`` may not
import ``subprocess`` or call external tools directly; it must route through
``core`` or ``tools``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder_in_explorer(path: Path | str) -> None:
    """Open the folder (or the path's parent if a file) in the OS file browser.

    Silent on missing paths or platform errors — the caller has already chosen
    to surface a "best-effort open" UX. Logging is intentionally absent so
    headless callers don't pull in a UI logger.
    """
    if isinstance(path, str):
        path = Path(path)
    if not path.exists():
        return
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        print(f"open_folder_in_explorer failed: {exc}")
