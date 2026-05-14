# Cerebrus Performance Telemetry — Grafana + Elasticsearch Handover

> **Audience:** DevOps engineer setting up dashboards, indices, and alerts for game-performance trend analysis.
> **Status:** Schema v2 (flat). Source-of-truth pipeline: CSV → HTML (PerfReportTool + Cerebrus injectors) → JSON (flat analytics doc) → ES → Grafana.

---

## 1. Pipeline overview

```
Device CSV  ──►  PerfReportTool.exe (vendored Unreal CSV tool)
                       │
                       ▼
                Cerebrus HTML
                       │  injects:
                       │   • metadata rows (DeviceProfile, Scalability Tier,
                       │     DeviceProfile Chain, Report Value, …)
                       │   • FPS Avg column
                       │   • percentile gauges
                       │   • embedded raw CSV  + <script id="cerebrus-metadata">
                       ▼
              Analytics Converter
                       │  • parses raw CSV from HTML (re-extracted)
                       │  • enriches with BaseDeviceProfiles.ini → tier
                       │  • flattens nested groups (build_*, device_*, …)
                       │  • applies sentinels for missing fields
                       │  • computes report_value (1-100)
                       ▼
                  Flat JSON doc  ──►  Elasticsearch  ──►  Grafana
```

---

## 2. JSON document — flat schema (v2)

Every document is a **single-level flat object**, one doc per profiling run.

### Top-level metadata

| Field | Type | Example |
|---|---|---|
| `@timestamp` | date | `2026-04-27T05:08:58Z` |
| `schema_version` | integer | `2` |
| `source_type` | keyword | `profiling_html_raw_csv` |
| `source_name` | keyword | `Profile(20260427_050858).html` |
| `source_file` | keyword | absolute path |
| `device_id` | keyword | `samsung_SM-S948U1` |
| `report_fingerprint` | keyword | SHA-256, used as ES `_id` |

### Field-name prefixes

| Prefix | Meaning | ES type |
|---|---|---|
| `build_*` | project / branch / CL / config | keyword + int/float |
| `device_*` | manufacturer / model / GPU / profile / tier / chain | keyword |
| `capture_*` | session metadata (frame count, duration, timestamps) | keyword / long / float |
| `metrics_*` | numeric perf metrics (FPS, frametimes, memory, etc.) | float |
| `threshold_counts_*` | frame-time bucket counts | integer |
| `flags_*` | build flags (0/1) | integer |
| `extra_*` | unmapped passthrough fields | keyword |
| `data_quality_*` | corruption tracking | int / keyword |
| `report_value` | universal 1–100 weight | integer |

### Sentinels for missing/corrupt fields

| Sentinel | Meaning | Field types |
|---|---|---|
| `-1` | numeric missing | `metrics_*`, `capture_frame_count`, `build_cl`, … |
| `"Unknown"` | string missing | `device_tier`, `device_profile`, `build_config`, … |
| `2000-01-01T00:00:00Z` | timestamp missing | `@timestamp` |

`data_quality_has_corruption` is `1` whenever any expected field was sentineled.

---

## 3. The `report_value` weight (1–100)

A single integer per document combining **data volume** + **data quality**. Use as the `weight` field in every Grafana weighted_avg aggregation. **One weight to rule them all.**

### Formula

```
report_value = round( 100 × (
      0.50 × min(frame_count / 36000, 1)        // volume    – capped at 10 min @ 60 fps
    + 0.25 × min(duration_s  / 600,   1)        // duration  – capped at 10 minutes
    + 0.10 × consistency_score                  // observed_fps within ±25% of target
    + 0.15 × (1 - missing_fields / expected)    // completeness
) ), clamped [1, 100]
```

### Reference values (current TestData)

