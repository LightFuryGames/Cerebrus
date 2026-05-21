"""Device management panel components."""

from __future__ import annotations

import threading
import time

import dearpygui.dearpygui as dpg

from cerebrus.core.devices import DeviceInfo, collect_device_info
from cerebrus.core.jobs import Job, get_default_scheduler
from cerebrus.tools.adb import AdbClient, AdbError

from ....state import UIState
from ....themes import get_theme_manager
from ...shared import SELECTED_ROW_COLOR, add_help_button, log_message
from ...ui_config import UIConfig

# How often the auto-detect watcher checks adb. 10 seconds is short enough
# to feel "live" when a device is plugged in but long enough to avoid log
# spam on machines with no device connected.
_AUTODETECT_INTERVAL_S: float = 10.0
# A submitted job whose timestamp is younger than this is treated as
# "still in flight" so a fast manual click does not pile a second job on
# top of the running one.
_AUTODETECT_DEBOUNCE_S: float = 1.5

_autodetect_stop: threading.Event | None = None
_autodetect_thread: threading.Thread | None = None
_last_submit_at: float = 0.0
_submit_guard = threading.Lock()


def build_device_controls(state: UIState) -> None:
    """Render device actions and the device table container."""
    tm = get_theme_manager()
    dpg.add_separator()
    with dpg.group(horizontal=True, horizontal_spacing=8):
        dpg.bind_item_theme(dpg.add_text("Device(s)"), tm.get_header_theme())
        add_help_button("device_table")
        dpg.add_button(
            label="List Devices",
            width=UIConfig.get_instance().get_dimension("button_width_standard"),
            callback=lambda: _trigger_device_detection(state, manual=True),
        )
        add_help_button("list_devices")
        dpg.add_button(
            label="Start ADB Server",
            callback=lambda: _trigger_adb_server(state, action="start"),
        )
        add_help_button("start_adb_server")
        dpg.add_button(
            label="Stop ADB Server",
            callback=lambda: _trigger_adb_server(state, action="stop"),
        )
        add_help_button("stop_adb_server")
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
    _resize_device_table_container(state)


def _populate_devices(state: UIState) -> None:
    """Backwards-compatible entry point.

    Old call sites (profiling panel, layout module) invoke this name
    directly. Route through the scheduler so they pick up the new
    async + window-suppressed behaviour without each having to import
    the Job system.
    """
    _trigger_device_detection(state, manual=True)


def _trigger_device_detection(state: UIState, *, manual: bool) -> None:
    """Submit a device-detection job to the global scheduler.

    The actual adb work runs on a worker thread so the DPG callback returns
    immediately. ``manual=True`` bypasses the debounce guard so the user's
    "List Devices" click always fires; ``manual=False`` (the auto-detect
    watcher) skips the submission when one is already in flight.
    """
    global _last_submit_at
    now = time.monotonic()
    with _submit_guard:
        if not manual and (now - _last_submit_at) < _AUTODETECT_DEBOUNCE_S:
            return
        _last_submit_at = now

    package_value = (
        dpg.get_value("package_input") if dpg.does_item_exist("package_input") else ""
    )
    state.package_name = package_value or ""
    if manual:
        log_message(state, "DEBUG", "List Devices clicked")

    def _work() -> None:
        try:
            devices = collect_device_info(state.package_name)
        except Exception as exc:  # noqa: BLE001 - all errors land in the UI log
            log_message(state, "ERROR", f"collect_device_info failed: {exc}")
            return
        prior_count = len(state.devices)
        state.devices = devices
        if manual or prior_count != len(devices):
            log_message(
                state,
                "DEBUG" if not manual else "INFO",
                f"Devices found: {len(devices)}",
            )
            for d in devices:
                log_message(state, "DEBUG", f"Device: {d.serial} - {d.model}")
        _refresh_device_table(state)
        if manual and not devices:
            _show_device_troubleshooting_dialog(state)

    name = "detect-devices (manual)" if manual else "detect-devices (auto)"
    get_default_scheduler().submit(Job(fn=_work, name=name))


def _trigger_adb_server(state: UIState, *, action: str) -> None:
    """Submit a Start/Stop ADB Server job. Manual override only — never
    auto-triggered."""

    def _work() -> None:
        client = AdbClient()
        try:
            if action == "start":
                client.start_server()
                log_message(state, "SUCCESS", "ADB server started.")
            elif action == "stop":
                client.kill_server()
                log_message(state, "SUCCESS", "ADB server stopped.")
            else:
                log_message(state, "ERROR", f"Unknown ADB server action: {action!r}")
                return
        except AdbError as exc:
            log_message(state, "ERROR", f"ADB server {action} failed: {exc}")
            return
        # Refresh the device list after the daemon state changed.
        _trigger_device_detection(state, manual=True)

    get_default_scheduler().submit(Job(fn=_work, name=f"adb-{action}-server"))


# ---------------------------------------------------------------------------
# Auto-detect watcher
# ---------------------------------------------------------------------------


def start_adb_autodetect(state: UIState) -> None:
    """Start the background watcher that periodically refreshes the device
    list.

    Idempotent — calling twice has no extra effect. The watcher submits a
    job to the global :class:`JobScheduler` every
    :data:`_AUTODETECT_INTERVAL_S` seconds, with a debounce so manual
    clicks don't double-queue.
    """
    global _autodetect_stop, _autodetect_thread
    if _autodetect_thread is not None and _autodetect_thread.is_alive():
        return
    stop_event = threading.Event()

    def _loop() -> None:
        # Initial detect runs after a short delay so the UI has time to
        # finish drawing before the first log line appears.
        if stop_event.wait(1.0):
            return
        while not stop_event.is_set():
            try:
                _trigger_device_detection(state, manual=False)
            except Exception as exc:  # noqa: BLE001
                log_message(state, "ERROR", f"adb autodetect tick failed: {exc}")
            if stop_event.wait(_AUTODETECT_INTERVAL_S):
                return

    _autodetect_stop = stop_event
    _autodetect_thread = threading.Thread(
        target=_loop, name="cerebrus-adb-autodetect", daemon=True
    )
    _autodetect_thread.start()


