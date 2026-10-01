from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from cerebrus.plugins.analytics.core.csv_report_parser import PerformanceCSVReportParser
from cerebrus.plugins.analytics.core.html_report_parser import (
    PerformanceHTMLReportParser,
)
from cerebrus.plugins.analytics.core.normalizer import (
    build_analytics_document,
    parse_scalar,
)
from cerebrus.plugins.analytics.core.session_samples import build_session_samples
from cerebrus.plugins.analytics.core.settings import load_analytics_settings

SUPPORTED_EXTENSIONS = {".html", ".htm", ".csv", ".json"}
SESSION_SAMPLES_INDEX = "telemetry-cerebrus-session-samples"


def convert_file_to_document(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    suffix = source.suffix.lower()
    settings = load_analytics_settings()
    device_profile_config_path = settings.device_profile_config_path
    if suffix in {".html", ".htm"}:
        html_parser = PerformanceHTMLReportParser(source)
        raw_csv = html_parser.extract_embedded_raw_csv()
        if raw_csv:
            embedded_name = html_parser.embedded_profile_name()
            logical_source = (
                source.with_name(f"{embedded_name}.csv") if embedded_name else source
            )
            raw_values = PerformanceCSVReportParser(
                logical_source,
                csv_text=raw_csv,
            ).parse()
            source_type = "profiling_html_raw_csv"
        else:
            raw_values = html_parser.parse()
            source_type = "profiling_html"
        return build_analytics_document(
            source_path=source,
            source_type=source_type,
            raw_values=raw_values,
            device_profile_config_path=device_profile_config_path,
        )
    if suffix == ".csv":
        raw_values = PerformanceCSVReportParser(source).parse()
        return build_analytics_document(
            source_path=source,
            source_type="profiling_csv",
            raw_values=raw_values,
            device_profile_config_path=device_profile_config_path,
        )
    if suffix == ".json":
        raw_values = json.loads(source.read_text(encoding="utf-8"))
        if "schema_version" in raw_values and "report_fingerprint" in raw_values:
            return raw_values
        return build_analytics_document(
            source_path=source,
            source_type="profiling_json",
            raw_values=raw_values,
            device_profile_config_path=device_profile_config_path,
        )
    raise ValueError(f"Unsupported analytics source: {source}")


def convert_file_to_json(
    path: str | Path, output_path: str | Path | None = None
) -> Path:
    source = Path(path)
    target = Path(output_path) if output_path else source.with_suffix(".analytics.json")
    document = convert_file_to_document(source)
    target.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return target


def convert_file_to_session_samples(path: str | Path) -> list[dict[str, Any]]:
    """Create timeline records from a local raw CSV or HTML containing raw CSV.

    Cloud-uploaded reports intentionally remove their raw CSV payload, so this
    function must run on the original local report before it is uploaded to S3.
    """
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        raw_csv = source.read_text(encoding="utf-8-sig", errors="ignore")
    elif suffix in {".html", ".htm"}:
        raw_csv = PerformanceHTMLReportParser(source).extract_embedded_raw_csv()
        if not raw_csv:
            raise ValueError(
                "The selected HTML has no embedded raw CSV. Select the original "
                "local report before the S3 upload copy is created."
            )
    else:
        raise ValueError("Session samples require an HTML or CSV source report.")
    return build_session_samples(raw_csv, convert_file_to_document(source))


def export_elasticsearch_bulk(
    paths: list[str | Path],
    output_path: str | Path,
    index_name: str = "telemetry-cerebrus-performance",
) -> Path:
    target = Path(output_path)
    with target.open("w", encoding="utf-8") as handle:
        for path in paths:
            document = convert_file_to_document(path)
            action: dict[str, Any] = {"_index": index_name}
            if document.get("report_fingerprint"):
                action["_id"] = document["report_fingerprint"]
            handle.write(json.dumps({"create": action}) + "\n")
            handle.write(json.dumps(document) + "\n")
    return target


def push_document_to_elasticsearch(
    document: dict[str, Any], url: str
) -> tuple[int, str]:
    import requests  # type: ignore[import-untyped]

    request_url = url.rstrip("/")
    method = requests.post
    fingerprint = document.get("report_fingerprint")
    if fingerprint and request_url.endswith("/_doc"):
        request_url = f"{request_url}/{fingerprint}"
        method = requests.put

    response = method(
        request_url,
        json=document,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return response.status_code, response.text


def _bulk_endpoint(upload_url: str) -> str:
    """Resolve an index document endpoint to Elasticsearch's cluster bulk API."""
    endpoint = upload_url.rstrip("/")
    if not endpoint.endswith("/_doc"):
        raise ValueError("The upload endpoint must end with '/_doc'.")
    return endpoint.rsplit("/", 2)[0] + "/_bulk"


def push_session_samples_to_elasticsearch(
    documents: list[dict[str, Any]],
    upload_url: str,
    *,
    index_name: str = SESSION_SAMPLES_INDEX,
    batch_size: int = 500,
) -> tuple[int, str, int]:
    """Bulk index one-second records using deterministic sample IDs.

    The normal report endpoint supplies the Elasticsearch host only.  Samples
    are sent to their own index to avoid changing the aggregate report schema.
    """
    if not documents:
        return 200, "No session samples were generated.", 0
    if batch_size < 1:
        raise ValueError("batch_size must be at least one.")

    import requests  # type: ignore[import-untyped]

    endpoint = _bulk_endpoint(upload_url)
    indexed = 0
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        lines: list[str] = []
        for document in batch:
            sample_id = str(document.get("session_sample_id") or "").strip()
            if not sample_id:
                raise ValueError("Every session sample must have a session_sample_id.")
            lines.append(
                json.dumps({"index": {"_index": index_name, "_id": sample_id}})
            )
            lines.append(json.dumps(document, allow_nan=False))
        response = requests.post(
            endpoint,
            data="\n".join(lines) + "\n",
            headers={"Content-Type": "application/x-ndjson"},
            timeout=60,
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError(
                f"Elasticsearch bulk upload failed: {response.status_code} {response.text}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Elasticsearch bulk response was not valid JSON.") from exc
        if payload.get("errors"):
            failed = next(
                (
                    item
                    for item in payload.get("items", [])
                    if item.get("index", {}).get("error")
                ),
                {},
            )
            raise RuntimeError(f"Elasticsearch rejected session samples: {failed}")
        indexed += len(batch)
    return 200, f"Indexed {indexed} one-second session samples.", indexed


def summarize_folder(folder: str | Path, output_path: str | Path | None = None) -> Path:
    source_dir = Path(folder)
    documents = [
        convert_file_to_document(path)
        for path in sorted(source_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    target = Path(output_path) if output_path else source_dir / "analytics_summary.csv"
    reserved_keys = {"@timestamp", "device_id"}
    value_keys = sorted(
        {
            key
            for document in documents
            for key in document.keys()
            if key not in reserved_keys
        }
    )
    fields = [
        "@timestamp",
        "device_id",
        *value_keys,
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for document in documents:
            row = {
                "@timestamp": document.get("@timestamp", ""),
                "device_id": document.get("device_id", ""),
            }
            row.update(
                {
                    key: parse_scalar(value)
                    for key, value in document.items()
                    if key not in reserved_keys
                }
            )
            writer.writerow(row)
    return target
