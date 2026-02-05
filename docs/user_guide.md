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

## Report Generation
Process collected data into readable formats.

### Bulk Actions (PC to PC)
- **Generate Perf Report Only**: Runs `PerfreportTool.exe` on CSV files.
- **Generate Colored Logs Only**: Converts text logs to color-coded HTML files.
- **Generate Perf Report + Colored Logs**: Performs both operations in sequence.
- **View HTML Logs**: Opens the output folder to view generated HTML logs.

## Settings
Customize your experience via the Settings menu.
- **Load Theme**: Switch between Dark, Light, or System themes.
- **Log Colors**: Customize the colors used in the application log window.
- **Key Bindings**: View or edit keyboard shortcuts.

## Troubleshooting
- **No Devices Found**: Ensure USB debugging is enabled and ADB is running.
- **Tool Not Found**: Verify that `PerfreportTool.exe` path is correctly configured in your environment or settings.