def stop_adb_autodetect() -> None:
    """Stop the auto-detect watcher. Idempotent."""
    global _autodetect_stop, _autodetect_thread
    if _autodetect_stop is not None:
        _autodetect_stop.set()
    if _autodetect_thread is not None:
        _autodetect_thread.join(timeout=2.0)
    _autodetect_stop = None
    _autodetect_thread = None


def _refresh_device_table(state: UIState) -> None:
    if not dpg.does_item_exist("device_table_container"):
        return

    existing_table = "device_table"
    if dpg.does_item_exist(existing_table):
        dpg.delete_item(existing_table)

    _render_device_table(state)
    _resize_device_table_container(state)


def _resize_device_table_container(state: UIState) -> None:
    """Shrink the device table container to fit the current row count.

    Empty state shows a single placeholder row; otherwise we size for the
    actual device count, clamped so a long list doesn't push the rest of
    the UI off-screen.
    """
    if not dpg.does_item_exist("device_table_container"):
        return
    row_count = max(1, len(state.devices))
    # 32px header + ~30px per row + 16px padding.
    height = 32 + 30 * min(row_count, 6) + 16
    try:
        dpg.configure_item("device_table_container", height=height)
    except Exception:
        pass


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
            label="Package Found", width_stretch=True, init_width_or_weight=0.15
        )
        dpg.add_table_column(
            label="App Status", width_stretch=True, init_width_or_weight=0.10
        )

        state.device_cell_tags = []

        if not state.devices:
            with dpg.table_row():
                for message in ["-", "-", "No devices listed", "-", "-", "-"]:
                    dpg.add_text(message)
        else:
            for row_index, device in enumerate(state.devices):
                _render_device_row(row_index, device, state)


def _render_device_row(row_index: int, device: DeviceInfo, state: UIState) -> None:
    tm = get_theme_manager()
    with dpg.table_row():
        values = [
            device.make,
            device.model,
            device.serial,
            device.android_version,
            device.sdk_level,
            "True" if device.package_found else "False",
            "Running" if device.is_running else "Stopped",
        ]

        row_tags: list[str] = []
        for column_index, value in enumerate(values):
            cell_tag = f"device_cell_{row_index}_{column_index}"
            # Color code specific columns
            if column_index == len(values) - 2:  # Package Found column
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

        # We need a way to trigger auto-save or profile updates from here
        # For now, let's just accept state changes are transient until next manual save
        # or rely on other triggers. Or assume _auto_save_profile is imported if needed.
        # But _auto_save_profile is in dialogs technically or app logic.
        # Let's import it if we extract it, but circular imports are tricky.
        # Better to keep state logic pure or use events.
        # For this refactor, I will omit _auto_save_profile here to avoid circular dep for now
        # unless moved to shared.


def _select_device_row(row_index: int, state: UIState) -> None:
    for index in range(len(state.devices)):
        dpg.unhighlight_table_row("device_table", index)

    dpg.highlight_table_row("device_table", row_index, SELECTED_ROW_COLOR)

    for cell_tags in state.device_cell_tags:
        for col_idx, tag in enumerate(cell_tags):
            # Skip the last two columns (Package Found, App Status) as they're text widgets, not selectable
            if col_idx < len(cell_tags) - 2 and dpg.does_item_exist(tag):
                dpg.set_value(tag, False)

    if 0 <= row_index < len(state.device_cell_tags):
        for col_idx, tag in enumerate(state.device_cell_tags[row_index]):
            # Skip the last two columns (Package Found, App Status) as they're text widgets, not selectable
            if col_idx < len(
                state.device_cell_tags[row_index]
            ) - 2 and dpg.does_item_exist(tag):
                dpg.set_value(tag, True)


def _show_device_troubleshooting_dialog(state: UIState) -> None:
    """Show a dialog with ADB troubleshooting steps."""
    tm = get_theme_manager()
    if dpg.does_item_exist("adb_troubleshoot_dialog"):
        dpg.delete_item("adb_troubleshoot_dialog")

    # Centre the dialog. The previous 500x320 was too short for the
    # four-step troubleshooting list — the OK button clipped behind the
    # window border on standard scaling. 560x440 fits the content with
    # breathing room and still leaves space on a 1280x720 viewport.
    viewport_width = dpg.get_viewport_width() or 1200
    viewport_height = dpg.get_viewport_height() or 800
    width = 560
    height = 440
    text_wrap = width - 40
    pos_x = max(20, (viewport_width - width) // 2)
    pos_y = max(20, (viewport_height - height) // 2)

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
            wrap=text_wrap,
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

        # Right-align the OK button by computing the spacer width from the
        # actual dialog width, so any future width tweak doesn't push the
        # button off-screen the way the hard-coded 380 did.
        button_width = UIConfig.get_instance().get_dimension("button_width_small")
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=max(0, width - button_width - 32))
            dpg.add_button(
                label="OK",
                width=button_width,
                callback=lambda: dpg.delete_item("adb_troubleshoot_dialog"),
            )
