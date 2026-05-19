from __future__ import annotations

import json
from pathlib import Path

from cerebrus.plugins.analytics.core import (
    convert_file_to_document,
    convert_file_to_json,
    export_elasticsearch_bulk,
    summarize_folder,
)
from cerebrus.plugins.analytics.core.converter import (
    ElasticsearchClient,
    push_document_to_elasticsearch,
)
from cerebrus.plugins.analytics.core.device_profiles import (
    enrich_with_device_profile_tier,
)
from cerebrus.plugins.analytics.core.settings import (
    AnalyticsSettings,
    load_analytics_settings,
    save_analytics_settings,
)


def test_convert_csv_to_analytics_document(tmp_path: Path) -> None:
    report = tmp_path / "DeviceA" / "Profile(20260427_152033).csv"
    report.parent.mkdir()
    report.write_text(
        "\n".join(
            [
                "FrameTime,GameThreadTime,MemoryFreeMB,RHI/DrawCalls",
                "16.0,12.0,1000,40",
                "20.0,14.0,990,42",
                "80.0,60.0,970,50",
                "[HasHeaderRowAtEnd],1,[targetframerate],60,[cpu],OnePlus|ONEPLUS A3003|Qualcomm Technologies, Inc MSM8996,[programsizemb],123.378906",
            ]
        ),
        encoding="utf-8",
    )

    document = convert_file_to_document(report)

    assert document["@timestamp"] == "2026-04-27T15:20:33Z"
    assert document["device_id"] == "OnePlus_ONEPLUS A3003"
    assert document["schema_version"] == 2
    assert document["source_type"] == "profiling_csv"
    assert document["device_manufacturer"] == "OnePlus"
    assert document["device_model"] == "ONEPLUS A3003"
    assert document["device_gpu"] == "Qualcomm Technologies, Inc MSM8996"
    assert document["capture_target_fps"] == 60
    assert document["capture_frame_count"] == 3
    assert document["capture_excluded_frame_count"] == 0
    assert document["build_program_size_mb"] == 123.378906
    assert document["metrics_frametime_avg_ms"] == 38.67
    assert document["threshold_counts_frame_time_gt_60ms"] == 1
    assert document["metrics_drawcalls_avg"] == 44.0
    assert "report_fingerprint" in document


def test_html_device_id_comes_from_report_not_desktop_folder(tmp_path: Path) -> None:
    report = tmp_path / "Desktop" / "Profile(20260427_152033).html"
    report.parent.mkdir()
    report.write_text(
        """
        <html><body>
          <table>
            <tr><td>Configuration</td><td><b>Test</b></td></tr>
            <tr><td>OS</td><td><b>Android 16</b></td></tr>
            <tr><td>CPU/Device</td><td><b>samsung|SM-S948U1|Adreno (TM) 840</b></td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )

    document = convert_file_to_document(report)

    assert document["device_id"] == "samsung_SM-S948U1"
    assert document["device_manufacturer"] == "samsung"
    assert document["device_model"] == "SM-S948U1"
    assert document["device_gpu"] == "Adreno (TM) 840"
    assert document["device_id"] != "Desktop"


def test_html_device_id_can_be_desktop_for_desktop_report(tmp_path: Path) -> None:
    report = tmp_path / "Desktop" / "Profile(20260427_152033).html"
    report.parent.mkdir()
    report.write_text(
        """
        <html><body>
          <table>
            <tr><td>platform</td><td><b>Windows</b></td></tr>
            <tr><td>OS</td><td><b>Windows 11</b></td></tr>
            <tr><td>CPU/Device</td><td><b>Desktop</b></td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )

    document = convert_file_to_document(report)

    assert document["device_id"] == "Desktop"
    assert document["device_model"] == "Desktop"


def test_convert_flat_json_to_analytics_json(tmp_path: Path) -> None:
    source = tmp_path / "Profile(20260427_152033).json"
    source.write_text(
        json.dumps(
            {
                "Profiling Timestamp": "27:04:2026:15:20:33",
                "FPS Avg": "58.2",
                "CPU/Device": "Samsung|SM-G991B",
            }
        ),
        encoding="utf-8",
    )

    output = convert_file_to_json(source)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert output == source.with_suffix(".analytics.json")
    assert payload["@timestamp"] == "2026-04-27T15:20:33Z"
    assert payload["metrics_fps_avg"] == 58.2
    assert payload["device_manufacturer"] == "Samsung"
    assert payload["device_model"] == "SM-G991B"


