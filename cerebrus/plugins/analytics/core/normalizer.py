from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cerebrus.plugins.analytics.core.device_profiles import (
    enrich_with_device_profile_tier,
)

TIMESTAMP_INPUT_FORMATS = (
    "%d:%m:%Y:%H:%M:%S",
    "%Y%m%d_%H%M%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
)

SCHEMA_VERSION = 2

# Sentinel values written into flat docs when an expected field is absent or
# corrupt. Goal: never emit nulls/blanks so ES mapping stays stable and Grafana
# can filter by sentinel.
DEFAULT_TIMESTAMP = "2000-01-01T00:00:00Z"
SENTINEL_STRING = "Unknown"
SENTINEL_NUMERIC = -1

# Expected fields after flattening + tier enrichment. Field -> kind.
EXPECTED_FIELDS: dict[str, str] = {
    "@timestamp": "timestamp",
    "build_config": "string",
    "build_version": "string",
    "build_cl": "numeric",
    "device_manufacturer": "string",
    "device_model": "string",
    "device_gpu": "string",
    "device_profile": "string",
    "device_tier": "string",
    "device_profile_root": "string",
    "device_profile_chain": "string",
    "capture_start_timestamp": "numeric",
    "capture_end_timestamp": "numeric",
    "capture_duration_s": "numeric",
    "capture_frame_count": "numeric",
    "capture_target_fps": "numeric",
    "metrics_fps_avg": "numeric",
    "metrics_frametime_avg_ms": "numeric",
    "metrics_game_thread_avg_ms": "numeric",
    "metrics_render_thread_avg_ms": "numeric",
    "metrics_gpu_avg_ms": "numeric",
}


RAW_TO_CANONICAL_KEYS = {
    "asan": "asan_enabled",
    "[asan]": "asan_enabled",
    "build configuration": "config",
    "build version": "build_version",
    "[buildversion]": "build_version",
    "capture duration": "duration_s",
    "[captureduration]": "duration_s",
    "command line": "command_line",
    "[commandline]": "command_line",
    "config": "config",
    "[config]": "config",
    "configuration": "config",
    "cpu/device": "cpu_device",
    "[cpu]": "cpu_device",
    "csvid": "csv_id",
    "[csvid]": "csv_id",
    "deviceprofile": "device_profile",
    "device profile": "device_profile",
    "device manufacturer": "manufacturer",
    "device model": "model",
    "device gpu": "gpu",
    "[deviceprofile]": "device_profile",
    "endtimestamp": "end_timestamp",
    "[endtimestamp]": "end_timestamp",
    "engineversion": "engine_version",
    "extradevelopmentmemorymb": "extra_development_memory_mb",
    "[extradevelopmentmemorymb]": "extra_development_memory_mb",
    "features": "features",
    "frame count": "frame_count",
    "frametime avg": "frametime_avg_ms",
    "gamethreadtime avg": "game_thread_avg_ms",
    "gputime avg": "gpu_avg_ms",
    "hasheaderrowatend": "has_header_row_at_end",
    "hitches/min": "hitches_per_min",
    "hitchtimepercent": "hitch_time_percent",
    "interquartile range (iqr)": "fps_iqr",
    "largeworldcoordinates": "large_world_coordinates",
    "[largeworldcoordinates]": "large_world_coordinates",
    "loginid": "login_id",
    "[loginid]": "login_id",
    "ltoenabled": "lto_enabled",
    "[ltoenabled]": "lto_enabled",
    "memoryfreemb min": "memory_free_min_mb",
    "mvp60": "mvp60",
    "namedevents": "named_events",
    "[namedevents]": "named_events",
    "os": "os",
    "pgoenabled": "pgo_enabled",
    "[pgoenabled]": "pgo_enabled",
    "pgoprofilingenabled": "pgo_profiling_enabled",
    "[pgoprofilingenabled]": "pgo_profiling_enabled",
    "physicalusedmb max": "physical_used_max_mb",
    "platform": "platform",
    "programsizemb": "program_size_mb",
    "[programsizemb]": "program_size_mb",
    "renderthreadtime avg": "render_thread_avg_ms",
    "rhi/drawcalls avg": "drawcalls_avg",
    "rhithreadtime avg": "rhi_thread_avg_ms",
    "scalability tier": "scalability_tier",
    "standard deviation (sd)": "fps_stddev",
    "starttimestamp": "start_timestamp",
    "[starttimestamp]": "start_timestamp",
    "target framerate": "target_fps",
    "[targetframerate]": "target_fps",
    "total time (s)": "total_time_s",
}


