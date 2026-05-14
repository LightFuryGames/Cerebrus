"""Coverage for report_fingerprint determinism + Unix epoch -> ISO timestamp."""

from __future__ import annotations

from pathlib import Path

from cerebrus.plugins.analytics.core.normalizer import (
    build_analytics_document,
    timestamp_from_unix_epoch,
)

# ---------------------------------------------------------------------------
# timestamp_from_unix_epoch


def test_epoch_seconds_to_iso_utc() -> None:
    assert timestamp_from_unix_epoch(1777280938) == "2026-04-27T09:08:58Z"


def test_epoch_string_accepted() -> None:
    assert timestamp_from_unix_epoch("1777280938") == "2026-04-27T09:08:58Z"


def test_epoch_negative_rejected() -> None:
    assert timestamp_from_unix_epoch(-1) is None


def test_epoch_sentinel_string_rejected() -> None:
    assert timestamp_from_unix_epoch("-1") is None


def test_epoch_year_1990_rejected() -> None:
    """Before 2000-01-01 is treated as garbage."""
    assert timestamp_from_unix_epoch(631152000) is None


def test_epoch_year_2200_rejected() -> None:
    """After 2100-01-01 is treated as garbage."""
    assert timestamp_from_unix_epoch(7258118400) is None


def test_epoch_none_returns_none() -> None:
    assert timestamp_from_unix_epoch(None) is None


def test_epoch_garbage_returns_none() -> None:
    assert timestamp_from_unix_epoch("abc") is None
    assert timestamp_from_unix_epoch([]) is None


# ---------------------------------------------------------------------------
# report_fingerprint


_BASE_RAW = {
    "Profiling Timestamp": "27:04:2026:09:08:58",
    "CPU/Device": "samsung|SM-S948U1|Adreno (TM) 840",
    "OS": "Android 16",
    "Build Version": "++titan-game+development-CL-32261",
    "Configuration": "Test",
    "csvid": "ABC123",
    "starttimestamp": "1777280938",
    "endtimestamp": "1777281143",
    "framecount": "6388",
}


def test_fingerprint_is_deterministic() -> None:
    a = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    b = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    assert a["report_fingerprint"] == b["report_fingerprint"]
    assert len(a["report_fingerprint"]) == 64  # SHA-256 hex


def test_fingerprint_changes_when_cl_changes() -> None:
    a = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    raw = dict(_BASE_RAW)
    raw["Build Version"] = "++titan-game+development-CL-99999"
    b = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=raw,
    )
    assert a["report_fingerprint"] != b["report_fingerprint"]


def test_fingerprint_changes_when_csv_id_changes() -> None:
    raw = dict(_BASE_RAW)
    raw["csvid"] = "OTHER"
    b = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=raw,
    )
    a = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    assert a["report_fingerprint"] != b["report_fingerprint"]


def test_fingerprint_stable_across_source_path() -> None:
    """source_path is metadata and must NOT affect the fingerprint."""
    a = build_analytics_document(
        source_path="foo/bar.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    b = build_analytics_document(
        source_path="other/place.csv",
        source_type="profiling_csv",
        raw_values=dict(_BASE_RAW),
    )
    assert a["report_fingerprint"] == b["report_fingerprint"]


def test_timestamp_fallback_to_epoch_when_filename_absent(tmp_path: Path) -> None:
    """If no filename/Profiling Timestamp/@timestamp, use starttimestamp."""
    raw = {k: v for k, v in _BASE_RAW.items() if k != "Profiling Timestamp"}
    doc = build_analytics_document(
        source_path=tmp_path / "no_pattern_filename.csv",
        source_type="profiling_csv",
        raw_values=raw,
    )
    # 1777280938 -> 2026-04-27T09:08:58Z
    assert doc["@timestamp"] == "2026-04-27T09:08:58Z"
