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
    - That the bundled binaries exist under `Binaries/`.
    - That `Binaries/CsvTools/PerfReportTool.exe` exists when performance reports fail.
  - **Remedy**:
    - Ensure Unreal Engine installation is intact.
    - Rebuild or reinstall Cerebrus if bundled tools are missing.

## No Devices Visible

- **Problem**: Device panel is empty.
  - **Check**:
    - `adb devices` from a command prompt.
    - USB debugging enabled on device.
    - Correct drivers installed.
  - **Remedy**:
    - Reconnect device and approve the host PC’s RSA key.
    - Restart ADB server: `adb kill-server` then `adb start-server`.
    - Manual Restart (if above fails): Open Task Manager, kill `adb.exe`, then run `adb computers` or `adb devices`.

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

## Plugin Issues

- **Problem**: AWS or S3 tabs are missing.
  - **Check**:
    - Open `Settings -> Plugins`.
    - Confirm `AWS Secrets` and `S3 Uploader - Profiling Reports` are enabled.
  - **Remedy**:
    - Enable the plugin and restart Cerebrus if the tab does not appear immediately.

- **Problem**: S3 Uploader does not show a bucket.
  - **Check**:
    - Open the `AWS Secrets` tab.
    - Confirm a key alias exists.
    - Confirm a bucket mapping exists for that key alias and region.
  - **Remedy**:
    - Add the missing key or bucket mapping.

- **Problem**: S3 upload fails.
  - **Check**:
    - `boto3` is installed.
    - The selected bucket mapping has credentials.
    - The selected file is an HTML report.
  - **Remedy**:
    - Reinstall `requirements.txt`.
    - Recreate the bucket mapping in AWS Secrets.
    - Review `cerebrus/plugins/s3_uploader.md`.

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
2.  Your active profile JSON if profile settings are relevant.
3.  Steps to reproduce.

Never attach AWS keys, local secret JSON files, or unsanitized credential files. Current `.cbx` exports are JSON bucket/key-alias maps with `contains_secret_values: false`, but still treat them as internal configuration files.
