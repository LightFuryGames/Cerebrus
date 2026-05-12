"""Main Application Layout and Layout-related components."""

from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import PluginManager
from cerebrus.ui.components.dialogs.files.file_dialog import (
    _browse_folder_native,
    _register_file_dialogs,
)
from cerebrus.ui.components.file_manager import (
    _handle_bulk_action_toggle,
    _handle_generate_actions,
    _handle_output_file_name_change,
    _handle_use_prefix_toggle,
    _handle_view_html_logs,
    _open_folder_in_explorer,
    _open_profile_folder,
)
from cerebrus.ui.components.shared import (
    _add_help_button,
    _auto_save_profile,
    log_message,
)
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager

from .panels.device.device_panel import _populate_devices, _render_device_table
from .panels.logs_panel.logs_panel import (
    _clear_logs,
    _handle_export_logs,
    _handle_log_filter,
    _render_log_entries,
)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _get_viewport_size() -> tuple[int, int]:
    try:
        width = dpg.get_viewport_client_width() or dpg.get_viewport_width() or 1200
        height = dpg.get_viewport_client_height() or dpg.get_viewport_height() or 800
    except Exception:
        width, height = 1200, 800
    return int(width), int(height)


def _calculate_responsive_layout() -> dict[str, int]:
    width, height = _get_viewport_size()

    tab_height = _clamp(int(height * 0.44) + 100, 440, 470)
    panel_height = _clamp(tab_height - 150, 185, 210)
    log_height = _clamp(int(height * 0.26) - 100, 90, 150)

    available_width = max(760, width - 24)
    group_gap = 24
    usable_panel_width = available_width - group_gap

    if usable_panel_width >= 1280:
        left_width, right_width, compare_width = 360, 460, 460
    elif usable_panel_width >= 1080:
        left_width = 300
        right_width = 380
        compare_width = max(360, usable_panel_width - left_width - right_width)
    else:
        left_width = int(usable_panel_width * 0.30)
        right_width = int(usable_panel_width * 0.34)
        compare_width = usable_panel_width - left_width - right_width

    return {
        "tab_height": tab_height,
        "log_height": log_height,
        "panel_height": panel_height,
        "left_panel_width": max(240, left_width),
        "right_panel_width": max(300, right_width),
        "compare_panel_width": max(300, compare_width),
    }


def apply_responsive_layout() -> None:
    """Resize the main tab/log split and profiling panels for the viewport."""
    sizes = _calculate_responsive_layout()
    item_updates = {
        "tab_container": {"height": sizes["tab_height"]},
        "logs_panel_container": {"height": sizes["log_height"]},
        "bulk_actions_left_panel": {
            "height": sizes["panel_height"],
            "width": sizes["left_panel_width"],
        },
        "bulk_actions_right_panel": {
            "height": sizes["panel_height"],
            "width": sizes["right_panel_width"],
        },
        "local_report_comparison_panel": {
            "height": sizes["panel_height"],
            "width": sizes["compare_panel_width"],
        },
    }
    for tag, kwargs in item_updates.items():
        if dpg.does_item_exist(tag):
            dpg.configure_item(tag, **kwargs)


def render_tabs(state: UIState) -> None:
    """Render or re-render all enabled tabs based on plugins."""
    if dpg.does_item_exist("main_tab_bar"):
        dpg.delete_item("main_tab_bar", children_only=True)

        plugins = PluginManager.get_enabled_plugins()
        for plugin in plugins:
            with dpg.tab(label=plugin.name, parent="main_tab_bar"):
                plugin.build_tab(state)


def setup_fonts() -> None:
    """Setup application fonts."""
    with dpg.font_registry():
        # Try to locate a standard Windows font
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            # Use a larger font size for better readability
            default_font = dpg.add_font(str(font_path), 18)
            dpg.bind_font(default_font)

            # Larger font for titles/headers
            dpg.add_font(str(font_path), 28, tag="title_font")
        else:
            print("Segoe UI font not found, using default.")


def build_profile_summary(state: UIState) -> None:
    """Render the profile summary strip with read-only inputs."""
    tm = get_theme_manager()
    # Reduced horizontal spacing from 12 to 8
    with dpg.group(horizontal=True, horizontal_spacing=8):
        dpg.add_text("Profile Name:")
        # Use theme binding for status colors
        status = (
            "DEFAULT" if not state.profile_manager.current_profile_path else "LOADED"
        )

        dpg.bind_item_theme(
            dpg.add_text(
                tag="profile_nickname_input",
                default_value=state.profile_nickname,
            ),
            tm.get_profile_status_theme(status),
        )

        dpg.add_text("Package Name:")
        dpg.bind_item_theme(
            dpg.add_text(
                tag="package_input",
                default_value=state.package_name,
            ),
            tm.get_profile_status_theme(status),
        )

        _add_help_button("package_name")
        dpg.add_text("Profile Path:")
        with dpg.group(horizontal=True, horizontal_spacing=4):
            dpg.bind_item_theme(
                dpg.add_text(
                    tag="profile_path_input",
                    default_value=str(state.profile_path),
                ),
                tm.get_profile_status_theme(status),
            )

            dpg.add_button(label="Open", callback=lambda: _open_profile_folder(state))


def build_file_actions(state: UIState) -> None:
    """Render file copy actions and reporting panels in tabs."""
    dpg.add_separator()
    dpg.add_separator()
    config = UIConfig.get_instance()
    sizes = _calculate_responsive_layout()

    # The tab area uses a shared fixed work height for all tabs. It should not
    # scroll; logs below own scrolling once entries exceed the visible area.
    with dpg.child_window(
        tag="tab_container",
        height=sizes["tab_height"],
        border=False,
        no_scrollbar=True,
    ):
        with dpg.tab_bar(tag="main_tab_bar"):
            pass

        # Initial render
        render_tabs(state)

    dpg.add_separator()
    tm = get_theme_manager()

    with dpg.child_window(
        **config.get_component_settings("logs_filter_child"),
        tag="logs_panel_container",
        height=sizes["log_height"],
        no_scrollbar=True,
    ):
        dpg.bind_item_theme(
            dpg.add_text("Cerebrus App Live log"), tm.get_header_theme()
        )
        with dpg.group(horizontal=True):
            dpg.add_input_text(
                tag="log_filter_input",
                label="Filter",
                width=280,
                callback=_handle_log_filter,
                user_data=state,
            )
            dpg.add_button(label="Clear", callback=lambda: _clear_logs(state))
            dpg.add_button(label="Export", callback=lambda: _handle_export_logs(state))

        with dpg.child_window(tag="log_container", border=True, width=0, height=-1):
            _render_log_entries(state)

    _register_file_dialogs(state)
    apply_responsive_layout()
