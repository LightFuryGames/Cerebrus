# Project Cerebrus Architecture Overview

This document describes the high-level architecture of Cerebrus. All implementation work—human and Codex—must align with these boundaries.

## Top-Level Modules

- `cerebrus.core`
  - Application lifecycle and orchestration.
  - Device discovery and workload management.
  - Project configuration and profile definitions.
- `cerebrus.ui`
  - Dear ImGui-based UI.
  - Panels for devices, captures, reports, and configuration.
  - Error and notification surfaces.
- `cerebrus.tools`
  - Thin, testable wrappers around external tools:
    - UAFT (Unreal Android File Tool)
    - CsvTools:
      - CSVCollate
      - CsvConvert
      - CSVFilter
      - CSVSplit
      - CsvToSVG
      - csvinfo
    - PerfReportTool
- `cerebrus.config`
  - Loading, validating, and persisting project configuration.
  - Tool-path configuration and per-project overrides.
- `cerebrus.cache`
  - Per-project cache management.
  - Summary table caches, temporary CSV/PRC processing outputs.
- `cerebrus.installers`
  - Windows-only one-click installer logic.
  - Environment validation: Python, ADB, Unreal tool presence.

## Cross-Cutting Concerns

- **Logging**
  - Central logging abstraction.
  - Clear separation between user-facing messages and diagnostic logs.
- **Error Handling**
  - Fail fast on configuration errors.
  - Graceful degradation and user-visible messages for missing external tools.
- **Configuration**
  - JSON or YAML-based configuration for:
    - Tool paths
    - Device profiles
    - Report types and CSV filters
  - No hardcoded developer-specific paths.
- **Profiles**
  - Named profiles for types of workloads (e.g. flythrough, playthrough, playthroughmemory).
  - Profiles map to:
    - PerfReportTool `-reportType` values.
    - CSV stat filters and thresholds.
    - Device and build metadata expectations.

## External Tools Integration

### UAFT

- Responsible for communicating with Android devices and retrieving artifacts (logs, CSVs, PRCs, Insights captures).
- Cerebrus should:
  - Encapsulate UAFT usage in `cerebrus.tools.uaft`.
  - Provide high-level operations like:
    - `pull_logcat(device, output_dir)`
    - `pull_csv_profiles(device, project_profile, output_dir)`

### CsvTools

- Wrap CsvTools utilities in dedicated modules:
  - `cerebrus.tools.csv.collate` → CSVCollate
  - `cerebrus.tools.csv.convert` → CsvConvert
  - `cerebrus.tools.csv.filter` → CSVFilter
  - `cerebrus.tools.csv.split` → CSVSplit
  - `cerebrus.tools.csv.svg` → CsvToSVG
  - `cerebrus.tools.csv.info` → csvinfo
- Each wrapper should:
  - Accept high-level parameters (paths, stat names, thresholds) rather than raw CLI strings.
  - Assemble the appropriate command line.
  - Execute the process and capture stdout/stderr and exit status.
  - Surface structured results to callers (e.g. output paths, basic parsed info).

### PerfReportTool

- Encapsulate all PerfReportTool usage under `cerebrus.tools.perfreport`.
- Support:
  - Single CSV/PRC report generation.
  - Bulk directory processing with optional recursion and metadata filters.
  - Summary table and JSON export flows.

## UI Layer

- Use Dear ImGui panels for:
  - Device list and selection.
  - Capture orchestration.
  - Report generation and browsing.
  - Configuration editing (tool paths, profiles, cache settings).
- Follow immediate-mode patterns:
  - Read current state, draw, then apply mutations explicitly.
- Keep business logic in `core` and `tools`; the UI calls into those modules.

## Installer and Environment Validation

- One-click Windows installer should:
  - Bundle Python and required packages.
  - Detect presence of ADB and Unreal Engine tools.
  - Configure environment variables or config files accordingly.
  - Avoid admin elevation unless strictly necessary.

- Environment checks:
  - Python version compatibility.
  - Access to UAFT, CsvTools, PerfReportTool binaries.
  - Write access to cache and report directories.

## Extensibility Guidelines

- When adding new capabilities:
  - First update this document to define the new module or boundary.
  - Then implement minimal, coherent slices of functionality.
  - Add tests and documentation for any new external tool integrations.

Keep this overview up to date as the project evolves.
