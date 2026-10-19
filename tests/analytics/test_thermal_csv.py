from pathlib import Path

from cerebrus.plugins.analytics.core.converter import (
    convert_file_to_document,
    convert_file_to_session_samples,
)


THERMAL_CSV = """Timestamp,ElapsedSeconds,BatteryTempC
2026-10-15 11:02:55,0.4,31.8
2026-10-15 11:02:56,0.9,32.2
2026-10-15 11:02:57,1.8,33.0
2026-10-15 11:02:58,2.7,34.0
"""


def test_thermal_csv_is_converted_to_canonical_document(tmp_path: Path) -> None:
    source = tmp_path / "vivo_V2351_battery_thermal_7.csv"
    source.write_text(THERMAL_CSV, encoding="utf-8")

    document = convert_file_to_document(source)

    assert document["source_type"] == "battery_thermal_csv"
    assert document["device_id"] == "vivo_V2351"
    assert document["metrics_battery_temp_avg_c"] == 32.75
    assert document["metrics_battery_temp_min_c"] == 31.8
    assert document["metrics_battery_temp_max_c"] == 34.0
    assert document["capture_thermal_duration_s"] == 2.7


def test_thermal_csv_recovers_s3_path_dimensions(tmp_path: Path) -> None:
    source = tmp_path / "Test" / "vivo" / "V2351" / "54738" / "15-10-2026" / "152904" / "vivo_V2351_battery_thermal_7.csv"
    source.parent.mkdir(parents=True)
    source.write_text(THERMAL_CSV, encoding="utf-8")

    document = convert_file_to_document(source)

    assert document["build_cl"] == 54738
    assert document["build_config"] == "Test"
    assert document["device_id"] == "vivo_V2351"
    assert document["capture_session_id"] == "152904"


def test_thermal_csv_produces_elapsed_session_samples(tmp_path: Path) -> None:
    source = tmp_path / "samsung_SM-F956B_battery_thermal.csv"
    source.write_text(THERMAL_CSV, encoding="utf-8")

    samples = convert_file_to_session_samples(source)

    assert len(samples) == 3
    assert samples[0]["source_type"] == "battery_thermal_session_sample"
    assert samples[0]["session_sample_id"].endswith(":thermal:000000")
    assert samples[0]["metrics_battery_temp_avg_c"] == 32.0
    assert samples[0]["capture_started_at"] == "2026-10-15T11:02:55Z"
    assert samples[1]["elapsed_seconds"] == 1
    assert samples[1]["metrics_battery_temp_max_c"] == 33.0
