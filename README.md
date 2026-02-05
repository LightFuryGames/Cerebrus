# Project Cerebrus

**Cerebrus** is a comprehensive Python-based GUI toolkit designed to streamline Unreal Engine Android profiling workflows. It orchestrates device management, file retrieval, and report generation, providing a deterministic and efficient way to analyze performance data.

## Key Features

### 📱 Device Management
- **Automatic Discovery**: Instantly list connected Android devices via ADB.
- **Profiling Control**: Start and stop CSV profiling directly from the UI.
- **Remote Control**: Launch or resume your application with a single click.
- **Memory Profiling**: Execute `memreport` and custom console commands remotely.
- **Remote Console**: Execute any custom console command remotely on the device.
- **Troubleshooting**: Built-in guidance for common connectivity issues.

### 📂 File Management
- **Smart Retrieval**: Automatically move logs and profiling data (CSV) from your device to your PC.
- **Recursive Search**: Bulk generation tool now recursively searches directories for files.
- **Organized Output**: Automatically organizes files into device-specific folders (e.g., `OutputPath/DeviceModel/`).
- **Flexible Naming**: Configure output filenames with optional prefixing and auto-incrementing counters.

### 📊 Report Generation
- **Performance Reports**: One-click generation of visual performance reports from CSV data using `PerfReportTool`.
    - **Enhanced Metrics**: Includes System Metadata, FPS Analysis, and Average FPS.
- **Advanced Memory Reporting**: New visualization tool for deep dives into memory usage from `.memreport` files.
- **Colored Logs**: Convert raw text logs into searchable, color-coded HTML files for easier debugging.
- **Batch Processing**: Process multiple files in bulk with a single click.

### ⚙️ Configuration & Customization
- **Profiles**: Save and load project-specific configurations (Package Name, Paths, etc.).
- **Auto-Update**: Automatically checks for and installs the latest version.
- **Cloud Integration**: Configure AWS S3 settings for remote configuration syncing.
- **Themes**: Includes High Contrast and Color Blind modes (Deuteranopia, Tritanopia).
- **Auto-Save**: Your settings are automatically saved to the active profile.

## Installation

### Using the Installer (Recommended)
1. Download the latest `Cerebrus_Setup.exe` from the Releases page.
2. Run the installer. It will automatically:
   - Install the Cerebrus application.
   - Set up necessary dependencies (Python, ADB, .NET 6/8).
   - Create desktop shortcuts.

### Running from Source (Developers)
1. **Clone the repository**:
   ```bash
   git clone <REPO_URL> cerebrus
   cd cerebrus
   ```
2. **Create a virtual environment**:
   ```bash
   py -3 -m venv .venv
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
  ui/                     # Dear PyGui UI and layout logic
  tools/                  # Wrappers around UAFT, CsvTools, PerfReportTool
  config/                 # Configuration and profile definitions
  resources/              # Static resources (icons, user guide)
  installers/             # Installer scripts (Inno Setup)
/docs/                    # User + developer documentation
/tests/                   # Automated tests
```

## Continuous Integration

GitHub Actions enforces:
1. **Linting**: `black`, `isort`, and `mypy`.
2. **Preflight Checks**: Verifies configuration and caching.
3. **Unit Tests**: Runs `pytest`.

## Documentation

- `docs/user_guide.md` — Comprehensive usage instructions.
- `CONTRIBUTING.md` — Contribution guidelines.
- `CODEX_GUIDE.md` — Guide for working with the AI coding assistant.