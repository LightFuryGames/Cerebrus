"""Composable DearPyGui building blocks."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from cerebrus._version import __version__
from cerebrus.core.devices import DeviceInfo, collect_device_info
from cerebrus.tools.adb import AdbClient, AdbError
from cerebrus.tools.log_to_html import convert_log_to_html
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager

# Log colors are now handled by ThemeManager
SELECTED_ROW_COLOR = (0, 119, 200, 153)  # Blue highlight with transparency


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
        dpg.add_text(
            "https://github.com/rahul-gupta-lightfury/Cerebrus", color=(100, 150, 255)
        )

        # Description
        dpg.add_text(
            "Python-based Windows-only toolkit with a Dear Py Gui UI for managing"
        )
        dpg.add_text("Unreal Engine Android profiling workflows.")

        # License
        with dpg.group(horizontal=True):
            dpg.add_text("Licensed under the")
            dpg.add_text("BSD 3-Clause License", color=(100, 150, 255))
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

    dpg.add_separator()
    with dpg.group(horizontal=True, horizontal_spacing=8):
        dpg.add_text("Remote Profiling", color=(120, 180, 255))
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


def build_file_actions(state: UIState) -> None:
    """Render file copy actions and reporting panels."""
    dpg.add_separator()
    with dpg.child_window(border=True, autosize_x=True, autosize_y=False, height=320):
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
    tool_path = repo_root / "Binaries" / "CsvTools" / "PerfreportTool.exe"

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

        # Get unique path to avoid overwriting existing files
        # PerfreportTool generates .html output
        output_file_path = _get_unique_output_path(output_dir, output_filename, ".html")

        # Remove extension for the -o parameter (tool adds it automatically)
        output_path_param = output_file_path.with_suffix("")

        cmd = [
            str(tool_path),
            "-csv",
            str(csv_file),
            "-reportType",
            "Default60fps",
            "-o",
            str(output_path_param),
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
                log_message(
                    state, "SUCCESS", f"Generated report: {output_file_path.name}"
                )
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

        # Update output file name to match device make and model
        new_file_name = f"{selected_device.make}_{selected_device.model}"
        state.output_file_name = new_file_name
        if dpg.does_item_exist("output_file_name"):
            dpg.set_value("output_file_name", new_file_name)
        _auto_save_profile(state)


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
            else:  # output
                state.base_output_path = selected_path
                state.output_path = selected_path

                if dpg.does_item_exist("output_path_label"):
                    dpg.set_value("output_path_label", str(state.output_path))
                log_message(
                    state, "SUCCESS", f"Output path set to: {state.output_path}"
                )
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
        tag="profile_dialog", label=title, modal=True, width=500, height=250
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
        }
        _save_profile_native(state, nickname)
    else:
        # Update existing profile
        profile = state.profile_manager.current_profile
        if profile:
            profile.nickname = nickname
            profile.package_name = package_name
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
        profile.generate_perf_report_enabled = state.generate_perf_report_enabled
        profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled

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
    # Populate fields
    profile.output_file_name = state.output_file_name
    profile.input_path = str(state.input_path)
    profile.output_path = str(state.output_path)
    profile.use_prefix_only = state.use_prefix_only

    profile.move_logs_enabled = state.move_logs_enabled
    profile.move_csv_enabled = state.move_csv_enabled
    profile.generate_perf_report_enabled = state.generate_perf_report_enabled
    profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled

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
        state.use_prefix_only = profile.use_prefix_only

        # Load bulk action states (with defaults if missing in old profiles)
        state.move_logs_enabled = getattr(profile, "move_logs_enabled", True)
        state.move_csv_enabled = getattr(profile, "move_csv_enabled", True)
        state.generate_perf_report_enabled = getattr(
            profile, "generate_perf_report_enabled", True
        )
        state.generate_colored_logs_enabled = getattr(
            profile, "generate_colored_logs_enabled", True
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

        if dpg.does_item_exist("use_prefix_only"):
            dpg.set_value("use_prefix_only", state.use_prefix_only)

        if dpg.does_item_exist("cb_move_logs"):
            dpg.set_value("cb_move_logs", state.move_logs_enabled)
        if dpg.does_item_exist("cb_move_csv"):
            dpg.set_value("cb_move_csv", state.move_csv_enabled)
        if dpg.does_item_exist("cb_gen_perf"):
            dpg.set_value("cb_gen_perf", state.generate_perf_report_enabled)
        if dpg.does_item_exist("cb_gen_logs"):
            dpg.set_value("cb_gen_logs", state.generate_colored_logs_enabled)

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
