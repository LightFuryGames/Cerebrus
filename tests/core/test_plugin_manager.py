import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from cerebrus.core.plugins import PluginManager, TabPlugin

class MockPlugin(TabPlugin):
    @property
    def id(self) -> str:
        return "mock_plugin"
    @property
    def name(self) -> str:
        return "Mock Plugin"
    @property
    def version(self) -> str:
        return "1.0.0"
    def build_tab(self, state) -> None:
        pass

@pytest.fixture
def clean_plugin_manager():
    """Reset PluginManager state before and after tests."""
    PluginManager._plugins = {}
    PluginManager._enabled_plugins = set()
    PluginManager._known_plugins = set()
    PluginManager._initialized = False
    yield
    PluginManager._plugins = {}
    PluginManager._enabled_plugins = set()
    PluginManager._known_plugins = set()
    PluginManager._initialized = False

def test_register_enables_new_plugin_by_default(clean_plugin_manager, tmp_path):
    """Test that a new plugin is enabled by default if not in cache."""
    # Mock cache path to point to a temporary directory
    with patch.object(PluginManager, "_get_cache_path", return_value=tmp_path / "plugin_cache.json"):
        plugin = MockPlugin()
        PluginManager.register(plugin)
        
        assert plugin.id in PluginManager._plugins
        assert PluginManager.is_enabled(plugin.id) is True

def test_register_respects_existing_cache(clean_plugin_manager, tmp_path):
    """Test that register respects explicitly disabled plugins in cache."""
    cache_file = tmp_path / "plugin_cache.json"
    cache_data = {
        "plugins": {
            "mock_plugin": {"enabled": False}
        }
    }
    with open(cache_file, "w") as f:
        json.dump(cache_data, f)
        
    with patch.object(PluginManager, "_get_cache_path", return_value=cache_file):
        plugin = MockPlugin()
        PluginManager.register(plugin)
        
        assert plugin.id in PluginManager._plugins
        assert PluginManager.is_enabled(plugin.id) is False
