# Project Cerebrus Architecture Overview

This document describes the high-level architecture of Cerebrus. All implementation work—human and AI—must align with these boundaries.

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
    - ADB (Android Debug Bridge)
    - CsvTools (CSVCollate, CsvConvert, CSVFilter, CSVSplit, CsvToSVG, csvinfo)
    - PerfReportTool
    - MemReport (Modular generic parsing and HTML visualizer)
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

### ADB Wrapper
- Responsible for communicating with Android devices via `adb` to manage application state and retrieve artifacts (logs, CSVs, PRCs, Insights captures).
- Cerebrus encapsulates ADB usage in `cerebrus.tools.adb.AdbClient`.
- High-level operations include:
  - `list_devices()`
  - `get_package_info(device, package)`
  - `pull_file(device, remote_path, local_path)`
  - `shell_command(device, cmd)`

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

### MemReport Tool
- **Pattern**: Modular Tool Pattern (Data -> Parser -> Analyzer -> Renderer).
- **Extensibility**: Logic is split into independent `ReportTabs`.
- **Output**: Single-file, self-contained HTML with embedded JS for interactivity.

## UI Layer

Cerebrus employs two distinct UI technologies optimized for different use cases:

### 1. Control Plane (Desktop App)
- **Technology**: **Dear PyGui** (wrapping Dear ImGui).
- **Purpose**: Real-time control, device management, and tool orchestration.
- **Characteristics**: Fast, native, immediate-mode, requires Python runtime.

### 2. Data Plane (Generated Reports)
- **Technology**: **HTML5 / CSS3 / Vanilla JS**.
- **Purpose**: Viewing static analysis data (MemReports, Perf Diffs).
- **Characteristics**: Portable (can be emailed), zero-dependency (runs in any browser), completely decoupled from the main app.
- **Note**: These files do **not** use ImGui.

- **Pattern**: Functional UI Components (Stateless rendering functions).
  - Components receive `State` and return `Events`.
  - No direct mutation of state inside draw calls.
- **Scaling**: All layouts use relative sizing / DPI-aware style variables.

## Future Architecture (Roadmap)

- **Plugin System**:
  - `cerebrus.plugins` module to load external Python files at runtime.
  - Strict `Protocol` interfaces for Tabs and Device Actions.
- **Event Sourcing**:
  - Central event bus for QA Macro recording/replay.

## Installer and Environment Validation

- One-click Windows installer should:
  - Bundle Python and required packages.
  - Detect presence of ADB and Unreal Engine tools.
  - Configure environment variables or config files accordingly.
  - Avoid admin elevation unless strictly necessary.

- Environment checks:
  - Python version compatibility (3.12+).
  - Access to UAFT, CsvTools, PerfReportTool binaries.
  - Write access to cache and report directories.

## Extensibility Guidelines

- When adding new capabilities:
  - First update this document to define the new module or boundary.
  - Then implement minimal, coherent slices of functionality.
  - Add tests and documentation for any new external tool integrations.

Keep this overview up to date as the project evolves.
