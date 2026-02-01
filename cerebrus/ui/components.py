"""Composable DearPyGui building blocks."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from tkinter import Tk, filedialog
import re

import dearpygui.dearpygui as dpg

from cerebrus._version import __version__
from cerebrus.core.devices import DeviceInfo, collect_device_info
from cerebrus.tools.adb import AdbClient, AdbError
from cerebrus.tools.log_to_html import convert_log_to_html
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager
from cerebrus.core.updater import check_for_updates, download_update, run_installer

# Log colors are now handled by ThemeManager
SELECTED_ROW_COLOR = (0, 119, 200, 153)  # Blue highlight with transparency

# Hardcoded S3 Bucket URL for Config Downloads
S3_CONFIG_BASE_URL = "https://titan-cerebrus-configurations.s3.ap-south-1.amazonaws.com"


# Tooltip definitions
TOOLTIPS = {
    "output_file_name": "The name to use for output files. If a file with the same name exists, a counter (_1, _2, etc.) will be added to keep both files. This will be used as the filename or prefix depending on the 'Use as Prefix only' setting.",
    "use_prefix_only": "When enabled, the Output File Name will be used as a prefix with the original filename appended (e.g., 'prefix_filename.html'). When disabled, all generated files will use the exact Output File Name (with counters added if files exist).",
    "input_path": "The folder path where files will be moved from the device. CSV and Logs subfolders will be created here.",
    "output_path": "The main workspace folder. Files moved from devices will be saved here, and generated reports will be output here.",
    "move_logs": "Moves log files from the selected device's Unreal Engine Saved/Logs folder to your PC.",
    "move_csv": "Moves CSV profiling data from the selected device's Unreal Engine Saved/Profiling/CSV folder to your PC.",
    "generate_perf": "Generates performance reports from CSV files in the Output Path. Requires CSV files to be present.Source files are deleted after successful conversion.",
    "generate_logs": "Generates colored HTML logs from text logs in the Output Path. Requires log files to be present.Source files are deleted after successful conversion.",
    "generate_both": "Runs both Perf Report generation and Colored Logs conversion in sequence.",
    "view_html_logs": "Opens the Output Folder Path and allows you to select and view generated HTML log files in your default web browser.",
    "package_name": "The Android package identifier for your application (e.g., com.company.appname). Must start with 'com.' and have at least 3 parts.",
    "device_table": "Lists all connected Android devices. Select a device to perform operations. Only devices with the package installed can be selected.",
    "list_devices": "Scans for connected Android devices via ADB and checks if the specified package is installed on each device.",
    "start_profiling": "Starts profiling data on selected device if Package is running actively in foreground.",
    "stop_profiling": "Stops profiling data on selected device if Package is running actively in foreground.",
    "generate_actions": "Executes all selected bulk actions (Move Logs, Move Profiling Data, Generate Reports) in sequence.",
    "sync_remote_config": "Downloads the BackendConfig.ini from the configured URL for this environment and pushes it to the selected device, replacing any existing config.",
    "memreport": "Sends the 'memreport' console command to the running application to generate a standard memory report.",
    "memreport_full": "Sends the 'memreport -full' console command to the running application to generate a comprehensive memory report.",
    "custom_command": "Sends a custom console command to the running application (e.g., 'stat unit', 'memreport -concise').",
    "custom_command": "Sends a custom console command to the running application (e.g., 'stat unit', 'memreport -concise').",
    "launch_package": "Launches the application on the device. If already running in background, brings it to foreground.",
}


def _handle_theme_change(state: UIState, palette: str = None, mode: str = None) -> None:
    get_theme_manager().apply_theme(palette, mode)
    _update_profile_display_colors(state)
    _render_log_entries(state)  # Re-render logs to apply new colors


def build_menu_bar(state: UIState) -> None:
    """Render the top menu bar."""
    with dpg.menu_bar():
        with dpg.menu(label="File"):
            dpg.add_menu_item(
                label="Exit Window", shortcut="Alt+F4", callback=lambda: sys.exit(0)
            )

        with dpg.menu(label="Tools"):
            dpg.add_menu_item(
                label="Echo Test Command",
                callback=lambda: log_message(
                    state, "INFO", "Echo Test Command Executed"
                ),
            )
            dpg.add_menu_item(
                label="AWS Configuration",
                callback=lambda: _show_aws_config_dialog(state),
            )

        with dpg.menu(label="Profile"):
            dpg.add_menu_item(
                label="New", callback=lambda: _show_profile_dialog(state, is_edit=False)
            )
            dpg.add_menu_item(
                label="Open", callback=lambda: _open_profile_native(state)
            )
            dpg.add_menu_item(
                label="Edit", callback=lambda: _show_profile_dialog(state, is_edit=True)
            )

        with dpg.menu(label="Settings"):
            with dpg.menu(label="Load Theme"):
                dpg.add_menu_item(
                    label="Standard",
                    callback=lambda: _handle_theme_change(state, "Standard", "Dark"),
                )
                dpg.add_menu_item(
                    label="Deuteranopia",
                    callback=lambda: _handle_theme_change(
                        state, "Deuteranopia", "Dark"
                    ),
                )
                dpg.add_menu_item(
                    label="Tritanopia",
                    callback=lambda: _handle_theme_change(state, "Tritanopia", "Dark"),
                )

        with dpg.menu(label="Help"):
            dpg.add_menu_item(
                label="Help", shortcut="F1", callback=lambda: _open_user_guide(state)
            )
            dpg.add_menu_item(
                label="Check for Updates", callback=lambda: check_for_updates_ui(state)
            )
            dpg.add_menu_item(
                label="Provide Feedback", callback=lambda: _provide_feedback(state)
            )
            dpg.add_menu_item(label="About", callback=lambda: _show_about_dialog(state))


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
        base_path = Path(__file__).resolve().parent.parent
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
        # Try online fallback if needed, or just log error


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


from cerebrus.core.updater import check_for_updates, download_update, run_installer
import threading
import time

def check_for_updates_ui(state: UIState, silent_on_up_to_date: bool = False) -> None:
    """Check for updates and show dialog. Set silent_on_up_to_date=True for startup checks."""
    if not silent_on_up_to_date:
        log_message(state, "INFO", "Checking for updates...")
    
    # Run in thread to avoid UI freeze
    def check_thread():
        is_available, latest_tag, download_url = check_for_updates()
        
        if is_available:
            # Always show updates
            _show_update_dialog(state, latest_tag, download_url)
        else:
            if not silent_on_up_to_date:
                if latest_tag:
                    log_message(state, "SUCCESS", f"You are up to date (Latest: {latest_tag})")
                else:
                    log_message(state, "WARNING", "Could not determine latest version.")
    
    threading.Thread(target=check_thread, daemon=True).start()
             
             
def _show_update_dialog(state: UIState, latest_tag: str, download_url: str = None) -> None:
    """Show update confirmation dialog."""
    if dpg.does_item_exist("update_dialog"):
        dpg.delete_item("update_dialog")
        
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    width = 500
    height = 300
    pos_x = (viewport_width - width) // 2
    pos_y = (viewport_height - height) // 2
    
    with dpg.window(
        tag="update_dialog",
        label="Update Available",
        modal=True,
        width=width,
        height=height,
        pos=(pos_x, pos_y),
        no_resize=True,
    ):
        dpg.add_text(f"A new version is available: {latest_tag}")
        
        is_frozen = getattr(sys, 'frozen', False)
        
        if is_frozen and download_url:
            dpg.add_text("Ready to download and install.", color=(120, 255, 120))
            dpg.add_text(f"Installer: {download_url.split('/')[-1]}")
            
            dpg.add_spacer(height=10)
            dpg.add_progress_bar(tag="update_progress_bar", label="Progress", width=-1, default_value=0.0, show=False)
            dpg.add_text(tag="update_status_text", default_value="", color=(200, 200, 200))

            dpg.add_spacer(height=20)
            with dpg.group(horizontal=True, tag="update_button_group"):
                dpg.add_spacer(width=200)
                dpg.add_button(label="Cancel", callback=lambda: dpg.delete_item("update_dialog"))
                dpg.add_button(
                    label="Download & Install", 
                    width=150, 
                    callback=lambda: _start_download_update(state, download_url)
                )
        else:
            # Source mode or no installer found
            dpg.add_text("Please pull the latest changes from git.", color=(200, 200, 200))
            dpg.add_text("Auto-update is only available for installed versions.", wrap=380, color=(255, 100, 100))
            if not download_url:
                 dpg.add_text("(No installer found for this release)", color=(255, 100, 100))
            
            dpg.add_spacer(height=20)
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=250)
                dpg.add_button(label="OK", width=80, callback=lambda: dpg.delete_item("update_dialog"))
                dpg.add_button(
                    label="Open GitHub",
                    callback=lambda: webbrowser.open("https://github.com/LightFuryGames/Cerebrus/releases")
                )


def _start_download_update(state: UIState, url: str) -> None:
    dpg.configure_item("update_button_group", show=False)
    dpg.configure_item("update_progress_bar", show=True)
    dpg.set_value("update_status_text", "Starting download...")
    
    def download_thread():
        try:
            def progress(current, total):
                if total > 0:
                    dpg.set_value("update_progress_bar", current / total)
                    dpg.set_value("update_status_text", f"Downloading: {current/1024/1024:.1f}/{total/1024/1024:.1f} MB")
            
            installer_path = download_update(url, progress)
            
            dpg.set_value("update_status_text", "Download complete. Launching installer...")
            time.sleep(1) # Give user a moment to see completion
            
            # Launch installer
            if run_installer(installer_path):
                 dpg.set_value("update_status_text", "Installer launched. Exiting...")
                 time.sleep(2)
                 sys.exit(0)
            else:
                 dpg.set_value("update_status_text", "Failed to launch installer.")
                 dpg.configure_item("update_button_group", show=True)
                 
        except Exception as e:
            dpg.set_value("update_status_text", f"Error: {e}")
            dpg.configure_item("update_button_group", show=True)
            
    threading.Thread(target=download_thread, daemon=True).start()


def _show_about_dialog(state: UIState) -> None:
    """Show the About dialog."""
    if dpg.does_item_exist("about_dialog"):
        dpg.delete_item("about_dialog")

    # Calculate center position
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    window_width = 600
    window_height = 400
    pos_x = (viewport_width - window_width) // 2
    pos_y = (viewport_height - window_height) // 2

    with dpg.window(
        tag="about_dialog",
        label="About",
        modal=True,
        width=window_width,
        height=window_height,
        no_resize=True,
        pos=(pos_x, pos_y),
        no_scrollbar=True,
    ):
        # Title
        dpg.add_text("Cerebrus", color=(120, 200, 255))

        # Version
        dpg.add_text(f"Version: {__version__}")

        # Author
        dpg.add_text("Author: Lightfury Games")

        # Copyright
        dpg.add_text(
            "Copyright © 2025 LeagueX Gaming Private Limited (LightFury Games)."
        )
        dpg.add_text("All rights reserved.")

        # Repository
        dpg.add_text("Repository:")
        _add_hyperlink(
            "https://github.com/LightFuryGames/Cerebrus",
            "https://github.com/LightFuryGames/Cerebrus",
        )

        # Description
        with dpg.group(horizontal=True):
            dpg.add_text("Python-based Windows-only toolkit with ")
            _add_hyperlink("DearPyGUI", "https://github.com/hoffstadt/DearPyGui")
            dpg.add_text("UI for managing")

        dpg.add_text("Unreal Engine Android profiling workflows.")

        # License
        with dpg.group(horizontal=True):
            dpg.add_text("Licensed under the")
            _add_hyperlink(
                "BSD 3-Clause License",
                "https://github.com/LightFuryGames/Cerebrus?tab=BSD-3-Clause-1-ov-file",
            )
            dpg.add_text(".")

        dpg.add_spacer(height=20)

        # OK Button
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=480)
            dpg.add_button(
                label="OK", width=80, callback=lambda: dpg.delete_item("about_dialog")
            )


def build_profile_summary(state: UIState) -> None:
    """Render the profile summary strip with read-only inputs."""
    with dpg.group(horizontal=True, horizontal_spacing=12):
        dpg.add_text("Profile Name:")
        # Use warning color for default profile, green for loaded profiles
        colors = get_theme_manager().get_profile_status_colors()
        profile_color = (
            colors["DEFAULT"]
            if not state.profile_manager.current_profile_path
            else colors["LOADED"]
        )
        dpg.add_text(
            tag="profile_nickname_input",
            default_value=state.profile_nickname,
            color=profile_color,
        )
        dpg.add_text("Package Name:")
        dpg.add_text(
            tag="package_input",
            default_value=state.package_name,
            color=profile_color,
        )
        _add_help_button("package_name")
        dpg.add_text("Profile Path:")
        with dpg.group(horizontal=True, horizontal_spacing=4):
            dpg.add_text(
                tag="profile_path_input",
                default_value=str(state.profile_path),
                color=profile_color,
            )
            dpg.add_button(label="Open", callback=lambda: _open_profile_folder(state))


def build_device_controls(state: UIState) -> None:
    """Render device actions and the device table container."""
    dpg.add_separator()
    with dpg.group(horizontal=True, horizontal_spacing=8):
        dpg.add_text("Device(s)", color=(120, 180, 255))
        _add_help_button("device_table")
        dpg.add_button(
            label="List Devices", width=120, callback=lambda: _populate_devices(state)
        )
        _add_help_button("list_devices")
    with dpg.child_window(
        border=False, autosize_x=True, height=220, tag="device_table_container"
    ):
        _render_device_table(state)


def build_file_actions(state: UIState) -> None:
    """Render file copy actions and reporting panels in tabs."""
    dpg.add_separator()
    with dpg.tab_bar():
        with dpg.tab(label="Profiling"):
            _build_profiling_tab(state)
        with dpg.tab(label="Configuration Sync"):
            _build_config_sync_tab(state)

    dpg.add_separator()
    with dpg.child_window(border=True, autosize_x=True, autosize_y=False, height=200):
        dpg.add_text("Cerebrus App Live log", color=(120, 180, 255))
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
        with dpg.child_window(
            border=True, autosize_x=True, height=130, tag="log_container"
        ):
            _render_log_entries(state)

    _register_file_dialogs(state)


def _build_profiling_tab(state: UIState) -> None:
    """Profiling tab content including remote profiling and file actions."""
    with dpg.child_window(border=True, autosize_x=True, autosize_y=False, height=350):
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Remote Profiling", color=(120, 180, 255))
            dpg.add_button(
                label="Launch Package",
                width=120,
                callback=lambda: _handle_launch_package(state),
            )
            _add_help_button("launch_package", state)
            dpg.add_button(
                label="Start Profiling",
                width=120,
                callback=lambda: _handle_start_profiling(state),
            )
            _add_help_button("start_profiling", state)
            dpg.add_button(
                label="Stop Profiling",
                width=120,
                callback=lambda: _handle_stop_profiling(state),
            )
            _add_help_button("stop_profiling", state)
        
        dpg.add_spacer(height=5)
        dpg.add_separator()
        dpg.add_spacer(height=5)

        dpg.add_text("Frame Memory Profiling", color=(120, 180, 255))
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_button(
                label="Memreport",
                width=120,
                callback=lambda: _handle_memreport(state),
            )
            _add_help_button("memreport", state)
            dpg.add_button(
                label="Memreport Full",
                width=120,
                callback=lambda: _handle_memreport_full(state),
            )
            _add_help_button("memreport_full", state)

        with dpg.group(horizontal=True, horizontal_spacing=8):
             dpg.add_input_text(
                tag="custom_command_input",
                hint="Custom Console Command (e.g. stat unit)",
                width=260,
                on_enter=True,
                callback=lambda: _handle_custom_command(state),
             )
             dpg.add_button(
                label="Send Command",
                width=120,
                callback=lambda: _handle_custom_command(state),
             )
             _add_help_button("custom_command", state)
        
        dpg.add_spacer(height=5)
        dpg.add_separator()
        dpg.add_spacer(height=5)

        dpg.add_text("Data and Perf Report", color=(120, 180, 255))
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=360)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=280)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=200)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)

            with dpg.table_row():
                with dpg.group(horizontal=True, horizontal_spacing=4):
                    dpg.add_text("Output file Name:")
                    _add_help_button("output_file_name")
                dpg.add_input_text(
                    tag="output_file_name",
                    default_value=state.output_file_name,
                    width=-1,
                    callback=_handle_output_file_name_change,
                    user_data=state,
                )
                with dpg.group(horizontal=True, horizontal_spacing=4):
                    dpg.add_checkbox(
                        tag="use_prefix_only",
                        label="Use as Prefix Only",
                        default_value=state.use_prefix_only,
                        callback=_handle_use_prefix_toggle,
                        user_data=state,
                    )
                    _add_help_button("use_prefix_only")
                dpg.add_spacer()

            with dpg.table_row():
                with dpg.group(horizontal=True, horizontal_spacing=4):
                    dpg.add_text("Output Path:")
                    _add_help_button("output_path")
                dpg.add_input_text(
                    tag="output_path_label",
                    default_value=str(state.output_path),
                    width=-1,
                    readonly=True,
                )
                dpg.add_button(
                    label="Browse",
                    width=-1,
                    callback=lambda: _browse_folder_native(state, "output"),
                )
                dpg.add_button(
                    label="Open Folder",
                    width=-1,
                    callback=lambda: _open_folder_in_explorer(state.output_path),
                )

        with dpg.group(horizontal=True, horizontal_spacing=12):
            with dpg.child_window(border=True, autosize_y=True, width=360):
                dpg.add_text(
                    "Bulk Actions From Selected Phone to PC", color=(200, 200, 200)
                )
                with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit):
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=210)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=30)

                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_move_csv",
                            label="Move Profiling Data",
                            default_value=state.move_csv_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "move_csv_enabled"),
                        )
                        _add_help_button("move_csv")

                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_move_mem",
                            label="Move Memreport Data",
                            default_value=state.move_memreport_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "move_memreport_enabled"),
                        )
                        _add_help_button("memreport")

                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_move_logs",
                            label="Move logs",
                            default_value=state.move_logs_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "move_logs_enabled"),
                        )
                        _add_help_button("move_logs")

            with dpg.child_window(border=True, autosize_y=True, width=460):
                dpg.add_text("Bulk Actions From PC to PC", color=(200, 200, 200))
                with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit):
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=310)
                    dpg.add_table_column(width_fixed=True, init_width_or_weight=30)

                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_gen_perf",
                            label="Generate Perf Report Only",
                            default_value=state.generate_perf_report_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "generate_perf_report_enabled"),
                        )
                        _add_help_button("generate_perf")

                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_gen_mem",
                            label="Generate Mem Report Only",
                            default_value=state.generate_memreport_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "generate_memreport_enabled"),
                        )
                        _add_help_button("memreport_full")
                    
                    with dpg.table_row():
                        dpg.add_checkbox(
                            tag="cb_gen_logs",
                            label="Generate Colored Logs Only",
                            default_value=state.generate_colored_logs_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "generate_colored_logs_enabled"),
                        )
                        _add_help_button("generate_logs")

                    with dpg.table_row():
                        dpg.add_button(
                            label="Generate",
                            width=300,
                            callback=lambda: _handle_generate_actions(state),
                        )
                        _add_help_button("generate_actions")

                    with dpg.table_row():
                        dpg.add_button(
                            label="View HTML Logs",
                            width=300,
                            callback=lambda: _handle_view_html_logs(state),
                        )
                        _add_help_button("view_html_logs")


def _build_config_sync_tab(state: UIState) -> None:
    """Configuration Sync panel tab content."""
    with dpg.child_window(border=True, autosize_x=True, autosize_y=False, height=450):
        build_remote_config_sync(state)


def _populate_devices(state: UIState) -> None:
    package_value = (
        dpg.get_value("package_input") if dpg.does_item_exist("package_input") else ""
    )
    state.package_name = package_value or ""
    state.devices = collect_device_info(state.package_name)

    if not state.devices:
        _show_device_troubleshooting_dialog(state)

    _refresh_device_table(state)


def _show_device_troubleshooting_dialog(state: UIState) -> None:
    """Show a dialog with ADB troubleshooting steps."""
    if dpg.does_item_exist("adb_troubleshoot_dialog"):
        dpg.delete_item("adb_troubleshoot_dialog")

    # Center the dialog
    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    width = 500
    height = 320
    pos_x = (viewport_width - width) // 2
    pos_y = (viewport_height - height) // 2

    with dpg.window(
        tag="adb_troubleshoot_dialog",
        label="Device Connection Issue",
        modal=True,
        width=width,
        height=height,
        pos=(pos_x, pos_y),
        no_resize=True,
    ):
        dpg.add_text("No active devices found.", color=(255, 100, 100))
        dpg.add_text(
            "If your device is connected but not showing up, please try the following:",
            wrap=460,
        )
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            dpg.add_text("1.")
            dpg.add_text("Open Command Prompt (cmd.exe) or PowerShell.")

        with dpg.group(horizontal=True):
            dpg.add_text("2.")
            dpg.add_text("Run the command:")
            dpg.add_text("adb devices", color=(120, 255, 120))

        with dpg.group(horizontal=True):
            dpg.add_text("3.")
            dpg.add_text("Check your phone for a USB Debugging permission popup.")

        with dpg.group(horizontal=True):
            dpg.add_text("  ")
            dpg.add_text(
                "Select 'Always allow' and click Allow.", color=(255, 255, 150)
            )

        with dpg.group(horizontal=True):
            dpg.add_text("4.")
            dpg.add_text("Restart Cerebrus or click 'List Devices' again.")

        dpg.add_spacer(height=20)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            dpg.add_spacer(width=380)
            dpg.add_button(
                label="OK",
                width=80,
                callback=lambda: dpg.delete_item("adb_troubleshoot_dialog"),
            )
            
            
def _handle_launch_package(state: UIState) -> None:
    """Launch or resume the package on the selected device."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()

    # Check if installed
    if not client.is_package_installed(state.selected_device_serial, state.package_name):
        log_message(state, "ERROR", f"Package {state.package_name} not found on device.")
        return

    try:
        log_message(state, "INFO", f"Launching {state.package_name}...")
        client.launch_package(state.selected_device_serial, state.package_name)
        log_message(state, "SUCCESS", f"Sent launch command for {state.package_name}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to launch package: {e}")


