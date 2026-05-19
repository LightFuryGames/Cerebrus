"""Pipeline unit tests for AnalyticsController + ElasticsearchClient.

Exercises the refactored analytics core without touching DPG or the network.
The stub session below is the seam that lets the suite be both a unit test
(individual ES interactions) and a smoke test (end-to-end conversion ->
upload -> delete).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cerebrus.plugins.analytics.controller import AnalyticsController
from cerebrus.plugins.analytics.core.converter import (
    ElasticsearchClient,
    _parse_index_location,
)


class StubResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        payload: dict | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("no json payload")
        return self._payload


class StubSession:
    """Programmable Session replacement for ES tests."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.head_response = StubResponse(status_code=200)
        self.put_response = StubResponse(status_code=201, text="created")
        self.post_response = StubResponse(
            status_code=200, text="ok", payload={"items": []}
        )

    def head(self, url, **kw):
        self.calls.append({"method": "HEAD", "url": url, **kw})
        return self.head_response

    def put(self, url, **kw):
        self.calls.append({"method": "PUT", "url": url, **kw})
        return self.put_response

    def post(self, url, **kw):
        self.calls.append({"method": "POST", "url": url, **kw})
        return self.post_response


@pytest.fixture
def session() -> StubSession:
    return StubSession()


@pytest.fixture
def client(session: StubSession) -> ElasticsearchClient:
    return ElasticsearchClient(session=session)


@pytest.fixture
def log_capture():
    captured: list[tuple[str, str]] = []

    def logger(level: str, message: str) -> None:
        captured.append((level, message))

    return captured, logger


def _write_analytics_json(path: Path, fingerprint: str, timestamp: str = "2026-04-27T15:20:33Z") -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "report_fingerprint": fingerprint,
                "@timestamp": timestamp,
                "device_id": "DeviceA",
                "metrics_fps_avg": 58.2,
            }
        ),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def test_parse_index_location_handles_doc_endpoint() -> None:
    loc = _parse_index_location("http://host:9200/my-index/_doc")
    assert loc is not None
    assert loc.cluster_url == "http://host:9200"
    assert loc.index_url == "http://host:9200/my-index"
    assert loc.bulk_url == "http://host:9200/_bulk"
    assert loc.index_name == "my-index"
    assert loc.is_doc_endpoint is True


def test_parse_index_location_handles_plain_index() -> None:
    loc = _parse_index_location("https://host/my-index/")
    assert loc is not None
    assert loc.cluster_url == "https://host"
    assert loc.index_url == "https://host/my-index"
    assert loc.bulk_url == "https://host/_bulk"
    assert loc.is_doc_endpoint is False


def test_parse_index_location_preserves_reverse_proxy_prefix() -> None:
    """A reverse-proxy URL like ``host/cerebrus/api/idx/_doc`` must keep the
    ``/cerebrus/api`` prefix on the derived bulk URL — otherwise bulk uploads
    bypass the proxy entirely while single uploads route through it."""
    loc = _parse_index_location("https://host/cerebrus/api/telemetry/_doc")
    assert loc is not None
    assert loc.cluster_url == "https://host"
    assert loc.index_url == "https://host/cerebrus/api/telemetry"
    assert loc.bulk_url == "https://host/cerebrus/api/_bulk"
    assert loc.index_name == "telemetry"


def test_parse_index_location_rejects_clusterless_url() -> None:
    assert _parse_index_location("http://host:9200/") is None
    assert _parse_index_location("ftp://host/index/_doc") is None
    assert _parse_index_location("not-a-url") is None


# ---------------------------------------------------------------------------
# ensure_index_mapping
# ---------------------------------------------------------------------------


def test_ensure_index_mapping_skips_when_index_exists(client, session) -> None:
    ok, msg = client.ensure_index_mapping("http://host:9200/index/_doc")
    assert ok and msg == "index exists"
    assert [c["method"] for c in session.calls] == ["HEAD"]

    ok, msg = client.ensure_index_mapping("http://host:9200/index/_doc")
    assert ok and msg == "cached"
    assert [c["method"] for c in session.calls] == ["HEAD"]


