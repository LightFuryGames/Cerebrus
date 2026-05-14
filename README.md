# Project Cerebrus

**Cerebrus** is a comprehensive Python-based GUI toolkit designed to streamline Unreal Engine Android profiling workflows. It orchestrates device management, file retrieval, and report generation, providing a deterministic and efficient way to analyze performance data.

## Key Features

### 📱 Device Management
- **Automatic Discovery**: Instantly list connected Android devices via ADB.
- **Profiling Control**: Start and stop CSV profiling directly from the UI.
- **Troubleshooting**: Built-in guidance for common connectivity issues.

### 📂 File Management
- **Smart Retrieval**: Automatically move logs and profiling data (CSV) from your device to your PC.
- **Organized Output**: Automatically organizes files into device-specific folders (e.g., `OutputPath/DeviceModel/`).
- **Flexible Naming**: Configure output filenames with optional prefixing and auto-incrementing counters.

### 📊 Report Generation
- **Performance Reports**: One-click generation of visual performance reports from CSV data using `PerfReportTool`.
    - **Enhanced Metrics**: Includes System Metadata, FPS Analysis, and Average FPS. Supports Dark Mode.
- **Advanced Memory Reporting**: New visualization tool for deep dives into memory usage from `.memreport` files.
- **Colored Logs**: Convert raw text logs into searchable, color-coded HTML files for easier debugging.
- **Batch Processing**: Process multiple files in bulk with a single click.

### ⚙️ Configuration & Customization
- **Profiles**: Save and load project-specific configurations (Package Name, Paths, etc.).
- **Auto-Update**: Automatically checks for and installs the latest version.
- **Cloud Integration**: AWS Secrets Manager and S3 Uploader plugins for secure credential handling and automated report sharing.
- **Themes**: Includes High Contrast and Color Blind modes (Deuteranopia, Tritanopia).
- **Auto-Save**: Your settings are automatically saved to the active profile.

### Plugin System
- **Plugin Tabs**: Runtime plugins add their own tabs to the main workspace.
- **Plugin Menus**: Plugins can add settings or management actions under `Settings -> Plugins`.
- **Plugin Documentation**: Plugin-specific markdown now lives beside the plugin code in [`cerebrus/plugins/`](cerebrus/plugins/README.md).
- **Data-Driven Config**: Plugin state, tooltip resources, AWS region lists, and `.cbx` transfer files use explicit JSON contracts.
- **AWS Export Safety**: `.cbx` exports carry bucket mappings and key aliases only; AWS secret values remain local and must be re-entered after import when needed.
- **Deprecated Path**: The top-level `Plugins/ConversionTools` folder is not the runtime plugin system. Treat it as legacy or experimental conversion tooling until it is migrated.

## Multi-Agent Collaboration

This repo may be edited by Codex, Claude Code, Gemini, Antigravity, and other agents. All agents should read [`AGENTS.md`](AGENTS.md) before making changes. It defines the shared rules for dirty worktrees, plugin modularity, JSON/data contracts, secret handling, testing, and preserving the Antigravity-style HTML user guide.

## Installation

### Using the Installer (Recommended)
1. Download the latest `Cerebrus_Setup.exe` from the Releases page.
2. Run the installer. It will automatically:
   - Install the Cerebrus application.
   - Set up necessary dependencies (Python 3.12+, ADB, .NET 6/8).
   - Create desktop shortcuts.

### Running from Source (Developers)
1. **Clone the repository**:
   ```bash
   git clone <REPO_URL> cerebrus
   cd cerebrus
   ```