| Profile | Frames | Duration | Tier | report_value |
|---|---:|---:|---|---:|
| samsung_SM-S948U1 Profile(20260425_152533) | 14138 | 239.8 s | Epic | **55** |
| samsung_SM-S948U1 Profile(20260425_144238) | 10690 | 179.2 s | Epic | 47 |
| samsung_SM-G770F Profile(20260427_152033) | 8764 | 159.0 s | Medium | 44 |
| OnePlus_ONEPLUS A3003 Profile(20260427_050858) | 6388 | 204.4 s | Low | 38 |
| OnePlus_ONEPLUS A3003 Profile(20260511_083213) | 1410 | 122.9 s | Low | 24 |
| Corrupt_all_expected_fields.json | — | — | Unknown | **1** |

Healthy runs land 30–60. Short captures and corrupt data trend toward 1.

---

## 4. Elasticsearch — index setup

### Index template (one-time)

```bash
curl -X PUT 'http://es:9200/_index_template/telemetry-cerebrus-performance' \
  -H 'Content-Type: application/json' -d @index-template.json
```

```jsonc
{
  "index_patterns": ["telemetry-cerebrus-performance*"],
  "template": {
    "settings": {
      "index.mapping.total_fields.limit": 2000,
      "index.mapping.depth.limit": 1,
      "number_of_shards": 1,
      "number_of_replicas": 1
    },
    "mappings": {
      "dynamic": true,
      "date_detection": false,
      "properties": {
        "@timestamp":              { "type": "date" },
        "schema_version":          { "type": "integer" },
        "source_type":             { "type": "keyword" },
        "source_file":             { "type": "keyword" },
        "source_name":             { "type": "keyword" },
        "device_id":               { "type": "keyword" },
        "report_fingerprint":      { "type": "keyword" },
        "report_value":            { "type": "integer" },
        "build_config":            { "type": "keyword" },
        "build_branch":            { "type": "keyword" },
        "build_project":           { "type": "keyword" },
        "build_version":           { "type": "keyword" },
        "build_engine_version":    { "type": "keyword" },
        "build_cl":                { "type": "integer" },
        "build_program_size_mb":   { "type": "float"   },
        "device_platform":         { "type": "keyword" },
        "device_os_name":          { "type": "keyword" },
        "device_os_version":       { "type": "keyword" },
        "device_manufacturer":     { "type": "keyword" },
        "device_model":            { "type": "keyword" },
        "device_gpu":              { "type": "keyword" },
        "device_profile":          { "type": "keyword" },
        "device_profile_root":     { "type": "keyword" },
        "device_profile_chain":    { "type": "keyword" },
        "device_profile_chain_depth": { "type": "integer" },
        "device_profile_reference":      { "type": "keyword" },
        "device_profile_reference_sha1": { "type": "keyword" },
        "device_tier":             { "type": "keyword" },
        "capture_csv_id":          { "type": "keyword" },
        "capture_start_timestamp": { "type": "long" },
        "capture_end_timestamp":   { "type": "long" },
        "capture_target_fps":      { "type": "integer" },
        "capture_frame_count":     { "type": "integer" },
        "capture_excluded_frame_count": { "type": "integer" },
        "capture_duration_s":      { "type": "float" },
        "capture_total_time_s":    { "type": "float" },
        "capture_command_line":    { "type": "text" },
        "data_quality_has_corruption": { "type": "integer" },
        "data_quality_missing_count":  { "type": "integer" },
        "data_quality_missing_fields": { "type": "keyword" }
      },
      "dynamic_templates": [
        { "metrics_floats":  { "match": "metrics_*",          "mapping": { "type": "float"   } } },
        { "thresholds_int":  { "match": "threshold_counts_*", "mapping": { "type": "integer" } } },
        { "flags_int":       { "match": "flags_*",            "mapping": { "type": "integer" } } },
        { "extra_keyword":   { "match": "extra_*",            "mapping": { "type": "keyword" } } }
      ]
    }
  }
}
```

### Ingest

- **Single doc:** `PUT /telemetry-cerebrus-performance/_doc/<report_fingerprint>` (Cerebrus does this when configured).
- **Bulk:** Cerebrus `export_elasticsearch_bulk` → NDJSON → `POST /_bulk?refresh`.
- `_id = report_fingerprint` ⇒ re-uploads are idempotent.

