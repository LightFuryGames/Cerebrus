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

## Configuration Panel & S3 Settings
The **Configuration Sync** tab allows you to manage remote configuration files stored in AWS S3.
- **Sync Remote Config**: Downloads the latest `BackendConfig.ini` from your configured S3 bucket and pushes it to the connected device.

### AWS Configuration
To enable S3 features, go to **Tools -> AWS Configuration** and set:
1. **S3 Bucket URL**: Base URL of your config bucket.
2. **Access Key/Secret Key**: Your AWS credentials.
3. **Region**: Target AWS region (e.g., `ap-south-1`).

## Report Generation
Process collected data into readable formats.

### Bulk Actions (PC to PC)
- **Recursive Search**: The tool now recursively searches for files in the selected directory.
- **Generate Perf Report Only**: Runs `PerfreportTool.exe` on CSV files to create visual reports.
    - **New Metrics**: Reports now include System Metadata, FPS Analysis, and Average FPS.
- **Generate Memory Report Only**: Converts `.memreport` files into interactive HTML visualizations.
    - **Visualization**: Provides tree maps and detailed object tracking for memory analysis.
- **Generate Colored Logs Only**: Converts text logs to color-coded HTML files.
- **Generate All**: Performs all enabled operations in sequence.
- **View HTML Logs**: Opens the output folder to view generated HTML logs.

## Tools
Access additional utilities from the **Tools** menu.

### Advanced Memory Reporting
Convert raw `.memreport` files into easier-to-read HTML dashboards.
1. Go to **Tools -> MemReport to HTML**.
2. Select your input `.memreport` file.
3. The tool generates an HTML file with tabs for **Device Info**, **Memory Stats**, and **Object Summaries**.

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

