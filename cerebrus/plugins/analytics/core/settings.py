from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cerebrus.core.paths import get_app_data_dir


@dataclass
class AnalyticsSettings:
    elasticsearch_url: str = ""
    device_profile_config_path: str = ""


def get_analytics_settings_path() -> Path:
    return get_app_data_dir() / "analytics_settings.json"


def load_analytics_settings(path: str | Path | None = None) -> AnalyticsSettings:
    settings_path = Path(path) if path else get_analytics_settings_path()
    if not settings_path.exists():
        return AnalyticsSettings()
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AnalyticsSettings()
    return AnalyticsSettings(
        elasticsearch_url=str(payload.get("elasticsearch_url", "")).strip(),
        device_profile_config_path=str(
            payload.get("device_profile_config_path", "")
        ).strip(),
    )


def save_analytics_settings(
    settings: AnalyticsSettings,
    path: str | Path | None = None,
) -> Path:
    settings_path = Path(path) if path else get_analytics_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return settings_path
