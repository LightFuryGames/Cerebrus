"""State containers for the Cerebrus DearPyGui UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from cerebrus.core.devices import DeviceInfo
from cerebrus.core.profile import ProfileManager


@dataclass
class UIState:
    package_name: str = ""
    profile_nickname: str = "Nickname"
    profile_path: Path = Path("/complete/path/to/profile")
    devices: List[DeviceInfo] = field(default_factory=list)
    selected_device_serial: str | None = None
    copy_directory: Path = Path("/path/to/copy")
    date_string: str = "2024-01-01"
    device_cell_tags: list[list[str]] = field(default_factory=list)
    output_file_name: str = "perf_report"
    use_prefix_only: bool = False
    input_path: Path = Path("C:/")
    output_path: Path = Path("C:/")
    logs: list[tuple[str, str, str]] = field(default_factory=list)
    log_filter: str = ""
    profile_manager: ProfileManager = field(default_factory=ProfileManager)
    base_output_path: Path | None = (
        None  # Store the original path without device appended
    )

    # Bulk Action States
    move_logs_enabled: bool = True
    move_csv_enabled: bool = True
    generate_perf_report_enabled: bool = True
    generate_colored_logs_enabled: bool = True
