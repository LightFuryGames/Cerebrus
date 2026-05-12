"""Main Menu Bar component."""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import MenuPlugin, PluginManager
from cerebrus.ui.components.dialogs.app.about_dialog import _show_about_dialog
from cerebrus.ui.components.dialogs.app.updates_dialog import check_for_updates_ui
from cerebrus.ui.components.dialogs.profile.profile_dialog import (
    _open_profile_native,
    _show_profile_dialog,
)
from cerebrus.ui.components.file_manager import _open_profile_folder
from cerebrus.ui.components.layout import render_tabs
from cerebrus.ui.components.palette_manager import (
    _show_create_palette_dialog,
    _show_load_palette_dialog,
    _show_theme_editor,
)
from cerebrus.ui.components.panels.logs_panel.logs_panel import _render_log_entries
from cerebrus.ui.components.shared import _update_profile_display_colors, log_message
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager


def _safe_run(state: UIState, func) -> None:
    """Safely run a callback and log exceptions."""
    try:
        func()
    except Exception as e:
        import traceback

        traceback.print_exc()
        try:
            log_message(state, "ERROR", f"Menu Error: {e}")
        except:
            pass


def build_menu_bar(state: UIState) -> None:
    """Render the top menu bar."""
    with dpg.menu_bar():
        with dpg.menu(label="File"):
            dpg.add_menu_item(
                label="Exit Window",
                shortcut="Alt+F4",
                callback=lambda: dpg.stop_dearpygui(),
            )

        with dpg.menu(label="Tools"):
            dpg.add_menu_item(
                label="Echo Test Command",
                callback=lambda: _safe_run(
                    state,
                    lambda: log_message(state, "INFO", "Echo Test Command Executed"),
                ),
            )

        with dpg.menu(label="Profile"):
            dpg.add_menu_item(
                label="New",
                callback=lambda: _safe_run(
                    state, lambda: _show_profile_dialog(state, is_edit=False)
                ),
            )
            dpg.add_menu_item(
                label="Open",
                callback=lambda: _safe_run(state, lambda: _open_profile_native(state)),
            )
            dpg.add_menu_item(
                label="Edit",
                callback=lambda: _safe_run(
                    state, lambda: _show_profile_dialog(state, is_edit=True)
                ),
            )
            dpg.add_separator()
            dpg.add_menu_item(
                label="Open Profile Folder",
                callback=lambda: _safe_run(state, lambda: _open_profile_folder(state)),
            )

        with dpg.menu(label="Settings"):
            tm = get_theme_manager()
            with dpg.menu(label="Theme Mode"):
                dpg.add_menu_item(
                    label="System Default",
                    tag="menu_mode_system",
                    check=True,
                    default_value=(tm.current_mode == "System"),
                    callback=lambda: _safe_run(
                        state, lambda: _handle_theme_change(state, mode="System")
                    ),
                )
                dpg.add_menu_item(
                    label="Light Mode",
                    tag="menu_mode_light",
                    check=True,
                    default_value=(tm.current_mode == "Light"),
                    callback=lambda: _safe_run(
                        state, lambda: _handle_theme_change(state, mode="Light")
                    ),
                )
                dpg.add_menu_item(
                    label="Dark Mode",
                    tag="menu_mode_dark",
                    check=True,
                    default_value=(tm.current_mode == "Dark"),
                    callback=lambda: _safe_run(
                        state, lambda: _handle_theme_change(state, mode="Dark")
                    ),
                )
            dpg.add_separator()
            with dpg.menu(label="Color Palette"):
                # Separation: Defaults vs Custom
                defaults = ["Standard", "High Contrast", "Deuteranopia", "Tritanopia"]
                all_palettes = sorted(list(tm.themes.keys()))
                custom_palettes = [p for p in all_palettes if p not in defaults]

                dpg.add_text(
                    "Built-in", color=tm.get_text_color("disabled", (150, 150, 150))
                )
                for p in defaults:
                    if p in tm.themes:
                        tag = f"menu_palette_{p.lower().replace(' ', '_')}"
                        dpg.add_menu_item(
                            label=p,
                            tag=tag,
                            check=True,
                            default_value=(tm.current_palette == p),
                            callback=lambda s, a, u: _safe_run(
                                state, lambda: _handle_theme_change(state, palette=u)
                            ),
                            user_data=p,
                        )

                if custom_palettes:
                    dpg.add_separator()
                    dpg.add_text(
                        "Custom", color=tm.get_text_color("disabled", (150, 150, 150))
                    )
                    for p in custom_palettes:
                        tag = f"menu_palette_{p.lower().replace(' ', '_')}"
                        dpg.add_menu_item(
                            label=p,
                            tag=tag,
                            check=True,
                            default_value=(tm.current_palette == p),
                            callback=lambda s, a, u: _safe_run(
                                state, lambda: _handle_theme_change(state, palette=u)
                            ),
                            user_data=p,
                        )

                dpg.add_separator()
                dpg.add_menu_item(
                    label="Edit Current Palette",
                    callback=lambda: _safe_run(
                        state, lambda: _show_theme_editor(state)
                    ),
                )
                dpg.add_menu_item(
                    label="Create Custom Palette",
                    callback=lambda: _safe_run(
                        state, lambda: _show_create_palette_dialog(state)
                    ),
                )
                dpg.add_menu_item(
                    label="Import Palette JSON",
                    callback=lambda: _safe_run(
                        state, lambda: _show_load_palette_dialog(state)
                    ),
                )
                dpg.add_menu_item(
                    label="Open Palettes Folder",
                    callback=lambda: _safe_run(
                        state, lambda: os.startfile(tm.palettes_dir)
                    ),
                )

            dpg.add_separator()
            with dpg.menu(label="Plugins"):
                for plugin in PluginManager.get_all_plugins():
                    # If the plugin has a custom menu builder, create a submenu for it
                    if isinstance(plugin, MenuPlugin):
                        with dpg.menu(label=plugin.name):
                            dpg.add_menu_item(
                                label="Enable Plugin",
                                check=True,
                                default_value=PluginManager.is_enabled(plugin.id),
                                callback=lambda s, a, u: _safe_run(
                                    state, lambda: _handle_plugin_toggle(state, u, a)
                                ),
                                user_data=plugin.id,
                            )
                            dpg.add_separator()
                            plugin.build_menu(state)
                    else:
                        # Otherwise, just render a standard toggle item
                        dpg.add_menu_item(
                            label=plugin.name,
                            check=True,
                            default_value=PluginManager.is_enabled(plugin.id),
                            callback=lambda s, a, u: _safe_run(
                                state, lambda: _handle_plugin_toggle(state, u, a)
                            ),
                            user_data=plugin.id,
                        )

        with dpg.menu(label="Help"):
            dpg.add_menu_item(
                label="Help",
                shortcut="F1",
                callback=lambda: _safe_run(state, lambda: _open_user_guide(state)),
            )
            dpg.add_menu_item(
                label="Check for Updates",
                callback=lambda: _safe_run(state, lambda: check_for_updates_ui(state)),
            )
            dpg.add_menu_item(
                label="Provide Feedback",
                callback=lambda: _safe_run(state, lambda: _provide_feedback(state)),
            )
            dpg.add_menu_item(
                label="About",
                callback=lambda: _safe_run(state, lambda: _show_about_dialog(state)),
            )


