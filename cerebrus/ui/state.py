"""State containers for the Cerebrus DearPyGui UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

from cerebrus.core.devices import DeviceInfo
from cerebrus.core.profile import ProfileManager
from cerebrus.tools.screenshot_capture import ScreenshotSampler
from cerebrus.tools.thermal_capture import BatteryThermalSampler


@dataclass
class UIState:
    package_name: str = ""
    profile_nickname: str = "Nickname"
    profile_path: Path = Path("/complete/path/to/profile")
    devices: List[DeviceInfo] = field(default_factory=list)
    selected_device_serial: str | None = None
    # Serials checked for simultaneous profiling via the "Profile" column in
    # the device table. Independent of `selected_device_serial`, which still
    # drives the single-device output-path/file-name auto-fill behavior.
    profiling_device_serials: Set[str] = field(default_factory=set)
    # Cached daemon reachability per serial, populated by "Check Daemons".
    # None = not checked yet, True/False = last known result.
    daemon_status: Dict[str, bool | None] = field(default_factory=dict)
    daemon_port: int = 8765
    copy_directory: Path = Path("/path/to/copy")
    date_string: str = "2024-01-01"
    device_cell_tags: list[list[str]] = field(default_factory=list)
    output_file_name: str = ""
    use_prefix_only: bool = False
    input_path: Path = Path("C:/")
    output_path: Path = Path("C:/")
    config_output_path: Path = Path("C:/")
    logs: list[tuple[str, str, str]] = field(default_factory=list)
    log_filter: str = ""
    log_selection_mode: bool = False
    profile_manager: ProfileManager = field(default_factory=ProfileManager)
    base_output_path: Path | None = (
        None  # Store the original path without device appended
    )
    base_config_output_path: Path | None = None

    # Bulk Action States
    move_logs_enabled: bool = True
    move_csv_enabled: bool = True
    generate_perf_report_enabled: bool = True
    generate_colored_logs_enabled: bool = True
    move_memreport_enabled: bool = True
    generate_memreport_enabled: bool = True
    generate_thermal_report_enabled: bool = True
    remote_config_custom_name: str = ""
    remote_manifest_url: str = (
        "https://titan-cerebrus-configurations.s3.ap-south-1.amazonaws.com/config_manifest.json"
    )

    # Battery thermal capture - runs alongside CsvProfile Start/Stop.
    # Keyed by device serial so multiple devices can sample in parallel.
    thermal_samplers: Dict[str, BatteryThermalSampler] = field(default_factory=dict)
    capture_battery_thermal: bool = True

    # Low-resolution screenshot capture - runs alongside CsvProfile
    # Start/Stop, keyed by device serial like the thermal samplers.
    screenshot_samplers: Dict[str, ScreenshotSampler] = field(default_factory=dict)
    capture_screenshots: bool = True

    # Port the Termux-hosted daemon listens on (raw TCP, separate from
    # adb). Configurable since different projects/builds may use a
    # different port.
    daemon_port: int = 8022
    # Maps device serial -> dpg tag of its "Daemon" status cell, so the
    # background daemon-check thread can update the right cell directly
    # by serial, without depending on row index (which can shift when
    # the table is re-rendered).
    daemon_status_cell_tags: Dict[str, str] = field(default_factory=dict)