def _handle_start_profiling(state: UIState) -> None:
    """Send 'CsvProfile Start' command to the selected device."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()

    # Check if running - Fail if not
    if not client.is_package_running(state.selected_device_serial, state.package_name):
        log_message(
            state,
            "ERROR",
            f"Package {state.package_name} is not running on the device.",
        )
        log_message(
            state,
            "ERROR",
            "Please launch the application on the device before starting profiling.",
        )
        return

    try:
        log_message(state, "INFO", "Sending 'CsvProfile Start'...")
        client.send_console_command(state.selected_device_serial, "CsvProfile Start")
        log_message(state, "SUCCESS", "Sent start profiling command.")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to send command: {e}")


def _handle_stop_profiling(state: UIState) -> None:
    """Send 'CsvProfile Stop' command to the selected device."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()

    # Check if running - Fail if not
    if not client.is_package_running(state.selected_device_serial, state.package_name):
        log_message(
            state,
            "ERROR",
            f"Package {state.package_name} is not running on the device.",
        )
        log_message(
            state, "ERROR", "Cannot stop profiling if the application is not running."
        )
        return

    try:
        log_message(state, "INFO", "Sending 'CsvProfile Stop'...")
        client.send_console_command(state.selected_device_serial, "CsvProfile Stop")
        log_message(state, "SUCCESS", "Sent stop profiling command.")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to send command: {e}")


def _handle_memreport(state: UIState) -> None:
    """Send 'memreport' command to the selected device."""
    _send_console_command_wrapper(state, "memreport")


def _handle_memreport_full(state: UIState) -> None:
    """Send 'memreport -full' command to the selected device."""
    _send_console_command_wrapper(state, "memreport -full")


def _handle_custom_command(state: UIState) -> None:
    """Send custom console command from input."""
    command = dpg.get_value("custom_command_input")
    if not command:
        log_message(state, "WARNING", "No command entered.")
        return
    
    _send_console_command_wrapper(state, command)


