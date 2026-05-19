from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests  # type: ignore[import-untyped]

from cerebrus.plugins.analytics.core.csv_report_parser import PerformanceCSVReportParser
from cerebrus.plugins.analytics.core.html_report_parser import (
    PerformanceHTMLReportParser,
)
from cerebrus.plugins.analytics.core.normalizer import (
    SCHEMA_VERSION,
    build_analytics_document,
    parse_scalar,
)
from cerebrus.plugins.analytics.core.settings import load_analytics_settings

SUPPORTED_EXTENSIONS = {".html", ".htm", ".csv", ".json"}

_KEYWORD_MAPPING: dict[str, Any] = {
    "mappings": {
        "dynamic_templates": [
            {
                "strings_as_keywords": {
                    "match_mapping_type": "string",
                    "mapping": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 256},
                        },
                    },
                }
            }
        ]
    }
}


def _resolve_device_profile_config_path(
    device_profile_config_path: str | Path | None,
) -> str | Path:
    if device_profile_config_path is not None:
        return device_profile_config_path
    return load_analytics_settings().device_profile_config_path


def convert_file_to_document(
    path: str | Path,
    device_profile_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Convert a report file to an analytics document.

    ``device_profile_config_path`` is required for Scalability Tier enrichment.
    When omitted (UI path) the analytics settings store is consulted; library
    callers should pass it explicitly to avoid the hidden dependency.
    """
    source = Path(path)
    suffix = source.suffix.lower()
    config_path = _resolve_device_profile_config_path(device_profile_config_path)
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
            device_profile_config_path=config_path,
        )
    if suffix == ".csv":
        raw_values = PerformanceCSVReportParser(source).parse()
        return build_analytics_document(
            source_path=source,
            source_type="profiling_csv",
            raw_values=raw_values,
            device_profile_config_path=config_path,
        )
    if suffix == ".json":
        raw_values = json.loads(source.read_text(encoding="utf-8"))
        if (
            isinstance(raw_values, dict)
            and raw_values.get("schema_version") == SCHEMA_VERSION
            and raw_values.get("report_fingerprint")
            and raw_values.get("@timestamp")
            and raw_values.get("device_id")
        ):
            return raw_values
        return build_analytics_document(
            source_path=source,
            source_type="profiling_json",
            raw_values=raw_values,
            device_profile_config_path=config_path,
        )
    raise ValueError(f"Unsupported analytics source: {source}")


def convert_file_to_json(
    path: str | Path,
    output_path: str | Path | None = None,
    device_profile_config_path: str | Path | None = None,
) -> Path:
    source = Path(path)
    target = Path(output_path) if output_path else source.with_suffix(".analytics.json")
    document = convert_file_to_document(source, device_profile_config_path)
    target.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return target


def export_elasticsearch_bulk(
    paths: list[str | Path],
    output_path: str | Path,
    index_name: str = "telemetry-cerebrus-performance",
    device_profile_config_path: str | Path | None = None,
) -> Path:
    target = Path(output_path)
    with target.open("w", encoding="utf-8") as handle:
        for path in paths:
            document = convert_file_to_document(path, device_profile_config_path)
            action: dict[str, Any] = {"_index": index_name}
            if document.get("report_fingerprint"):
                action["_id"] = document["report_fingerprint"]
            handle.write(json.dumps({"index": action}) + "\n")
            handle.write(json.dumps(document) + "\n")
    return target


@dataclass
class IndexLocation:
    """Parsed Elasticsearch endpoint components.

    ``bulk_url`` includes any reverse-proxy path prefix that sat between
    the cluster host and the index segment so single-doc and bulk paths
    route through the same proxy.
    """

    cluster_url: str
    index_url: str
    bulk_url: str
    index_name: str
    is_doc_endpoint: bool


def _parse_index_location(url: str) -> IndexLocation | None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return None
    is_doc = segments[-1] == "_doc" or (len(segments) >= 2 and segments[-2] == "_doc")
    if is_doc:
        index_segments = segments[: segments.index("_doc")] if "_doc" in segments else []
    else:
        index_segments = segments
    if not index_segments:
        return None
    cluster_url = f"{parts.scheme}://{parts.netloc}"
    index_path = "/".join(index_segments)
    prefix_segments = index_segments[:-1]
    proxy_base = f"{cluster_url}/{'/'.join(prefix_segments)}" if prefix_segments else cluster_url
    return IndexLocation(
        cluster_url=cluster_url,
        index_url=f"{cluster_url}/{index_path}",
        bulk_url=f"{proxy_base}/_bulk",
        index_name=index_segments[-1],
        is_doc_endpoint=is_doc,
    )


@dataclass
class BulkCounts:
    created: int = 0
    updated: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"created": self.created, "updated": self.updated, "errors": self.errors}


class ElasticsearchClient:
    """Session-backed client for the Cerebrus analytics index.

    Holds a per-instance mapping cache and a ``requests.Session`` so repeated
    pushes reuse the same TCP connection. Construct one per URL or share across
    targets — the cache is keyed by index URL.
    """

    def __init__(self, session: Any | None = None) -> None:
        self._session: Any = session if session is not None else requests.Session()
        self._mapping_cache: set[str] = set()

    @property
    def session(self) -> Any:
        return self._session

    def ensure_index_mapping(self, url: str) -> tuple[bool, str]:
        location = _parse_index_location(url)
        if location is None:
            return False, f"Cannot derive index URL from: {url}"
        if location.index_url in self._mapping_cache:
            return True, "cached"
        try:
            head = self._session.head(location.index_url, timeout=10)
            if head.status_code == 200:
                self._mapping_cache.add(location.index_url)
                return True, "index exists"
            if head.status_code != 404:
                return False, f"HEAD {location.index_url} returned {head.status_code}"
            create = self._session.put(
                location.index_url,
                json=_KEYWORD_MAPPING,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            if create.status_code in {200, 201}:
                self._mapping_cache.add(location.index_url)
                return True, "created index with keyword mapping"
            return (
                False,
                f"PUT {location.index_url} returned {create.status_code}: {create.text}",
            )
        except Exception as exc:
            return False, f"ensure_index_mapping error: {exc}"

    def push_document(
        self, document: dict[str, Any], url: str
    ) -> tuple[int, str]:
        ok, msg = self.ensure_index_mapping(url)
        if not ok:
            return 0, f"ensure_index_mapping failed: {msg}"

        request_url = url.rstrip("/")
        fingerprint = document.get("report_fingerprint")
        if fingerprint and request_url.endswith("/_doc"):
            request_url = f"{request_url}/{fingerprint}"
            method = self._session.put
        else:
            method = self._session.post

        response = method(
            request_url,
            json=document,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        return response.status_code, response.text

    def push_bulk(
        self, documents: list[dict[str, Any]], url: str
    ) -> tuple[int, str, BulkCounts]:
        counts = BulkCounts()
        location = _parse_index_location(url)
        if location is None:
            counts.errors = len(documents)
            return 0, f"Cannot derive index URL from: {url}", counts

        ok, msg = self.ensure_index_mapping(url)
        if not ok:
            counts.errors = len(documents)
            return 0, f"ensure_index_mapping failed: {msg}", counts

        lines: list[str] = []
        for document in documents:
            action: dict[str, Any] = {"_index": location.index_name}
            fingerprint = document.get("report_fingerprint")
            if fingerprint:
                action["_id"] = fingerprint
            lines.append(json.dumps({"index": action}))
            lines.append(json.dumps(document))
        body = "\n".join(lines) + "\n"

        response = self._session.post(
            location.bulk_url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
            timeout=60,
        )

        # Any failure to parse a structured _bulk response is treated as a
        # full-batch failure. A 200 from a misbehaving proxy returning HTML
        # would otherwise be indistinguishable from success and trigger
        # delete-after-upload to drop never-indexed files.
        try:
            payload = response.json()
        except Exception:
            counts.errors = len(documents)
            return response.status_code, response.text, counts
        if not isinstance(payload, dict) or "items" not in payload:
            counts.errors = len(documents)
            return response.status_code, response.text, counts
        if payload.get("errors") is True:
            # Cluster signalled at least one item error; trust it even if the
            # item parser undercounts due to schema surprises.
            pass

        items = payload.get("items", [])
        for item in items:
            op = next(iter(item.values()))
            status = op.get("status", 0)
            if op.get("error"):
                counts.errors += 1
            elif status == 201:
                counts.created += 1
            elif status == 200:
                counts.updated += 1
        # Non-2xx HTTP or under-reported items: surface as batch failure so
        # the caller's is_success predicate refuses delete-after-upload.
        if response.status_code not in {200, 201}:
            counts.errors = max(counts.errors, len(documents))
        processed = counts.created + counts.updated + counts.errors
        if processed < len(documents):
            counts.errors += len(documents) - processed
        return response.status_code, response.text, counts


_default_client: ElasticsearchClient | None = None


def _get_default_client() -> ElasticsearchClient:
    global _default_client
    if _default_client is None:
        _default_client = ElasticsearchClient()
    return _default_client


def reset_default_client() -> None:
    """Drop the cached process-wide client (test hook)."""
    global _default_client
    _default_client = None


def ensure_index_mapping(url: str) -> tuple[bool, str]:
    return _get_default_client().ensure_index_mapping(url)


def push_document_to_elasticsearch(
    document: dict[str, Any], url: str
) -> tuple[int, str]:
    return _get_default_client().push_document(document, url)


def push_bulk_to_elasticsearch(
    documents: list[dict[str, Any]], url: str
) -> tuple[int, str, dict[str, int]]:
    status, text, counts = _get_default_client().push_bulk(documents, url)
    return status, text, counts.as_dict()


def summarize_folder(
    folder: str | Path,
    output_path: str | Path | None = None,
    device_profile_config_path: str | Path | None = None,
) -> Path:
    source_dir = Path(folder)
    documents = [
        convert_file_to_document(path, device_profile_config_path)
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
