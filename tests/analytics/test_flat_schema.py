"""Schema-shape contract tests for the v2 flat analytics document."""

from __future__ import annotations

from cerebrus.plugins.analytics.core.normalizer import (
    SCHEMA_VERSION,
    build_analytics_document,
)

_HEALTHY = {
    "Profiling Timestamp": "27:04:2026:09:08:58",
    "CPU/Device": "samsung|SM-S948U1|Adreno (TM) 840",
    "OS": "Android 16",
    "Build Version": "++titan-game+development-CL-32261",
    "Configuration": "Test",
    "csvid": "ABC123",
    "starttimestamp": "1777280938",
    "endtimestamp": "1777281143",
    "framecount": "6388",
    "targetframerate": "60",
    "FPS Avg": 58.2,
}


def test_schema_version_pinned_to_2() -> None:
    assert SCHEMA_VERSION == 2
    doc = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_HEALTHY),
    )
    assert doc["schema_version"] == 2


def test_document_is_flat_no_nested_dicts() -> None:
    doc = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_HEALTHY),
    )
    nested = [k for k, v in doc.items() if isinstance(v, (dict, list))]
    assert nested == [], f"Schema must be flat. Nested fields found: {nested}"


def test_required_top_level_fields() -> None:
    doc = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_HEALTHY),
    )
    for required in (
        "@timestamp",
        "schema_version",
        "source_type",
        "source_file",
        "source_name",
        "device_id",
        "report_fingerprint",
        "report_value",
        "data_quality_has_corruption",
        "data_quality_missing_count",
        "data_quality_missing_fields",
    ):
        assert required in doc, f"missing required field: {required}"


def test_field_prefixes_present() -> None:
    doc = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_HEALTHY),
    )
    prefixes = {k.split("_", 1)[0] for k in doc if "_" in k}
    # At minimum these prefix groups must be present in a healthy doc.
    for prefix in ("build", "device", "capture", "data"):
        assert prefix in prefixes, f"prefix '{prefix}' missing from doc"


def test_data_quality_fields_are_correct_types() -> None:
    doc = build_analytics_document(
        source_path="x.csv",
        source_type="profiling_csv",
        raw_values=dict(_HEALTHY),
    )
    assert isinstance(doc["data_quality_has_corruption"], int)
    assert doc["data_quality_has_corruption"] in (0, 1)
    assert isinstance(doc["data_quality_missing_count"], int)
    assert isinstance(doc["data_quality_missing_fields"], str)
    assert isinstance(doc["report_value"], int)
