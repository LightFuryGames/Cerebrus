# Analytics & Trends Plugin

`AnalyticsPlugin` converts generated Cerebrus and Unreal profiling artifacts into
stable analytics documents for trends, comparisons, and Elasticsearch/OpenSearch
ingestion.

## What Users See

The plugin adds the `Analytics & Trends` tab. From the tab a user can:

- **Source File** — HTML, CSV, or existing `.analytics.json` report. After a
  successful Convert this field is auto-filled with the generated JSON so the
  next click can be Upload.
- **Output File Path** (optional) — Folder where `.analytics.json` is written
  by Convert. If empty, the JSON is written next to the Source File. When set
  with no Source File, every `.analytics.json` in this folder becomes the
  Upload target list.
- **Upload Endpoint** — Elasticsearch `_doc` endpoint, e.g.
  `http://host:9200/telemetry-cerebrus-performance/_doc`. Persisted to the
  local Cerebrus app data folder as `analytics_settings.json`.
- **Convert File to Analytics JSON** — turn one HTML, CSV, or legacy flat JSON
  report into `.analytics.json` (schema v2, flat keys). Honours Output File
  Path; falls back to writing next to the source.
- **Upload Analytics Document** — POST/PUT one or every `.analytics.json` to
  the configured `_doc` endpoint. PUT uses `report_fingerprint` as `_id` so
  re-uploads are idempotent.
- **Delete Analytics JSON after Upload Success** — checkbox; deletes only the
  `.analytics.json` source after the per-target push confirms success. Failed
  targets are always kept.

Bulk `_bulk` upload and the folder-wide trend-summary CSV are still available
as a library API in `cerebrus.plugins.analytics.controller.AnalyticsController`
(`upload_bulk`, `build_trend_summary`) and `cerebrus.plugins.analytics.core.converter`
(`export_elasticsearch_bulk`, `summarize_folder`) for CLI/CI callers, but the
in-app tab now exposes only the single-document workflow.

## Data Shape

Converted files use schema version **2** with a **flat, snake_case** key
layout (no nested `build` / `device` / `capture` objects):

```json
{
  "schema_version": 2,
  "@timestamp": "2026-04-27T15:20:33Z",
  "source_type": "profiling_csv",
  "source_file": "C:/Reports/Profile(20260427_152033).csv",
  "source_name": "Profile(20260427_152033).csv",
  "report_fingerprint": "sha256...",
  "device_id": "Samsung_SM-G991B",
  "device_manufacturer": "Samsung",
  "device_model": "SM-G991B",
  "device_gpu": "Adreno",
  "device_platform": "Android",
  "device_profile": "Android_Adreno6xx_Vulkan",
  "device_tier": "High",
  "build_project": "titan-game",
  "build_branch": "development",
  "build_cl": 123456,
  "build_config": "Test",
  "build_version": "++titan-game+development-CL-123456",
  "build_engine_version": "5.5.4-123456+++titan-game+development",
  "capture_target_fps": 60,
  "capture_frame_count": 12000,
  "capture_excluded_frame_count": 0,
  "capture_duration_s": 200.0,
  "metrics_fps_avg": 58.2,
  "metrics_frametime_avg_ms": 17.1,
  "metrics_hitches_per_min": 2.4,
  "metrics_fps_p01": 42.0,
  "metrics_mvp60": 88.5,
  "threshold_counts_frame_time_gt_60ms": 3,
  "flags_pgo_enabled": 0,
  "report_value": 87,
  "data_quality_has_corruption": 0
}
```

All keys are snake_case. Logical groups are encoded via stable prefixes
(`build_`, `device_`, `capture_`, `metrics_`, `threshold_counts_`, `flags_`).
This keeps the Elasticsearch mapping flat and stable; new report columns add a
new key with the same prefix instead of mutating a nested object's shape.

`report_value` is a 1–100 integer used as the Grafana `weighted_avg` weight
(longer / cleaner / on-target captures score higher).
`data_quality_has_corruption` is a 0/1 flag the converter sets when sentinel
substitutions had to be made because the underlying CSV footer was truncated.

The `report_fingerprint` is computed from stable build, device, and capture
identity fields. Online single uploads use `PUT /_doc/{report_fingerprint}`
when the configured endpoint ends in `/_doc`. Both online bulk
(`ElasticsearchClient.push_bulk`) and offline NDJSON export
(`export_elasticsearch_bulk`) use the `index` action keyed by fingerprint, so
re-uploads are idempotent (upsert, not insert-only).

Percentile metrics are FPS percentiles derived from each frame's `FrameTime`
sample (`fps = 1000 / FrameTime`). They are therefore frame-sample percentiles
over the capture, not raw frame-time percentiles.

## Upload Modes

| Mode | Surface | Network | Notes |
|---|---|---|---|
| Single doc | "Upload Analytics Document" button | One HTTP request per target | The only mode reachable from the UI. Lets users see per-document failure rows; `report_fingerprint` is used as `_id` so re-uploads are idempotent. |
| Bulk (`_bulk`) | `AnalyticsController.upload_bulk` (library only) | One HTTP request for all targets | For CI/CLI use. Same delete-after-success, reverse-proxy prefix, and keyword-mapping guarantees as single-doc mode. |

Both modes route through `AnalyticsController` and `ElasticsearchClient`, so
delete-after-success, reverse-proxy URL prefixes, and the keyword-friendly
index mapping behave identically.

## Relationship To Profiling

The `Profiling` plugin owns live device capture and report generation. The
`Analytics` plugin owns post-processing: conversion, normalization, trend files,
and external analytics exports.

The parser/converter modules live in `cerebrus/plugins/analytics/core` because
they are plugin-owned support code, not part of the global Cerebrus runtime.
The UI-agnostic orchestration sits in `cerebrus/plugins/analytics/controller.py`
(`AnalyticsController`) so the same pipeline can be exercised from tests, CLI
scripts, and CI without spinning up DPG.

## Current Limitations

- Folder summaries include discovered metric columns, but do not yet render an
  in-app trend chart.
- HTML parsing supports current Unreal/Cerebrus performance report tables and
  may need small adapters if report markup changes.
