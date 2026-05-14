from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any

from cerebrus.plugins.analytics.core.normalizer import timestamp_from_profile_filename


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _stddev(values: list[float]) -> float:
    if not values:
        return 0.0
    avg = _mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


class PerformanceCSVReportParser:
    """Parse Unreal CSV profiler captures into flat summary values."""

    def __init__(self, csv_path: str | Path, csv_text: str | None = None):
        self.csv_path = Path(csv_path)
        if csv_text is None:
            csv_text = self.csv_path.read_text(encoding="utf-8-sig", errors="ignore")
        self.lines = csv_text.splitlines()
        self.metadata = self._extract_metadata()
        self.data = self._load_csv_data()

    def _extract_metadata(self) -> dict[str, str]:
        metadata: dict[str, str] = {}
        if not self.lines or "[HasHeaderRowAtEnd]" not in self.lines[-1]:
            return metadata

        metadata["HasHeaderRowAtEnd"] = "1"
        friendly_keys = {
            "buildversion": "Build Version",
            "platform": "platform",
            "deviceprofile": "DeviceProfile",
            "os": "OS",
            "cpu": "CPU/Device",
            "captureduration": "Capture Duration",
            "commandline": "Command Line",
            "targetframerate": "Target Framerate",
        }

        footer = self.lines[-1].strip()
        for match in re.finditer(r"\[([^\]]+)\],(.*?)(?=,\[[^\]]+\]|$)", footer):
            key, value = match.groups()
            metadata[friendly_keys.get(key, key)] = value
        return metadata

    def _load_csv_data(self) -> dict[str, list[float]]:
        csv_lines = self.lines
        if csv_lines and "[HasHeaderRowAtEnd]" in csv_lines[-1]:
            csv_lines = csv_lines[:-1]
        if csv_lines and "EVENTS" in csv_lines[-1]:
            csv_lines = csv_lines[:-1]

        data: dict[str, list[float]] = {}
        for row in csv.DictReader(csv_lines):
            for key, value in row.items():
                if not key or value in (None, ""):
                    continue
                try:
                    data.setdefault(key, []).append(float(value))
                except ValueError:
                    continue
        return data

    def parse(self) -> dict[str, Any]:
        values: dict[str, Any] = {"device_id": self.csv_path.parent.name}
        timestamp = timestamp_from_profile_filename(self.csv_path)
        if timestamp:
            values["Profiling Timestamp"] = timestamp
        values.update(self.metadata)

        frame_times = self.data.get("FrameTime", [])
        if not frame_times:
            return values

        target_fps = 60.0
        try:
            target_fps = float(self.metadata.get("Target Framerate", target_fps))
        except ValueError:
            pass
        target_ms = 1000.0 / target_fps

        total_frames = len(frame_times)
        duration_s = sum(frame_times) / 1000.0
        avg_frame_time = _mean(frame_times)
        fps_values = [1000.0 / value for value in frame_times if value > 0]

        values["Frame count"] = f"{total_frames} (0 excluded)"
        values["Total Time (s)"] = round(duration_s, 2)
        values["Frametime Avg"] = round(avg_frame_time, 2)
        values["FPS Avg"] = round(1000.0 / avg_frame_time, 2)
        values["Hitches/Min"] = round(
            sum(1 for value in frame_times if value > 60.0) / (duration_s / 60.0),
            2,
        )
        hitch_time = sum(value for value in frame_times if value > 60.0)
        values["HitchTimePercent"] = round(
            (hitch_time / (duration_s * 1000.0)) * 100.0, 2
        )
        values[f"MVP{int(target_fps)}"] = round(
            (sum(1 for value in frame_times if value <= target_ms) / total_frames)
            * 100.0,
            2,
        )
        values["Standard Deviation (SD)"] = round(_stddev(fps_values), 2)
        values["Interquartile Range (IQR)"] = round(
            _percentile(fps_values, 75) - _percentile(fps_values, 25),
            2,
        )

        percentile_labels = {
            1: "1st Percentile",
            5: "5th Percentile",
            50: "50th Percentile",
            90: "90th Percentile",
            95: "95th Percentile",
            99: "99th Percentile",
        }
        for percentile, label in percentile_labels.items():
            values[label] = round(
                _percentile(fps_values, percentile),
                1,
            )

        for thread in [
            "GameThreadTime",
            "RenderThreadTime",
            "RHIThreadTime",
            "GPUTime",
        ]:
            if thread in self.data:
                values[f"{thread} Avg"] = round(_mean(self.data[thread]), 2)

        thresholds = [60, 150, 250, 500, 750, 1000, 2000]
        for row_name in [
            "FrameTime",
            "GameThreadTime",
            "RenderThreadTime",
            "RHIThreadTime",
            "GPUTime",
        ]:
            if row_name not in self.data:
                continue
            for threshold in thresholds:
                values[f"{row_name}_>{threshold}ms"] = sum(
                    1 for value in self.data[row_name] if value > threshold
                )

        extra_metrics = {
            "MemoryFreeMB": ("MemoryFreeMB Min", min),
            "PhysicalUsedMB": ("PhysicalUsedMB Max", max),
            "RHI/DrawCalls": ("RHI/Drawcalls Avg", _mean),
            "RHI/Drawcalls": ("RHI/Drawcalls Avg", _mean),
        }
        for source_key, (target_key, func) in extra_metrics.items():
            if source_key in self.data:
                values[target_key] = round(float(func(self.data[source_key])), 2)  # type: ignore[operator]
        return values
