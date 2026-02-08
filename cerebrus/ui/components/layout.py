"""Main Application Layout and Layout-related components."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager
from cerebrus.ui.components.shared import log_message, _add_help_button, _auto_save_profile
from cerebrus.ui.components.file_manager import (
    _handle_output_file_name_change,
    _handle_use_prefix_toggle,
    _open_folder_in_explorer,
    _handle_bulk_action_toggle,
    _handle_generate_actions,
    _handle_view_html_logs,
    _open_profile_folder,
)
from cerebrus.ui.components.dialogs.files.file_dialog import (
     _browse_folder_native,
     _register_file_dialogs
)
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.components.panels.profiling.profiling_panel import (
    _build_profiling_tab
)
from cerebrus.ui.components.dialogs.aws.sync_panel import build_remote_config_sync
from cerebrus.ui.components.panels.logs.logs_panel import (
    _handle_log_filter, 
    _clear_logs, 
    _handle_export_logs, 
    _render_log_entries
)
from cerebrus.ui.components.panels.device.device_panel import _populate_devices, _render_device_table
from pathlib import Path

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
        status = "DEFAULT" if not state.profile_manager.current_profile_path else "LOADED"
        
        dpg.bind_item_theme(dpg.add_text(
            tag="profile_nickname_input",
            default_value=state.profile_nickname,
        ), tm.get_profile_status_theme(status))

        dpg.add_text("Package Name:")
        dpg.bind_item_theme(dpg.add_text(
            tag="package_input",
            default_value=state.package_name,
        ), tm.get_profile_status_theme(status))

        _add_help_button("package_name")
        dpg.add_text("Profile Path:")
        with dpg.group(horizontal=True, horizontal_spacing=4):
            dpg.bind_item_theme(dpg.add_text(
                tag="profile_path_input",
                default_value=str(state.profile_path),
            ), tm.get_profile_status_theme(status))

            dpg.add_button(label="Open", callback=lambda: _open_profile_folder(state))


def build_file_actions(state: UIState) -> None:
    """Render file copy actions and reporting panels in tabs."""
    dpg.add_separator()
    dpg.add_separator()
    config = UIConfig.get_instance()
    
    # Tab Container with Fixed Height
    with dpg.child_window(
        tag="tab_container",
        height=config.get_dimension("tab_container_height", 450),
        border=False
    ):
        with dpg.tab_bar():
            with dpg.tab(label="Profiling"):
                _build_profiling_tab(state)
            with dpg.tab(label="Configuration Sync"):
                build_remote_config_sync(state)

    dpg.add_separator()
    tm = get_theme_manager()
    
    # Log Panel with Fixed Height
    log_height = config.get_dimension("logs_container_height", 250)
    
    # Parent container: No scrollbar, fixed height.
    # We use config settings but FORCE no_scrollbar via override or ensuring json has it.
    # Parent container: Ensure NO SCROLL on the parent, so controls stay fixed.
    # Parent container: Ensure NO SCROLL on the parent, so controls stay fixed.
    # no_scrollbar=True disables the decoration.
    with dpg.child_window(**config.get_component_settings("logs_filter_child"), height=log_height, no_scrollbar=True):
        dpg.bind_item_theme(dpg.add_text("Cerebrus App Live log"), tm.get_header_theme())
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
        
        # Log Container fills remaining space in the Log Panel
        # height=-1 takes all remaining vertical space. width=0 (default) takes all horizontal specific.
        # Ensure autosize is FALSE so it stretches.
        with dpg.child_window(tag="log_container", border=True, width=0, height=-1):
            _render_log_entries(state)

    _register_file_dialogs(state)
