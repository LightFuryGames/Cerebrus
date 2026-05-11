"""Plugin system for dynamic UI components."""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from cerebrus.core.paths import get_app_data_dir
from cerebrus.ui.state import UIState


class TabPlugin(Protocol):
    """Protocol for plugins that provide a tab in the main layout."""

    @property
    def id(self) -> str:
        """Unique identifier for the plugin."""
        ...

    @property
    def name(self) -> str:
        """Display name for the plugin tab."""
        ...

    @property
    def version(self) -> str:
        """Version of the plugin."""
        ...

    def build_tab(self, state: UIState) -> None:
        """Render the DearPyGui UI for this tab."""
        ...


@runtime_checkable
class MenuPlugin(TabPlugin, Protocol):
    """Optional plugin protocol for Settings -> Plugins menu actions."""

    def build_menu(self, state: UIState) -> None:
        """Render plugin-specific menu actions under Settings -> Plugins."""
        ...


class PluginManager:
    """Manages the registration and state of plugins."""

    _plugins: dict[str, TabPlugin] = {}
    _enabled_plugins: set[str] = set()
    _known_plugins: set[str] = set()
    _initialized: bool = False
    _schema_version: str = "1.0"

    @classmethod
    def _get_cache_path(cls):
        """Get the path to the plugins config JSON."""
        return get_app_data_dir() / "plugins.json"

    @classmethod
    def initialize(cls) -> None:
        """Load plugin state from configuration."""
        if cls._initialized:
            return

        cache_path = cls._get_cache_path()
        if cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)

                plugins_data = data.get("plugins", {})
                cls._known_plugins = set(plugins_data.keys())
                cls._enabled_plugins = set(
                    plugin_id
                    for plugin_id, p_info in plugins_data.items()
                    if p_info.get("enabled", False)
                )
            except Exception as e:
                print(f"Error loading plugins cache: {e}")
                cls._enabled_plugins = {"profiling"}
                cls._known_plugins = {"profiling"}
        else:
            cls._enabled_plugins = {"profiling"}
            cls._known_plugins = {"profiling"}

        cls._initialized = True

    @classmethod
    def _save_cache(cls) -> None:
        """Save plugin state to JSON cache."""
        cache_path = cls._get_cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        plugins_data = {}
        # Iterate over registered plugins to write their state and version
        for p_id, plugin in cls._plugins.items():
            plugins_data[p_id] = {
                "enabled": p_id in cls._enabled_plugins,
                "version": plugin.version,
            }

        data = {"schema_version": cls._schema_version, "plugins": plugins_data}

        try:
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving plugins cache: {e}")

    @classmethod
    def register(cls, plugin: TabPlugin) -> None:
        """Register a new plugin."""
        cls.initialize()
        cls._plugins[plugin.id] = plugin

        # If it's a new plugin (not tracked in config at all), enable it by default
        if plugin.id not in cls._known_plugins:
            cls._enabled_plugins.add(plugin.id)
            cls._known_plugins.add(plugin.id)
            cls._save_cache()

    @classmethod
    def get_all_plugins(cls) -> list[TabPlugin]:
        """Get all registered plugins."""
        return list(cls._plugins.values())

    @classmethod
    def get_enabled_plugins(cls) -> list[TabPlugin]:
        """Get plugins that are currently enabled."""
        cls.initialize()
        return [p for p in cls._plugins.values() if p.id in cls._enabled_plugins]

    @classmethod
    def is_enabled(cls, plugin_id: str) -> bool:
        cls.initialize()
        return plugin_id in cls._enabled_plugins

    @classmethod
    def set_enabled(cls, plugin_id: str, enabled: bool) -> None:
        """Enable or disable a plugin and save to config."""
        cls.initialize()
        if enabled:
            cls._enabled_plugins.add(plugin_id)
        else:
            cls._enabled_plugins.discard(plugin_id)

        cls._save_cache()
