from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable

from cerebrus.plugins.analytics.core.csv_report_parser import PerformanceCSVReportParser
from cerebrus.plugins.analytics.core.html_report_parser import (
    PerformanceHTMLReportParser,
)
from cerebrus.plugins.analytics.core.normalizer import (
    build_analytics_document,
    parse_scalar,
)
from cerebrus.plugins.analytics.core.settings import load_analytics_settings

SUPPORTED_EXTENSIONS = {".html", ".htm", ".csv", ".json"}


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
    method: Callable[..., Any] = requests.post
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
