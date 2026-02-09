# Reporting and Analysis

Cerebrus uses CsvTools and PerfReportTool to transform raw CSV/PRC captures into human-readable reports.

## Overview

From the Reports or Analysis panel, you can:

- Select one or more runs.
- Generate:
  - PerfReportTool HTML reports.
  - Summary CSV tables.
  - SVG graphs using CsvToSVG.
- Compare runs (e.g. baseline vs candidate builds).

## Typical Workflow

1. Choose a **project** and **profile**.
2. Select runs to analyze (by date, build, device).
3. Generate reports:
   - Cerebrus invokes:
     - CSVCollate (if needed) to collate multiple CSVs.
     - PerfReportTool for HTML / CSV / JSON summary generation.
     - CsvToSVG for visual graphs.
4. Inspect:
   - Open generated HTML in a browser.
   - Open CSVs in spreadsheet tools or internal viewers.
   - View SVG graphs directly or from the UI.

## Run Comparison and Regression Detection

Cerebrus can drive PerfReportTool options for regression-focused summaries:

- Only show regressed columns.
- Sort by diff magnitude.
- Highlight outliers.

Profiles can define:

- Which runs are “baseline”.
- Which metrics to prioritize.
- Thresholds for regression alerts.

## Output Locations

Configurable per project but typically:

```text
<ProjectRoot>/
  reports/
    Profiling/          # Performance reports
      <report_name>.html
    Logs/               # Colored logs
      <log_file>.html
    MemReports/         # Memory reports
      <memreport_name>.html
```

## Report Features

Generated HTML reports now include:
- **Dark Mode Toggle**: Switch between light and dark themes.
- **Scroll to Top**: Quickly navigate to the top of long reports.

## Troubleshooting

- If reports fail to generate:
  - Check logs for PerfReportTool or CsvTools errors.
  - Validate metadata (e.g. build ID, device tags).
  - Ensure the correct report type is configured for the profile.

See `docs/user/TROUBLESHOOTING.md` for common failure modes.