def test_ensure_index_mapping_creates_when_missing(client, session) -> None:
    session.head_response = StubResponse(status_code=404)
    ok, msg = client.ensure_index_mapping("http://host:9200/index/_doc")
    assert ok
    assert "created index" in msg
    methods = [c["method"] for c in session.calls]
    assert methods == ["HEAD", "PUT"]
    put_call = session.calls[1]
    assert put_call["url"] == "http://host:9200/index"
    keyword_mapping = put_call["json"]["mappings"]["dynamic_templates"][0]
    assert keyword_mapping["strings_as_keywords"]["match_mapping_type"] == "string"


def test_ensure_index_mapping_surfaces_hard_errors(client, session) -> None:
    session.head_response = StubResponse(status_code=500, text="boom")
    ok, msg = client.ensure_index_mapping("http://host:9200/index/_doc")
    assert not ok
    assert "500" in msg


def test_push_document_aborts_when_mapping_fails(client, session) -> None:
    session.head_response = StubResponse(status_code=403)
    status, text = client.push_document(
        {"report_fingerprint": "x"}, "http://host:9200/i/_doc"
    )
    assert status == 0
    assert "ensure_index_mapping failed" in text
    # No POST/PUT for the actual document push
    assert [c["method"] for c in session.calls] == ["HEAD"]


# ---------------------------------------------------------------------------
# Bulk pipeline
# ---------------------------------------------------------------------------


def test_push_bulk_marks_full_batch_failed_on_json_parse_error(
    client, session
) -> None:
    """Reverse-proxy 200 with an HTML body is the classic silent-success
    failure mode. Without the parse-failure guard, the controller would
    treat the request as a clean success and delete the source files."""

    class HtmlResponse:
        status_code = 200
        text = "<html>login required</html>"

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    session.post_response = HtmlResponse()

    docs = [{"report_fingerprint": "a"}, {"report_fingerprint": "b"}]
    status, _, counts = client.push_bulk(docs, "http://host:9200/idx/_doc")

    assert status == 200
    assert counts.errors == 2
    assert counts.created == 0


def test_push_bulk_marks_full_batch_failed_when_items_missing(client, session) -> None:
    """A 200 body with no ``items`` key (e.g. an _bulk endpoint returning a
    cluster-level diagnostic) must also count as full-batch failure."""
    session.post_response = StubResponse(
        status_code=200, text="ok", payload={"took": 5, "errors": False}
    )
    docs = [{"report_fingerprint": "a"}]
    status, _, counts = client.push_bulk(docs, "http://host:9200/idx/_doc")
    assert counts.errors == 1


def test_push_bulk_uses_proxy_prefix_when_routing(client, session) -> None:
    """Bulk URL preservation regression: must POST to the proxy-prefixed
    ``/_bulk``, not the cluster root."""
    session.post_response = StubResponse(
        status_code=200, text="ok", payload={"items": [{"index": {"status": 201}}]}
    )
    client.push_bulk([{"report_fingerprint": "a"}], "https://host/cerebrus/api/idx/_doc")
    post = next(c for c in session.calls if c["method"] == "POST")
    assert post["url"] == "https://host/cerebrus/api/_bulk"


def test_push_bulk_emits_ndjson_with_index_actions(client, session) -> None:
    session.post_response = StubResponse(
        status_code=200,
        text="ok",
        payload={
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 200}},
                {"index": {"status": 400, "error": {"type": "mapper"}}},
            ]
        },
    )

    docs = [
        {"report_fingerprint": "a", "metrics_fps_avg": 60.0},
        {"report_fingerprint": "b", "metrics_fps_avg": 30.0},
        {"metrics_fps_avg": 10.0},
    ]
    status, _, counts = client.push_bulk(docs, "http://host:9200/idx/_doc")

    assert status == 200
    assert counts.created == 1
    assert counts.updated == 1
    assert counts.errors == 1

    post = next(c for c in session.calls if c["method"] == "POST")
    assert post["url"] == "http://host:9200/_bulk"
    assert post["headers"] == {"Content-Type": "application/x-ndjson"}

    body_lines = post["data"].decode("utf-8").strip().splitlines()
    assert len(body_lines) == 6
    first_action = json.loads(body_lines[0])
    assert first_action == {"index": {"_index": "idx", "_id": "a"}}
    third_action = json.loads(body_lines[4])
    assert third_action == {"index": {"_index": "idx"}}


