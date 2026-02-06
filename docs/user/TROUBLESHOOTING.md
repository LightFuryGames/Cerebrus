# Troubleshooting

This guide lists common issues and suggested resolutions.

## Installation Issues

- **Problem**: Installer fails or Python environment not created.
  - **Check**:
    - Disk space.
    - Antivirus or security software interfering with executables.
  - **Remedy**:
    - Temporarily disable real-time scanning during install.
    - Run installer again.
    - For manual install, verify `python` is available on PATH. And `python --version` return value > 3.12.

## External Tools Not Found

- **Problem**: Cerebrus reports that UAFT or CsvTools/PerfReportTool cannot be found.
  - **Check**:
    - Paths configured in `config/tools.paths.json`.
    - That the binaries actually exist at those paths.
  - **Remedy**:
    - Correct the paths.
    - Ensure Unreal Engine installation is intact.

## No Devices Visible

- **Problem**: Device panel is empty.
  - **Check**:
    - `adb devices` from a command prompt.
    - USB debugging enabled on device.
    - Correct drivers installed.
  - **Remedy**:
    - Reconnect device and approve the host PC’s RSA key.
    - Restart ADB server: `adb kill-server` then `adb start-server`.

## Capture Failures

- **Problem**: Capture aborts or no CSV/PRC produced.
  - **Check**:
    - Device logs for crashes or permission issues.
    - Unreal project configuration for profiling (stat groups, CSV capture enabled).
  - **Remedy**:
    - Rebuild project with profiling enabled.
    - Verify correct command-line options are used to trigger CSV capture.

## Report Generation Failures

- **Problem**: PerfReportTool exits with errors.
  - **Check**:
    - Log output from PerfReportTool for missing metadata or incompatible reportType.
    - CSV integrity via `csvinfo`.
  - **Remedy**:
    - Normalize CSVs with `CsvConvert`.
    - Adjust profile configuration to use a supported `-reportType`.

## Locating Logs

When things go wrong, these files are your first stop:

### 1. Installer/Updater Logs
- **Location**: `%TEMP%\cerebrus_install_debug.txt`
- **Contents**: Detailed trace of the dependency installation (Python, ADB, etc.) performed by the installer or `install_dependencies.ps1`.
- **Inno Setup Log**: `%TEMP%\Setup Log *.txt` (if the installer crash itself).

### 2. Application Runtime Logs
- **Console Output**: When running from source, logs appear in the terminal.
- **Log File**: `%APPDATA%\Cerebrus\logs\cerebrus.log` (Default location for production builds).

### 3. CI/Build Logs (Local)
- **Location**: `dist/build_log.txt` (if configured) or the PowerShell terminal output.

## Reporting Issues

When opening an issue, please attach:
1.  The relevant log file.
2.  Your `config/cerebrus.yaml` (sanitize secrets first).
3.  Steps to reproduce.
