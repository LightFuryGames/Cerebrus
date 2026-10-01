from __future__ import annotations

import json
from pathlib import Path

import pytest

from cerebrus.plugins.analytics.core.converter import (
    convert_file_to_session_samples,
    push_session_samples_to_elasticsearch,
)
from cerebrus.plugins.analytics.core.session_samples import build_session_samples


def _summary() -> dict[str, object]:
    return {
        "@timestamp": "2026-09-30T10:00:00Z",
        "report_fingerprint": "session-abc",
        "source_type": "profiling_html_raw_csv",
        "source_name": "Profile(20260930_100000).html",
        "device_id": "vivo_V2351",
        "build_cl": 52119,
        "build_config": "Test",
        "device_tier": "Medium",
    }


def test_build_session_samples_rolls_frames_into_seconds_and_copies_dimensions() -> None:
    raw_csv = "\n".join(
        [
            "EVENTS,FrameTime,GameThreadTime,GPUTime,AndroidCPU/CPUTemp,AndroidMemory/Mem_RSS",
            "LoadingScreen/Show,400,10,8,30,500",
            ",400,12,9,32,510",
            "LoadingScreen/Hide,400,14,10,35,520",
            ",400,16,11,36,530",
            "[HasHeaderRowAtEnd],1,[targetframerate],60",
        ]
    )

    documents = build_session_samples(raw_csv, _summary())

    assert len(documents) == 2
    first, second = documents
    assert first["session_sample_id"] == "session-abc:000000"
    assert first["@timestamp"] == "2026-09-30T10:00:00Z"
    assert first["sample_frame_count"] == 3
    assert first["metrics_fps_avg"] == 2.5
    assert first["metrics_game_thread_avg_ms"] == 12.0
    assert first["metrics_cpu_temp_max_c"] == 35.0
    assert first["event_names"] == ["LoadingScreen/Hide", "LoadingScreen/Show"]
    assert first["build_cl"] == 52119
    assert second["elapsed_seconds"] == 1
    assert second["@timestamp"] == "2026-09-30T10:00:01Z"


def test_session_samples_ignore_non_finite_rows() -> None:
    raw_csv = "FrameTime,GPUTime\n500,10\nNaN,Infinity\n500,20\n"

    documents = build_session_samples(raw_csv, _summary())

    assert len(documents) == 1
    assert documents[0]["sample_frame_count"] == 2
    assert documents[0]["metrics_gpu_avg_ms"] == 15.0
    assert json.dumps(documents, allow_nan=False)


def test_convert_html_session_samples_requires_embedded_raw_csv(tmp_path: Path) -> None:
    report = tmp_path / "Profile(20260930_100000).html"
    report.write_text("<html><body>No raw payload</body></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="no embedded raw CSV"):
        convert_file_to_session_samples(report)


def test_push_session_samples_uses_dedicated_index_and_stable_id(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class Response:
        status_code = 200
        text = "ok"

        @staticmethod
        def json() -> dict[str, object]:
            return {"errors": False, "items": []}

    def fake_post(url, data, headers, timeout):
        calls.update(url=url, data=data, headers=headers, timeout=timeout)
        return Response()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)
    status, _, count = push_session_samples_to_elasticsearch(
        [{"session_sample_id": "session-abc:000000", "metrics_fps_avg": 60.0}],
        "http://localhost:9200/telemetry-cerebrus-performance/_doc",
    )

    action = json.loads(str(calls["data"]).splitlines()[0])
    assert status == 200
    assert count == 1
    assert calls["url"] == "http://localhost:9200/_bulk"
    assert action["index"]["_index"] == "telemetry-cerebrus-session-samples"
    assert action["index"]["_id"] == "session-abc:000000"