### ILM (recommended)

```jsonc
PUT _ilm/policy/cerebrus-perf
{ "policy": { "phases": {
  "hot":    { "actions": { "rollover": { "max_age": "30d", "max_primary_shard_size": "10gb" } } },
  "warm":   { "min_age": "30d",  "actions": { "shrink": { "number_of_shards": 1 }, "forcemerge": { "max_num_segments": 1 } } },
  "delete": { "min_age": "365d", "actions": { "delete": {} } }
} } }
```

---

## 5. Grafana — datasource + variables

### 5.1 Datasource

- **Type:** Elasticsearch
- **URL:** `http://<es>:9200`
- **Index pattern:** `telemetry-cerebrus-performance*`
- **Time field:** `@timestamp`
- **Version:** ≥ 7.10
- **Default query (filters corrupt rows globally):**
  ```
  data_quality_has_corruption:0 AND capture_frame_count:>=600
  ```

### 5.2 Dashboard variables (templating)

Create in `Dashboard settings → Variables → New`.

| Name | Type | Query | Multi | Include All |
|---|---|---|---|---|
| `$device` | Query | `{ "find": "terms", "field": "device_id" }` | ✅ | ✅ |
| `$tier` | Query | `{ "find": "terms", "field": "device_tier" }` | ✅ | ✅ |
| `$gpu` | Query | `{ "find": "terms", "field": "device_gpu" }` | ✅ | ✅ |
| `$profile_root` | Query | `{ "find": "terms", "field": "device_profile_root" }` | ✅ | ✅ |
| `$branch` | Query | `{ "find": "terms", "field": "build_branch" }` | ✅ | ✅ |
| `$config` | Query | `{ "find": "terms", "field": "build_config" }` | ✅ | ✅ |
| `$min_frames` | Custom | `60, 600, 1800, 3600, 7200` (default `600`) | ❌ | ❌ |
| `$min_report_value` | Custom | `1, 10, 25, 50, 75` (default `10`) | ❌ | ❌ |

These plug into every panel query for **smart filtering**:

```
data_quality_has_corruption:0 AND
device_id:($device) AND device_tier:($tier) AND device_gpu:($gpu) AND
build_branch:($branch) AND build_config:($config) AND
capture_frame_count:>=$min_frames AND
report_value:>=$min_report_value
```

---

## 6. Panels — replacement for current dashboard

Reference: the existing `E-Cricket Performance Trends` dashboard (per-device, time series). Below is the v2 layout with weighting + tier comparison.

### 6.1 Headline KPIs (Stat panels, row 1)

| Panel title | Query | Notes |
|---|---|---|
| Weighted FPS Avg | `weighted_avg(metrics_fps_avg, report_value)` | The single most-important number |
| Weighted Frametime Avg (ms) | `weighted_avg(metrics_frametime_avg_ms, report_value)` | |
| Capture Volume (frames) | `sum(capture_frame_count)` | Sanity for data ingest |
| Reports Indexed | `count` | Compare vs. yesterday for ingestion alarms |
| Corruption Ratio (%) | `count(data_quality_has_corruption:1) / count() × 100` | Data-quality monitor |

### 6.2 Time-series — Averages (replaces existing "Averages" panel)

```
Aggregation : Weighted Average
Value field : metrics_fps_avg
Weight field: report_value
Group by    : Date Histogram on @timestamp, interval = $__auto
Split by    : Terms on device_tier   (size 4)
```

Repeat for: `metrics_frametime_avg_ms`, `metrics_game_thread_avg_ms`, `metrics_render_thread_avg_ms`, `metrics_gpu_avg_ms`.

### 6.3 Time-series — Average Time (ms)

Same as 6.2 but multiple metric series in one panel:
- `metrics_game_thread_avg_ms`
- `metrics_render_thread_avg_ms`
- `metrics_rhi_thread_avg_ms`
- `metrics_gpu_avg_ms`
- `metrics_frametime_avg_ms`

