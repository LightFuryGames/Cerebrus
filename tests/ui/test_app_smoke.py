"""App launch smoke test.

Goal: confirm the CerebrusApp class imports cleanly, can be instantiated, and
that all top-level UI builders/plugins resolve. Stops short of starting the
DearPyGui event loop (that needs a display, blocks indefinitely, and is out of
scope for a CI smoke test).

Catches:
- Import-time crashes (missing modules, circular imports).
- Plugin registration errors at app construction time.
- Profile manager bootstrap failures.
- Settings file parsing regressions.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_app_module_imports() -> None:
    """If anything is broken in the import chain, this test fails immediately."""
    from cerebrus import __main__ as entry
    from cerebrus.ui.app import CerebrusApp  # noqa: F401

    assert callable(entry.main)


def test_app_constructs_without_crash(tmp_path, monkeypatch) -> None:
    """Construct CerebrusApp end-to-end with a clean state.

    Patches:
    - The DearPyGui context calls so we don't open a real window.
    - get_app_data_dir to a temp folder so plugin/profile caches don't leak.
    """
    from cerebrus.core import paths as core_paths

    monkeypatch.setattr(core_paths, "get_app_data_dir", lambda: tmp_path)

    import dearpygui.dearpygui as dpg

    with (
        patch.object(dpg, "create_context"),
        patch.object(dpg, "create_viewport"),
        patch.object(dpg, "setup_dearpygui"),
        patch.object(dpg, "show_viewport"),
        patch.object(dpg, "set_viewport_resize_callback"),
        patch.object(dpg, "set_viewport_resizable"),
        patch.object(dpg, "set_viewport_title"),
        patch.object(dpg, "bind_font", create=True),
        patch.object(dpg, "bind_theme", create=True),
        patch.object(dpg, "destroy_context"),
        patch.object(dpg, "start_dearpygui"),
        patch.object(dpg, "is_dearpygui_running", return_value=False),
    ):
        try:
            from cerebrus.ui.app import CerebrusApp

            app = CerebrusApp()
            assert app is not None
            assert app.state is not None
        except SystemExit:
            pytest.fail("App constructor exited unexpectedly during smoke test")


def test_plugins_register_at_app_import() -> None:
    """Importing cerebrus.plugins should register the core tab plugins."""
    from cerebrus.core.plugins import PluginManager

    # Reset to force fresh registration on import.
    PluginManager._plugins = {}
    PluginManager._enabled_plugins = set()
    PluginManager._known_plugins = set()
    PluginManager._plugin_order = []
    PluginManager._initialized = False

    import importlib

    import cerebrus.plugins  # noqa: F401

    importlib.reload(cerebrus.plugins)

    # At minimum the profiling plugin must self-register on import.
    ids = {p.id for p in PluginManager.get_all_plugins()}
    assert "profiling" in ids or "profiling" in PluginManager._known_plugins


def test_entry_point_main_is_callable() -> None:
    """`python -m cerebrus` must expose a no-arg `main` callable."""
    from cerebrus.__main__ import main

    assert callable(main)