def _send_console_command_wrapper(state: UIState, command: str) -> None:
    """Helper to send console commands with common validation."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()

    # Check if running - Fail if not
    if not client.is_package_running(state.selected_device_serial, state.package_name):
        log_message(
            state,
            "ERROR",
            f"Package {state.package_name} is not running on the device.",
        )
        log_message(
             state, "ERROR", f"Cannot send '{command}' if the application is not running."
        )
        return

    try:
        log_message(state, "INFO", f"Sending '{command}'...")
        client.send_console_command(state.selected_device_serial, command)
        log_message(state, "SUCCESS", f"Sent command: {command}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to send command: {e}")


def _handle_log_filter(sender: int, app_data: str, user_data: UIState) -> None:
    user_data.log_filter = app_data or ""
    _render_log_entries(user_data)


def _handle_output_file_name_change(
    sender: int, app_data: str, user_data: UIState
) -> None:
    user_data.output_file_name = app_data
    _auto_save_profile(user_data)


def _handle_use_prefix_toggle(sender: int, app_data: bool, user_data: UIState) -> None:
    user_data.use_prefix_only = bool(app_data)
    _auto_save_profile(user_data)


def _handle_bulk_action_toggle(
    sender: int, app_data: bool, user_data: tuple[UIState, str]
) -> None:
    state, field_name = user_data
    setattr(state, field_name, app_data)
    _auto_save_profile(state)


def _handle_generate_actions(state: UIState) -> None:
    """Execute selected bulk actions."""
    if state.move_logs_enabled:
        _handle_move_logs(state)
    if state.move_csv_enabled:
        _handle_move_csv(state)
    if state.move_memreport_enabled:
        _handle_move_memreport(state)
    if state.generate_perf_report_enabled:
        _handle_generate_perf_report(state)
    if state.generate_colored_logs_enabled:
        _handle_generate_colored_logs(state)


def _open_profile_folder(state: UIState) -> None:
    """Open the folder containing the current profile."""
    if state.profile_path and state.profile_path.exists():
        if state.profile_path.is_file():
            _open_folder_in_explorer(state.profile_path.parent)
        else:
            _open_folder_in_explorer(state.profile_path)
    else:
        log_message(state, "WARNING", "Profile path does not exist.")


def _handle_move_csv(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/CSV", "CSV")


def _handle_move_memreport(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/MemReports", "MemReports")


def _handle_move_logs(state: UIState) -> None:
    _move_files_from_device(state, "Logs", "Logs")


def _get_unique_output_path(base_path: Path, filename: str, extension: str) -> Path:
    """
    Generate a unique file path by appending a counter if the file already exists.

    Args:
        base_path: Directory where the file will be saved
        filename: Desired filename without extension
        extension: File extension (with or without leading dot)

    Returns:
        A unique Path object that doesn't conflict with existing files
    """
    # Ensure extension has a leading dot
    if not extension.startswith("."):
        extension = f".{extension}"

    output_path = base_path / f"{filename}{extension}"

    # If file doesn't exist, return it
    if not output_path.exists():
        return output_path

    # File exists, find a unique name by appending counter
    counter = 1
    while True:
        output_path = base_path / f"{filename}_{counter}{extension}"
        if not output_path.exists():
            return output_path
        counter += 1


def _handle_generate_perf_report(state: UIState) -> None:
    """Run PerfreportTool on CSV files and delete them on success."""
    # Locate PerfreportTool.exe
    # Assuming repo root is 3 levels up from this file (cerebrus/ui/components.py -> cerebrus/ui -> cerebrus -> root)
    repo_root = Path(__file__).resolve().parent.parent.parent
    tool_path = repo_root / "Binaries" / "CsvTools" / "PerfReportTool.exe"

    if not tool_path.exists():
        log_message(state, "ERROR", f"PerfreportTool not found at: {tool_path}")
        return

    # Input CSV directory: Use base path / CSV (where files are actually moved)
    base_path = state.base_output_path if state.base_output_path else state.output_path
    csv_dir = base_path / "CSV"
    if not csv_dir.exists():
        log_message(state, "ERROR", f"CSV directory not found: {csv_dir}")
        return

    # Output directory: state.output_path (which includes device folder if set)
    output_dir = state.output_path

    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_message(state, "ERROR", f"Failed to create output directory: {e}")
            return

    csv_files = list(csv_dir.glob("*.csv"))
    if not csv_files:
        log_message(state, "WARNING", f"No CSV files found in {csv_dir}")
        return

    log_message(
        state, "INFO", f"Found {len(csv_files)} CSV files. Starting processing..."
    )

    for csv_file in csv_files:
        # Determine output filename based on use_prefix_only setting
        if state.use_prefix_only:
            # Use output_file_name as prefix + CSV filename
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{csv_file.stem}"
            else:
                output_filename = csv_file.stem
        else:
        # Use output_file_name as exact filename (or CSV filename if not set)
            output_filename = (
                state.output_file_name if state.output_file_name else csv_file.stem
            )

        # PerfReportTool uses -o as the Output Directory
        # We need a unique directory name to avoid conflicts
        report_dir_name = output_filename
        report_dir = output_dir / report_dir_name
        
        # Simple uniqueness check for directory
        counter = 1
        while report_dir.exists():
             report_dir = output_dir / f"{report_dir_name}_{counter}"
             counter += 1

        cmd = [
            str(tool_path),
            "-csv",
            str(csv_file),
            "-reportType",
            "Default60fps",
            "-o",
            str(report_dir),
            "-perfLog",
        ]

        log_message(state, "INFO", f"Processing {csv_file.name}...")

        try:
            # Run command
            # Create startupinfo to hide console window on Windows
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd, capture_output=True, text=True, startupinfo=startupinfo
            )

            if result.returncode == 0:
                # Calculate likely HTML path
                generated_html_path = report_dir / f"{csv_file.stem}.html"
                
                log_message(
                    state, "SUCCESS", f"Generated report in: {report_dir.name}"
                )
                # Inject System Metadata
                try:
                    _inject_metadata_into_report(state, csv_file, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Metadata injection failed: {e}")

                # Post-process to add Avg FPS - pass the actual HTML file
                try:
                    _post_process_perf_report(state, generated_html_path)
                except Exception as e:
                     log_message(state, "WARNING", f"Post-processing failed: {e}")

                # Delete the CSV file
                try:
                    csv_file.unlink()
                    log_message(state, "INFO", f"Deleted {csv_file.name}")
                except Exception as e:
                    log_message(
                        state, "WARNING", f"Failed to delete {csv_file.name}: {e}"
                    )

            else:
                log_message(state, "ERROR", f"Failed to process {csv_file.name}")
                log_message(state, "ERROR", f"Tool Output: {result.stdout}")
                log_message(state, "ERROR", f"Tool Error: {result.stderr}")

        except Exception as e:
            log_message(
                state, "ERROR", f"Exception while processing {csv_file.name}: {e}"
            )

    log_message(state, "INFO", "Batch processing completed.")


def _post_process_perf_report(state: UIState, file_path: Path) -> None:
    """Post-process the generated HTML report to add Avg FPS column."""
    if not file_path.exists():
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        
        # We target the table immediately following "FPSChart"
        # 1. Find the start of FPSChart section
        chart_start_match = re.search(r"FPSChart", content)
        if not chart_start_match:
            _log_debug_to_file("FPSChart section not found")
            return

        # 2. Find the table start after that
        table_start_match = re.search(r"<table", content[chart_start_match.end():])
        if not table_start_match:
            _log_debug_to_file("Table after FPSChart not found")
            return
            
        real_table_start_idx = chart_start_match.end() + table_start_match.start()
        
        # 3. Find table end
        table_end_match = re.search(r"</table>", content[real_table_start_idx:])
        if not table_end_match:
            return
            
        real_table_end_idx = real_table_start_idx + table_end_match.end()
        
        table_content = content[real_table_start_idx:real_table_end_idx]
        
        # PROCESS HEADER
        # Find the header row (contains Frametime)
        # Using a marker for the FrameTime column to insert after.
        # Screenshot shows: "Frametime Avg" or "Frametime<br>Avg"
        
        if "Frametime" in table_content:
             # pattern to find <th>...Frametime...</th>
            header_pattern = re.compile(r"(<th[^>]*>.*?Frametime.*?</th>)", re.IGNORECASE | re.DOTALL)
            if header_pattern.search(table_content):
                table_content = header_pattern.sub(r"\1<th style=\"background-color:#e0e0e0\">FPS Avg</th>", table_content, count=1)
                _log_debug_to_file("Injected Header")

        # PROCESS ROWS
        # We iterate over <tr> rows
        # We need to find the index of Frametime column if possible, or assume based on screenshot.
        # Screenshot: Section Name(0), Total Time(1), Hitches/Min(2), HitchTimePercent(3), MVP60(4), Frametime(5)
        # We will assume index 5 for Frametime.
        
        def row_processor(match):
            row_html = match.group(0)
            # Skip if header (contains <th>)
            if "<th" in row_html:
                return row_html
                
            cells_match = list(re.finditer(r"(<td[^>]*>.*?</td>)", row_html, re.IGNORECASE | re.DOTALL))
            if not cells_match:
                return row_html
                
            # Target Frametime column (Index 5)
            target_idx = 5
            if len(cells_match) > target_idx:
                try:
                    # Extract text from cell
                    cell_html = cells_match[target_idx].group(0)
                    # Strip tags
                    cell_text = re.sub(r"<[^>]+>", "", cell_html).strip()
                    frametime = float(cell_text)
                    
                    if frametime > 0:
                        fps = 1000.0 / frametime
                        
                        # Color Coding
                        if fps >= 59.99:
                            color = "#87d387" # Green
                        elif fps <= 30.0:
                            color = "#ff6666" # Red
                        else:
                            color = "#ffedcc" # Orange
                            
                        new_cell = f'<td bgcolor="{color}" style="font-weight:bold;">{fps:.2f}</td>'
                        
                        # Insert after target cell
                        target_end = cells_match[target_idx].end()
                        
                        # We must splice into original row_html
                        # But row_html is just the <tr>...</tr> string from regex
                        # We use the relative positions from finditer
                        
                        return row_html[:target_end] + new_cell + row_html[target_end:]
                        
                except ValueError:
                    pass # Header row or invalid data
            
            return row_html

        # Replace rows in table_content
        new_table_content = re.sub(r"<tr[^>]*>.*?</tr>", row_processor, table_content, flags=re.DOTALL)
        
        # Splice back into main content
        new_content = content[:real_table_start_idx] + new_table_content + content[real_table_end_idx:]
        
        file_path.write_text(new_content, encoding="utf-8")
        _log_debug_to_file("FPS Column processing complete")
        log_message(state, "SUCCESS", "Added FPS Avg column to report.")

    except Exception as e:
        _log_debug_to_file(f"Post-process error: {e}")
        log_message(state, "ERROR", f"Failed to post-process report: {e}")


def _log_debug_to_file(msg: str):
    try:
        # Determine root: Handle frozen vs script
        if getattr(sys, 'frozen', False):
            # In installed app, use executable dir
            root_path = Path(sys.executable).parent
        else:
             # In dev, use repo root (cerebrus/ui/components.py -> cerebrus/ui -> cerebrus -> root)
            root_path = Path(__file__).resolve().parent.parent.parent
            
        debug_dir = root_path / "DebugInfo"
        if not debug_dir.exists():
            debug_dir.mkdir(parents=True, exist_ok=True)
            
        debug_path = debug_dir / "cerebrus_debug.txt"
        
        with open(debug_path, "a", encoding="utf-8") as f:
             from datetime import datetime
             f.write(f"[{datetime.now()}] {msg}\n")
    except:
        pass

def _inject_metadata_into_report(state: UIState, csv_file: Path, html_file: Path) -> None:
    """Read metadata from CSV and append to HTML report table."""
    _log_debug_to_file(f"Starting injection for {html_file}")
    if not html_file.exists():
        _log_debug_to_file("HTML file does not exist")
        return

    try:
        metadata = _read_csv_metadata(csv_file)
        _log_debug_to_file(f"Parsed metadata keys: {list(metadata.keys())}")
        
        if not metadata:
            log_message(state, "WARNING", f"No metadata found in {csv_file.name}")
            return
        
        # Log metadata keys for debugging
        # log_message(state, "DEBUG", f"Metadata keys: {list(metadata.keys())}")

        # Extract fields
        config = metadata.get("config", "Unknown")
        os_name = metadata.get("os", "Unknown")
        cpu = metadata.get("cpu", "Unknown")
        duration = metadata.get("captureduration", "0")
        try:
            duration_val = float(duration)
            duration_str = f"{duration_val:.2f} s"
        except ValueError:
            duration_str = duration
        
        cmd_line = metadata.get("commandline", "").strip()
        target_fps = metadata.get("targetframerate", "60")

        # Features Logic
        features_list = []
        if metadata.get("largeworldcoordinates") == "1":
            features_list.append("Large World Coordinates (LWC) Enabled")
        
        # PGO/LTO/ASAN
        pgo = metadata.get("pgoenabled", "0")
        lto = metadata.get("ltoenabled", "0")
        asan = metadata.get("asan", "0")
        if pgo == "0" and lto == "0" and asan == "0":
            features_list.append("PGO/LTO/ASAN Disabled")
        else:
            enabled = []
            if pgo == "1": enabled.append("PGO")
            if lto == "1": enabled.append("LTO")
            if asan == "1": enabled.append("ASAN")
            if enabled:
                features_list.append(f"{'/'.join(enabled)} Enabled")

        features_str = "; ".join(features_list)

        # Build HTML Rows
        extra_rows = f'''
        <tr><td>Configuration</td><td><b>{config}</b></td></tr>
        <tr><td>OS</td><td><b>{os_name}</b></td></tr>
        <tr><td>CPU/Device</td><td><b>{cpu}</b></td></tr>
        <tr><td>Capture Duration</td><td><b>{duration_str}</b></td></tr>
        <tr><td>Command Line</td><td><b>{cmd_line}</b></td></tr>
        <tr><td>Features</td><td><b>{features_str}</b></td></tr>
        <tr><td>Target Framerate</td><td><b>{target_fps} FPS</b></td></tr>
        '''

        # Inject into HTML
        content = html_file.read_text(encoding="utf-8")

        # Robust regex to find the summary table row containing "Frame count"
        # Matches: <tr ...> ... Frame count ... </tr>
        # Uses [\s\S] or DOTALL to match across newlines inside tags/content
        pattern = re.compile(r"(<tr[^>]*>.*?Frame\s*count.*?</tr>)", re.IGNORECASE | re.DOTALL)
        
        match = pattern.search(content)
        
        if match:
             _log_debug_to_file("Found Frame count row match")
             insertion_point = match.end()
             new_content = content[:insertion_point] + extra_rows + content[insertion_point:]
             html_file.write_text(new_content, encoding="utf-8")
             log_message(state, "SUCCESS", f"Metadata successfully appended to {html_file.name}")
        else:
             # Fallback: Try finding specific table class or ID if known, or just log clearer warning
             _log_debug_to_file("Failed to find Frame count row match")
             _log_debug_to_file(f"HTML Preview: {content[:1000]}") # First 1000 chars
             
             log_message(state, "WARNING", f"Metadata injection failed: Could not find 'Frame count' row in {html_file.name}")
             # Dump snippet for debugging if needed
             # log_message(state, "DEBUG", f"Content start: {content[:500]}")

    except Exception as e:
        _log_debug_to_file(f"Exception: {e}")
        log_message(state, "ERROR", f"Failed to inject metadata into {html_file.name}: {e}")


def _read_csv_metadata(csv_path: Path) -> dict:
    """Read the last chunk of CSV to extract metadata."""
    metadata = {}
    try:
        with open(csv_path, 'rb') as f:
            try:
                f.seek(-16384, 2)  # Read last 16KB
            except OSError:
                f.seek(0)
            
            tail_bytes = f.read()
            # Decode carefully
            tail = tail_bytes.decode('utf-8', errors='ignore')
            
        _log_debug_to_file(f"CSV Tail read: {len(tail)} chars")
        # _log_debug_to_file(f"Tail snippet: {tail[-200:]}")

        # Find key-values: [key] value (handling commas from CSV format)
        # Regex captures:
        # Group 1: key (inside [])
        # Group 2: remaining content until next [ or newline
        matches = re.findall(r"\[([a-zA-Z0-9_]+)\]\s*([^[\]\r\n]+)", tail)
        for key, value in matches:
            # Strip whitespace and potential CSV commas
            clean_value = value.strip().strip(',').strip()
            metadata[key.lower()] = clean_value
            
    except Exception as e:
        _log_debug_to_file(f"CSV Read Exception: {e}")
        print(f"Error reading CSV metadata: {e}")
        
    return metadata


def _handle_generate_colored_logs(state: UIState) -> None:
    """Convert text logs to colored HTML logs."""
    # Input Logs directory: Use base path / Logs (where files are actually moved)
    base_path = state.base_output_path if state.base_output_path else state.output_path
    logs_dir = base_path / "Logs"
    if not logs_dir.exists():
        log_message(state, "ERROR", f"Logs directory not found: {logs_dir}")
        return

    # Output directory: state.output_path (which includes device folder if set)
    output_dir = state.output_path

    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_message(state, "ERROR", f"Failed to create output directory: {e}")
            return

    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.txt"))
    if not log_files:
        log_message(state, "WARNING", f"No log files found in {logs_dir}")
        return

    log_message(
        state, "INFO", f"Found {len(log_files)} log files. Starting conversion..."
    )

    for log_file in log_files:
        # Determine output filename based on use_prefix_only setting
        if state.use_prefix_only:
            # Use output_file_name as prefix + log filename
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{log_file.stem}"
            else:
                output_filename = log_file.stem
        else:
            # Use output_file_name as exact filename (or log filename if not set)
            output_filename = (
                state.output_file_name if state.output_file_name else log_file.stem
            )

        # Get unique path to avoid overwriting existing files
        output_file_path = _get_unique_output_path(output_dir, output_filename, ".html")

        log_message(state, "INFO", f"Converting {log_file.name}...")

        try:
            # Run conversion directly
            convert_log_to_html(log_file, output_file_path)
            log_message(state, "SUCCESS", f"Created {output_file_path.name}")

            # Delete the source file
            try:
                log_file.unlink()
                log_message(state, "INFO", f"Deleted {log_file.name}")
            except Exception as e:
                log_message(state, "WARNING", f"Failed to delete {log_file.name}: {e}")

        except Exception as e:
            log_message(
                state, "ERROR", f"Exception while converting {log_file.name}: {e}"
            )

    log_message(state, "INFO", "Log conversion completed.")


def _handle_view_html_logs(state: UIState) -> None:
    """Open HTML log files in the default web browser."""
    # Output directory: state.output_path (device-specific folder)
    output_dir = state.output_path
    if not output_dir.exists():
        log_message(state, "ERROR", f"Output directory not found: {output_dir}")
        return

    # Find all HTML files recursively in the output directory and subdirectories
    html_files = list(output_dir.glob("**/*.html"))

    if not html_files:
        log_message(state, "WARNING", f"No HTML files found in {output_dir}")
        log_message(state, "INFO", "Generate colored logs first to create HTML files.")
        return

    # Sort by modification time (newest first)
    html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    log_message(state, "INFO", f"Found {len(html_files)} HTML file(s) in {output_dir}")

    # Show a dialog to select which HTML file to open
    _show_html_file_selector(state, html_files)


def _show_html_file_selector(state: UIState, html_files: list) -> None:
    """Show a dialog to select and open HTML files."""
    if dpg.does_item_exist("html_viewer_dialog"):
        dpg.delete_item("html_viewer_dialog")

    with dpg.window(
        tag="html_viewer_dialog",
        label="Select HTML Log to View",
        modal=True,
        width=600,
        height=400,
    ):
        dpg.add_text("Available HTML Log Files:", color=(120, 180, 255))
        dpg.add_separator()

        with dpg.child_window(border=True, autosize_x=True, height=280):
            for html_file in html_files:
                # Get file modification time
                from datetime import datetime

                mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

                # Create a button for each file
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label=f"📄 {html_file.name}",
                        width=400,
                        callback=lambda s, a, u: _open_html_file(state, u),
                        user_data=html_file,
                    )
                    dpg.add_text(f"Modified: {time_str}", color=(150, 150, 150))

        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Open All",
                width=120,
                callback=lambda: _open_all_html_files(state, html_files),
            )
            dpg.add_button(
                label="Close",
                width=120,
                callback=lambda: dpg.delete_item("html_viewer_dialog"),
            )


def _open_html_file(state: UIState, html_file: Path) -> None:
    """Open a single HTML file in the default web browser."""
    try:
        # Use webbrowser module (part of Python standard library)
        webbrowser.open(f"file:///{html_file.as_posix()}")
        log_message(state, "SUCCESS", f"Opened {html_file.name} in browser")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to open {html_file.name}: {e}")


def _open_all_html_files(state: UIState, html_files: list) -> None:
    """Open all HTML files in the default web browser."""
    opened_count = 0
    for html_file in html_files:
        try:
            webbrowser.open(f"file:///{html_file.as_posix()}")
            opened_count += 1
        except Exception as e:
            log_message(state, "ERROR", f"Failed to open {html_file.name}: {e}")

    if opened_count > 0:
        log_message(state, "SUCCESS", f"Opened {opened_count} HTML file(s) in browser")

    # Close the dialog
    if dpg.does_item_exist("html_viewer_dialog"):
        dpg.delete_item("html_viewer_dialog")


def _move_files_from_device(
    state: UIState, source_subpath: str, dest_subpath: str
) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    parts = state.package_name.split(".")
    if len(parts) < 3:
        log_message(
            state, "ERROR", "Invalid Package Name format. Cannot derive Project Name."
        )
        return
    project_name = parts[-1]

    # Source: /sdcard/Android/data/{package}/files/UnrealGame/{project}/{project}/Saved/{source_subpath}/
    # User confirmed structure: UnrealGame/{Name}/{Name}/Saved/...
    source_path = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/{source_subpath}/"

    # Dest: Use base_output_path (not device-specific) / {dest_subpath}/
    # This ensures files go to OutputPath/CSV and OutputPath/Logs, not OutputPath/Device/CSV
    base_path = state.base_output_path if state.base_output_path else state.output_path
    dest_path = base_path / dest_subpath

    if not dest_path.exists():
        dest_path.mkdir(parents=True, exist_ok=True)

    client = AdbClient()
    serial = state.selected_device_serial

    log_message(state, "INFO", f"Moving files from {source_path} to {dest_path}...")

    try:
        # Pull all files from source directory
        # Append . to source path to pull contents
        client.pull(serial, source_path + ".", str(dest_path))

        # Delete files from source
        client.shell(serial, ["rm", "-rf", source_path + "*"])

        log_message(state, "SUCCESS", f"Moved files to {dest_path}")
    except AdbError as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "No such file or directory" in error_msg:
            file_type = "Logs" if "Logs" in dest_subpath else "CSV Data"
            log_message(state, "ERROR", f"No {file_type} present on device.")
        else:
            log_message(state, "ERROR", f"ADB Error: {e}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to move files: {e}")


def _render_log_entries(state: UIState) -> None:
    if not dpg.does_item_exist("log_container"):
        return

    dpg.delete_item("log_container", children_only=True)
    filter_value = state.log_filter.lower()
    filtered_logs = [
        entry
        for entry in state.logs
        if filter_value in entry[1].lower() or filter_value in entry[2].lower()
    ]

    if not filtered_logs:
        dpg.add_text(
            "No log entries match the filter.",
            color=(180, 180, 180),
            parent="log_container",
        )
        return

    log_colors = get_theme_manager().get_log_colors()

    for timestamp, level, message in filtered_logs:
        color = log_colors.get(level.upper(), (220, 220, 220))
        full_msg = f"[{timestamp}] [{level}] {message}"

        item = dpg.add_input_text(
            default_value=full_msg,
            readonly=True,
            width=-1,
            parent="log_container",
        )

        theme = _get_log_theme(level.upper(), color)
        dpg.bind_item_theme(item, theme)

    # Auto-scroll to bottom
    # Using a large value to ensure it scrolls to the absolute bottom even if layout isn't fully updated
    dpg.set_y_scroll("log_container", 999999.0)


_LOG_THEMES: dict[str, int] = {}


def _get_log_theme(level: str, color: tuple) -> int:
    if level in _LOG_THEMES:
        if dpg.does_item_exist(_LOG_THEMES[level]):
            return _LOG_THEMES[level]

    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvInputText):
            dpg.add_theme_color(dpg.mvThemeCol_Text, color)
            dpg.add_theme_style(dpg.mvStyleVar_FrameBorderSize, 0)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (0, 0, 0, 0))

    _LOG_THEMES[level] = theme
    return theme


def log_message(state: UIState, level: str, message: str) -> None:
    from datetime import datetime

    timestamp = datetime.now().strftime("%d-%m-%y %H:%M:%S")
    state.logs.append((timestamp, level, message))
    _render_log_entries(state)


def _clear_logs(state: UIState) -> None:
    state.logs.clear()
    _render_log_entries(state)


def _handle_export_logs(state: UIState) -> None:
    """Export current logs to a text file."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".log",
            filetypes=[
                ("Log Files", "*.log"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )

        root.destroy()

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                for timestamp, level, message in state.logs:
                    f.write(f"[{timestamp}] [{level}] {message}\n")

            log_message(state, "SUCCESS", f"Logs exported to {file_path}")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to export logs: {e}")


def _refresh_device_table(state: UIState) -> None:
    if not dpg.does_item_exist("device_table_container"):
        return

    existing_table = "device_table"
    if dpg.does_item_exist(existing_table):
        dpg.delete_item(existing_table)

    _render_device_table(state)


def _render_device_table(state: UIState) -> None:
    with dpg.table(
        tag="device_table",
        parent="device_table_container",
        header_row=True,
        resizable=True,
        borders_outerH=True,
        borders_outerV=True,
        borders_innerH=True,
        borders_innerV=True,
    ):
        for column in [
            "Make",
            "Model",
            "Serial",
            "Android Ver.",
            "SDK level",
            "Package Found",
        ]:
            dpg.add_table_column(label=column)

        state.device_cell_tags = []

        if not state.devices:
            with dpg.table_row():
                for message in ["-", "-", "No devices listed", "-", "-", "-"]:
                    dpg.add_text(message)
        else:
            for row_index, device in enumerate(state.devices):
                _render_device_row(row_index, device, state)


def _render_device_row(row_index: int, device: DeviceInfo, state: UIState) -> None:
    with dpg.table_row():
        values = [
            device.make,
            device.model,
            device.serial,
            device.android_version,
            device.sdk_level,
            "True" if device.package_found else "False",
        ]

        row_tags: list[str] = []
        for column_index, value in enumerate(values):
            cell_tag = f"device_cell_{row_index}_{column_index}"
            # Color code the Package Found column (last column)
            if column_index == len(values) - 1:  # Package Found column
                if device.package_found:
                    text_color = (
                        get_theme_manager().get_log_colors().get("SUCCESS", (0, 255, 0))
                    )
                else:
                    text_color = (
                        get_theme_manager().get_log_colors().get("ERROR", (255, 0, 0))
                    )
                # Use text with color instead of selectable for this column
                dpg.add_text(value, color=text_color, tag=cell_tag)
            else:
                dpg.add_selectable(
                    tag=cell_tag,
                    label=value,
                    span_columns=False,
                    callback=_handle_device_select,
                    user_data=(state, row_index, device.serial),
                    enabled=device.package_found,  # Disable if package not found
                )
            row_tags.append(cell_tag)

        state.device_cell_tags.append(row_tags)

    if state.selected_device_serial == device.serial:
        _select_device_row(row_index, state)


def _handle_device_select(
    sender: int, app_data: int, user_data: tuple[UIState, int, str]
) -> None:
    state, row_index, serial = user_data

    # Check if package found on this device
    selected_device = None
    for device in state.devices:
        if device.serial == serial:
            selected_device = device
            break

    if selected_device and not selected_device.package_found:
        log_message(
            state,
            "WARNING",
            f"Package not found on {selected_device.make} {selected_device.model}. Please install the necessary package.",
        )
        # Don't select the row
        return

    state.selected_device_serial = serial

    if not dpg.does_item_exist("device_table"):
        return
    _select_device_row(row_index, state)

    # Update output path to show device-specific folder
    if selected_device:
        # Store base path if not already stored
        if state.base_output_path is None:
            state.base_output_path = state.output_path

        device_folder = f"{selected_device.make}_{selected_device.model}"
        state.output_path = state.base_output_path / device_folder

        if dpg.does_item_exist("output_path_label"):
            dpg.set_value("output_path_label", str(state.output_path))

        # Update config output path
        if state.base_config_output_path is None:
            state.base_config_output_path = state.config_output_path
        
        state.config_output_path = state.base_config_output_path / device_folder
        if dpg.does_item_exist("config_output_path_label"):
            dpg.set_value("config_output_path_label", str(state.config_output_path))

        # Update output file name to match device make and model
        new_file_name = f"{selected_device.make}_{selected_device.model}"
        state.output_file_name = new_file_name
        if dpg.does_item_exist("output_file_name"):
            dpg.set_value("output_file_name", new_file_name)
        _auto_save_profile(state)
        
        # Refresh config lists
        _render_device_configs_list(state)



def _select_device_row(row_index: int, state: UIState) -> None:
    for index in range(len(state.devices)):
        dpg.unhighlight_table_row("device_table", index)

    dpg.highlight_table_row("device_table", row_index, SELECTED_ROW_COLOR)

    for cell_tags in state.device_cell_tags:
        for col_idx, tag in enumerate(cell_tags):
            # Skip the last column (Package Found) as it's a text widget, not selectable
            if col_idx < len(cell_tags) - 1 and dpg.does_item_exist(tag):
                dpg.set_value(tag, False)

    if 0 <= row_index < len(state.device_cell_tags):
        for col_idx, tag in enumerate(state.device_cell_tags[row_index]):
            # Skip the last column (Package Found) as it's a text widget, not selectable
            if col_idx < len(
                state.device_cell_tags[row_index]
            ) - 1 and dpg.does_item_exist(tag):
                dpg.set_value(tag, True)


def _show_file_dialog(tag: str) -> None:
    if dpg.does_item_exist(tag):
        dpg.configure_item(tag, show=True)


def _browse_folder_native(state: UIState, path_type: str) -> None:
    """Open native Windows folder browser dialog."""
    try:
        # Create a hidden Tk root window
        root = Tk()
        root.withdraw()  # Hide the main window
        root.attributes("-topmost", True)  # Bring dialog to front

        # Get initial directory
        if path_type == "input":
            initial_dir = (
                str(state.input_path) if state.input_path.exists() else str(Path.home())
            )
        else:  # output
            initial_dir = (
                str(state.output_path)
                if state.output_path.exists()
                else str(Path.home())
            )

        # Show folder selection dialog
        folder_path = filedialog.askdirectory(
            title=f"Select {'Input' if path_type == 'input' else 'Output'} Folder",
            initialdir=initial_dir,
        )

        root.destroy()  # Clean up

        if folder_path:  # User selected a folder
            selected_path = Path(folder_path)

            if path_type == "input":
                state.input_path = selected_path
                if dpg.does_item_exist("input_path_label"):
                    dpg.set_value("input_path_label", str(selected_path))
                log_message(state, "SUCCESS", f"Input path set to: {selected_path}")
                _auto_save_profile(state)
            elif path_type == "output":
                state.base_output_path = selected_path
                state.output_path = selected_path

                if dpg.does_item_exist("output_path_label"):
                    dpg.set_value("output_path_label", str(state.output_path))
                log_message(
                    state, "SUCCESS", f"Output path set to: {state.output_path}"
                )
                _auto_save_profile(state)
            elif path_type == "config_output":
                state.base_config_output_path = selected_path
                state.config_output_path = selected_path

                if dpg.does_item_exist("config_output_path_label"):
                    dpg.set_value("config_output_path_label", str(state.config_output_path))
                log_message(
                    state, "SUCCESS", f"Config output path set to: {state.config_output_path}"
                )
                _render_downloaded_configs_list(state)
                _auto_save_profile(state)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to open folder browser: {e}")


def _open_folder_in_explorer(folder_path: Path) -> None:
    """Open a folder in Windows Explorer."""
    try:
        if not folder_path.exists():
            # Try to create the folder
            folder_path.mkdir(parents=True, exist_ok=True)

        # Open in Windows Explorer
        os.startfile(str(folder_path))
    except Exception as e:
        # If folder doesn't exist or can't be opened, log error
        print(f"Failed to open folder: {e}")


def _register_file_dialogs(state: UIState) -> None:
    if not dpg.does_item_exist("input_path_dialog"):
        with dpg.file_dialog(
            directory_selector=True,  # Allow directory selection
            show=False,
            callback=_handle_input_path_selected,
            user_data=state,
            tag="input_path_dialog",
            width=600,
            height=400,
        ):
            dpg.add_file_extension(".csv", color=(0, 120, 255, 255))
            dpg.add_file_extension(".txt", color=(120, 255, 120, 255))
            dpg.add_file_extension(".*")

    if not dpg.does_item_exist("output_path_dialog"):
        with dpg.file_dialog(
            directory_selector=True,
            show=False,
            callback=_handle_output_path_selected,
            user_data=state,
            tag="output_path_dialog",
            width=500,
            height=400,
        ):
            dpg.add_file_extension(".*")


def _handle_input_path_selected(
    sender: int, app_data: dict, user_data: UIState
) -> None:
    # For directory selector, use file_path_name; for file selector, use selections
    selection = app_data.get("file_path_name") or next(
        iter(app_data.get("selections", {}).values()), None
    )
    if selection is None:
        return

    # Validate path exists before setting
    path = Path(selection)
    if not path.exists():
        return

    user_data.input_path = path
    if dpg.does_item_exist("input_path_label"):
        dpg.set_value("input_path_label", str(path))

    _auto_save_profile(user_data)


def _handle_output_path_selected(
    sender: int, app_data: dict, user_data: UIState
) -> None:
    selection = app_data.get("file_path_name") or next(
        iter(app_data.get("selections", {}).values()), None
    )
    if selection is None:
        return

    user_data.output_path = Path(selection)

    # Sync input path with output path
    user_data.input_path = user_data.output_path

    if dpg.does_item_exist("output_path_label"):
        dpg.set_value("output_path_label", str(user_data.output_path))

    _auto_save_profile(user_data)


def _handle_package_name_change(sender: int, app_data: str, user_data: UIState) -> None:
    user_data.package_name = app_data
    # Validation logic
    if not app_data.startswith("com."):
        # We could show an error, or just let it be invalid until save?
        # User said "cannot be null and must start with com."
        # We can change text color to red if invalid?
        dpg.configure_item(sender, user_data=user_data)  # Trigger update?
        pass


def _show_profile_dialog(state: UIState, is_edit: bool = False) -> None:
    if is_edit:
        # Check if default profile
        if not state.profile_manager.current_profile_path:
            # Show warning and log it
            log_message(
                state,
                "WARNING",
                "Cannot edit Default Profile. Please create a New Profile or Open an existing one.",
            )
            if not dpg.does_item_exist("default_profile_warning"):
                with dpg.window(
                    tag="default_profile_warning",
                    label="Warning",
                    modal=True,
                    width=400,
                    height=150,
                ):
                    dpg.add_text(
                        "Cannot edit the Default Profile.\nPlease create a New Profile or Open an existing one."
                    )
                    dpg.add_button(
                        label="OK",
                        width=100,
                        callback=lambda: dpg.delete_item("default_profile_warning"),
                    )
            return
    else:
        # Creating new profile
        log_message(state, "INFO", "Opening New Profile dialog")
        # Mark that we're creating a new profile
        state.is_creating_new_profile = True

    if dpg.does_item_exist("profile_dialog"):
        dpg.delete_item("profile_dialog")

    title = "Edit Profile" if is_edit else "New Profile"

    # Pre-fill values ONLY if editing an existing profile
    if is_edit:
        profile = state.profile_manager.current_profile
        nickname = profile.nickname if profile else ""
        package_name = state.package_name
    else:
        # For new profiles, start with empty values
        nickname = ""
        package_name = ""

    with dpg.window(
        tag="profile_dialog", label=title, modal=True, width=600, height=550
    ):
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=100)
            dpg.add_table_column(init_width_or_weight=1)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=50)

            with dpg.table_row():
                dpg.add_text("Profile Name:")
                dpg.add_input_text(tag="pd_nickname", default_value=nickname or "")
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("Package Name:")
                dpg.add_input_text(tag="pd_package_name", default_value=package_name)
                dpg.add_spacer()

            dpg.add_table_row() # Empty row for spacer
            
            with dpg.table_row():
                dpg.add_text("Remote Config URLs:", color=(120, 180, 255))
                dpg.add_spacer()
                dpg.add_spacer()

            remote_configs = state.profile_manager.current_profile.remote_configs if state.profile_manager.current_profile else {
                "Development": "", "Shipping": "", "Debug": ""
            }
            
            with dpg.table_row():
                dpg.add_text("Remote Config Setup:", color=(120, 180, 255))
                dpg.add_spacer()
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("Base URL:")
                dpg.add_input_text(
                    tag="pd_base_url", 
                    default_value=state.profile_manager.current_profile.remote_config_base_url if state.profile_manager.current_profile else "",
                    hint="Leave empty to use default S3 Bucket"
                )
                dpg.add_spacer()

            for env in ["Development", "Shipping", "Debug"]:
                with dpg.table_row():
                    dpg.add_text(f"{env} Override:")
                    dpg.add_input_text(tag=f"pd_url_{env}", default_value=remote_configs.get(env, ""))
                    dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("AWS S3 Auth:", color=(120, 180, 255))
                dpg.add_spacer()
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("AWS Access Key:")
                dpg.add_input_text(tag="pd_aws_access_key", default_value=profile.aws_access_key if is_edit else "", password=True)
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("AWS Secret Key:")
                dpg.add_input_text(tag="pd_aws_secret_key", default_value=profile.aws_secret_key if is_edit else "", password=True)
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("AWS Region:")
                dpg.add_input_text(tag="pd_aws_region", default_value=profile.aws_region if is_edit else "ap-south-1")
                dpg.add_spacer()

            with dpg.table_row():
                dpg.add_text("AWS Profile:")
                dpg.add_input_text(tag="pd_aws_profile", default_value=profile.aws_profile if is_edit else "", hint="e.g. default, work")
                dpg.add_spacer()

        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Save", callback=lambda: _handle_profile_save(state, is_edit)
            )
            dpg.add_button(
                label="Cancel", callback=lambda: dpg.delete_item("profile_dialog")
            )