All as Weighted Average using `report_value`. Split by `$tier` for cohort lines.

### 6.4 Time-series — Memory

- `weighted_avg(metrics_memory_free_min_mb, report_value)`
- `weighted_avg(metrics_physical_used_max_mb, report_value)`

### 6.5 Time-series — Deviations

- `weighted_avg(metrics_fps_stddev, report_value)`
- `weighted_avg(metrics_fps_iqr,    report_value)`

### 6.6 Cohort comparison (Bar / Table)

```
Aggregation : Weighted Average  → metrics_fps_avg / report_value
Group by    : Terms device_tier  (then Terms build_branch)
```

Lets you read: **on branch X, tier Epic averages Y fps vs. tier Low Z fps.**

### 6.7 GPU-family rollup (Table)

```
Group by : Terms device_gpu, size 20
Metrics  : Weighted Average  → metrics_fps_avg / report_value
           Sum               → capture_frame_count
           Avg               → report_value
```

Useful for spotting GPU-family regressions independent of tier.

### 6.8 Data-quality diagnostics (Stat + Bar)

- **Stat:** `count(data_quality_has_corruption:1) / count() × 100` → "% corrupt"
- **Bar:** Top `data_quality_missing_fields` (Terms agg). Surface which fields the engine is failing to emit.
- **Bar:** `count` split by `report_value` bucketed in `[0–10, 10–25, 25–50, 50–75, 75–100]`.

### 6.9 Percentile panels (no weighting needed; values are pre-computed per-run)

Plain `avg(metrics_fps_p01)`, `avg(metrics_fps_p95)` grouped by tier/device. Per-run percentiles are already stable summaries; weighting changes them less than raw averages.

---

## 7. Raw ES query examples (copy-paste into Dev Tools)

### 7.1 Weighted FPS over time, by tier

```jsonc
GET telemetry-cerebrus-performance*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term":  { "data_quality_has_corruption": 0 } },
        { "range": { "capture_frame_count":          { "gte": 600 } } }
      ]
    }
  },
  "aggs": {
    "ts": {
      "date_histogram": { "field": "@timestamp", "calendar_interval": "1d" },
      "aggs": {
        "by_tier": {
          "terms": { "field": "device_tier", "size": 4 },
          "aggs": {
            "wfps": {
              "weighted_avg": {
                "value":  { "field": "metrics_fps_avg" },
                "weight": { "field": "report_value"    }
              }
            }
          }
        }
      }
    }
  }
}
```

### 7.2 Top 10 GPUs by weighted Frametime regression vs. baseline

```jsonc
GET telemetry-cerebrus-performance*/_search
{
  "size": 0,
  "query": { "term": { "data_quality_has_corruption": 0 } },
  "aggs": {
    "by_gpu": {
      "terms": { "field": "device_gpu", "size": 10, "order": { "wft": "desc" } },
      "aggs": {
        "wft": {
          "weighted_avg": {
            "value":  { "field": "metrics_frametime_avg_ms" },
            "weight": { "field": "report_value" }
          }
        }
      }
    }
  }
}
```

### 7.3 Detect runs where observed vs. target FPS is way off (data sanity)

```jsonc
GET telemetry-cerebrus-performance*/_search
{
  "size": 10,
  "_source": ["@timestamp","device_id","metrics_fps_avg","capture_target_fps","report_value"],
  "query": {
    "script": {
      "script": "doc['capture_target_fps'].value > 0 && Math.abs(doc['metrics_fps_avg'].value / doc['capture_target_fps'].value - 1) > 0.5"
    }
  }
}
```

---

## 8. Alerting rules

| Alert | Condition | Severity |
|---|---|---|
| **Corruption surge** | `count(data_quality_has_corruption:1)/count() > 0.05` for 1 h | warning |
| **No reports** | `count() == 0` for 6 h on a known active branch | critical |
| **Tier-cohort regression** | Weighted FPS for `device_tier=Epic` drops > 10 % vs. 7-day baseline | warning |
| **GPU-family regression** | Weighted Frametime for any `device_gpu` rises > 15 % vs. 14-day baseline | warning |
| **Low-quality flood** | `avg(report_value) < 20` for 24 h | informational |

