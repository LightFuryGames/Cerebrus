"""Build Grafana-ready one-second telemetry records from raw profile CSV data.

The normal analytics document is deliberately a small, report-level summary.
This module preserves the different concern of rendering a single capture over
time: it rolls frame rows into fixed one-second buckets without retaining every
frame in Elasticsearch.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Iterable

SESSION_SAMPLE_SCHEMA_VERSION = 1

_DIMENSION_FIELDS = (
    "device_id",
    "build_branch",
    "build_cl",
    "build_config",
    "build_project",
    "build_version",
    "device_manufacturer",
    "device_model",
    "device_gpu",
    "device_profile",
    "device_tier",
    "device_os_name",
    "device_os_version",
    "capture_target_fps",
)

_AVERAGE_COLUMNS = {
    "GameThreadTime": "metrics_game_thread_avg_ms",
    "RenderThreadTime": "metrics_render_thread_avg_ms",
    "RHIThreadTime": "metrics_rhi_thread_avg_ms",
    "GPUTime": "metrics_gpu_avg_ms",
    "AndroidCPU/CPUTemp": "metrics_cpu_temp_avg_c",
    "AndroidCPU/ThermalStress": "metrics_thermal_stress_avg",
    "AndroidCPU/CPUFreqMHzGroup0": "metrics_cpu_freq_group0_avg_mhz",
    "AndroidCPU/CPUFreqMHzGroup1": "metrics_cpu_freq_group1_avg_mhz",
    "AndroidCPU/CPUFreqPercentageGroup0": "metrics_cpu_freq_group0_avg_pct",
    "AndroidCPU/CPUFreqPercentageGroup1": "metrics_cpu_freq_group1_avg_pct",
    "AndroidMemory/Mem_RSS": "metrics_memory_rss_avg_mb",
    "AndroidMemory/Mem_TotalUsed": "metrics_memory_total_used_avg_mb",
    "AndroidMemory/Mem_Swap": "metrics_memory_swap_avg_mb",
}

_MAX_COLUMNS = {
    "FrameTime": "metrics_frametime_max_ms",
    "AndroidCPU/CPUTemp": "metrics_cpu_temp_max_c",
    "AndroidCPU/ThermalStatus": "metrics_thermal_status_max",
    "AndroidMemory/Mem_RSS": "metrics_memory_rss_max_mb",
    "AndroidMemory/Mem_TotalUsed": "metrics_memory_total_used_max_mb",
    "AndroidMemory/Mem_Swap": "metrics_memory_swap_max_mb",
}


def _finite_float(value: object) -> float | None:
    try:
        numeric = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _data_lines(raw_csv: str) -> list[str]:
    """Remove the metadata footer before passing data rows to ``DictReader``."""
    lines = raw_csv.splitlines()
    if lines and "[HasHeaderRowAtEnd]" in lines[-1]:
        return lines[:-1]
    return lines


def _sample_timestamp(capture_timestamp: object, elapsed_seconds: int) -> str:
    """Return a UTC timestamp for a bucket, retaining the capture start if valid."""
    text = str(capture_timestamp or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(seconds=elapsed_seconds)).astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _mean(values: Iterable[float]) -> float:
    values_list = list(values)
    return round(sum(values_list) / len(values_list), 3)


def build_session_samples(
    raw_csv: str,
    summary_document: dict[str, Any],
) -> list[dict[str, Any]]:
    """Roll embedded profile CSV rows into stable, one-second ES documents.

    Frame rows are assigned using their elapsed start time.  This matches how a
    timeline is read: bucket zero starts at the first valid frame.  Each record
    has a deterministic id so a repeat upload replaces that second rather than
    duplicating it.
    """
    session_id = str(summary_document.get("report_fingerprint") or "").strip()
    if not session_id:
        raise ValueError("A report_fingerprint is required to create session samples.")

    buckets: dict[int, dict[str, list[float] | set[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    elapsed_ms = 0.0
    for row in csv.DictReader(StringIO("\n".join(_data_lines(raw_csv)))):
        frame_time = _finite_float(row.get("FrameTime"))
        if frame_time is None or frame_time <= 0:
            continue

        second = int(elapsed_ms // 1000)
        bucket = buckets[second]
        frame_times = bucket["FrameTime"]
        assert isinstance(frame_times, list)
        frame_times.append(frame_time)

        event = str(row.get("EVENTS") or "").strip()
        if event:
            events = bucket.get("events")
            if events is None:
                events = set()
                bucket["events"] = events
            assert isinstance(events, set)
            events.add(event)

        for source_column in (set(_AVERAGE_COLUMNS) | set(_MAX_COLUMNS)) - {
            "FrameTime"
        }:
            value = _finite_float(row.get(source_column))
            if value is None:
                continue
            values = bucket[source_column]
            assert isinstance(values, list)
            values.append(value)
        elapsed_ms += frame_time

    dimensions = {
        field: summary_document[field]
        for field in _DIMENSION_FIELDS
        if field in summary_document
    }
    capture_start = summary_document.get("@timestamp")
    documents: list[dict[str, Any]] = []
    for second in sorted(buckets):
        bucket = buckets[second]
        frame_times = bucket["FrameTime"]
        assert isinstance(frame_times, list) and frame_times
        fps_values = [1000.0 / frame_time for frame_time in frame_times]
        document: dict[str, Any] = {
            "schema_version": SESSION_SAMPLE_SCHEMA_VERSION,
            "source_type": "profiling_session_sample",
            "source_report_type": summary_document.get("source_type", "Unknown"),
            "source_name": summary_document.get("source_name", "Unknown"),
            "report_fingerprint": session_id,
            "session_id": session_id,
            "session_sample_id": f"{session_id}:{second:06d}",
            "elapsed_seconds": second,
            "@timestamp": _sample_timestamp(capture_start, second),
            "capture_started_at": capture_start,
            "sample_frame_count": len(frame_times),
            "metrics_fps_avg": _mean(fps_values),
            "metrics_fps_min": round(min(fps_values), 3),
            "metrics_fps_max": round(max(fps_values), 3),
            "metrics_frametime_avg_ms": _mean(frame_times),
            "metrics_frametime_max_ms": round(max(frame_times), 3),
            **dimensions,
        }
        for source_column, target_field in _AVERAGE_COLUMNS.items():
            values = bucket.get(source_column, [])
            if isinstance(values, list) and values:
                document[target_field] = _mean(values)
        for source_column, target_field in _MAX_COLUMNS.items():
            values = bucket.get(source_column, [])
            if isinstance(values, list) and values:
                document[target_field] = round(max(values), 3)
        events = bucket.get("events", set())
        if isinstance(events, set) and events:
            document["event_count"] = len(events)
            document["event_names"] = sorted(events)
        else:
            document["event_count"] = 0
            document["event_names"] = []
        documents.append(document)
    return documents