def _handle_profile_save(state: UIState, is_edit: bool) -> None:
    package_name = dpg.get_value("pd_package_name")
    nickname = dpg.get_value("pd_nickname")

    # Enhanced validation for package name format: com.{company}.{product}
    if not package_name:
        log_message(state, "ERROR", "Package Name cannot be empty.")
        return

    if not package_name.startswith("com."):
        log_message(
            state,
            "ERROR",
            f"Invalid Package Name: '{package_name}'. Package name must start with 'com.'",
        )
        log_message(
            state,
            "INFO",
            "Correct format: com.{{company}}.{{product}} (e.g., com.lightfury.titan)",
        )
        return

    # Check if it has at least 3 parts: com.company.product
    parts = package_name.split(".")
    if len(parts) < 3:
        log_message(
            state,
            "ERROR",
            f"Invalid Package Name: '{package_name}'. Must have format: com.{{company}}.{{product}}",
        )
        log_message(
            state,
            "INFO",
            "Correct format: com.{{company}}.{{product}} (e.g., com.lightfury.titan)",
        )
        return

    # If new, we need a path to save to.
    # For now, let's just save to a default location or ask?
    # The reference image doesn't show a path selector for the profile itself,
    # but "Profile Path" is in the main UI.
    # If "New", we probably need to ask where to save the JSON.

    # Let's close the dialog and ask for save location if it's new.
    # Or if it's edit, just save.

    dpg.delete_item("profile_dialog")

    # Update state
    state.package_name = package_name
    if dpg.does_item_exist("package_input"):
        dpg.set_value("package_input", package_name)

    # For NEW profiles, ALWAYS prompt for save location
    # For EDIT, only prompt if no path exists (shouldn't happen but safety check)
    if not is_edit or not state.profile_manager.current_profile_path:
        # This is a new profile - prompt for location
        # Store the temp values to save after path selection
        state.temp_profile_data = {
            "nickname": nickname,
            "package_name": package_name,
            "remote_config_base_url": dpg.get_value("pd_base_url"),
            "remote_configs": {env: dpg.get_value(f"pd_url_{env}") for env in ["Development", "Shipping", "Debug"]},
            "aws_access_key": dpg.get_value("pd_aws_access_key"),
            "aws_secret_key": dpg.get_value("pd_aws_secret_key"),
            "aws_region": dpg.get_value("pd_aws_region"),
            "aws_profile": dpg.get_value("pd_aws_profile"),
        }
        _save_profile_native(state, nickname)
    else:
        # Update existing profile
        profile = state.profile_manager.current_profile
        if profile:
            profile.nickname = nickname
            profile.package_name = package_name
            
            # Update remote configs
            profile.remote_config_base_url = dpg.get_value("pd_base_url")
            for env in ["Development", "Shipping", "Debug"]:
                profile.remote_configs[env] = dpg.get_value(f"pd_url_{env}")

            # Update AWS credentials
            profile.aws_access_key = dpg.get_value("pd_aws_access_key")
            profile.aws_secret_key = dpg.get_value("pd_aws_secret_key")
            profile.aws_region = dpg.get_value("pd_aws_region")
            profile.aws_profile = dpg.get_value("pd_aws_profile")
                
            state.profile_manager.save_current_profile()
            state.profile_nickname = nickname or "None"

            log_message(
                state,
                "SUCCESS",
                f"Profile '{state.profile_nickname}' saved successfully.",
            )

            # Refresh UI
            if dpg.does_item_exist("profile_nickname_input"):
                dpg.set_value("profile_nickname_input", state.profile_nickname)
            _update_profile_display_colors(state)
            pass


