"""Robustness coverage for the analytics converter facade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cerebrus.plugins.analytics.core.converter import (
    convert_file_to_document,
    convert_file_to_json,
    export_elasticsearch_bulk,
)


def _write_csv(path: Path, target_fps: int = 60) -> None:
    path.write_text(
        "\n".join(
            [
                "FrameTime,GameThreadTime,RenderThreadTime,GPUTime,MemoryFreeMB,RHI/DrawCalls",
                "16.0,12.0,4.0,8.0,1000,40",
                "20.0,14.0,5.0,9.0,990,42",
                "80.0,60.0,30.0,40.0,970,50",
                f"[HasHeaderRowAtEnd],1,[targetframerate],{target_fps},[csvid],"
                f"TESTID123,[cpu],samsung|SM-S948U1|Adreno (TM) 840",
            ]
        ),
        encoding="utf-8",
    )


def test_convert_csv_returns_flat_doc(tmp_path: Path) -> None:
    csv = tmp_path / "Device" / "Profile(20260101_120000).csv"
    csv.parent.mkdir()
    _write_csv(csv)
    doc = convert_file_to_document(csv)
    assert doc["schema_version"] == 2
    # Flat: no nested dicts
    assert not any(isinstance(v, (dict, list)) for v in doc.values())
    assert "report_fingerprint" in doc
    assert "report_value" in doc


def test_convert_existing_flat_json_passes_through(tmp_path: Path) -> None:
    """A pre-flattened JSON with schema_version and report_fingerprint
    should be returned as-is, not re-built."""
    source = tmp_path / "preflat.json"
    payload = {
        "schema_version": 2,
        "report_fingerprint": "abc",
        "metrics_fps_avg": 58.2,
    }
    source.write_text(json.dumps(payload), encoding="utf-8")
    doc = convert_file_to_document(source)
    assert doc["metrics_fps_avg"] == 58.2
    assert doc["report_fingerprint"] == "abc"


def test_convert_legacy_nested_json_rebuilds(tmp_path: Path) -> None:
    """An older JSON without report_fingerprint should be rebuilt to v2."""
    source = tmp_path / "legacy.json"
    legacy = {
        "@timestamp": "2026-04-27T15:20:33Z",
        "FPS Avg": 58.2,
        "CPU/Device": "Samsung|SM-G991B|Mali-G77",
    }
    source.write_text(json.dumps(legacy), encoding="utf-8")
    doc = convert_file_to_document(source)
    assert doc["schema_version"] == 2
    assert doc["metrics_fps_avg"] == 58.2
    assert "report_fingerprint" in doc


def test_convert_unsupported_extension_raises(tmp_path: Path) -> None:
    bad = tmp_path / "x.txt"
    bad.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        convert_file_to_document(bad)


def test_convert_file_to_json_writes_to_default_path(tmp_path: Path) -> None:
    csv = tmp_path / "Device" / "Profile(20260101_120000).csv"
    csv.parent.mkdir()
    _write_csv(csv)
    out = convert_file_to_json(csv)
    assert out.exists()
    assert out.suffix == ".json"
    assert "analytics" in out.name
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2


def test_bulk_export_uses_fingerprint_as_id(tmp_path: Path) -> None:
    csv1 = tmp_path / "a.csv"
    csv2 = tmp_path / "b.csv"
    _write_csv(csv1)
    _write_csv(csv2, target_fps=30)
    out = tmp_path / "bulk.ndjson"
    export_elasticsearch_bulk([csv1, csv2], out, index_name="telemetry-test")
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4  # action + doc per file
    action1 = json.loads(lines[0])
    doc1 = json.loads(lines[1])
    assert action1["create"]["_index"] == "telemetry-test"
    assert action1["create"]["_id"] == doc1["report_fingerprint"]


def test_bulk_export_handles_mixed_sources(tmp_path: Path) -> None:
    csv = tmp_path / "a.csv"
    json_legacy = tmp_path / "b.json"
    _write_csv(csv)
    json_legacy.write_text(
        json.dumps({"@timestamp": "2026-04-27T00:00:00Z", "FPS Avg": 50}),
        encoding="utf-8",
    )
    out = tmp_path / "mixed.ndjson"
    export_elasticsearch_bulk([csv, json_legacy], out)
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
