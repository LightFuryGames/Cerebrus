"""Robustness coverage for PluginManager: corrupt cache, reordering,
disable/enable lifecycle, mixed known/unknown IDs, MenuPlugin detection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from cerebrus.core.plugins import MenuPlugin, PluginManager, TabPlugin


class _Plugin(TabPlugin):
    def __init__(self, plugin_id: str, version: str = "1.0.0"):
        self._id = plugin_id
        self._version = version

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._id.replace("_", " ").title()

    @property
    def version(self) -> str:
        return self._version

    def build_tab(self, state) -> None:
        pass


class _MenuPlugin(_Plugin):
    def build_menu(self, state) -> None:
        pass


@pytest.fixture(autouse=True)
def isolate_state(tmp_path):
    PluginManager._plugins = {}
    PluginManager._enabled_plugins = set()
    PluginManager._known_plugins = set()
    PluginManager._plugin_order = []
    PluginManager._initialized = False
    with patch.object(
        PluginManager, "_get_cache_path", return_value=tmp_path / "plugins.json"
    ):
        yield tmp_path
    PluginManager._plugins = {}
    PluginManager._enabled_plugins = set()
    PluginManager._known_plugins = set()
    PluginManager._plugin_order = []
    PluginManager._initialized = False


def test_corrupt_cache_falls_back_to_profiling_default(isolate_state):
    bad = isolate_state / "plugins.json"
    bad.write_text("{ not json", encoding="utf-8")
    PluginManager.initialize()
    assert "profiling" in PluginManager._enabled_plugins
    assert "profiling" in PluginManager._plugin_order


def test_missing_cache_seeds_profiling_default(isolate_state):
    PluginManager.initialize()
    assert PluginManager._enabled_plugins == {"profiling"}


def test_set_enabled_persists(isolate_state):
    PluginManager.register(_Plugin("alpha"))
    PluginManager.set_enabled("alpha", False)
    cache = json.loads((isolate_state / "plugins.json").read_text())
    assert cache["plugins"]["alpha"]["enabled"] is False
    assert PluginManager.is_enabled("alpha") is False


def test_set_enabled_idempotent_when_already_enabled(isolate_state):
    PluginManager.register(_Plugin("alpha"))
    PluginManager.set_enabled("alpha", True)
    PluginManager.set_enabled("alpha", True)
    assert PluginManager.is_enabled("alpha") is True


def test_get_enabled_plugins_filters_disabled(isolate_state):
    PluginManager.register(_Plugin("alpha"))
    PluginManager.register(_Plugin("beta"))
    PluginManager.set_enabled("beta", False)
    enabled_ids = [p.id for p in PluginManager.get_enabled_plugins()]
    assert enabled_ids == ["alpha"]


def test_move_plugin_clamps_at_boundaries(isolate_state):
    PluginManager.register(_Plugin("a"))
    PluginManager.register(_Plugin("b"))
    PluginManager.register(_Plugin("c"))
    PluginManager.move_plugin("a", -5)  # already at top
    assert [p.id for p in PluginManager.get_all_plugins()] == ["a", "b", "c"]
    PluginManager.move_plugin("c", 5)  # already at bottom
    assert [p.id for p in PluginManager.get_all_plugins()] == ["a", "b", "c"]


def test_move_unknown_plugin_is_noop(isolate_state):
    PluginManager.register(_Plugin("a"))
    PluginManager.move_plugin("ghost", -1)
    assert [p.id for p in PluginManager.get_all_plugins()] == ["a"]


def test_set_plugin_order_ignores_unknown_ids(isolate_state):
    PluginManager.register(_Plugin("a"))
    PluginManager.register(_Plugin("b"))
    PluginManager.set_plugin_order(["ghost", "b", "a", "phantom"])
    assert [p.id for p in PluginManager.get_all_plugins()] == ["b", "a"]


def test_set_plugin_order_appends_missing_registered_plugins(isolate_state):
    PluginManager.register(_Plugin("a"))
    PluginManager.register(_Plugin("b"))
    PluginManager.register(_Plugin("c"))
    PluginManager.set_plugin_order(["b"])
    ordered = [p.id for p in PluginManager.get_all_plugins()]
    # 'b' first, the rest get appended automatically.
    assert ordered[0] == "b"
    assert set(ordered) == {"a", "b", "c"}


def test_menu_plugin_runtime_check(isolate_state):
    tab_only = _Plugin("alpha")
    menu = _MenuPlugin("beta")
    assert not isinstance(tab_only, MenuPlugin)
    assert isinstance(menu, MenuPlugin)


def test_register_existing_plugin_id_updates_object(isolate_state):
    """Registering the same id twice replaces the instance (version bump scenario)."""
    PluginManager.register(_Plugin("alpha", "1.0.0"))
    PluginManager.register(_Plugin("alpha", "2.0.0"))
    plugins = PluginManager.get_all_plugins()
    assert len(plugins) == 1
    assert plugins[0].version == "2.0.0"


def test_cache_records_plugin_version(isolate_state):
    PluginManager.register(_Plugin("alpha", "3.2.1"))
    cache = json.loads((isolate_state / "plugins.json").read_text())
    assert cache["plugins"]["alpha"]["version"] == "3.2.1"
    assert cache["schema_version"] == "1.0"


def test_existing_disabled_plugin_stays_disabled_after_register(isolate_state):
    cache = isolate_state / "plugins.json"
    cache.write_text(
        json.dumps({"plugins": {"alpha": {"enabled": False}}, "order": ["alpha"]}),
        encoding="utf-8",
    )
    PluginManager.register(_Plugin("alpha"))
    assert PluginManager.is_enabled("alpha") is False


def test_new_plugin_id_auto_enabled_even_with_existing_cache(isolate_state):
    cache = isolate_state / "plugins.json"
    cache.write_text(
        json.dumps({"plugins": {"alpha": {"enabled": True}}, "order": ["alpha"]}),
        encoding="utf-8",
    )
    PluginManager.register(_Plugin("alpha"))
    PluginManager.register(_Plugin("brand_new"))
    assert PluginManager.is_enabled("brand_new") is True