def _save_current_profile(state: UIState) -> None:
    if (
        state.profile_manager.current_profile
        and state.profile_manager.current_profile_path
    ):
        # Update profile from current UI state
        profile = state.profile_manager.current_profile
        profile.package_name = state.package_name

        # Update fields from UI/State
        if dpg.does_item_exist("output_file_name"):
            state.output_file_name = dpg.get_value("output_file_name")

        profile.output_file_name = state.output_file_name
        profile.input_path = str(state.input_path)
        # Save base_output_path if available to avoid saving device-specific path
        if state.base_output_path:
            profile.output_path = str(state.base_output_path)
        else:
            profile.output_path = str(state.output_path)

        if state.base_config_output_path:
            profile.config_output_path = str(state.base_config_output_path)
        else:
            profile.config_output_path = str(state.config_output_path)

        profile.use_prefix_only = state.use_prefix_only

        state.profile_manager.save_current_profile()
    else:
        # No current profile path, prompt to save as new
        log_message(state, "INFO", "Please save profile with a name first")
        _save_profile_native(state, state.profile_nickname or "profile")


def _auto_save_profile(state: UIState) -> None:
    """Automatically save specific fields to the current profile."""
    if state.profile_manager.current_profile:
        profile = state.profile_manager.current_profile

        # Update fields
        if dpg.does_item_exist("output_file_name"):
            state.output_file_name = dpg.get_value("output_file_name")

        profile.output_file_name = state.output_file_name
        profile.input_path = str(state.input_path)
        # Save base_output_path if available to avoid saving device-specific path
        if state.base_output_path:
            profile.output_path = str(state.base_output_path)
        else:
            profile.output_path = str(state.output_path)
        profile.use_prefix_only = state.use_prefix_only

        # Save bulk action states
        profile.move_logs_enabled = state.move_logs_enabled
        profile.move_csv_enabled = state.move_csv_enabled
        profile.move_memreport_enabled = state.move_memreport_enabled
        profile.generate_perf_report_enabled = state.generate_perf_report_enabled
        profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled
        profile.generate_memreport_enabled = state.generate_memreport_enabled
        
        # Save manifest URL
        if dpg.does_item_exist("remote_manifest_url_input"):
            state.remote_manifest_url = dpg.get_value("remote_manifest_url_input")
            profile.remote_manifest_url = state.remote_manifest_url

        if state.profile_manager.current_profile_path:
            state.profile_manager.save_current_profile()
        else:
            # Shadow save for default profile (allow caching for default)
            try:
                from cerebrus.core.profile import CONFIG_DIR

                shadow_path = CONFIG_DIR / "default_profile.json"
                if not CONFIG_DIR.exists():
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                profile.save(shadow_path)
                # We do NOT update current_profile_path to keep it as "Default" in UI
            except Exception as e:
                print(f"Failed to shadow save default profile: {e}")