def test_summarize_folder_and_bulk_export(tmp_path: Path) -> None:
    first = tmp_path / "run1.json"
    second = tmp_path / "run2.json"
    first.write_text(
        json.dumps(
            {
                "@timestamp": "2026-04-27T15:20:33Z",
                "FPS Avg": 58.2,
                "Configuration": "Development",
            }
        ),
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(
            {
                "@timestamp": "2026-04-28T15:20:33Z",
                "FPS Avg": 55.0,
                "Configuration": "Shipping",
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_folder(tmp_path)
    bulk = export_elasticsearch_bulk(
        [first, second],
        tmp_path / "bulk.ndjson",
        index_name="telemetry-test",
    )

    summary_text = summary.read_text(encoding="utf-8")
    bulk_lines = bulk.read_text(encoding="utf-8").splitlines()

    assert "metrics_fps_avg" in summary_text
    assert "build_config" in summary_text
    assert len(bulk_lines) == 4
    assert json.loads(bulk_lines[0])["index"]["_index"] == "telemetry-test"
    assert json.loads(bulk_lines[1])["metrics_fps_avg"] == 58.2


def test_analytics_settings_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / "analytics_settings.json"
    endpoint = "http://10.10.10.66:9200/telemetry-cerebrus-performance/_doc"
    device_profiles = "D:/p4/temp/titan-engine/Engine/Config/BaseDeviceProfiles.ini"

    save_analytics_settings(
        AnalyticsSettings(
            elasticsearch_url=endpoint,
            device_profile_config_path=device_profiles,
        ),
        settings_path,
    )
    loaded = load_analytics_settings(settings_path)

    assert loaded.elasticsearch_url == endpoint
    assert loaded.device_profile_config_path == device_profiles


def test_device_profile_reference_resolves_scalability_tier(tmp_path: Path) -> None:
    config = tmp_path / "BaseDeviceProfiles.ini"
    config.write_text(
        """
        [Android_Epic DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android

        [Android_Adreno8xx DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android_Epic

        [Android_Adreno8xx_Vulkan DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android_Adreno8xx
        """,
        encoding="utf-8",
    )

    enriched = enrich_with_device_profile_tier(
        {"DeviceProfile": "Android_Adreno8xx_Vulkan"},
        config,
    )

    assert enriched["Scalability Tier"] == "Epic"
    assert enriched["scalability_tier"] == "Epic"
    assert (
        enriched["DeviceProfile Chain"]
        == "Android_Adreno8xx_Vulkan -> Android_Adreno8xx -> Android_Epic"
    )
    assert (
        enriched["device_profile_chain"]
        == "Android_Adreno8xx_Vulkan -> Android_Adreno8xx -> Android_Epic"
    )
    assert enriched["device_profile_chain_depth"] == 3
    assert enriched["device_profile_root"] == "Android_Epic"


class _StubResponse:
    def __init__(self, status_code: int = 200, text: str = "", payload: dict | None = None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class _StubSession:
    """Records every HTTP method call against the ES client."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.head_response = _StubResponse(status_code=200)
        self.put_response = _StubResponse(status_code=201, text="created")
        self.post_response = _StubResponse(status_code=200, text="ok")

    def head(self, url, **kwargs):
        self.calls.append({"method": "HEAD", "url": url, **kwargs})
        return self.head_response

    def put(self, url, **kwargs):
        self.calls.append({"method": "PUT", "url": url, **kwargs})
        return self.put_response

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.post_response


def test_push_document_to_elasticsearch_posts_canonical_payload(monkeypatch) -> None:
    import cerebrus.plugins.analytics.core.converter as converter_module

    session = _StubSession()
    monkeypatch.setattr(
        converter_module,
        "_get_default_client",
        lambda: ElasticsearchClient(session=session),
    )

    status_code, response_text = push_document_to_elasticsearch(
        {
            "@timestamp": "2026-04-27T15:20:33Z",
            "schema_version": 1,
            "source_type": "profiling_json",
            "source_file": "run.analytics.json",
            "source_name": "run.analytics.json",
            "device_id": "DeviceA",
            "report_fingerprint": "abc123",
            "build_config": "Development",
            "metrics_fps_avg": 58.2,
        },
        "http://localhost:9200/telemetry-cerebrus-performance/_doc",
    )

    put_calls = [c for c in session.calls if c["method"] == "PUT"]
    assert status_code == 201
    assert response_text == "created"
    assert len(put_calls) == 1
    assert (
        put_calls[0]["url"]
        == "http://localhost:9200/telemetry-cerebrus-performance/_doc/abc123"
    )
    assert put_calls[0]["json"]["metrics_fps_avg"] == 58.2
    assert put_calls[0]["json"]["build_config"] == "Development"
    assert put_calls[0]["headers"] == {"Content-Type": "application/json"}
