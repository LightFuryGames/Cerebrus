# Cerebrus User Guide

Cerebrus is a comprehensive GUI toolkit for Unreal Engine Android profiling workflows. It simplifies the process of collecting logs, moving files, and generating performance reports.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Profile Management](#profile-management)
3. [Device Management](#device-management)
4. [File Actions](#file-actions)
5. [Report Generation](#report-generation)
6. [Settings](#settings)

## Getting Started
Launch Cerebrus to see the main dashboard. The interface is divided into several sections:
- **Menu Bar**: Access file operations, views, tools, settings, and help.
- **Profile Summary**: Displays the currently loaded profile information.
- **Device List**: Shows connected Android devices.
- **Data and Perf Report**: Configure paths and perform bulk actions.
- **Logging**: View real-time application logs.

## Profile Management
Profiles allow you to save and load configurations for different projects or devices.
- **New Profile**: Create a fresh configuration.
- **Open Profile**: Load an existing JSON profile.
- **Edit Profile**: Modify the current profile settings.
- **Auto-Save**: Changes to paths and settings are automatically saved to the current profile.

## Device Management
The device list shows all connected Android devices.
- **Refresh**: Click "List Devices" to scan for connected devices.
- **Selection**: Click on a device row to select it for operations.
- **Status**: The table shows the device model, serial number, Android version, and if the target package is installed.
- **Remote Controls**:
    - **Launch Package**: Launch or resume the target application (supports Launch Package v2.0.0).
    - **Profiling**: Start/Stop CSV profiling.
    - **Remote Console**: Send `memreport` or custom console commands (e.g., `stat unit`).

## File Actions
Manage files between your PC and the connected Android device.

### Configuration
- **Output File Name**: The base name for generated files.
- **Move Files Folder Path**: The directory on your PC where files will be copied to.
- **Output Folder Path**: The destination for generated reports.
- **Append Device Make/Model**: Automatically creates subfolders based on the device name.

### Bulk Actions (Phone to PC)
- **Move Logs**: Copies logs from `Saved/Logs` on the device to your PC.
- **Move CSV Data**: Copies profiling data from `Saved/Profiling/CSV` on the device to your PC.

## Cloud Integration & AWS Plugins
Cerebrus uses plugins for cloud workflows. A plugin is a small extra work area that can add a tab and menu actions without changing the whole app.

For detailed plugin help, see:
- `cerebrus/plugins/README.md`
- `cerebrus/plugins/aws_secrets.md`
- `cerebrus/plugins/s3_uploader.md`

### AWS Secrets Manager
Think of AWS Secrets as the key locker. You give a key a friendly label, then map that label to an S3 bucket. The uploader later asks the locker for the right key.

- **Key Alias**: A friendly name for one AWS access key pair.
- **Bucket Mapping**: The bucket name, region, and key alias that belong together.
- **Local Protection**: Credentials use Windows DPAPI. If DPAPI is unavailable, Cerebrus refuses to save new AWS keys instead of writing plaintext secrets.
- **Portable Export**: Export/import `.cbx` JSON files when a teammate needs the same bucket map. These files include bucket mappings and key aliases, not AWS secret values.

### S3 Uploader
Think of S3 Uploader as the delivery cart. It picks up one generated HTML report, reads the hidden metadata note inside it, builds a tidy folder path, and uploads it to the bucket you selected.

- **Automatic Pathing**: Reads metadata from reports to determine the S3 path (`BuildConfig/Device/CL/Date/Time`).
- **Optimization**: Strips redundant raw memreport data before upload when possible.
- **Requirements**: Requires the `boto3` Python package.
- **Deprecated**: Old `Tools -> AWS Configuration` instructions no longer describe the current workflow. Use the plugin tabs and `Settings -> Plugins` menu.

## Report Generation
Process collected data into readable formats.

### Bulk Actions (PC to PC)
- **Generate Perf Report Only**: Runs `PerfreportTool.exe` on CSV files to create visual reports.
    - **New Metrics**: Reports now include System Metadata, FPS Analysis, and Average FPS.
- **Generate Memory Report Only**: Converts `.memreport` files into interactive HTML visualizations.
    - **Visualization**: Provides tree maps and detailed object tracking for memory analysis.
    - **Automatic Naming**: Reports are named as `{BuildConfig}_{Device}_{CL}_{Date}.html`.
    - **Metadata**: Embeds session data for S3 uploading and downstream analysis.
- **Generate Colored Logs Only**: Converts text logs to color-coded HTML files.
- **Generate All**: Performs all enabled operations in sequence.
- **View HTML Logs**: Opens the `Logs` output folder to view generated HTML logs.

> **Note**: Generated reports are automatically organized into `Profiling/`, `Logs/`, and `MemReports/` subdirectories within your Output Path.

## Plugins
Access plugin tabs in the main tab area. Enable or disable plugins from **Settings -> Plugins**.

- **Profiling**: Main capture and report workflow.
- **AWS Secrets**: Key locker and bucket map.
- **S3 Uploader - Profiling Reports**: Upload generated HTML reports.

### Auto-Update
Cerebrus automatically checks for updates on startup.
- If a new version is available, a prompt will appear.
- The update is downloaded and installed automatically.

## Settings
Customize your experience via the Settings menu.
- **Load Theme**: Switch between Dark, Light, or System themes.
- **Log Colors**: Customize the colors used in the application log window.
- **Key Bindings**: View or edit keyboard shortcuts.

## Troubleshooting
- **No Devices Found**: Ensure USB debugging is enabled and ADB is running.
- **Tool Not Found**: Verify that `PerfreportTool.exe` path is correctly configured in your environment or settings.
- **Report Features**: Generated HTML reports include a **Dark Mode** toggle and **Scroll to Top** button for better readability.