def _update_manifest_url_state(state: UIState, value: str) -> None:
    """Update manifest URL in state and profile."""
    state.remote_manifest_url = value
    if state.profile_manager.current_profile:
        state.profile_manager.current_profile.remote_manifest_url = value
        _auto_save_profile(state)


def _save_profile_native(state: UIState, default_name: str) -> None:
    """Open native save dialog for profile."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        default_filename = f"{default_name}.json" if default_name else "profile.json"

        file_path = filedialog.asksaveasfilename(
            title="Save Profile As",
            initialfile=default_filename,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )

        root.destroy()

        if file_path:
            path = Path(file_path)
            _finalize_profile_save(state, path)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to open save dialog: {e}")


def _open_profile_native(state: UIState) -> None:
    """Open native open dialog for profile."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="Open Profile",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )

        root.destroy()

        if file_path:
            path = Path(file_path)
            _load_profile_from_path(state, path)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to open file dialog: {e}")


def _finalize_profile_save(state: UIState, path: Path) -> None:
    """Complete profile creation after path selection."""
    temp_data = getattr(state, "temp_profile_data", {})
    nickname = temp_data.get("nickname")
    package_name = temp_data.get("package_name") or state.package_name

    # Update state.output_file_name from UI if exists
    if dpg.does_item_exist("output_file_name"):
        state.output_file_name = dpg.get_value("output_file_name")

    profile = state.profile_manager.create_new_profile(
        nickname=nickname, package_name=package_name, path=path
    )
    
    # Apply additional fields if they were in temp_data
    if "remote_config_base_url" in temp_data:
        profile.remote_config_base_url = temp_data["remote_config_base_url"]
    if "remote_configs" in temp_data:
        profile.remote_configs = temp_data["remote_configs"]
    if "aws_access_key" in temp_data:
        profile.aws_access_key = temp_data["aws_access_key"]
    if "aws_secret_key" in temp_data:
        profile.aws_secret_key = temp_data["aws_secret_key"]
    if "aws_region" in temp_data:
        profile.aws_region = temp_data["aws_region"]
    if "aws_profile" in temp_data:
        profile.aws_profile = temp_data["aws_profile"]

    # Populate fields
    profile.output_file_name = state.output_file_name
    profile.input_path = str(state.input_path)
    profile.output_path = str(state.output_path)
    profile.config_output_path = str(state.config_output_path)
    profile.use_prefix_only = state.use_prefix_only

    profile.move_logs_enabled = state.move_logs_enabled
    profile.move_csv_enabled = state.move_csv_enabled
    profile.generate_perf_report_enabled = state.generate_perf_report_enabled
    profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled

    # Update remote configs from dialog if tags exist
    if dpg.does_item_exist("pd_base_url"):
        profile.remote_config_base_url = dpg.get_value("pd_base_url")

    for env in ["Development", "Shipping", "Debug"]:
        tag = f"pd_url_{env}"
        if dpg.does_item_exist(tag):
            profile.remote_configs[env] = dpg.get_value(tag)

    profile.save(path)

    log_message(state, "SUCCESS", f"New profile '{nickname}' created at {path}")

    # Update UI
    state.profile_nickname = nickname or "None"
    state.package_name = package_name
    state.profile_path = path

    if dpg.does_item_exist("profile_nickname_input"):
        dpg.set_value("profile_nickname_input", nickname or "None")
    if dpg.does_item_exist("profile_path_input"):
        dpg.set_value("profile_path_input", str(path))
    if dpg.does_item_exist("package_input"):
        dpg.set_value("package_input", package_name)

    _update_profile_display_colors(state)


