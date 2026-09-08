"""Profiling and memory report panel components."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from cerebrus.core.devices import DeviceInfo
from cerebrus.tools.adb import AdbClient  # Assuming this exists based on context
from cerebrus.tools.screenshot_capture import ScreenshotSampler
from cerebrus.tools.thermal_capture import BatteryThermalSampler

from ....state import UIState
from ....themes import get_theme_manager
from ...dialogs.files.compare_dialog import _show_ab_compare_dialog
from ...dialogs.files.file_dialog import _browse_folder_native
from ...file_manager import (
    _get_unique_output_path,
    _handle_bulk_action_toggle,
    _handle_generate_actions,
    _handle_output_file_name_change,
    _handle_use_prefix_toggle,
    _handle_view_html_logs,
    _open_folder_in_explorer,
)
from ...shared import (
    _add_help_button,
    device_label as _device_label,
    device_output_subfolder_name as _device_output_subfolder_name,
    log_message,
    resolve_profiling_targets as _resolve_profiling_targets,
)
from ...ui_config import UIConfig
from ..device.device_panel import _populate_devices


def _build_profiling_tab(state: UIState) -> None:
    """Profiling tab content including remote profiling and file actions."""
    tm = get_theme_manager()
    header_color = tm.get_header_color()
    config = UIConfig.get_instance()

    with dpg.child_window(**config.get_component_settings("profiling_main_child")):
        # --- Section 1: Remote Execution & Commands (Streamlined Row) ---
        with dpg.group(horizontal=True, horizontal_spacing=12):
            dpg.bind_item_theme(
                dpg.add_text("Remote Execution:"), tm.get_header_theme()
            )
            with dpg.group(horizontal=True, horizontal_spacing=2):
                dpg.add_button(
                    label="Launch",
                    width=config.get_dimension("button_width_small"),
                    callback=lambda: _handle_launch_package(state),
                )
                _add_help_button("launch_package")

                dpg.add_button(
                    label="Minimize",
                    width=config.get_dimension("button_width_small"),
                    callback=lambda: _handle_minimize_app(state),
                )
                _add_help_button("minimize_app")

                dpg.add_button(
                    label="Kill App",
                    width=config.get_dimension("button_width_standard"),
                    callback=lambda: _handle_force_stop_package(state),
                )
                _add_help_button("kill_app")

                dpg.add_button(
                    label="Clear App Data",
                    width=config.get_dimension("button_width_standard"),
                    callback=lambda: _handle_clear_app_data(state),
                )
                _add_help_button("clear_app_data")

            dpg.add_spacer(width=config.get_spacer("section_gap"))
            # Vertical separator
            dpg.bind_item_theme(dpg.add_text("|"), tm.get_subheader_theme())
            dpg.add_spacer(width=config.get_spacer("section_gap"))

            dpg.bind_item_theme(
                dpg.add_text("Console Command:"), tm.get_subheader_theme()
            )
            with dpg.group(horizontal=True, horizontal_spacing=2):
                dpg.add_input_text(
                    tag="custom_command_input",
                    hint="(e.g. stat unit)",
                    width=config.get_dimension("input_width_wide"),
                    on_enter=True,
                    callback=lambda: _handle_custom_command(state),
                )
                dpg.add_button(
                    label="Send",
                    width=config.get_dimension("button_width_small"),
                    callback=lambda: _handle_custom_command(state),
                )
                _add_help_button("custom_command")

        dpg.add_spacer(height=config.get_spacer("half"))
        dpg.add_separator()
        dpg.add_spacer(height=config.get_spacer("half"))

        # --- Section 2: Profiling & Memory (Parallel Row) ---
        with dpg.group(horizontal=True, horizontal_spacing=12):
            # Remote Profiling Group
            with dpg.group(horizontal=True, horizontal_spacing=8):
                dpg.bind_item_theme(
                    dpg.add_text("Remote Profiling:"), tm.get_header_theme()
                )
                with dpg.group(horizontal=True, horizontal_spacing=2):
                    dpg.add_button(
                        label="Start Profiling",
                        width=config.get_dimension("button_width_standard"),
                        callback=lambda: _handle_start_profiling(state),
                    )
                    _add_help_button("start_profiling")
                    dpg.add_button(
                        label="Stop Profiling",
                        width=config.get_dimension("button_width_standard"),
                        callback=lambda: _handle_stop_profiling(state),
                    )
                    _add_help_button("stop_profiling")
                    dpg.add_checkbox(
                        tag="capture_battery_thermal",
                        label="Capture Battery Thermal",
                        default_value=state.capture_battery_thermal,
                        callback=lambda s, a: setattr(state, "capture_battery_thermal", a),
                    )
                    _add_help_button("capture_battery_thermal")
                    dpg.add_checkbox(
                        tag="capture_screenshots",
                        label="Capture Screenshots (Low-Res)",
                        default_value=state.capture_screenshots,
                        callback=lambda s, a: setattr(state, "capture_screenshots", a),
                    )
                    _add_help_button("capture_screenshots")

            dpg.add_spacer(width=15)
            # Use theme binding for separator
            dpg.bind_item_theme(dpg.add_text("|"), tm.get_subheader_theme())
            dpg.add_spacer(width=15)

            # Frame Memory Group
            with dpg.group(horizontal=True, horizontal_spacing=8):
                dpg.bind_item_theme(
                    dpg.add_text("Memory Profiling:"), tm.get_header_theme()
                )
                with dpg.group(horizontal=True, horizontal_spacing=2):
                    dpg.add_button(
                        label="Memreport",
                        width=config.get_dimension("button_width_standard"),
                        callback=lambda: _handle_memreport(state),
                    )
                    _add_help_button("memreport")
                    dpg.add_button(
                        label="Memreport Full",
                        width=config.get_dimension("button_width_standard"),
                        callback=lambda: _handle_memreport_full(state),
                    )
                    _add_help_button("memreport_full")

        dpg.add_spacer(height=config.get_spacer("half"))
        dpg.add_separator()
        dpg.add_spacer(height=config.get_spacer("half"))

        # --- Section 3: Data and Perf Report (Restored Legacy Alignment) ---
        dpg.bind_item_theme(dpg.add_text("Data and Perf Report"), tm.get_header_theme())
        with dpg.table(
            header_row=False, policy=config.get_table_policy("policy_stretch")
        ):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=160)
            dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=260)
            dpg.add_table_column(
                width_fixed=True, init_width_or_weight=10
            )  # Minimal padding col

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
                        label="Use Prefix Only",
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
                with dpg.group(horizontal=True, horizontal_spacing=8):
                    dpg.add_button(
                        label="Browse",
                        width=config.get_dimension("button_width_small"),
                        callback=lambda: _browse_folder_native(state, "output"),
                    )
                    dpg.add_button(
                        label="Open Folder",
                        width=config.get_dimension("button_width_standard"),
                        callback=lambda: _open_folder_in_explorer(state.output_path),
                    )
                dpg.add_spacer()

        with dpg.group(horizontal=True, horizontal_spacing=12):
            with dpg.child_window(
                **config.get_component_settings("bulk_actions_left_child")
            ):
                dpg.bind_item_theme(
                    dpg.add_text("Bulk Actions From Selected Phone to PC"),
                    tm.get_subheader_theme(),
                )
                with dpg.table(
                    header_row=False, policy=config.get_table_policy("policy_fixed")
                ):
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

            with dpg.child_window(
                **config.get_component_settings("bulk_actions_right_child")
            ):
                dpg.bind_item_theme(
                    dpg.add_text("Bulk Actions From PC to PC"), tm.get_subheader_theme()
                )
                with dpg.table(
                    header_row=False, policy=config.get_table_policy("policy_fixed")
                ):
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
                        dpg.add_checkbox(
                            tag="cb_gen_thermal",
                            label="Generate Battery Thermal Report Only",
                            default_value=state.generate_thermal_report_enabled,
                            callback=_handle_bulk_action_toggle,
                            user_data=(state, "generate_thermal_report_enabled"),
                        )
                        _add_help_button("generate_thermal_report")

                    with dpg.table_row():
                        dpg.add_button(
                            label="Generate",
                            width=300,
                            callback=lambda: _handle_generate_actions(state),
                        )
                        _add_help_button("generate_actions")

                    with dpg.table_row():
                        dpg.add_button(
                            label="View HTML Files",
                            width=300,
                            callback=lambda: _handle_view_html_logs(state),
                        )
                        _add_help_button("view_html_logs")

                    with dpg.table_row():
                        dpg.add_button(
                            label="Generate A/B Compare Report (WIP)",
                            width=300,
                            callback=lambda: _show_ab_compare_dialog(state),
                        )
                        _add_help_button("generate_ab_compare")


def _handle_launch_package(state: UIState) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()

    # Check if installed
    if not client.is_package_installed(
        state.selected_device_serial, state.package_name
    ):
        log_message(
            state, "ERROR", f"Package {state.package_name} not found on device."
        )
        return

    try:
        log_message(state, "INFO", f"Launching {state.package_name}...")
        client.launch_package(state.selected_device_serial, state.package_name)
        log_message(state, "SUCCESS", f"Sent launch command for {state.package_name}")
        # Refresh device table to show Running status
        _populate_devices(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to launch package: {e}")


def _handle_force_stop_package(state: UIState) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()
    try:
        log_message(state, "INFO", f"Killing {state.package_name}...")
        client.force_stop_package(state.selected_device_serial, state.package_name)
        # Clear from Recents/Overview screen
        client.remove_task_from_recents(
            state.selected_device_serial, state.package_name
        )
        log_message(
            state,
            "SUCCESS",
            f"Killed processes and cleared {state.package_name} from recents",
        )
        # Refresh device table to show Stopped status
        _populate_devices(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to kill package: {e}")


def _handle_minimize_app(state: UIState) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    client = AdbClient()
    try:
        log_message(state, "INFO", "Minimizing application...")
        client.minimize_package(state.selected_device_serial)
        log_message(state, "SUCCESS", "Application minimized (Home pressed)")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to minimize app: {e}")


def _handle_clear_app_data(state: UIState) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()
    try:
        log_message(state, "INFO", f"Clearing app data for {state.package_name}...")
        client.clear_package_data(state.selected_device_serial, state.package_name)
        # Also clear from recents if it was there
        client.remove_task_from_recents(
            state.selected_device_serial, state.package_name
        )
        log_message(
            state,
            "SUCCESS",
            f"Cleared app data and removed {state.package_name} from recents",
        )
        # Refresh device status
        _populate_devices(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to clear app data: {e}")


def _handle_custom_command(state: UIState) -> None:
    command = dpg.get_value("custom_command_input")
    if not command:
        return

    _send_console_command_wrapper(state, command)


def _handle_start_profiling(state: UIState) -> None:
    targets = _resolve_profiling_targets(state)
    if not targets:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()
    started_count = 0
    multi_device = len(targets) > 1

    for device in targets:
        label = _device_label(device) if multi_device else ""

        if not client.is_package_running(device.serial, state.package_name):
            log_message(
                state,
                "ERROR",
                f"Package {state.package_name} is not running on {label or 'the device'}. "
                "Please launch the application before starting profiling.",
            )
            continue

        try:
            client.send_console_command(device.serial, "CsvProfile Start")
            log_message(
                state, "SUCCESS", f"Sent start profiling command{f' to {label}' if label else ''}."
            )
        except Exception as e:
            log_message(
                state,
                "ERROR",
                f"Failed to send command{f' to {label}' if label else ''}: {e}",
            )
            continue

        started_count += 1

        if state.capture_battery_thermal:
            _start_thermal_capture_for_device(state, client, device, multi_device)

        if state.capture_screenshots:
            _start_screenshot_capture_for_device(state, client, device, multi_device)

    if multi_device:
        log_message(
            state, "INFO", f"Started profiling on {started_count}/{len(targets)} device(s)."
        )


def _start_thermal_capture_for_device(
    state: UIState, client: AdbClient, device: DeviceInfo, multi_device: bool
) -> None:
    """Begin polling battery temperature for one device alongside the CSV
    profiling capture that was just started for it. Each device gets its
    own sampler/thread so multiple devices can be captured in parallel.
    """
    existing = state.thermal_samplers.get(device.serial)
    if existing is not None and existing.is_running:
        log_message(
            state, "WARNING", f"Battery thermal capture already running for {_device_label(device)}."
        )
        return

    base_name = state.output_file_name or "cerebrus_capture"
    base_path = state.base_output_path if state.base_output_path else state.output_path
    if multi_device:
        # Isolate each device's outputs so simultaneous captures never
        # collide on the same filename.
        base_path = base_path / _device_output_subfolder_name(device)

    thermal_csv_path = _get_unique_output_path(
        base_path, f"{base_name}_battery_thermal", "csv"
    )

    sampler = BatteryThermalSampler(
        adb_client=client,
        serial=device.serial,
        output_path=thermal_csv_path,
    )
    sampler.start()
    state.thermal_samplers[device.serial] = sampler
    label = f" for {_device_label(device)}" if multi_device else ""
    log_message(
        state, "INFO", f"Started battery thermal capture{label} -> {thermal_csv_path.name}"
    )


def _stop_thermal_capture_for_serial(state: UIState, serial: str, label: str = "") -> None:
    sampler = state.thermal_samplers.pop(serial, None)
    if sampler is None or not sampler.is_running:
        return

    csv_path = sampler.stop()
    suffix = f" ({label})" if label else ""
    if sampler.sample_count > 0:
        log_message(
            state,
            "SUCCESS",
            f"Battery thermal capture stopped{suffix} ({sampler.sample_count} samples) -> {csv_path.name}",
        )
    else:
        log_message(
            state,
            "WARNING",
            f"Battery thermal capture stopped{suffix} with no samples recorded."
            f"{' Last error: ' + sampler.last_error if sampler.last_error else ''}",
        )


def _start_screenshot_capture_for_device(
    state: UIState, client: AdbClient, device: DeviceInfo, multi_device: bool
) -> None:
    """Begin periodic low-resolution screenshot capture for one device
    alongside the CSV profiling capture that was just started for it.
    Lightweight visual evidence for spotting anomalies or comparing runs
    - not a video capture, so the interval is intentionally coarse.
    """
    existing = state.screenshot_samplers.get(device.serial)
    if existing is not None and existing.is_running:
        log_message(
            state, "WARNING", f"Screenshot capture already running for {_device_label(device)}."
        )
        return

    base_path = state.base_output_path if state.base_output_path else state.output_path
    if multi_device:
        base_path = base_path / _device_output_subfolder_name(device)

    screenshots_dir = base_path / "Screenshots"

    sampler = ScreenshotSampler(
        adb_client=client,
        serial=device.serial,
        output_dir=screenshots_dir,
    )
    sampler.start()
    state.screenshot_samplers[device.serial] = sampler
    label = f" for {_device_label(device)}" if multi_device else ""
    log_message(
        state, "INFO", f"Started screenshot capture{label} -> {screenshots_dir.name}/"
    )


def _stop_screenshot_capture_for_serial(state: UIState, serial: str, label: str = "") -> None:
    sampler = state.screenshot_samplers.pop(serial, None)
    if sampler is None or not sampler.is_running:
        return

    output_dir = sampler.stop()
    suffix = f" ({label})" if label else ""
    if sampler.sample_count > 0:
        log_message(
            state,
            "SUCCESS",
            f"Screenshot capture stopped{suffix} ({sampler.sample_count} screenshots) -> {output_dir.name}/",
        )
    else:
        log_message(
            state,
            "WARNING",
            f"Screenshot capture stopped{suffix} with no screenshots captured."
            f"{' Last error: ' + sampler.last_error if sampler.last_error else ''}",
        )


def _handle_stop_profiling(state: UIState) -> None:
    targets = _resolve_profiling_targets(state)
    multi_device = len(targets) > 1

    if not targets:
        log_message(state, "ERROR", "No device selected.")
        return

    client = AdbClient()
    for device in targets:
        label = _device_label(device) if multi_device else ""
        try:
            client.send_console_command(device.serial, "CsvProfile Stop")
            log_message(
                state, "SUCCESS", f"Sent stop profiling command{f' to {label}' if label else ''}."
            )
        except Exception as e:
            log_message(
                state, "ERROR", f"Failed to send stop command{f' to {label}' if label else ''}: {e}"
            )

        _stop_thermal_capture_for_serial(state, device.serial, label)
        _stop_screenshot_capture_for_serial(state, device.serial, label)

    # Safety net: stop any samplers still running for devices that aren't
    # in the current target set (e.g. checkboxes changed between Start
    # and Stop), so a capture never keeps running unattended.
    stale_thermal_serials = list(state.thermal_samplers.keys())
    for serial in stale_thermal_serials:
        _stop_thermal_capture_for_serial(state, serial)

    stale_screenshot_serials = list(state.screenshot_samplers.keys())
    for serial in stale_screenshot_serials:
        _stop_screenshot_capture_for_serial(state, serial)


def _handle_memreport(state: UIState) -> None:
    _send_console_command_wrapper(state, "memreport")


def _handle_memreport_full(state: UIState) -> None:
    _send_console_command_wrapper(state, "memreport -full")


def _send_console_command_wrapper(state: UIState, command: str) -> None:
    targets = _resolve_profiling_targets(state)
    if not targets:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    client = AdbClient()
    multi_device = len(targets) > 1

    for device in targets:
        label = _device_label(device) if multi_device else ""

        if not client.is_package_running(device.serial, state.package_name):
            log_message(
                state,
                "WARNING",
                f"Package {state.package_name} does not seem to be running{f' on {label}' if label else ''}. Command might fail.",
            )

        try:
            client.send_console_command(device.serial, command)
            log_message(
                state, "SUCCESS", f"Sent command '{command}'{f' to {label}' if label else ''}."
            )
        except Exception as e:
            log_message(
                state, "ERROR", f"Failed to send command{f' to {label}' if label else ''}: {e}"
            )