---

## 9. Smart filtering — recipes

| Goal | Filter |
|---|---|
| Trust only high-confidence trend data | `report_value:>=50` |
| Exclude micro-captures | `capture_frame_count:>=1800` |
| Per-device drill-down | `device_id:"samsung_SM-S948U1"` |
| Compare same tier across GPU families | Group by `device_gpu`, filter `device_tier:"Epic"` |
| Compare same build across all tiers | Filter `build_cl:32261`, split by `device_tier` |
| Audit fallback classifications | `device_tier_source:"gpu_heuristic"` *(field removed in v2 — left here for archive; ignore)* |
| Investigate corrupt cohort | `data_quality_has_corruption:1` (manual review only) |

---

## 10. Pipeline operational notes

- **BaseDeviceProfiles.ini** must be configured in Cerebrus Analytics Settings before generating reports. Tier enrichment depends on it. `device_profile_reference_sha1` records the ini content hash in every doc — use it to trace tier mis-classifications back to a specific ini version.
- **Schema bumps**: when `schema_version` changes, swap the index template + alias atomically. Don't reindex unless dashboards need historical recomputation.
- **Tier fallback cascade**: `ini_chain` → `gpu_heuristic` → `Unknown`. If tier shows `Unknown` for a known device, check (1) ini configured, (2) `DeviceProfile` row present in CSV footer.
- **`report_value` recompute**: changing the formula requires re-ingest if you want historical docs to use the new score. The field is a static int per doc, computed at ingest time.

---

## 11. `report_value` — per-run isolation (no external reads)

`report_value` is computed entirely from the doc's own fields. Cerebrus has **no read access** to Elasticsearch or Grafana, and the formula has no cross-doc lookups. Each run is scored standalone.

### Inputs (all local to the doc)

| Input | Source |
|---|---|
| `frame_count` | `flat["capture_frame_count"]` — same doc |
| `duration_s` | `flat["capture_duration_s"]` — same doc |
| `target_fps` | `flat["capture_target_fps"]` — same doc |
| `missing_count` | result of local sentinel pass over same doc |
| `total_expected` | static constant (`len(EXPECTED_FIELDS)`) |

The formula is stateless and deterministic — re-running on the same input always yields the same integer. Safe for repeatable build pipelines.

### HTML / JSON parity

The HTML report's "Report Value (1–100)" row, the embedded `<script id="cerebrus-metadata">` JSON block, and the analytics JSON document that gets indexed in Elasticsearch all use the **same code path** ([file_manager.py](../cerebrus/ui/components/file_manager.py) routes through `PerformanceCSVReportParser` → `build_analytics_document` → reads `report_value` off the result). The number you see in the HTML metadata table is the exact number indexed in ES.

> **Note for devops.** Do not synthesize a "report value" yourself in an ingest pipeline — use the one Cerebrus already wrote into the doc. Any post-hoc computation will drift from what the HTML viewer shows users.

---

## 12. Fingerprinting — preventing duplicates in Elasticsearch

### How the fingerprint is built

```
report_fingerprint = SHA-256(
    @timestamp,
    build.{project, branch, cl, config},
    device.{manufacturer, model, gpu, profile},
    capture.{csv_id, start_timestamp, end_timestamp, frame_count}
)
```

Same physical report → same hash → same ES `_id` → upsert. Different captures produce different hashes (CSV id, start/end timestamps, and frame count make collisions practically impossible).

### Cerebrus uploaders already use `_id = report_fingerprint`

| Cerebrus method | Behavior |
|---|---|
| `export_elasticsearch_bulk` | Emits `{"create":{"_index":..., "_id": <report_fingerprint>}}` NDJSON action lines |
| `push_document_to_elasticsearch` | Issues `PUT /<index>/_doc/<report_fingerprint>` when the endpoint URL ends with `/_doc` |

