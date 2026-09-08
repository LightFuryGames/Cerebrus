"""Device management panel components."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from cerebrus.core.devices import DeviceInfo, collect_device_info
from cerebrus.tools.adb import DEFAULT_WIRELESS_PORT, AdbClient

from ....state import UIState
from ....themes import get_theme_manager
from ...shared import SELECTED_ROW_COLOR, _add_help_button, log_message
from ...ui_config import UIConfig


def build_device_controls(state: UIState) -> None:
    """Render device actions and the device table container."""
    tm = get_theme_manager()
    dpg.add_separator()
    with dpg.group(horizontal=True, horizontal_spacing=8):
        dpg.bind_item_theme(dpg.add_text("Device(s)"), tm.get_header_theme())
        _add_help_button("device_table")
        dpg.add_button(
            label="List Devices",
            width=UIConfig.get_instance().get_dimension("button_width_standard"),
            callback=lambda: _populate_devices(state),
        )
        _add_help_button("list_devices")
        dpg.add_button(
            label="Connect Wireless...",
            width=UIConfig.get_instance().get_dimension("button_width_standard"),
            callback=lambda: _show_connect_wireless_dialog(state),
        )
        _add_help_button("connect_wireless")
        dpg.add_button(
            label="Enable Wireless on Selected",
            width=UIConfig.get_instance().get_dimension("button_width_standard"),
            callback=lambda: _handle_enable_wireless(state),
        )
        _add_help_button("enable_wireless")
    # Use autosize_x=False and width=0 to ensure it fills available space but respects window bounds
    settings = UIConfig.get_instance().get_component_settings(
        "device_table_container", {"tag": "device_table_container"}
    )
    settings["autosize_x"] = False
    settings["width"] = 0
    # JSON overrides might miss the tag, so we force it to ensure refreshing works
    settings["tag"] = "device_table_container"
    with dpg.child_window(**settings):
        _render_device_table(state)


def _populate_devices(state: UIState) -> None:
    log_message(state, "DEBUG", "_populate_devices called")
    package_value = (
        dpg.get_value("package_input") if dpg.does_item_exist("package_input") else ""
    )
    state.package_name = package_value or ""
    log_message(state, "DEBUG", f"Package Name: {state.package_name}")

    try:
        state.devices = collect_device_info(state.package_name)
        log_message(state, "DEBUG", f"Devices found: {len(state.devices)}")
        for d in state.devices:
            log_message(state, "DEBUG", f"Device: {d.serial} - {d.model}")
    except Exception as e:
        log_message(state, "ERROR", f"collect_device_info failed: {e}")
        import traceback

        traceback.print_exc()

    if not state.devices:
        _show_device_troubleshooting_dialog(state)

    _refresh_device_table(state)


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
        policy=UIConfig.get_instance().get_table_policy("policy_stretch"),
        borders_outerH=True,
        borders_outerV=True,
        borders_innerH=True,
        borders_innerV=True,
    ):
        dpg.add_table_column(
            label="Profile", width_stretch=True, init_width_or_weight=0.06
        )
        dpg.add_table_column(
            label="Make", width_stretch=True, init_width_or_weight=0.12
        )
        dpg.add_table_column(
            label="Model", width_stretch=True, init_width_or_weight=0.22
        )
        dpg.add_table_column(
            label="Serial", width_stretch=True, init_width_or_weight=0.18
        )
        dpg.add_table_column(
            label="Android Ver.", width_stretch=True, init_width_or_weight=0.08
        )
        dpg.add_table_column(
            label="SDK level", width_stretch=True, init_width_or_weight=0.08
        )
        dpg.add_table_column(
            label="Connection", width_stretch=True, init_width_or_weight=0.10
        )
        dpg.add_table_column(
            label="Package Found", width_stretch=True, init_width_or_weight=0.15
        )
        dpg.add_table_column(
            label="App Status", width_stretch=True, init_width_or_weight=0.10
        )

        state.device_cell_tags = []

        if not state.devices:
            with dpg.table_row():
                for message in [
                    "-", "-", "-", "No devices listed", "-", "-", "-", "-", "-"
                ]:
                    dpg.add_text(message)
        else:
            for row_index, device in enumerate(state.devices):
                _render_device_row(row_index, device, state)

            # Restore the previous selection highlight only after every
            # row has actually been added to the table - doing this
            # mid-loop (from inside _render_device_row) would try to
            # highlight/unhighlight rows that don't exist yet whenever
            # there's more than one device, since DPG can't reference a
            # table row before it's been committed.
            if state.selected_device_serial:
                for row_index, device in enumerate(state.devices):
                    if device.serial == state.selected_device_serial:
                        _select_device_row(row_index, state)
                        break


def _render_device_row(row_index: int, device: DeviceInfo, state: UIState) -> None:
    tm = get_theme_manager()
    with dpg.table_row():
        dpg.add_checkbox(
            tag=f"device_profile_cb_{row_index}",
            default_value=device.serial in state.profiling_device_serials,
            callback=_handle_profile_checkbox_toggle,
            user_data=(state, device.serial),
            enabled=device.package_found,
        )

        values = [
            device.make,
            device.model,
            device.serial,
            device.android_version,
            device.sdk_level,
            device.connection_type,
            "True" if device.package_found else "False",
            "Running" if device.is_running else "Stopped",
        ]

        row_tags: list[str] = []
        for column_index, value in enumerate(values):
            cell_tag = f"device_cell_{row_index}_{column_index}"
            # Color code specific columns
            if column_index == len(values) - 3:  # Connection column
                status = "SUCCESS" if device.connection_type == "Wireless" else "DEFAULT"
                dpg.bind_item_theme(
                    dpg.add_text(value, tag=cell_tag), tm.get_log_theme(status)
                )
            elif column_index == len(values) - 2:  # Package Found column
                status = "SUCCESS" if device.package_found else "ERROR"
                dpg.bind_item_theme(
                    dpg.add_text(value, tag=cell_tag), tm.get_log_theme(status)
                )
            elif column_index == len(values) - 1:  # App Status column
                status = "SUCCESS" if device.is_running else "DEFAULT"
                dpg.bind_item_theme(
                    dpg.add_text(value, tag=cell_tag), tm.get_log_theme(status)
                )
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

        # We need a way to trigger auto-save or profile updates from here
        # For now, let's just accept state changes are transient until next manual save
        # or rely on other triggers. Or assume _auto_save_profile is imported if needed.
        # But _auto_save_profile is in dialogs technically or app logic.
        # Let's import it if we extract it, but circular imports are tricky.
        # Better to keep state logic pure or use events.
        # For this refactor, I will omit _auto_save_profile here to avoid circular dep for now
        # unless moved to shared.


def _handle_profile_checkbox_toggle(
    sender: int, app_data: bool, user_data: tuple[UIState, str]
) -> None:
    """Toggle a device's membership in the simultaneous-profiling set.

    Independent of `selected_device_serial` (the single-device highlight
    used for output-path/file-name auto-fill) - a device can be checked
    for parallel profiling without being the "selected" row, and vice
    versa.
    """
    state, serial = user_data
    if app_data:
        state.profiling_device_serials.add(serial)
    else:
        state.profiling_device_serials.discard(serial)


def _select_device_row(row_index: int, state: UIState) -> None:
    # Only unhighlight rows that actually exist in the table right now -
    # `state.devices`/`state.device_cell_tags` can briefly disagree with
    # what DPG has actually committed (e.g. mid-render), so cap the loop
    # to what's been built rather than the eventual final count.
    built_row_count = len(state.device_cell_tags)
    for index in range(built_row_count):
        try:
            dpg.unhighlight_table_row("device_table", index)
        except Exception:
            # Row not yet present in the underlying table - safe to skip.
            # (Defense in depth: the call site now only invokes this after
            # the full table is built, but this keeps the function itself
            # safe to call from anywhere.)
            continue

    dpg.highlight_table_row("device_table", row_index, SELECTED_ROW_COLOR)

    for cell_tags in state.device_cell_tags:
        for col_idx, tag in enumerate(cell_tags):
            # Skip the last three columns (Connection, Package Found, App
            # Status) as they're text widgets, not selectable.
            if col_idx < len(cell_tags) - 3 and dpg.does_item_exist(tag):
                dpg.set_value(tag, False)

    if 0 <= row_index < len(state.device_cell_tags):
        for col_idx, tag in enumerate(state.device_cell_tags[row_index]):
            # Skip the last three columns (Connection, Package Found, App
            # Status) as they're text widgets, not selectable.
            if col_idx < len(
                state.device_cell_tags[row_index]
            ) - 3 and dpg.does_item_exist(tag):
                dpg.set_value(tag, True)


def _show_connect_wireless_dialog(state: UIState) -> None:
    """Show a dialog to connect to a device already in TCP/IP mode."""
    tm = get_theme_manager()
    if dpg.does_item_exist("connect_wireless_dialog"):
        dpg.delete_item("connect_wireless_dialog")

    viewport_width = dpg.get_viewport_width()
    viewport_height = dpg.get_viewport_height()
    width = 420
    height = 220
    pos_x = (viewport_width - width) // 2
    pos_y = (viewport_height - height) // 2

    with dpg.window(
        tag="connect_wireless_dialog",
        label="Connect Wireless Device",
        modal=True,
        width=width,
        height=height,
        pos=(pos_x, pos_y),
        no_resize=True,
    ):
        dpg.add_text(
            "Enter the IP address of a device already in TCP/IP debugging"
            " mode (Settings > Developer options > Wireless debugging).",
            wrap=380,
        )
        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("standard"))

        with dpg.group(horizontal=True):
            dpg.add_text("IP Address:")
            dpg.add_input_text(tag="wireless_ip_input", width=180, hint="192.168.1.42")

        with dpg.group(horizontal=True):
            dpg.add_text("Port:")
            dpg.add_input_text(
                tag="wireless_port_input",
                width=80,
                default_value=str(DEFAULT_WIRELESS_PORT),
            )

        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("standard"))
        dpg.add_text("", tag="wireless_connect_status")

        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("standard"))
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Connect",
                width=UIConfig.get_instance().get_dimension("button_width_small"),
                callback=lambda: _handle_connect_wireless(state),
            )
            dpg.add_button(
                label="Cancel",
                width=UIConfig.get_instance().get_dimension("button_width_small"),
                callback=lambda: dpg.delete_item("connect_wireless_dialog"),
            )


def _handle_connect_wireless(state: UIState) -> None:
    ip_address = dpg.get_value("wireless_ip_input").strip()
    port_text = dpg.get_value("wireless_port_input").strip()

    if not ip_address:
        dpg.set_value("wireless_connect_status", "Please enter an IP address.")
        return

    try:
        port = int(port_text) if port_text else DEFAULT_WIRELESS_PORT
    except ValueError:
        dpg.set_value("wireless_connect_status", "Port must be a number.")
        return

    dpg.set_value("wireless_connect_status", f"Connecting to {ip_address}:{port}...")

    client = AdbClient()
    success, message = client.connect_wireless(ip_address, port)

    if success:
        log_message(state, "INFO", f"Connected to wireless device {ip_address}:{port}")
        dpg.delete_item("connect_wireless_dialog")
        _populate_devices(state)
    else:
        log_message(
            state, "ERROR", f"Failed to connect to {ip_address}:{port}: {message}"
        )
        dpg.set_value("wireless_connect_status", f"Failed: {message}")


def _handle_enable_wireless(state: UIState) -> None:
    """One-click flow: switch the currently selected USB device to
    wireless mode and connect to it, all over the existing USB cable.
    """
    serial = state.selected_device_serial
    if not serial:
        log_message(state, "WARNING", "Select a device first.")
        return

    if AdbClient.is_wireless_serial(serial):
        log_message(state, "WARNING", "Selected device is already wireless.")
        return

    log_message(state, "INFO", f"Enabling wireless debugging on {serial}...")
    client = AdbClient()
    success, message, ip_address = client.enable_wireless_debugging(serial)

    if success:
        log_message(
            state,
            "INFO",
            f"Wireless debugging enabled - connected at {ip_address}:{DEFAULT_WIRELESS_PORT}."
            " You can now disconnect the USB cable.",
        )
        _populate_devices(state)
    else:
        log_message(state, "ERROR", f"Could not enable wireless debugging: {message}")


def _show_device_troubleshooting_dialog(state: UIState) -> None:
    """Show a dialog with ADB troubleshooting steps."""
    tm = get_theme_manager()
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
        dpg.bind_item_theme(
            dpg.add_text("No active devices found."), tm.get_log_theme("ERROR")
        )
        dpg.add_text(
            "If your device is connected but not showing up, please try the following:",
            wrap=460,
        )
        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("standard"))

        with dpg.group(horizontal=True):
            dpg.add_text("1.")
            dpg.add_text("Open Command Prompt (cmd.exe) or PowerShell.")

        with dpg.group(horizontal=True):
            dpg.add_text("2.")
            dpg.add_text("Run the command:")
            dpg.bind_item_theme(dpg.add_text("adb devices"), tm.get_log_theme("INFO"))

        with dpg.group(horizontal=True):
            dpg.add_text("3.")
            dpg.add_text("Check your phone for a USB Debugging permission popup.")

        with dpg.group(horizontal=True):
            dpg.add_text("  ")
            dpg.bind_item_theme(
                dpg.add_text("Select 'Always allow' and click Allow."),
                tm.get_log_theme("WARNING"),
            )

        with dpg.group(horizontal=True):
            dpg.add_text("4.")
            dpg.add_text("Restart Cerebrus or click 'List Devices' again.")

        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("large"))
        dpg.add_separator()
        dpg.add_spacer(height=UIConfig.get_instance().get_spacer("standard"))

        with dpg.group(horizontal=True):
            dpg.add_spacer(width=380)
            dpg.add_button(
                label="OK",
                width=UIConfig.get_instance().get_dimension("button_width_small"),
                callback=lambda: dpg.delete_item("adb_troubleshoot_dialog"),
            )
