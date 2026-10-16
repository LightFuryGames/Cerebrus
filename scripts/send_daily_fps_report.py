#!/usr/bin/env python3
"""Send a compact daily Cerebrus FPS report to Slack.

The script deliberately uses only the Python standard library so Jenkins can
run it without changing the Cerebrus runtime dependencies.  Credentials are
read from arguments/environment and are never written to the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from statistics import mean


def _request_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def _es_endpoint(base_url: str, index: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/_search"):
        return base
    if base.endswith("/_doc"):
        base = base[:-5].rstrip("/")
    if base.endswith(index):
        return f"{base}/_search"
    return f"{base}/{index}/_search"


def query_elasticsearch(es_url: str, index: str, hours: int) -> dict:
    # Match Grafana's report/session view by collapsing re-uploaded reports.
    query = {
        "size": 10000,
        "track_total_hits": True,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "_source": ["@timestamp", "report_fingerprint", "build_cl", "device_id", "metrics_fps_avg", "metrics_hitches_per_min"],
        "query": {
            "bool": {
                "filter": [
                    {"range": {"@timestamp": {"gte": f"now-{hours}h", "lte": "now"}}},
                    {"exists": {"field": "metrics_fps_avg"}},
                ]
            }
        },
    }
    response = _request_json(_es_endpoint(es_url, index), query)
    unique: dict[str, dict] = {}
    for hit in response.get("hits", {}).get("hits", []):
        source = hit.get("_source", {})
        key = source.get("report_fingerprint") or hit.get("_id")
        if not key:
            key = "|".join(str(source.get(name, "")) for name in ("@timestamp", "build_cl", "device_id"))
        unique.setdefault(str(key), source)
    values = [float(doc["metrics_fps_avg"]) for doc in unique.values() if doc.get("metrics_fps_avg") is not None]
    hitches = [float(doc["metrics_hitches_per_min"]) for doc in unique.values() if doc.get("metrics_hitches_per_min") is not None]
    groups: dict[str, list[float]] = {}
    for doc in unique.values():
        if doc.get("metrics_fps_avg") is None:
            continue
        key = f"{doc.get('build_cl', 'Unknown')} | {doc.get('device_id', 'Unknown')}"
        groups.setdefault(key, []).append(float(doc["metrics_fps_avg"]))
    return {"fps_values": values, "hitches_values": hitches, "reports_by_build_device": [{"key": key, "fps": {"value": mean(fps)}, "count": {"value": len(fps)}} for key, fps in sorted(groups.items())]}


def _percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def build_message(result: dict, hours: int, grafana_url: str | None) -> str:
    values = result.get("fps_values", [])
    buckets = result.get("reports_by_build_device", [])
    total = len(values)
    percentiles = {"5.0": _percentile(values, 5), "50.0": _percentile(values, 50), "95.0": _percentile(values, 95)}
    dashboard = (grafana_url or "http://13.202.235.56:3000/d/ecricket-performance-health-poc/performance-insights").rstrip("/")
    if "/d/" not in dashboard:
        dashboard = f"{dashboard}/d/ecricket-performance-health-poc/performance-insights"
    query = urllib.parse.urlencode({"orgId": "1", "from": f"now-{hours}h", "to": "now", "timezone": "Asia/Kolkata"})
    dashboard_link = f"<{dashboard}?{query}|Open Performance Insights dashboard>"
    if not total:
        return "\n".join([
            f":information_source: *E-Cricket daily FPS report* (last {hours} hours, IST)",
            "No FPS samples were indexed in this window.",
            dashboard_link,
        ])
    lines = [
        f":bar_chart: *E-Cricket daily FPS report* (last {hours} hours, IST)",
        f"*Reports:* {int(total)}  |  *Average:* {mean(values):.1f} fps",
        f"*FPS distribution:* P05 {percentiles.get('5.0', 0):.1f}  •  Median {percentiles.get('50.0', 0):.1f}  •  P95 {percentiles.get('95.0', 0):.1f}",
    ]
    hitches = mean(result.get("hitches_values", [])) if result.get("hitches_values") else None
    if hitches is not None:
        lines.append(f"*Visible hitches:* {hitches:.2f}/min average")
    lines.append("*By build CL and device:*")
    for bucket in buckets[:10]:
        build_device = bucket['key'].replace(' | ', ' — ')
        lines.append(f"• {build_device}: {bucket['fps'].get('value', 0):.1f} fps ({int(bucket['count'].get('value', 0))} samples)")
    lines.append(dashboard_link)
    return "\n".join(lines)


def post_slack(webhook: str, message: str) -> None:
    body = json.dumps({"text": message}).encode("utf-8")
    request = urllib.request.Request(webhook, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Slack webhook returned HTTP {exc.code}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--es-url", default=os.getenv("CEREBRUS_ES_URL"), required=not os.getenv("CEREBRUS_ES_URL"))
    parser.add_argument("--index", default="telemetry-cerebrus-performance")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--grafana-url", default=os.getenv("CEREBRUS_GRAFANA_URL"))
    parser.add_argument("--slack-webhook", default=os.getenv("SLACK_WEBHOOK_URL"), required=not os.getenv("SLACK_WEBHOOK_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = query_elasticsearch(args.es_url, args.index, args.hours)
    message = build_message(result, args.hours, args.grafana_url)
    print(message)
    if not args.dry_run:
        post_slack(args.slack_webhook, message)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"daily FPS report failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
