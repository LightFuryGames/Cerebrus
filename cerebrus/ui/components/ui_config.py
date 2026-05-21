from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class UIConfig:
    _instance: UIConfig | None = None

    def __init__(self):
        self._config: dict[str, Any] = {}
        self._scale: float = 1.0
        self._load_config()
        self._load_scale()

    def _load_scale(self) -> None:
        try:
            from cerebrus.ui.ui_prefs import load_ui_prefs

            self._scale = max(0.5, float(load_ui_prefs().ui_scale))
        except Exception:
            self._scale = 1.0

    def refresh_scale(self) -> None:
        """Re-read the persisted UI scale. Existing widgets keep their sized
        widths until rebuilt, but new widgets created after this call pick
        up the new value.
        """
        self._load_scale()

    def scaled(self, value: int | float) -> int:
        """Multiply a raw pixel size by the current UI scale."""
        return int(round(float(value) * self._scale))

    @classmethod
    def get_instance(cls) -> UIConfig:
        if cls._instance is None:
            cls._instance = UIConfig()
        return cls._instance

    def _load_config(self) -> None:
        try:
            # Determine base path
            if getattr(sys, "frozen", False):
                base_path = Path(sys._MEIPASS)
                resource_path = base_path / "cerebrus" / "ui" / "resources"
                if not resource_path.exists():
                    resource_path = base_path / "ui" / "resources"
            else:
                # dev mode
                base_path = Path(__file__).resolve().parent.parent
                resource_path = base_path / "resources"

            self.layouts_path = resource_path / "layouts"

            # Load app_config.json first (base)
            app_config_path = self.layouts_path / "app_config.json"
            if app_config_path.exists():
                with open(app_config_path, "r") as f:
                    self._config = json.load(f)
            else:
                print(f"Warning: App Config not found at {app_config_path}")
                self._config = {}

            # Recursively load ALL other json files in layouts/ and subdirectories
            # Merge them into self._config
            # Keys in specific files will overwrite keys in app_config.json if they collide at top level
            # But typically we want to merge sub-dictionaries (like component_settings)

            for file_path in self.layouts_path.rglob("*.json"):
                if file_path.name == "app_config.json":
                    continue

                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        self._merge_config(data)
                except Exception as e:
                    print(f"Failed to load config {file_path}: {e}")

        except Exception as e:
            print(f"Failed to load UI layout config: {e}")

    def _merge_config(self, new_data: dict) -> None:
        """Deep merge config dictionaries."""
        for key, value in new_data.items():
            if (
                key in self._config
                and isinstance(self._config[key], dict)
                and isinstance(value, dict)
            ):
                self._config[key].update(value)
            else:
                self._config[key] = value

    def get_spacer(self, type_name: str) -> int:
        return self._config.get("spacers", {}).get(type_name, 10)

    def get_dimension(self, key: str, default: int = 100) -> int:
        """Get a UI dimension from config, multiplied by the active UI scale."""
        raw = self._config.get("dimensions", {}).get(key, default)
        return int(round(raw * self._scale))

    def get_table_policy(self, key: str, default=None):
        """Get a DearPyGui table policy constant."""
        policy_name = self._config.get("tables", {}).get(key)

        import dearpygui.dearpygui as dpg

        if policy_name == "dpg.mvTable_SizingStretchProp":
            return dpg.mvTable_SizingStretchProp
        elif policy_name == "dpg.mvTable_SizingFixedFit":
            return dpg.mvTable_SizingFixedFit

        return default if default is not None else dpg.mvTable_SizingStretchProp

    def get_component_settings(self, key: str, default: dict | None = None) -> dict:
        """Get a dictionary of component settings (e.g. border, autosize) for unpacking."""
        return self._config.get("component_settings", {}).get(key, default or {})