2. **Create a virtual environment**:
   ```bash
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Run the application**:
   ```bash
   python -m cerebrus
   ```

### Running Local CI/CD Pipeline
To validate your changes against the official build pipeline locally:

1. **Linting & Formatting**:
   ```powershell
   ./scripts/run_lint.ps1
   ```
2. **Unit Tests**:
   ```powershell
   ./scripts/run_unittests.ps1
   ```
3. **Full Build & Test Loop**:
   ```powershell
   ./run_pipeline.ps1
   ```
   *This script runs linting, testing, and builds the installer executable in `dist/`.*

## What's New in v2.0+

### 🧠 Advanced Memory Profiling
The **MemReport** tool has been overhauled to provide deep insights into Unreal Engine memory dumps (`.memreport` and `obj list`):

- **Object Summary**: High-level overview of total memory by class type (e.g., StaticMesh vs Texture).
- **Class Stats**: Detailed instance tracking to find leaks or heavy assets.
- **Persistent Actors**: Analysis of actor costs specifically in the persistent level.
- **Textures**: VRAM usage breakdown by format, resolution, and compression.
- **RHI Stats**: Hardware interface stats for Vertex Buffers, Index Buffers, and Draw Calls.
- **Render Targets**: Transient GPU memory usage for post-processing and shadow maps.
- **Particle Systems**: CPU simulation costs and memory footprint of FX.
- **Level Loading**: Streaming performance and memory footprint per level.
- **Config Cache**: Memory overhead of loaded INI configuration files.
- **Detailed Lists**: Deep dives into specific complex object lists.

**Key Analysis Features:**
- **Smart Filtering**: Search and sort millions of objects instantly.
- **Interactive Exports**: Save filtered lists as standalone HTML files that support **sub-filtering**, complete with preserved search bars and action buttons.
- **Hierarchy View**: Visualize actor attachment hierarchies with context-aware reset controls.
- **Health Checks**: Automatic warnings for duplicate render targets, huge assets.
- **Data Integrity**: Precise "Reported vs. Calculated" memory metrics (with fixed column-index drift logic).
- **Unit Intelligence**: Automatic scaling of memory to **KB, MB, GB** for easier high-tier device analysis.
- **Metadata-Driven Naming**: Reports are now automatically named based on build configuration, device info, and changelists.
- **Embedded Metadata**: HTML reports now contain a hidden JSON block with all session metadata for downstream processing.

### 📊 Performance Reporting
Powered by **PerfReportTool**, Cerebrus offers robust performance analysis:
- **Bulk Processing**: Process collected CSVs from the selected output folder.
- **Smart Caching**: Manages summary table caches to speed up repeated report generation.
- **Report Types**: Supports standard profiles like `flythrough`, `playthrough`, and `playthroughmemory`.
- **Diff & Regression**: (Experimental) Capabilities to compare runs and highlight regressions.
- **Export Formats**: Generation of HTML reports, CSV summaries, and JSON data tables.

### 🔄 Auto-Update & Deployment
- **Tag-Based workflow**: Updates are triggered by GitHub tags (e.g., `v.2.1.0`).
- **Smart Polling**: The client checks the GitHub API on startup for new releases.
- **Silent Updates**: Downloads and installs updates in the background (admin rights may be requested).
- **Self-Healing**: Installers verify and repair Python/ADB environments automatically.
- **Deterministic CI/CD**: Automated pipelines ensure that every release is fully tested and linted.

## Usage

1. **Launch Cerebrus**.
2. **Select a Profile** or create a new one.
3. **Connect your Android device** and click **List Devices**.
4. **Select your device** from the table.
5. **Configure your Output Path** and **Package Name**.
6. Use the **Bulk Actions** panel to:
   - **Move Logs/CSV**: Pull data from the device.
   - **Generate Reports**: Create HTML reports from the pulled data.

For detailed instructions, access the **User Guide** from the **Help** menu within the application.

## Repository Layout

```text
/cerebrus/                # Core Python packages
  core/                   # Core orchestration logic and abstractions
  plugins/                # Runtime plugins and plugin-local markdown docs
  ui/                     # Dear PyGui UI and layout logic
    components/           # Reusable UI components
      dialogs/            # Application dialogs (app, files, profile)
      panels/             # Usage panels (profiling, logs, device)
    resources/            # UI resources (fonts, palettes, layouts)
  tools/                  # Wrappers around UAFT, CsvTools, PerfReportTool
  config/                 # Configuration and profile definitions
  installers/             # Installer scripts (Inno Setup)