If you ingest using Cerebrus's own paths, dedup is automatic — re-uploading the same report overwrites the existing doc instead of creating a new one.

### Where duplicates can still slip in

Any ingest path that lets Elasticsearch auto-generate `_id` will create one new doc per upload.

| Ingest method | Default `_id` | Result |
|---|---|---|
| `POST /<index>/_doc` (no id) | Random UUID | **Duplicate per upload** |
| `_bulk` with `index` action and no `_id` | Random UUID | **Duplicate per upload** |
| Filebeat with no `document_id` configured | Random UUID | **Duplicate per upload** |
| Logstash ES output without `document_id` | Random UUID | **Duplicate per upload** |

### Required configuration — force `_id = report_fingerprint`

**Raw `_bulk` body** (matches what Cerebrus emits natively):
```
{ "index": { "_index": "telemetry-cerebrus-performance", "_id": "<report_fingerprint>" } }
{ ...flat doc... }
```

**Single document PUT:**
```
PUT /telemetry-cerebrus-performance/_doc/<report_fingerprint>
{ ...flat doc... }
```

**Logstash:**
```ruby
output {
  elasticsearch {
    hosts        => ["http://es:9200"]
    index        => "telemetry-cerebrus-performance-%{+YYYY.MM}"
    document_id  => "%{report_fingerprint}"
    action       => "index"   # idempotent upsert
  }
}
```

**Filebeat:**
```yaml
processors:
  - copy_fields:
      fields:
        - { from: "report_fingerprint", to: "@metadata._id" }

output.elasticsearch:
  hosts: ["http://es:9200"]
  index: "telemetry-cerebrus-performance-%{+yyyy.MM}"
```

### Audit existing duplicates

```jsonc
GET telemetry-cerebrus-performance*/_search
{
  "size": 0,
  "aggs": {
    "dup_check": {
      "terms": { "field": "report_fingerprint", "min_doc_count": 2, "size": 50 }
    }
  }
}
```
Should return no buckets after the ingest config above is in place. Any bucket listed represents a fingerprint that exists more than once — surfaces ingest-pipeline misconfiguration immediately.

### Reindex to collapse historical duplicates

If duplicates already exist in the cluster, copy through `_reindex` while forcing `_id` from the doc body:

```jsonc
POST _reindex
{
  "source": { "index": "telemetry-cerebrus-performance-old" },
  "dest":   { "index": "telemetry-cerebrus-performance-new", "op_type": "index" },
  "script": { "source": "ctx._id = ctx._source.report_fingerprint" }
}
```

Then swap aliases so dashboards point at `*-new`. Duplicates collapse into one doc per fingerprint; ILM eventually deletes the old index.

### Why this matters for Grafana

Without dedup, weighted_avg panels double-count high-`report_value` reports that were uploaded multiple times, skewing trend lines. Idempotent `_id` keeps cohort math honest regardless of how often the same report is re-ingested.

---

## 13. Glossary

| Term | Definition |
|---|---|
| **Tier** | Scalability tier (Low / Medium / High / Epic / Unknown) derived from `BaseProfileName` chain in BaseDeviceProfiles.ini. |
| **Chain** | The walk from the device's `DeviceProfile` up through `BaseProfileName` references until a tier sentinel (`Android_Low`/`_Mid`/`_High`/`_Epic`) is hit. |
| **Report fingerprint** | SHA-256 of `(timestamp, build, device, capture)` — used as ES `_id` for idempotent uploads. |
| **Report Value** | A 1–100 universal weight combining data volume + quality. Used as the `weight` for every weighted_avg agg. |
| **Sentinel** | Placeholder value (`-1`, `"Unknown"`, `2000-01-01T00:00:00Z`) written when a field is missing/corrupt. Lets ES mapping stay stable and dashboards filter cleanly. |
| **Corrupt doc** | Any doc with `data_quality_has_corruption:1`. Filter out of dashboards by default; surface only in diagnostics. |