GROUPS = {
    "build": {
        "branch",
        "cl",
        "config",
        "engine_version",
        "project",
        "program_size_mb",
        "version",
    },
    "device": {
        "device_id",
        "gpu",
        "manufacturer",
        "model",
        "os_name",
        "os_version",
        "platform",
        "profile",
        "profile_chain",
        "profile_chain_depth",
        "profile_root",
        "profile_reference",
        "profile_reference_sha1",
        "tier",
    },
    "capture": {
        "command_line",
        "csv_id",
        "duration_s",
        "end_timestamp",
        "excluded_frame_count",
        "frame_count",
        "named_events",
        "start_timestamp",
        "target_fps",
        "total_time_s",
    },
    "metrics": {
        "drawcalls_avg",
        "fps_avg",
        "fps_iqr",
        "fps_p01",
        "fps_p05",
        "fps_p50",
        "fps_p90",
        "fps_p95",
        "fps_p99",
        "fps_stddev",
        "frametime_avg_ms",
        "game_thread_avg_ms",
        "gpu_avg_ms",
        "hitches_per_min",
        "hitch_time_percent",
        "memory_free_min_mb",
        "mvp60",
        "physical_used_max_mb",
        "render_thread_avg_ms",
        "rhi_thread_avg_ms",
    },
    "flags": {
        "asan_enabled",
        "has_header_row_at_end",
        "large_world_coordinates",
        "lto_enabled",
        "pgo_enabled",
        "pgo_profiling_enabled",
    },
}


def normalize_timestamp(value: object) -> str | None:
    """Return an ISO-8601 UTC-looking timestamp when the input is recognized."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in TIMESTAMP_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    return text


def timestamp_from_unix_epoch(value: object) -> str | None:
    """Convert a Unix epoch seconds value (int/str) to ISO-8601 UTC."""
    if value is None:
        return None
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    # Reject obviously bad values (negative, sentinel, far past, far future).
    if seconds < 946684800 or seconds > 4102444800:  # 2000-01-01 .. 2100-01-01
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def timestamp_from_profile_filename(path: str | Path) -> str | None:
    """Extract Profile(YYYYMMDD_HHMMSS) timestamps from generated report names."""
    match = re.search(r"\((\d{8}_\d{6})\)", Path(path).name)
    if not match:
        return None
    return normalize_timestamp(match.group(1))


def parse_scalar(value: Any) -> Any:
    """Coerce string values to int/float/bool/None where that is unambiguous."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool, list, dict)):
        return value

    text = str(value).strip()
    if text == "":
        return None
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"

    numeric_text = text.replace(",", "")
    try:
        if re.fullmatch(r"[-+]?\d+", numeric_text):
            return int(numeric_text)
        if re.fullmatch(r"[-+]?(\d+\.\d*|\d*\.\d+)(e[-+]?\d+)?", numeric_text, re.I):
            return float(numeric_text)
    except ValueError:
        pass
    return text


def snake_case_key(value: object) -> str:
    """Convert report labels into stable snake_case field names."""
    text = str(value).strip()
    text = text.strip("[]")
    text = text.replace(">", "gt_")
    text = text.replace("/", "_")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text


def parse_cpu_device(value: object) -> dict[str, str]:
    """Split Unreal's vendor|model|gpu CPU/Device field into dimensions."""
    text = str(value or "").strip()
    if not text:
        return {}
    parts = [_clean_device_part(part) for part in text.split("|") if part.strip()]
    if len(parts) >= 3:
        return {
            "manufacturer": parts[0],
            "model": parts[1],
            "gpu": "|".join(parts[2:]),
        }
    if len(parts) == 2:
        return {"manufacturer": parts[0], "model": parts[1]}
    return {"model": parts[0]}


