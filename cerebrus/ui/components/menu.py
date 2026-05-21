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
from cerebrus.ui.ui_prefs import (
    UI_SCALE_DEFAULT,
    UI_SCALE_MAX,
    UI_SCALE_MIN,
    load_ui_prefs,
    save_ui_prefs,
)


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
            dpg.add_menu_item(
                label="UI Scale...",
                callback=lambda: _safe_run(state, lambda: _show_ui_scale_dialog(state)),
            )
            dpg.add_separator()
            with dpg.menu(label="Plugins"):
                dpg.add_menu_item(
                    label="Manage Tab Order...",
                    callback=lambda: _safe_run(
                        state, lambda: _show_plugin_tab_order_dialog(state)
                    ),
                )
                dpg.add_separator()
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


def _show_plugin_tab_order_dialog(state: UIState) -> None:
    window_tag = "plugin_tab_order_dialog"
    list_tag = "plugin_tab_order_list"
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    labels = _plugin_order_labels()
    with dpg.window(
        label="Plugin Tab Order",
        tag=window_tag,
        modal=True,
        width=440,
        height=360,
        no_collapse=True,
    ):
        dpg.add_text("Visible plugin tabs")
        dpg.add_listbox(
            labels,
            tag=list_tag,
            width=-1,
            num_items=max(4, min(8, len(labels))),
            default_value=labels[0] if labels else "",
        )
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Top",
                callback=lambda: _safe_run(
                    state, lambda: _move_selected_plugin_tab(state, list_tag, "top")
                ),
            )
            dpg.add_button(
                label="Up",
                callback=lambda: _safe_run(
                    state, lambda: _move_selected_plugin_tab(state, list_tag, "up")
                ),
            )
            dpg.add_button(
                label="Down",
                callback=lambda: _safe_run(
                    state, lambda: _move_selected_plugin_tab(state, list_tag, "down")
                ),
            )
            dpg.add_button(
                label="Bottom",
                callback=lambda: _safe_run(
                    state, lambda: _move_selected_plugin_tab(state, list_tag, "bottom")
                ),
            )
        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Close",
                callback=lambda: dpg.delete_item(window_tag),
            )


def _plugin_order_labels() -> list[str]:
    return [
        f"{plugin.name} ({plugin.id})" for plugin in PluginManager.get_enabled_plugins()
    ]


def _plugin_id_from_order_label(label: str) -> str | None:
    if not label.endswith(")") or "(" not in label:
        return None
    return label.rsplit("(", 1)[1][:-1]


def _move_selected_plugin_tab(state: UIState, list_tag: str, action: str) -> None:
    selected = dpg.get_value(list_tag)
    plugin_id = _plugin_id_from_order_label(selected)
    if not plugin_id:
        return

    labels = _plugin_order_labels()
    selected_index = labels.index(selected) if selected in labels else -1
    if selected_index < 0:
        return

    if action == "top":
        direction = -selected_index
    elif action == "bottom":
        direction = len(labels) - selected_index - 1
    elif action == "up":
        direction = -1
    elif action == "down":
        direction = 1
    else:
        return

    PluginManager.move_plugin(plugin_id, direction)
    labels = _plugin_order_labels()
    new_label = next(
        (label for label in labels if _plugin_id_from_order_label(label) == plugin_id),
        labels[0] if labels else "",
    )
    dpg.configure_item(list_tag, items=labels)
    if new_label:
        dpg.set_value(list_tag, new_label)
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


def _show_ui_scale_dialog(state: UIState) -> None:
    """Slider dialog to override the global UI font scale. Persists on Apply."""
    window_tag = "ui_scale_dialog"
    slider_tag = "ui_scale_slider"
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)

    prefs = load_ui_prefs()

    def _apply(value: float) -> None:
        try:
            dpg.set_global_font_scale(value)
        except Exception:
            pass
        prefs.ui_scale = value
        save_ui_prefs(prefs)
        # Refresh UIConfig so any widgets built AFTER this point pick up the
        # new scale. Already-rendered widgets keep their current widths; full
        # apply requires restart.
        try:
            from cerebrus.ui.components.ui_config import UIConfig

            UIConfig.get_instance().refresh_scale()
        except Exception:
            pass
        log_message(
            state,
            "INFO",
            f"UI scale set to {value:.2f}x (saved). Restart for full layout reflow.",
        )

    def _on_apply() -> None:
        value = float(dpg.get_value(slider_tag))
        _apply(value)
        dpg.delete_item(window_tag)

    def _on_reset() -> None:
        dpg.set_value(slider_tag, UI_SCALE_DEFAULT)
        _apply(UI_SCALE_DEFAULT)

    def _on_preview(_sender, app_data, _ud) -> None:
        # Live preview without persisting until Apply.
        try:
            dpg.set_global_font_scale(float(app_data))
        except Exception:
            pass

    # Size the dialog for the *current* scale so contents don't clip when
    # the user opens it after picking a large multiplier. Base 420x190 at 1x,
    # grows linearly with the active scale and capped at viewport bounds.
    try:
        active_scale = max(1.0, float(dpg.get_global_font_scale() or 1.0))
    except Exception:
        active_scale = max(1.0, prefs.ui_scale)
    win_w = int(420 * active_scale) + 40
    win_h = int(190 * active_scale) + 30

    with dpg.window(
        label="UI Scale",
        tag=window_tag,
        modal=True,
        no_collapse=True,
        no_resize=False,
        width=win_w,
        height=win_h,
    ):
        dpg.add_text("Multiplier applied on top of system DPI scaling.")
        dpg.add_text("Changes save to your Cerebrus user profile.", color=(150, 150, 150))
        dpg.add_spacer(height=6)
        dpg.add_slider_float(
            tag=slider_tag,
            default_value=prefs.ui_scale,
            min_value=UI_SCALE_MIN,
            max_value=UI_SCALE_MAX,
            format="%.2fx",
            width=-1,
            callback=_on_preview,
        )
        dpg.add_spacer(height=8)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Apply", width=90, callback=lambda: _safe_run(state, _on_apply))
            dpg.add_button(label="Reset", width=90, callback=lambda: _safe_run(state, _on_reset))
            dpg.add_button(
                label="Cancel",
                width=90,
                callback=lambda: (
                    dpg.set_global_font_scale(prefs.ui_scale),
                    dpg.delete_item(window_tag),
                ),
            )
