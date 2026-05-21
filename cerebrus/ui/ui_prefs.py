"""User-facing UI preferences (scale, etc.) persisted to LOCALAPPDATA."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from cerebrus.core.paths import get_app_data_dir


_PREFS_FILE_NAME = "ui_prefs.json"

UI_SCALE_MIN = 0.75
UI_SCALE_MAX = 2.0
UI_SCALE_DEFAULT = 1.0


@dataclass
class UIPrefs:
    ui_scale: float = UI_SCALE_DEFAULT


def _prefs_path():
    return get_app_data_dir() / _PREFS_FILE_NAME


def load_ui_prefs() -> UIPrefs:
    path = _prefs_path()
    if not path.exists():
        return UIPrefs()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return UIPrefs()
    scale = float(data.get("ui_scale", UI_SCALE_DEFAULT))
    scale = max(UI_SCALE_MIN, min(UI_SCALE_MAX, scale))
    return UIPrefs(ui_scale=scale)


def save_ui_prefs(prefs: UIPrefs) -> None:
    path = _prefs_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(prefs), f, indent=2)
    except Exception:
        pass