def parse_os(value: object) -> dict[str, str]:
    text = str(value or "").strip()
    if not text:
        return {}
    match = re.match(r"([A-Za-z ]+?)\s+(.+)$", text)
    if not match:
        return {"os_name": text}
    return {"os_name": match.group(1).strip(), "os_version": match.group(2).strip()}


def parse_build_version(value: object) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}

    parsed: dict[str, Any] = {"version": text}
    match = re.search(r"\+\+([^+]+)\+([^+]+)-CL-(\d+)", text)
    if match:
        parsed["project"] = match.group(1)
        parsed["branch"] = match.group(2)
        parsed["cl"] = int(match.group(3))
        return parsed

    cl_match = re.search(r"\bCL[-_]?(\d+)\b", text, re.IGNORECASE)
    if cl_match:
        parsed["cl"] = int(cl_match.group(1))
    return parsed


def parse_engine_version(value: object) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    parsed: dict[str, Any] = {"engine_version": text}
    match = re.search(r"-(\d+)\+\+\+([^+]+)\+([^+]+)", text)
    if match:
        parsed.setdefault("cl", int(match.group(1)))
        parsed.setdefault("project", match.group(2))
        parsed.setdefault("branch", match.group(3))
    return parsed


def parse_frame_count(value: object) -> dict[str, int]:
    text = str(value or "").strip()
    match = re.match(r"(\d+)(?:\s+\((\d+)\s+excluded\))?", text)
    if not match:
        return {}
    return {
        "frame_count": int(match.group(1)),
        "excluded_frame_count": int(match.group(2) or 0),
    }


def canonical_key(raw_key: object) -> str:
    text = str(raw_key).strip()
    lowered = text.lower()
    if lowered in RAW_TO_CANONICAL_KEYS:
        return RAW_TO_CANONICAL_KEYS[lowered]

    percentile_match = re.fullmatch(
        r"(1st|1th|5th|50th|90th|95th|99th)\s+percentile",
        lowered,
    )
    if percentile_match:
        number = re.match(r"\d+", percentile_match.group(1))
        if number:
            return f"fps_p{int(number.group(0)):02d}"

    threshold_match = re.fullmatch(
        r"(FrameTime|GameThreadTime|RenderThreadTime|RHIThreadTime|GPUTime)_>(\d+)ms",
        text,
    )
    if threshold_match:
        prefix_by_row = {
            "FrameTime": "frame_time",
            "GameThreadTime": "game_thread",
            "RenderThreadTime": "render_thread",
            "RHIThreadTime": "rhi_thread",
            "GPUTime": "gpu",
        }
        prefix = prefix_by_row[threshold_match.group(1)]
        return f"{prefix}_gt_{threshold_match.group(2)}ms"

    return snake_case_key(text)


def _copy_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value not in (None, ""):
        target[key] = parse_scalar(value)