def _load_profile_from_path(state: UIState, path: Path) -> None:
    try:
        from cerebrus.core.profile import Profile

        profile = Profile.load(path)

        # Validate that required fields exist
        if not hasattr(profile, "nickname") or not hasattr(profile, "package_name"):
            raise ValueError("Profile missing required fields")

        state.profile_manager.current_profile = profile
        state.profile_manager.current_profile_path = path
        state.profile_manager.set_last_used_profile_path(path)

        log_message(state, "SUCCESS", f"Profile loaded: {profile.nickname} from {path}")

        # Update UI
        state.profile_nickname = profile.nickname or "None"
        state.package_name = profile.package_name
        state.profile_path = path

        # Load persisted fields
        state.output_file_name = profile.output_file_name
        state.input_path = Path(profile.input_path) if profile.input_path else Path("")
        state.output_path = (
            Path(profile.output_path) if profile.output_path else Path("")
        )
        state.base_output_path = state.output_path  # Set base path to loaded path
        
        state.config_output_path = (
            Path(profile.config_output_path) if profile.config_output_path else Path("")
        )
        state.base_config_output_path = state.config_output_path

        state.use_prefix_only = profile.use_prefix_only

        # Load bulk action states (with defaults if missing in old profiles)
        state.move_logs_enabled = getattr(profile, "move_logs_enabled", True)
        state.move_csv_enabled = getattr(profile, "move_csv_enabled", True)
        state.move_memreport_enabled = getattr(profile, "move_memreport_enabled", True)
        state.generate_perf_report_enabled = getattr(
            profile, "generate_perf_report_enabled", True
        )
        state.generate_colored_logs_enabled = getattr(
            profile, "generate_colored_logs_enabled", True
        )
        state.generate_memreport_enabled = getattr(
            profile, "generate_memreport_enabled", False
        )

        # Update UI elements
        if dpg.does_item_exist("package_input"):
            dpg.set_value("package_input", profile.package_name)

        if dpg.does_item_exist("profile_nickname_input"):
            dpg.set_value("profile_nickname_input", profile.nickname or "None")

        if dpg.does_item_exist("profile_path_input"):
            dpg.set_value("profile_path_input", str(path))

        if dpg.does_item_exist("output_file_name"):
            dpg.set_value("output_file_name", state.output_file_name)

        if dpg.does_item_exist("input_path_label"):
            dpg.set_value("input_path_label", str(state.input_path))

        if dpg.does_item_exist("output_path_label"):
            dpg.set_value("output_path_label", str(state.output_path))

        if dpg.does_item_exist("config_output_path_label"):
            dpg.set_value("config_output_path_label", str(state.config_output_path))
        
        if dpg.does_item_exist("remote_manifest_url_input"):
            dpg.set_value("remote_manifest_url_input", profile.remote_manifest_url or state.remote_manifest_url)
        
        _render_downloaded_configs_list(state)

        if dpg.does_item_exist("use_prefix_only"):
            dpg.set_value("use_prefix_only", state.use_prefix_only)

        if dpg.does_item_exist("cb_move_logs"):
            dpg.set_value("cb_move_logs", state.move_logs_enabled)
        if dpg.does_item_exist("cb_move_csv"):
            dpg.set_value("cb_move_csv", state.move_csv_enabled)
        if dpg.does_item_exist("cb_move_mem"):
            dpg.set_value("cb_move_mem", state.move_memreport_enabled)

        # Refresh AWS S3 fields in dialog if open
        if dpg.does_item_exist("dlg_aws_access_key"):
            dpg.set_value("dlg_aws_access_key", profile.aws_access_key)
        if dpg.does_item_exist("dlg_aws_secret_key"):
            dpg.set_value("dlg_aws_secret_key", profile.aws_secret_key)
        if dpg.does_item_exist("dlg_aws_region"):
            dpg.set_value("dlg_aws_region", profile.aws_region)
        if dpg.does_item_exist("dlg_aws_profile"):
            dpg.set_value("dlg_aws_profile", profile.aws_profile)
        if dpg.does_item_exist("cb_gen_perf"):
            dpg.set_value("cb_gen_perf", state.generate_perf_report_enabled)
        if dpg.does_item_exist("cb_gen_logs"):
            dpg.set_value("cb_gen_logs", state.generate_colored_logs_enabled)
        if dpg.does_item_exist("cb_gen_mem"):
            dpg.set_value("cb_gen_mem", state.generate_memreport_enabled)

        _update_profile_display_colors(state)

    except (ValueError, KeyError, TypeError) as e:
        # Invalid profile schema
        filename = path.name if path else "Unknown"
        log_message(
            state,
            "ERROR",
            f"{filename} is not a valid Profile. Please create a new profile or open a valid existing profile.",
        )
        print(f"Error loading profile: {e}")
    except Exception as e:
        # Other errors (file not found, JSON parse error, etc.)
        filename = path.name if path else "Unknown"
        log_message(state, "ERROR", f"Failed to load {filename}: {str(e)}")
        print(f"Error loading profile: {e}")


def _update_profile_display_colors(state: UIState) -> None:
    """Update the display colors for profile labels based on whether it's default or loaded."""
    colors = get_theme_manager().get_profile_status_colors()
    profile_color = (
        colors["DEFAULT"]
        if not state.profile_manager.current_profile_path
        else colors["LOADED"]
    )

    if dpg.does_item_exist("profile_nickname_input"):
        dpg.configure_item("profile_nickname_input", color=profile_color)
    if dpg.does_item_exist("profile_path_input"):
        dpg.configure_item("profile_path_input", color=profile_color)
    if dpg.does_item_exist("package_input"):
        dpg.configure_item("package_input", color=profile_color)


def _update_profile_path_display(path: Path) -> None:
    # Deprecated/Unused for labels but kept if needed or just remove?
    # User said "Should auto adjust the size for the complete path to be visible."
    # Labels auto-adjust.
    pass


def setup_fonts() -> None:
    """Setup application fonts."""
    with dpg.font_registry():
        # Try to locate a standard Windows font
        font_path = Path("C:/Windows/Fonts/segoeui.ttf")
        if font_path.exists():
            # Use a larger font size for better readability
            default_font = dpg.add_font(str(font_path), 18)
            dpg.bind_font(default_font)
        else:
            print("Segoe UI font not found, using default.")


def _add_help_button(tooltip_key: str, state: UIState = None) -> None:
    """Add a small '?' help button with tooltip."""
    tooltip_text = TOOLTIPS.get(tooltip_key, "No help available.")

    # Dynamic tooltip update for profiling
    if state and (tooltip_key == "start_profiling" or tooltip_key == "stop_profiling"):
        package_name = state.package_name or "Unknown Package"
        tooltip_text = tooltip_text.replace("Package", f"Package ({package_name})")

    # Removed spacer to rely on natural alignment or table alignment
    button = dpg.add_button(label="?", width=20, height=20, callback=lambda: None)

    with dpg.tooltip(button):
        # Wrap text to max width for readability
        dpg.add_text(tooltip_text, wrap=500)


def _add_hyperlink(text: str, url: str, color: tuple[int, int, int] = (100, 150, 255)) -> None:
    """Add a clickable text hyperlink."""
    link = dpg.add_text(text, color=color)

    # Create a unique handler registry for this link
    with dpg.item_handler_registry() as registry:
        dpg.add_item_clicked_handler(callback=lambda: webbrowser.open(url))

    dpg.bind_item_handler_registry(link, registry)

    # Add a tooltip to show the URL
    with dpg.tooltip(link):
        dpg.add_text(url)


def _is_aws_configured(state: UIState) -> bool:
    """Check if AWS credentials or profile are configured."""
    profile = state.profile_manager.current_profile
    if not profile:
        return False
    return bool(
        (profile.aws_access_key and profile.aws_secret_key) or profile.aws_profile
    )


def _ensure_aws_configured_with_prompt(state: UIState, on_success_callback) -> None:
    """Check AWS config; if not set, prompt the user before proceeding."""
    if _is_aws_configured(state):
        on_success_callback()
    else:
        _show_aws_not_configured_modal(state, on_success_callback)


def _show_aws_not_configured_modal(state: UIState, on_success_callback) -> None:
    """Show a modal prompt when AWS is not configured."""
    if dpg.does_item_exist("aws_not_configured_modal"):
        dpg.delete_item("aws_not_configured_modal")

    def _on_configure_click():
        # Log to both UI and console for debugging
        print("[Cerebrus] Configure Now clicked in modal.")
        log_message(state, "INFO", "Switching to AWS Configuration...")
        
        # Cleanup current modal first
        if dpg.does_item_exist("aws_not_configured_modal"):
            dpg.delete_item("aws_not_configured_modal")
            
        # Launch target window
        _show_aws_config_dialog(state)

    # Center position
    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    width, height = 450, 160
    pos = [(viewport_width - width) // 2, (viewport_height - height) // 2]

    with dpg.window(
        tag="aws_not_configured_modal",
        label="AWS Configuration Required",
        modal=True,
        width=width,
        height=height,
        pos=pos,
        no_resize=True,
    ):
        dpg.add_text(
            "AWS setup is not done. Please configure it now to proceed.", wrap=430
        )
        dpg.add_spacer(height=15)

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Configure Now", 
                width=140, 
                callback=_on_configure_click
            )
            dpg.add_button(
                label="Cancel",
                width=100,
                callback=lambda: dpg.delete_item("aws_not_configured_modal"),
            )


def build_remote_config_sync(state: UIState) -> None:
    """Render the Remote Configuration Sync panel."""
    with dpg.group():
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Remote Configuration Sync", color=(120, 180, 255))
            _add_help_button("sync_remote_config")

        # Show current source
        profile = state.profile_manager.current_profile
        if profile and profile.remote_config_base_url:
            source_msg = f"Source: Custom Base URL ({profile.remote_config_base_url})"
        else:
            source_msg = "Source: Default S3 Bucket"
        dpg.add_text(source_msg, color=(150, 255, 150, 255) if "S3" in source_msg else (255, 200, 100, 255), bullet=True)

        dpg.add_spacer(height=5)

        # Added dedicated output path for config sync
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Config Output Path:")
            dpg.add_input_text(
                tag="config_output_path_label",
                default_value=str(state.config_output_path),
                width=400,
                readonly=True,
            )
            dpg.add_button(
                label="Browse",
                width=80,
                callback=lambda: _browse_folder_native(state, "config_output"),
            )
            dpg.add_button(
                label="Open",
                width=80,
                callback=lambda: _open_folder_in_explorer(state.config_output_path),
            )

        dpg.add_spacer(height=5)

        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Manifest URL:")
            dpg.add_input_text(
                tag="remote_manifest_url_input",
                default_value=profile.remote_manifest_url if profile and profile.remote_manifest_url else state.remote_manifest_url,
                width=-1,
                callback=lambda s, a: _update_manifest_url_state(state, a),
            )

        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_button(
                label="Update Manifest",
                width=140,
                callback=lambda: _ensure_aws_configured_with_prompt(
                    state, lambda: _update_manifest(state)
                ),
            )
            dpg.add_button(
                label="Download Config",
                width=140,
                callback=lambda: _ensure_aws_configured_with_prompt(
                    state, lambda: _download_configs_from_manifest(state)
                ),
            )

        dpg.add_spacer(height=5)
        
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(init_width_or_weight=1.0)
            dpg.add_table_column(init_width_or_weight=1.0)
            
            with dpg.table_row():
                # Left Column: Local Configs
                with dpg.group():
                    with dpg.group(horizontal=True, horizontal_spacing=8):
                        dpg.add_text("Local Downloaded Configs:", color=(120, 180, 255))
                        dpg.add_button(
                            label="Refresh",
                            width=100,
                            callback=lambda: _render_downloaded_configs_list(state),
                        )
                    with dpg.child_window(tag="config_files_list_container", border=True, height=250, autosize_x=True):
                        pass
                
                # Right Column: Device Configs
                with dpg.group():
                    with dpg.group(horizontal=True, horizontal_spacing=8):
                        dpg.add_text("Configs on Device (Persistent):", color=(120, 180, 255))
                        dpg.add_button(
                            label="Refresh",
                            width=100,
                            callback=lambda: _render_device_configs_list(state),
                        )
                        dpg.add_button(
                            label="Delete All",
                            width=100,
                            callback=lambda: _handle_delete_all_configs_on_device(state),
                        )
                    with dpg.child_window(tag="device_config_files_list_container", border=True, height=250, autosize_x=True):
                        pass
        
        # Initial render of the lists
        _render_downloaded_configs_list(state)
        _render_device_configs_list(state)


def _update_manifest(state: UIState) -> None:
    """Download the remote manifest JSON file."""
    # Always pull current value from UI to be safe
    url = dpg.get_value("remote_manifest_url_input") if dpg.does_item_exist("remote_manifest_url_input") else state.remote_manifest_url
    
    if not url:
        log_message(state, "ERROR", "Manifest URL is empty.")
        return

    # Save to Configs subfolder to avoid root permission issues (like C:\)
    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        try:
            configs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_message(state, "ERROR", f"Failed to create Configs directory: {e}")
            return
            
    manifest_path = configs_dir / "config_manifest.json"
    
    log_message(state, "INFO", f"Updating manifest from {url}...")

    if _smart_download(state, url, manifest_path):
        # Validate JSON
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                json.load(f)
            log_message(state, "SUCCESS", f"Manifest updated and saved to: {manifest_path}")
        except json.JSONDecodeError:
            log_message(state, "ERROR", "Downloaded manifest is not valid JSON.")
    else:
        log_message(state, "ERROR", "Failed to update manifest.")


