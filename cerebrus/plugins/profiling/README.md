# Profiling Plugin

`ProfilingPlugin` is the default plugin and should normally stay enabled. It hosts the main day-to-day workflow for Android profiling.

## What Users See

The plugin adds the `Profiling` tab. This tab is the big control tray for:

- Launching, minimizing, killing, and clearing app data on a selected device.
- Sending Unreal console commands.
- Starting and stopping CSV profiling.
- Triggering `memreport` and `memreport -full`.
- Moving logs, CSV captures, and memreport files from the phone to the PC.
- Generating performance reports, memory reports, and colored log HTML.

## Simple Workflow

1. Load or create a profile.
2. Connect a phone.
3. Click `List Devices`.
4. Select the row for the phone that has the target package installed.
5. Choose the output folder.
6. Select the checkboxes for the work you want.
7. Click `Generate`.

If the plugin is the toy box, the `Generate` button is the big green cleanup button: it collects the pieces from the phone, sorts them into folders, and turns them into readable HTML reports.

## Output Folders

The plugin writes under the selected output path, with device-specific folders when a device row is selected:

```text
OutputPath/
  DeviceMake_DeviceModel/
    Profiling/
    Logs/
    MemReports/
```

Temporary pulled files may sit under `CSV`, `Logs`, or `MemReports` before being converted and cleaned up.

## Current Tests

Existing tests cover some shared behavior used by this plugin:

- `tests/ui/test_file_manager.py`
- `tests/ui/test_output_naming.py`
- `tests/core/test_devices.py`
- `tests/tools/test_adb.py`

## Missing Tests

Add focused tests for:

- Bulk action ordering in `_handle_generate_actions`.
- Device-specific output path updates when selecting a device.
- Memreport UI path using the same metadata-driven naming as the CLI path.
- Error messages when selected device/package/output folders are missing.
- Safe handling when one generated report succeeds and another fails.