# ---------------------------------------------------------------------------
# Controller — target resolution and uploads
# ---------------------------------------------------------------------------


def test_resolve_targets_prefers_explicit_file(
    tmp_path, log_capture, client
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    file_target = _write_analytics_json(tmp_path / "one.analytics.json", "f1")
    folder = tmp_path / "folder"
    folder.mkdir()
    _write_analytics_json(folder / "two.analytics.json", "f2")

    assert controller.resolve_targets(file_target, folder) == [file_target]


def test_resolve_targets_globs_folder_when_no_file(
    tmp_path, log_capture, client
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    folder = tmp_path / "folder"
    folder.mkdir()
    one = _write_analytics_json(folder / "one.analytics.json", "f1")
    two = _write_analytics_json(folder / "two.analytics.json", "f2")
    # non-matching files are ignored
    (folder / "ignore.txt").write_text("nope", encoding="utf-8")

    assert controller.resolve_targets(None, folder) == sorted([one, two])


def test_resolve_targets_returns_empty_when_nothing_set(
    tmp_path, log_capture, client
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    assert controller.resolve_targets(None, None) == []
    assert controller.resolve_targets(tmp_path / "missing.json", None) == []


def test_upload_individual_reports_outcome_and_skips_delete_on_failure(
    tmp_path, log_capture, client, session
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    good = _write_analytics_json(tmp_path / "good.analytics.json", "good-id")
    bad = _write_analytics_json(tmp_path / "bad.analytics.json", "bad-id")

    # First doc gets 201, second gets 500
    session.put_response = StubResponse(status_code=201, text="created")

    responses = iter(
        [
            StubResponse(status_code=201, text="created"),
            StubResponse(status_code=500, text="kaput"),
        ]
    )

    original_put = session.put

    def sequenced_put(url, **kw):
        session.calls.append({"method": "PUT", "url": url, **kw})
        return next(responses)

    session.put = sequenced_put  # type: ignore[assignment]

    outcome = controller.upload_individual(
        [good, bad],
        "http://host:9200/idx/_doc",
        delete_after_success=True,
    )

    assert len(outcome.successes) == 1
    assert outcome.successes[0] == good
    assert len(outcome.failures) == 1
    assert outcome.failures[0][0] == bad
    assert outcome.last_status == 500

    # Successful target deleted, failed target preserved
    assert not good.exists()
    assert bad.exists()

    # Summary lines describe both buckets
    joined = "\n".join(outcome.summary_lines)
    assert "Uploaded: 1 / 2" in joined
    assert "Failures: 1" in joined
    assert any(level == "SUCCESS" for level, _ in captured)
    assert any(level == "ERROR" for level, _ in captured)


def test_upload_bulk_deletes_only_when_all_items_succeed(
    tmp_path, log_capture, client, session
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    a = _write_analytics_json(tmp_path / "a.analytics.json", "a-id")
    b = _write_analytics_json(tmp_path / "b.analytics.json", "b-id")
    session.post_response = StubResponse(
        status_code=200,
        text="ok",
        payload={
            "items": [
                {"index": {"status": 201}},
                {"index": {"status": 201}},
            ]
        },
    )

    outcome = controller.upload_bulk(
        [a, b], "http://host:9200/idx/_doc", delete_after_success=True
    )

    assert outcome.is_success
    assert outcome.documents_sent == 2
    assert outcome.counts["created"] == 2
    assert not a.exists()
    assert not b.exists()


def test_upload_bulk_is_success_requires_documents_sent_match(
    tmp_path, log_capture, client, session
) -> None:
    """If ES under-reports items (e.g. truncated response, schema drift),
    is_success must refuse to delete files even though counts.errors == 0."""
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    a = _write_analytics_json(tmp_path / "a.analytics.json", "a-id")
    b = _write_analytics_json(tmp_path / "b.analytics.json", "b-id")
    # Cluster claims 200 but only returns one item row for two docs.
    session.post_response = StubResponse(
        status_code=200,
        text="ok",
        payload={"items": [{"index": {"status": 201}}]},
    )

    outcome = controller.upload_bulk(
        [a, b], "http://host:9200/idx/_doc", delete_after_success=True
    )
    assert outcome.is_success is False
    assert a.exists() and b.exists()


def test_upload_bulk_is_success_false_on_non_2xx(
    tmp_path, log_capture, client, session
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)
    a = _write_analytics_json(tmp_path / "a.analytics.json", "a-id")
    session.post_response = StubResponse(
        status_code=500, text="server error",
        payload={"items": [{"index": {"status": 500, "error": {"type": "x"}}}]},
    )
    outcome = controller.upload_bulk(
        [a], "http://host:9200/idx/_doc", delete_after_success=True
    )
    assert outcome.is_success is False
    assert a.exists()


def test_upload_bulk_keeps_files_when_any_item_errors(
    tmp_path, log_capture, client, session
) -> None:
    captured, logger = log_capture
    controller = AnalyticsController(logger=logger, client=client)

    a = _write_analytics_json(tmp_path / "a.analytics.json", "a-id")
    session.post_response = StubResponse(
        status_code=200,
        text="ok",
        payload={
            "items": [
                {"index": {"status": 400, "error": {"type": "mapper"}}},
            ]
        },
    )

    outcome = controller.upload_bulk(
        [a], "http://host:9200/idx/_doc", delete_after_success=True
    )

    assert not outcome.is_success
    assert outcome.counts["errors"] == 1
    assert a.exists()


# ---------------------------------------------------------------------------
# Settings + end-to-end smoke
# ---------------------------------------------------------------------------


def test_controller_settings_round_trip(tmp_path, log_capture, client) -> None:
    captured, logger = log_capture
    settings_path = tmp_path / "analytics_settings.json"
    controller = AnalyticsController(
        logger=logger, client=client, settings_path=settings_path
    )

    saved = controller.save_upload_url(
        "  http://host:9200/telemetry-cerebrus-performance/_doc  "
    )
    assert saved == "http://host:9200/telemetry-cerebrus-performance/_doc"

    loaded = controller.load_settings()
    assert (
        loaded.elasticsearch_url
        == "http://host:9200/telemetry-cerebrus-performance/_doc"
    )


def test_smoke_csv_to_json_to_bulk_upload(tmp_path, log_capture, client, session) -> None:
    """End-to-end: CSV -> .analytics.json -> bulk upload -> file deletion."""
    captured, logger = log_capture
    settings_path = tmp_path / "settings.json"
    controller = AnalyticsController(
        logger=logger, client=client, settings_path=settings_path
    )

    report = tmp_path / "DeviceA" / "Profile(20260427_152033).csv"
    report.parent.mkdir()
    report.write_text(
        "\n".join(
            [
                "FrameTime,GameThreadTime,MemoryFreeMB,RHI/DrawCalls",
                "16.0,12.0,1000,40",
                "20.0,14.0,990,42",
                "80.0,60.0,970,50",
                "[HasHeaderRowAtEnd],1,[targetframerate],60,[cpu],OnePlus|ONEPLUS A3003|Qualcomm,[programsizemb],123.0",
            ]
        ),
        encoding="utf-8",
    )

    json_path = controller.convert_to_json_file(report)
    assert json_path.exists()
    assert json_path.name.endswith(".analytics.json")

    session.post_response = StubResponse(
        status_code=200,
        text="ok",
        payload={"items": [{"index": {"status": 201}}]},
    )
    outcome = controller.upload_bulk(
        [json_path],
        "http://host:9200/telemetry/_doc",
        delete_after_success=True,
    )

    assert outcome.is_success
    assert outcome.counts["created"] == 1
    assert not json_path.exists()

    head_calls = [c for c in session.calls if c["method"] == "HEAD"]
    post_calls = [c for c in session.calls if c["method"] == "POST"]
    assert len(head_calls) == 1
    assert len(post_calls) == 1
    assert post_calls[0]["url"] == "http://host:9200/_bulk"

    success_logs = [m for level, m in captured if level == "SUCCESS"]
    assert any("Bulk uploaded 1 document" in m for m in success_logs)