def _download_configs_from_manifest(state: UIState) -> None:
    """Download configs based on the local manifest JSON."""
    configs_dir = state.config_output_path / "Configs"
    manifest_path = configs_dir / "config_manifest.json"
    
    if not manifest_path.exists():
        log_message(state, "ERROR", f"Manifest file not found at {manifest_path}. Please click 'Update Json' first.")
        return

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to read manifest: {e}")
        return

    if not isinstance(manifest, dict):
        log_message(state, "ERROR", "Invalid manifest format. Expected a dictionary of {EnvName: URL/URLs}.")
        return

    log_message(state, "INFO", f"Found {len(manifest)} entries in manifest. Starting download...")

    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        configs_dir.mkdir(parents=True, exist_ok=True)

    from urllib.parse import urlparse

    for env_name, value in manifest.items():
        urls = [value] if isinstance(value, str) else value
        if not isinstance(urls, list):
            log_message(state, "WARNING", f"Invalid value for {env_name} in manifest. Expected string or list.")
            continue

        for url in urls:
            if not url:
                continue

            try:
                # Derive filename from URL
                parsed_url = urlparse(url)
                remote_filename = os.path.basename(parsed_url.path)
                if not remote_filename:
                    remote_filename = f"BackendConfig_{env_name}.ini"

                local_file = configs_dir / remote_filename
                log_message(state, "INFO", f"Downloading {remote_filename} for {env_name}...")
                
                if _smart_download(state, url, local_file):
                    log_message(state, "SUCCESS", f"Saved: {local_file.name}")
                else:
                    log_message(state, "ERROR", f"Failed to download {remote_filename}")

            except Exception as e:
                log_message(state, "ERROR", f"Error processing {url}: {e}")

    log_message(state, "INFO", "Batch download completed.")
    _render_downloaded_configs_list(state)


def _smart_download(state: UIState, url: str, dest_path: Path) -> bool:
    """Download a file from an S3 URL or standard HTTP URL, using boto3 if S3."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    
    bucket = ""
    key = ""
    
    # 1. Detect S3 URLs (s3://bucket/key or https://bucket.s3.region.amazonaws.com/key)
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    elif "s3" in parsed.netloc and ".amazonaws.com" in parsed.netloc:
        # Standard S3 virtual-host style: bucket.s3.region.amazonaws.com
        parts = parsed.netloc.split(".")
        if len(parts) >= 3:
            bucket = parts[0]
            key = parsed.path.lstrip("/")
    
    if bucket and key:
        log_message(state, "INFO", f"S3 detected. Bucket: '{bucket}', Key: '{key}'")
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
            
            profile = state.profile_manager.current_profile
            session_kwargs = {}
            region = "ap-south-1"
            
            if profile:
                if profile.aws_access_key and profile.aws_secret_key:
                    log_message(state, "INFO", "Using AWS Access Keys for authentication...")
                    session_kwargs["aws_access_key_id"] = profile.aws_access_key
                    session_kwargs["aws_secret_access_key"] = profile.aws_secret_key
                    region = profile.aws_region or region
                elif profile.aws_profile:
                    log_message(state, "INFO", f"Using AWS Profile '{profile.aws_profile}' for authentication...")
                    session_kwargs["profile_name"] = profile.aws_profile
                    region = profile.aws_region or region
                else:
                    log_message(state, "WARNING", "No Keys or Profile provided in UI. Attempting default machine auth...")

            session_kwargs["region_name"] = region
            session = boto3.Session(**session_kwargs)
            s3 = session.client('s3')
            
            # Ensure folder exists before writing
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Using get_object is often more robust than download_file for restricted buckets
            response = s3.get_object(Bucket=bucket, Key=key)
            with open(dest_path, "wb") as f:
                f.write(response["Body"].read())
                
            return True
        except NoCredentialsError:
            log_message(state, "WARNING", "No AWS credentials found (setup in Profile settings). Falling back to public URL request.")
        except Exception as e:
            log_message(state, "WARNING", f"S3 authenticated download failed: {e}")
            log_message(state, "INFO", "Falling back to public URL request...")

    # 2. Fallback to standard requests (signed requests or public)
    try:
        import requests
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        log_message(state, "ERROR", f"Download failed: {e}")
        return False


    _auto_save_profile(state)


def _update_aws_credential(state: UIState, key: str, value: str) -> None:
    """Update AWS credential in current profile and auto-save."""
    profile = state.profile_manager.current_profile
    if not profile:
        return
        
    if key == "access_key":
        profile.aws_access_key = value
    elif key == "secret_key":
        profile.aws_secret_key = value
    elif key == "region":
        profile.aws_region = value
    elif key == "profile":
        profile.aws_profile = value
        
    _auto_save_profile(state)


def _show_aws_config_dialog(state: UIState) -> None:
    """Show the AWS Configuration dialog."""
    if dpg.does_item_exist("aws_config_dialog"):
        dpg.delete_item("aws_config_dialog")
        
    profile = state.profile_manager.current_profile
    if not profile:
        log_message(state, "ERROR", "No active profile. Please load a profile first.")
        return

    # Calculate center position
    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    width, height = 500, 300
    pos = [(viewport_width - width) // 2, (viewport_height - height) // 2]

    with dpg.window(
        tag="aws_config_dialog", 
        label="AWS S3 Configuration", 
        modal=False,  # Set to false to ensure it's not blocked by other modals
        width=width, 
        height=height,
        pos=pos,
        no_resize=True
    ):
        # Force to front
        dpg.focus_item("aws_config_dialog")
        dpg.add_text("Configure AWS credentials for restricted S3 buckets.", color=(120, 180, 255))
        dpg.add_spacer(height=10)
        
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingStretchProp):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(init_width_or_weight=1)
            
            with dpg.table_row():
                dpg.add_text("Access Key:")
                dpg.add_input_text(
                    tag="dlg_aws_access_key", 
                    default_value=profile.aws_access_key,
                    password=True,
                    callback=lambda s, a: _update_aws_credential(state, "access_key", a)
                )
            
            with dpg.table_row():
                dpg.add_text("Secret Key:")
                dpg.add_input_text(
                    tag="dlg_aws_secret_key", 
                    default_value=profile.aws_secret_key,
                    password=True,
                    callback=lambda s, a: _update_aws_credential(state, "secret_key", a)
                )
            
            with dpg.table_row():
                dpg.add_text("Region:")
                dpg.add_input_text(
                    tag="dlg_aws_region", 
                    default_value=profile.aws_region or "ap-south-1",
                    callback=lambda s, a: _update_aws_credential(state, "region", a)
                )
            
            with dpg.table_row():
                dpg.add_text("AWS Profile:")
                dpg.add_input_text(
                    tag="dlg_aws_profile", 
                    default_value=profile.aws_profile,
                    hint="e.g. default",
                    callback=lambda s, a: _update_aws_credential(state, "profile", a)
                )

        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Done", width=100, callback=lambda: dpg.delete_item("aws_config_dialog"))
            dpg.add_text("(Saved automatically to profile)", color=(150, 150, 150))


def _render_downloaded_configs_list(state: UIState) -> None:
    """Render the list of downloaded .ini files with individual push buttons."""
    if not dpg.does_item_exist("config_files_list_container"):
        return
        
    dpg.delete_item("config_files_list_container", children_only=True)
    
    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        dpg.add_text("No configs downloaded yet.", parent="config_files_list_container")
        return
        
    files = sorted(list(configs_dir.glob("*.ini")), key=lambda x: x.name.lower())
    if not files:
        dpg.add_text("No .ini files found in Configs folder.", parent="config_files_list_container")
        return
        
    for file_path in files:
        with dpg.group(horizontal=True, parent="config_files_list_container"):
            dpg.add_text(file_path.name)
            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Push", 
                width=80, 

                callback=lambda s, a, u: _push_single_file_to_device(state, u),
                user_data=file_path.name
            )


def _render_device_configs_list(state: UIState) -> None:
    """Render the list of .ini files present on the device's persistent storage."""
    if not dpg.does_item_exist("device_config_files_list_container"):
        return
        
    dpg.delete_item("device_config_files_list_container", children_only=True)
    
    if not state.selected_device_serial:
        dpg.add_text("No device selected.", parent="device_config_files_list_container", color=(200, 100, 100))
        return

    if not state.package_name:
        dpg.add_text("Package Name not set.", parent="device_config_files_list_container", color=(200, 100, 100))
        return

    # Derive project name from package name
    parts = state.package_name.split(".")
    if len(parts) < 3:
        dpg.add_text("Invalid Package Name.", parent="device_config_files_list_container", color=(200, 100, 100))
        return
    project_name = parts[-1]

    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"
    
    # Show the path we are checking
    dpg.add_text(f"Checking: {device_dir}", parent="device_config_files_list_container", color=(150, 150, 150), wrap=500)
    dpg.add_separator(parent="device_config_files_list_container")

    try:
        remote_files = client.list_files(serial, device_dir)
        ini_files = sorted([f for f in remote_files if f.lower().endswith(".ini")], key=lambda x: x.lower())
        
        if not ini_files:
            dpg.add_text("No .ini files found on device.", parent="device_config_files_list_container")
            return
            
        for filename in ini_files:
            with dpg.group(horizontal=True, parent="device_config_files_list_container"):
                dpg.add_text(filename)
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Delete", 
                    width=80, 
                    callback=lambda s, a, u: _handle_delete_config_on_device(state, u),
                    user_data=filename
                )
    except Exception as e:
        dpg.add_text(f"Error: {e}", parent="device_config_files_list_container", color=(255, 100, 100))


def _handle_delete_config_on_device(state: UIState, filename: str) -> None:
    """Delete a configuration file from the device's persistent storage."""
    if not state.selected_device_serial or not state.package_name:
        return

    # Derive project name
    parts = state.package_name.split(".")
    project_name = parts[-1]
    
    client = AdbClient()
    serial = state.selected_device_serial
    device_file = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/{filename}"
    
    try:
        log_message(state, "INFO", f"Deleting {filename} from device...")
        client.remove_file(serial, device_file)
        log_message(state, "SUCCESS", f"Deleted {filename} from device.")
        _render_device_configs_list(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to delete {filename}: {e}")


def _handle_delete_all_configs_on_device(state: UIState) -> None:
    """Delete all .ini files from the device's persistent storage."""
    if not state.selected_device_serial or not state.package_name:
        log_message(state, "ERROR", "No device or package selected.")
        return

    # Derive project name
    parts = state.package_name.split(".")
    if len(parts) < 3:
        return
    project_name = parts[-1]
    
    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"
    
    try:
        log_message(state, "INFO", "Attempting to delete all config files on device...")
        # Use shell rm -f *.ini
        client.shell(serial, ["rm", "-f", f"{device_dir}*.ini"])
        log_message(state, "SUCCESS", "All .ini files deleted from device persistent storage.")
        _render_device_configs_list(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to delete all configs: {e}")


def _push_single_file_to_device(state: UIState, filename: str) -> None:
    """Push a single local configuration file to the device."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    # Derive project name from package name (com.company.project)
    parts = state.package_name.split(".")
    if len(parts) < 3:
        log_message(
            state,
            "ERROR",
            "Invalid Package Name format. Cannot derive Project Name.",
        )
        return
    project_name = parts[-1]

    # Local source file
    local_file = state.config_output_path / "Configs" / filename
    
    if not local_file.exists():
        log_message(state, "ERROR", f"File not found: {local_file}")
        return

    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"
    device_file = device_dir + filename

    try:
        log_message(state, "INFO", f"Pushing {filename} to {device_file}...")
        
        # 1. Push original file
        client.push(serial, str(local_file), device_file)
        log_message(state, "SUCCESS", f"Pushed: {filename}")

        # 2. If it's a main config file (contains 'BackendConfig'), also push as BackendConfig.ini
        if "backendconfig" in filename.lower():
            log_message(state, "INFO", f"Detected main config. Updating BackendConfig.ini...")
            target_device_file = device_dir + "BackendConfig.ini"
            try:
                client.remove_file(serial, target_device_file)
            except:
                pass
            client.push(serial, str(local_file), target_device_file)
            log_message(state, "SUCCESS", "Updated BackendConfig.ini on device.")
        
        # Refresh device list after push
        _render_device_configs_list(state)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to push {filename}: {e}")