/docs/                    # User + developer documentation
/tests/                   # Automated tests
```

## Continuous Integration

GitHub Actions enforces quality gates on every Pull Request or Push to the **`dev-py`** branch or branches matching the **`Feat/*`** pattern:
1. **Linting**: `black`, `isort`, and `mypy`.
2. **Preflight Checks**: Verifies configuration wiring and data schemas.
3. **Unit Tests**: Runs the `pytest` suite for core logic.

Releases are automatically generated when a tag matching the `v.*.*.*` pattern is pushed, provided the tagged commit is an ancestor of either the **`main`** or **`dev-py`** branches.

## Documentation

The `docs/` directory contains comprehensive documentation for Users, Developers, and Contributors.

### 📘 For Users
- **[User Guide](docs/user_guide.md)**: Master guide on how to use Cerebrus.
- **[Troubleshooting](docs/user/TROUBLESHOOTING.md)**: Solutions for common issues.
- **[Installation](docs/user/INSTALLATION.md)**: Detailed installation steps.
- **[Running Cerebrus](docs/user/RUNNING_CEREBRUS.md)**: How to launch the app.
- **[Device & Capture](docs/user/DEVICE_CAPTURE_WORKFLOWS.md)**: Workflows for profiling.
- **[Reporting](docs/user/REPORTING_AND_ANALYSIS.md)**: Guide to generating reports.
- **[Plugin Guide](cerebrus/plugins/README.md)**: Plugin system and plugin-specific help.

### 🛠️ For Developers
- **[Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)**: High-level system design.
- **[Project Structure](docs/developer/PROJECT_STRUCTURE.md)**: Directory layout and module breakdown (**Auto-maintained**).
- **[Setup & Building](docs/BUILDING.md)**: How to set up the dev environment.
- **[Coding Standards](CODE_STANDARDS.md)**: Guidelines for code style and structure.
- **[Testing Guide](docs/developer/TESTING_GUIDE.md)**: How to run and write tests.
- **[Logging & Errors](docs/developer/LOGGING_AND_ERROR_HANDLING.md)**: Debugging and error handling patterns.
- **[Tool Wrappers](docs/developer/TOOL_WRAPPER_DESIGN.md)**: Design of external tool interfaces.
- **[Plugin Test Plan](cerebrus/plugins/TESTING.md)**: Existing and missing plugin test coverage.

### 🎨 UI & Design
- **[Theme Specification](docs/ui/THEME_SPECIFICATION.md)**: Color palettes and styling rules.
- **[Layout Guidelines](docs/ui/IMGUI_LAYOUT_GUIDELINES.md)**: Best practices for Dear PyGui layouts.
- **[Widget Patterns](docs/ui/WIDGET_PATTERNS.md)**: Reusable UI component patterns.

### 📦 Release & Installers
- **[Auto Update](docs/AUTO_UPDATE.md)**: How the self-updater works.
- **[Windows Installer](docs/installer/WINDOWS_INSTALLER_SPEC.md)**: Inno Setup specifications.
- **[Output Filenames](docs/output_filename_guide.md)**: Naming conventions for generated files.

### 🤖 AI Info
- **[AI Guide](AI_GUIDE.md)**: Rules and context for AI Agents working on this repo.
- **[AI Agent Config](AI_AGENT_CONFIG.md)**: Technical operational rules for AI agents.

### 🔄 Maintenance & Workflows
- **[User Guide Maintenance](.agent/workflows/user-guide-maintenance.md)**: Strict instructions for AI agents on how to update and preserve the `user_guide.html`.

### ✍️ Documentation Guidelines
1. **Keep it Fresh**: Update documentation *immediately* when code changes.
2. **Be Explicit**: Avoid vague descriptions; use examples and file paths.
3. **Structure**: Use the categorization above (User, Developer, UI) for new docs.
4. **Auto-Maintenance**: Files like `PROJECT_STRUCTURE.md` are maintained by AI. Check the file header before editing manually.