def _handle_plugin_toggle(state: UIState, plugin_id: str, enabled: bool) -> None:
    PluginManager.set_enabled(plugin_id, enabled)
    render_tabs(state)


def _handle_theme_change(state: UIState, palette: str = None, mode: str = None) -> None:
    tm = get_theme_manager()
    tm.apply_theme(palette, mode)

    # Update Menu Checkmarks to reflect current selection
    mode_tags = {
        "System": "menu_mode_system",
        "Light": "menu_mode_light",
        "Dark": "menu_mode_dark",
    }

    # We should iterate over known palettes for tags
    # But since we generate tags dynamically, we can reconstruct or just unset all?
    # Simpler: just set the specific ones we know or use the TM list

    if mode:
        for m, tag in mode_tags.items():
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, m == mode)

    if palette:
        tm.apply_theme(palette=palette)
        # Update Palette checkmarks dynamically
        p_list = list(tm.themes.keys())
        for p in p_list:
            tag = f"menu_palette_{p.lower().replace(' ', '_')}"
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, p == palette)

    _update_profile_display_colors(state)
    _render_log_entries(state)  # Re-render logs to apply new colors


def _open_user_guide(state: UIState) -> None:
    """Open the bundled user guide HTML file."""
    # Determine base path
    # Check multiple locations
    possible_paths = []
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
        possible_paths.append(base_path / "cerebrus" / "resources" / "user_guide.html")
        possible_paths.append(base_path / "resources" / "user_guide.html")
        # Also check executable dir
        exe_dir = Path(sys.executable).parent
        possible_paths.append(exe_dir / "resources" / "user_guide.html")
    else:
        # Fallback based on relative path from this file
        # cerebro/ui/components/menu.py -> cerebro/resources/user_guide.html
        base_path = Path(__file__).resolve().parent.parent.parent
        possible_paths.append(base_path / "resources" / "user_guide.html")

    html_file = None
    for path in possible_paths:
        if path.exists():
            html_file = path
            break

    if html_file and html_file.exists():
        try:
            webbrowser.open(f"file:///{html_file.as_posix()}")
            log_message(state, "SUCCESS", "Opened User Guide")
        except Exception as e:
            log_message(state, "ERROR", f"Failed to open User Guide: {e}")
    else:
        log_message(state, "ERROR", "User Guide not found.")


def _provide_feedback(state: UIState) -> None:
    """Open default mail client for feedback."""
    email = "engineering-enginetools@lightfurygames.com"
    subject = "[CEREBRUS][FEEDBACK]"
    # Use Gmail compose link as requested
    gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={email}&su={subject}"
    try:
        webbrowser.open(gmail_url)
        log_message(state, "SUCCESS", "Opened Gmail for feedback")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to open mail client: {e}")
