"""Coverage for the sentinel-fill pass + data_quality tracking."""

from __future__ import annotations

from cerebrus.plugins.analytics.core.normalizer import (
    DEFAULT_TIMESTAMP,
    EXPECTED_FIELDS,
    SENTINEL_NUMERIC,
    SENTINEL_STRING,
    _apply_sentinels,
    _is_missing,
    build_analytics_document,
)


def test_empty_doc_fills_all_sentinels() -> None:
    flat = _apply_sentinels({})
    assert flat["@timestamp"] == DEFAULT_TIMESTAMP
    assert flat["metrics_fps_avg"] == SENTINEL_NUMERIC
    assert flat["device_tier"] == SENTINEL_STRING
    assert flat["data_quality_has_corruption"] == 1
    assert flat["data_quality_missing_count"] == len(EXPECTED_FIELDS)


def test_healthy_doc_no_corruption() -> None:
    flat = {key: _stub(kind) for key, kind in EXPECTED_FIELDS.items()}
    out = _apply_sentinels(dict(flat))
    assert out["data_quality_has_corruption"] == 0
    assert out["data_quality_missing_count"] == 0
    assert out["data_quality_missing_fields"] == ""


def _stub(kind: str) -> object:
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "numeric": 1,
        "string": "ok",
    }[kind]


def test_partial_corruption_reports_correct_fields() -> None:
    flat = {key: _stub(kind) for key, kind in EXPECTED_FIELDS.items()}
    flat.pop("metrics_fps_avg")
    flat["device_tier"] = "Unknown"  # already a sentinel string
    out = _apply_sentinels(dict(flat))
    assert out["data_quality_has_corruption"] == 1
    missing = set(out["data_quality_missing_fields"].split(","))
    assert "metrics_fps_avg" in missing
    assert "device_tier" in missing
    assert out["data_quality_missing_count"] == 2


def test_sentinels_dont_overwrite_real_zero() -> None:
    """A real numeric zero is valid data, not a sentinel."""
    flat = {"capture_excluded_frame_count": 0}
    out = _apply_sentinels(dict(flat))
    # Real 0 stays. _is_missing treats 0 as valid.
    assert out["capture_excluded_frame_count"] == 0


def test_is_missing_recognizes_common_dirty_strings() -> None:
    for value in (None, "", "  ", "Unknown", "N/A", "NaN", "n/a", "unknown"):
        assert _is_missing(value), f"{value!r} should count as missing"
    for value in (0, 0.0, False, "0", "Low", "x"):
        assert not _is_missing(value), f"{value!r} should NOT count as missing"


def test_build_analytics_document_emits_sentinels_for_empty_raw() -> None:
    doc = build_analytics_document(
        source_path="fake.csv",
        source_type="profiling_csv",
        raw_values={},
    )
    assert doc["@timestamp"] == DEFAULT_TIMESTAMP
    assert doc["device_tier"] == SENTINEL_STRING
    assert doc["metrics_fps_avg"] == SENTINEL_NUMERIC
    assert doc["data_quality_has_corruption"] == 1
    assert doc["report_value"] >= 1
    assert doc["report_value"] <= 100


def test_sentinel_constants_match_doc_contract() -> None:
    assert DEFAULT_TIMESTAMP == "2000-01-01T00:00:00Z"
    assert SENTINEL_NUMERIC == -1
    assert SENTINEL_STRING == "Unknown"