def _make_report_fingerprint(document: dict[str, Any]) -> str:
    fingerprint_basis = {
        "timestamp": document.get("@timestamp"),
        "build": {
            key: document.get("build", {}).get(key)
            for key in ("project", "branch", "cl", "config")
        },
        "device": {
            key: document.get("device", {}).get(key)
            for key in ("manufacturer", "model", "gpu", "profile")
        },
        "capture": {
            key: document.get("capture", {}).get(key)
            for key in ("csv_id", "start_timestamp", "end_timestamp", "frame_count")
        },
    }
    encoded = json.dumps(fingerprint_basis, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _clean_device_part(value: object) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text.replace("/", "_").replace("\\", "_")


def _derive_device_id(raw_values: dict[str, Any], source: Path) -> str:
    platform = str(
        raw_values.get("platform") or raw_values.get("Platform") or ""
    ).lower()
    os_value = str(raw_values.get("OS") or "").lower()
    report_is_desktop_os = any(
        token in platform or token in os_value for token in ["windows", "linux"]
    )

    cpu_device = str(raw_values.get("CPU/Device") or "").strip()
    if cpu_device:
        parts = [
            _clean_device_part(part) for part in cpu_device.split("|") if part.strip()
        ]
        if len(parts) >= 2:
            return f"{parts[0]}_{parts[1]}"
        if parts:
            if parts[0].lower() == "desktop" and not report_is_desktop_os:
                return "UnknownDevice"
            return parts[0]

    make = raw_values.get("Device Make")
    model = raw_values.get("Device Model")
    if make and model:
        return f"{_clean_device_part(make)}_{_clean_device_part(model)}"

    existing = str(raw_values.get("device_id") or "").strip()
    if existing and existing.lower() != "desktop":
        return existing

    report_mentions_desktop = any(
        "desktop" in str(raw_values.get(key) or "").lower()
        for key in ["CPU/Device", "Device Make", "Device Model", "device_id"]
    )
    if report_mentions_desktop and report_is_desktop_os:
        return "Desktop"

    folder_name = source.parent.name
    if folder_name.lower() == "desktop":
        return "UnknownDevice"
    return folder_name


def build_analytics_document(
    *,
    source_path: str | Path,
    source_type: str,
    raw_values: dict[str, Any],
    schema_version: int = SCHEMA_VERSION,
    device_profile_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the canonical analytics document expected by the Elasticsearch index."""
    source = Path(source_path)
    timestamp = normalize_timestamp(raw_values.get("Profiling Timestamp"))
    if timestamp is None:
        timestamp = normalize_timestamp(raw_values.get("@timestamp"))
    if timestamp is None:
        timestamp = timestamp_from_profile_filename(source)
    if timestamp is None:
        timestamp = timestamp_from_unix_epoch(
            raw_values.get("starttimestamp")
            or raw_values.get("StartTimestamp")
            or raw_values.get("[starttimestamp]")
        )

    enriched_values = dict(raw_values)
    enriched_values.update(
        enrich_with_device_profile_tier(enriched_values, device_profile_config_path)
    )

    document: dict[str, Any] = {
        "schema_version": schema_version,
        "source_type": source_type,
        "source_file": str(source),
        "source_name": source.name,
        "device_id": _derive_device_id(enriched_values, source),
        "build": {},
        "device": {},
        "capture": {},
        "metrics": {},
        "threshold_counts": {},
        "flags": {},
        "extra": {},
    }
    if timestamp:
        document["@timestamp"] = timestamp

    document["device"]["device_id"] = document["device_id"]

    for key, value in enriched_values.items():
        if key in {"Profiling Timestamp", "@timestamp", "device_id"}:
            continue

        canonical = canonical_key(key)
        scalar = parse_scalar(value)

        if canonical == "cpu_device":
            document["device"].update(parse_cpu_device(value))
            continue
        if canonical == "os":
            document["device"].update(parse_os(value))
            continue
        if canonical == "build_version":
            document["build"].update(parse_build_version(value))
            continue
        if canonical == "engine_version":
            document["build"].update(parse_engine_version(value))
            continue
        if canonical == "frame_count":
            frame_counts = parse_frame_count(value)
            if frame_counts:
                document["capture"].update(frame_counts)
            else:
                _copy_present(document["capture"], canonical, scalar)
            continue
        if canonical == "device_profile":
            _copy_present(document["device"], "profile", scalar)
            continue
        if canonical == "scalability_tier":
            _copy_present(document["device"], "tier", scalar)
            continue
        if canonical == "device_profile_chain":
            _copy_present(document["device"], "profile_chain", scalar)
            continue
        if canonical == "device_profile_reference":
            _copy_present(document["device"], "profile_reference", scalar)
            continue
        if canonical == "device_profile_reference_sha1":
            _copy_present(document["device"], "profile_reference_sha1", scalar)
            continue
        if canonical == "device_profile_chain_depth":
            _copy_present(document["device"], "profile_chain_depth", scalar)
            continue
        if canonical == "device_profile_root":
            _copy_present(document["device"], "profile_root", scalar)
            continue

        if canonical in GROUPS["build"]:
            _copy_present(document["build"], canonical, scalar)
        elif canonical in GROUPS["device"]:
            _copy_present(document["device"], canonical, scalar)
        elif canonical in GROUPS["capture"]:
            _copy_present(document["capture"], canonical, scalar)
        elif canonical in GROUPS["metrics"]:
            _copy_present(document["metrics"], canonical, scalar)
        elif canonical in GROUPS["flags"]:
            _copy_present(document["flags"], canonical, scalar)
        elif "_gt_" in canonical and canonical.endswith("ms"):
            _copy_present(document["threshold_counts"], canonical, scalar)
        else:
            _copy_present(document["extra"], canonical, scalar)

    if "model" not in document["device"]:
        existing_id = document["device_id"]
        if existing_id:
            document["device"]["model"] = existing_id

    document["report_fingerprint"] = _make_report_fingerprint(document)

    flat = _flatten_groups(document)
    return _apply_sentinels(flat)


GROUP_KEYS = (
    "build",
    "device",
    "capture",
    "metrics",
    "threshold_counts",
    "flags",
    "extra",
)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, str) and value.strip().lower() in {
        "unknown",
        "n/a",
        "na",
        "nan",
    }:
        return True
    return False


def _apply_sentinels(flat: dict[str, Any]) -> dict[str, Any]:
    """Fill missing/corrupt expected fields with sentinels and record corruption.

    Also computes report_value (1-100), a universal weight for Grafana
    weighted_avg aggregations. Higher = more trustworthy / data-rich run.
    """
    missing: list[str] = []
    for key, kind in EXPECTED_FIELDS.items():
        if _is_missing(flat.get(key)):
            missing.append(key)
            if kind == "timestamp":
                flat[key] = DEFAULT_TIMESTAMP
            elif kind == "numeric":
                flat[key] = SENTINEL_NUMERIC
            else:
                flat[key] = SENTINEL_STRING

    flat["data_quality_has_corruption"] = 1 if missing else 0
    flat["data_quality_missing_count"] = len(missing)
    flat["data_quality_missing_fields"] = ",".join(missing)
    flat["report_value"] = compute_report_value(
        frame_count=flat.get("capture_frame_count"),
        duration_s=flat.get("capture_duration_s"),
        target_fps=flat.get("capture_target_fps"),
        missing_count=len(missing),
        total_expected=len(EXPECTED_FIELDS),
    )
    return flat


def compute_report_value(
    *,
    frame_count: Any,
    duration_s: Any,
    target_fps: Any,
    missing_count: int,
    total_expected: int,
) -> int:
    """Return a 1-100 weighting score combining data volume + quality.

    Components (each 0..1, then weighted):
      * 0.50 - volume       min(frame_count / 36000, 1)   (cap = 10 min @ 60fps)
      * 0.25 - duration     min(duration_s  / 600,   1)
      * 0.10 - consistency  1 if observed_fps within +/-25% of target, else 0
      * 0.15 - completeness 1 - missing/total
    Result clamped to [1, 100].
    """

    def _num(value: Any, default: float = 0.0) -> float:
        try:
            f = float(value)
            return f if f >= 0 else default
        except (TypeError, ValueError):
            return default

    fc = _num(frame_count)
    dur = _num(duration_s)
    tgt = _num(target_fps, default=60.0) or 60.0

    volume = min(fc / 36000.0, 1.0)
    duration = min(dur / 600.0, 1.0)

    consistency = 0.0
    if fc > 0 and dur > 0:
        observed = fc / dur
        ratio = observed / tgt
        consistency = 1.0 if 0.75 <= ratio <= 1.25 else max(0.0, 1.0 - abs(1.0 - ratio))

    completeness = 1.0
    if total_expected > 0:
        completeness = max(0.0, 1.0 - (missing_count / total_expected))

    score = 100.0 * (
        0.50 * volume + 0.25 * duration + 0.10 * consistency + 0.15 * completeness
    )
    return max(1, min(100, int(round(score))))


def _flatten_groups(document: dict[str, Any]) -> dict[str, Any]:
    """Flatten the canonical group dicts into top-level keys joined with '_'.

    Top-level scalar metadata (@timestamp, schema_version, source_*, device_id,
    report_fingerprint) is preserved as-is. Empty groups are dropped.
    """
    flat: dict[str, Any] = {}
    for key, value in document.items():
        if key in GROUP_KEYS:
            if not isinstance(value, dict):
                continue
            for sub_key, sub_value in value.items():
                if sub_key == "device_id" and key == "device":
                    continue
                flat[f"{key}_{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat
