"""Parser and one-second bucketer for battery thermal capture CSVs."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any


THERMAL_COLUMNS = {"Timestamp", "ElapsedSeconds", "BatteryTempC"}


def _number(value: object) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def is_battery_thermal_csv(csv_text: str) -> bool:
    first_line = next(iter(csv.reader(StringIO(csv_text))), [])
    return THERMAL_COLUMNS.issubset({column.strip() for column in first_line})


def _device_from_name(path: Path) -> str:
    stem = re.sub(r"_battery_thermal(?:_\d+)?$", "", path.stem, flags=re.IGNORECASE)
    return stem or "UnknownDevice"


def _path_metadata(path: Path) -> dict[str, Any]:
    """Recover upload dimensions when the local path preserves the S3 layout."""
    parts = list(path.parts)
    for index, part in enumerate(parts):
        if not re.fullmatch(r"\d{2}-\d{2}-\d{4}", part) or index < 4 or index + 1 >= len(parts):
            continue
        session_id = parts[index + 1]
        if not session_id.isdigit():
            continue
        config, manufacturer, model, build_cl = parts[index - 4 : index]
        metadata: dict[str, Any] = {
            "config": config,
            "manufacturer": manufacturer,
            "model": model,
            "build_cl": build_cl,
            "session_id": session_id,
        }
        metadata["device_id"] = f"{manufacturer}_{model}"
        return metadata
    return {}


def _sibling_report_metadata(path: Path) -> dict[str, Any]:
    """Recover dimensions from the Cerebrus HTML beside a sidecar CSV.

    The S3 uploader derives its destination from this same report metadata, but
    analytics conversion normally receives the local CSV path.  Reading the
    metadata block here keeps both flows data-driven and prevents a valid S3
    Build CL from becoming ``-1`` in Elasticsearch.
    """
    device_prefix = _device_from_name(path).lower()
    candidates = sorted(
        [*path.parent.glob("*.html"), *path.parent.glob("*.htm")],
        key=lambda candidate: (
            not candidate.stem.lower().startswith(device_prefix),
            candidate.name.lower(),
        ),
    )
    for report in candidates:
        try:
            content = report.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        match = re.search(
            r'<script type=["\']application/json["\'] id=["\']cerebrus-metadata["\']>(.*?)</script>',
            content,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            continue
        try:
            metadata = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict):
            continue

        def first(*keys: str) -> object:
            for key in keys:
                value = metadata.get(key)
                if value not in (None, ""):
                    return value
            return None

        dimensions: dict[str, Any] = {}
        config = first(
            "build_config", "Build Configuration", "configuration", "Configuration", "config"
        )
        if config is not None:
            dimensions["build_config"] = config
        build_cl = first(
            "build_cl", "Changelist", "changelist", "cl", "build_changelist"
        )
        if build_cl is not None:
            match_cl = re.search(r"\d+", str(build_cl))
            if match_cl:
                dimensions["build_cl"] = int(match_cl.group(0))
        manufacturer = first(
            "device_manufacturer", "Device Make", "device_make", "manufacturer"
        )
        model = first("device_model", "Device Model", "device_model", "model")
        if manufacturer is not None:
            dimensions["device_manufacturer"] = manufacturer
        if model is not None:
            dimensions["device_model"] = model
        if manufacturer is not None and model is not None:
            dimensions["device_id"] = f"{manufacturer}_{model}"

        # Profile(YYYYMMDD_HHMMSS) is the source used by the S3 uploader for
        # capture time; retain the opaque HHMMSS portion as the session ID.
        profile = re.search(r"Profile\(\d{8}_(\d{6})\)", content)
        session_id = first("capture_session_id", "session_id")
        if session_id is None and profile:
            session_id = profile.group(1)
        if session_id is not None:
            dimensions["session_id"] = str(session_id)
        return dimensions
    return {}


def parse_battery_thermal_csv(path: str | Path, csv_text: str | None = None) -> dict[str, Any]:
    source = Path(path)
    text = csv_text if csv_text is not None else source.read_text(encoding="utf-8-sig", errors="ignore")
    rows = list(csv.DictReader(StringIO(text)))
    samples = [
        row for row in rows
        if _number(row.get("ElapsedSeconds")) is not None and _number(row.get("BatteryTempC")) is not None
    ]
    temperatures = [float(_number(row["BatteryTempC"])) for row in samples]
    elapsed = [float(_number(row["ElapsedSeconds"])) for row in samples]
    first_timestamp = str(samples[0].get("Timestamp") or "").strip() if samples else ""
    values: dict[str, Any] = {
        "device_id": _device_from_name(source),
        "Profiling Timestamp": first_timestamp,
        "Battery Temp Avg (C)": round(sum(temperatures) / len(temperatures), 3) if temperatures else -1,
        "Battery Temp Min (C)": round(min(temperatures), 3) if temperatures else -1,
        "Battery Temp Max (C)": round(max(temperatures), 3) if temperatures else -1,
        "Thermal Sample Count": len(temperatures),
        "Thermal Duration (s)": round(max(elapsed), 3) if elapsed else 0,
        "Thermal Source": "battery",
    }
    values.update(_sibling_report_metadata(source))
    # A preserved S3-style path is the strongest source of truth and wins over
    # any incomplete metadata block in the sibling report.
    values.update(_path_metadata(source))
    return values


def _sample_timestamp(value: str, elapsed_seconds: int) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (parsed + timedelta(seconds=elapsed_seconds)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_battery_thermal_samples(raw_csv: str, summary_document: dict[str, Any]) -> list[dict[str, Any]]:
    session_id = str(summary_document.get("report_fingerprint") or "").strip()
    if not session_id:
        raise ValueError("A report_fingerprint is required to create thermal samples.")

    buckets: dict[int, list[float]] = defaultdict(list)
    capture_start = ""
    for row in csv.DictReader(StringIO(raw_csv)):
        elapsed = _number(row.get("ElapsedSeconds"))
        temperature = _number(row.get("BatteryTempC"))
        if elapsed is None or temperature is None:
            continue
        capture_start = capture_start or str(row.get("Timestamp") or "").strip()
        buckets[int(elapsed)].append(temperature)

    dimensions = {
        field: summary_document[field]
        for field in (
            "device_id", "build_branch", "build_cl", "build_config", "build_project",
            "build_version", "device_manufacturer", "device_model", "device_tier",
        )
        if field in summary_document
    }
    documents: list[dict[str, Any]] = []
    for second in sorted(buckets):
        values = buckets[second]
        documents.append({
            "schema_version": 1,
            "source_type": "battery_thermal_session_sample",
            "source_report_type": summary_document.get("source_type", "battery_thermal_csv"),
            "source_name": summary_document.get("source_name", "Unknown"),
            "report_fingerprint": session_id,
            "session_id": session_id,
            "session_sample_id": f"{session_id}:thermal:{second:06d}",
            "elapsed_seconds": second,
            "@timestamp": _sample_timestamp(capture_start, second),
            "capture_started_at": _sample_timestamp(capture_start, 0),
            "sample_thermal_count": len(values),
            "metrics_battery_temp_avg_c": round(sum(values) / len(values), 3),
            "metrics_battery_temp_min_c": round(min(values), 3),
            "metrics_battery_temp_max_c": round(max(values), 3),
            **dimensions,
        })
    return documents
