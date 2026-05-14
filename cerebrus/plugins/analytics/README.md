# Analytics & Trends Plugin

`AnalyticsPlugin` converts generated Cerebrus and Unreal profiling artifacts into
stable analytics documents for trends, comparisons, and Elasticsearch/OpenSearch
ingestion.

## What Users See

The plugin adds the `Analytics & Trends` tab. This tab can:

- Convert one HTML, CSV, or legacy flat JSON report into `.analytics.json`.
- Upload one normalized analytics document to a configured Elasticsearch/OpenSearch `_doc` endpoint.
- Scan a report folder and write `analytics_summary.csv`.

Bulk export support exists in the analytics core, but the visible tab workflow is
hidden until the bulk ingestion UX is redesigned.

## Data Shape

Converted files use a common JSON shape:

```json
{
  "schema_version": 1,
  "@timestamp": "2026-04-27T15:20:33Z",
  "source_type": "profiling_csv",
  "source_file": "C:/Reports/Profile(20260427_152033).csv",
  "source_name": "Profile(20260427_152033).csv",
  "report_fingerprint": "sha256...",
  "device_id": "Samsung_SM-G991B",
  "build": {
    "project": "titan-game",
    "branch": "development",
    "cl": 123456,
    "config": "Test",
    "version": "++titan-game+development-CL-123456",
    "engine_version": "5.5.4-123456+++titan-game+development"
  },
  "device": {
    "device_id": "Samsung_SM-G991B",
    "manufacturer": "Samsung",
    "model": "SM-G991B",
    "gpu": "Adreno",
    "platform": "Android",
    "profile": "Android_Adreno6xx_Vulkan",
    "tier": "High"
  },
  "capture": {
    "target_fps": 60,
    "frame_count": 12000,
    "excluded_frame_count": 0,
    "duration_s": 200.0
  },
  "metrics": {
    "fps_avg": 58.2,
    "frametime_avg_ms": 17.1,
    "hitches_per_min": 2.4,
    "fps_p01": 42.0,
    "mvp60": 88.5
  },
  "threshold_counts": {
    "frame_time_gt_60ms": 3
  },
  "flags": {
    "pgo_enabled": 0
  },
  "extra": {}
}
```

All generated JSON keys use snake_case. Known fields are grouped under stable
objects (`build`, `device`, `capture`, `metrics`, `threshold_counts`, and
`flags`). Unknown future key-value pairs are normalized into `extra` so the
Elasticsearch mapping does not grow a new top-level field for every new report
column.

The `report_fingerprint` is computed from stable build, device, and capture
identity fields. Bulk exports use it as the Elasticsearch `_id` with a `create`
action, and single uploads use `PUT /_doc/{report_fingerprint}` when the
configured endpoint ends in `/_doc`. This makes accidental repeated uploads
idempotent instead of producing duplicate analytics rows.

Percentile metrics are FPS percentiles derived from each frame's `FrameTime`
sample (`fps = 1000 / FrameTime`). They are therefore frame-sample percentiles
over the capture, not raw frame-time percentiles.

## Relationship To Profiling

The `Profiling` plugin owns live device capture and report generation. The
`Analytics` plugin owns post-processing: conversion, normalization, trend files,
and external analytics exports.

The parser/converter modules live in `cerebrus/plugins/analytics/core` because
they are plugin-owned support code, not part of the global Cerebrus runtime.

## Current Limitations

- Folder summaries include discovered metric columns, but do not yet render an
  in-app trend chart.
- The upload endpoint is stored in the local Cerebrus app data folder as
  `analytics_settings.json`.
- Upload currently posts one normalized document at a time to the configured
  endpoint.
- HTML parsing supports current Unreal/Cerebrus performance report tables and
  may need small adapters if report markup changes.
