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
    query = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"range": {"@timestamp": {"gte": f"now-{hours}h", "lte": "now"}}},
                    {"exists": {"field": "metrics_fps_avg"}},
                ]
            }
        },
        "aggs": {
            "fps": {
                "stats": {"field": "metrics_fps_avg"}
            },
            "fps_percentiles": {
                "percentiles": {
                    "field": "metrics_fps_avg",
                    "percents": [5, 50, 95],
                }
            },
            "hitches": {"avg": {"field": "metrics_hitches_per_min"}},
            "reports_by_build_device": {
                "terms": {"script": {"lang": "painless", "source": """
                    def b = doc.containsKey('build_cl.keyword') && !doc['build_cl.keyword'].empty ? doc['build_cl.keyword'].value : (doc.containsKey('build_cl') && !doc['build_cl'].empty ? doc['build_cl'].value.toString() : 'Unknown');
                    def d = doc.containsKey('device_id.keyword') && !doc['device_id.keyword'].empty ? doc['device_id.keyword'].value : (doc.containsKey('device_id') && !doc['device_id'].empty ? doc['device_id'].value.toString() : 'Unknown');
                    return b + ' | ' + d;
                """}, "size": 50},
                "aggs": {"fps": {"avg": {"field": "metrics_fps_avg"}}, "count": {"value_count": {"field": "metrics_fps_avg"}}},
            },
        },
    }
    return _request_json(_es_endpoint(es_url, index), query)


def build_message(result: dict, hours: int, grafana_url: str | None) -> str:
    aggregations = result.get("aggregations", {})
    stats = aggregations.get("fps", {}).get("value", None)
    if stats is None:
        stats = aggregations.get("fps", {})
    percentiles = aggregations.get("fps_percentiles", {}).get("values", {})
    buckets = aggregations.get("reports_by_build_device", {}).get("buckets", [])
    total = aggregations.get("fps", {}).get("count", 0)
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
        f"*Samples:* {int(total)}  |  *Average:* {stats.get('avg', 0):.1f} fps",
        f"*FPS distribution:* P05 {percentiles.get('5.0', 0):.1f}  •  Median {percentiles.get('50.0', 0):.1f}  •  P95 {percentiles.get('95.0', 0):.1f}",
    ]
    hitches = aggregations.get("hitches", {}).get("value")
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
