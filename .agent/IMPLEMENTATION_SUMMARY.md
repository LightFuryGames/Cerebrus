# Output File Name & Use as Prefix Implementation Summary

## Overview
Implemented proper functionality for the "Output File Name" and "Use as Prefix Only" checkbox to control how generated files (performance reports and colored logs) are named. Additionally, implemented organized subdirectory output and feature injection (Dark Mode).

## Changes Made

### 1. New Helper Function: `_get_unique_output_path()`
**Location:** `cerebrus/ui/components.py` (lines ~537-565)

**Purpose:** Generates unique file paths by appending sequential counters (`_1`, `_2`, etc.) when files with the same name already exist, preventing accidental overwrites.

**Signature:**
```python
def _get_unique_output_path(base_path: Path, filename: str, extension: str) -> Path
```

**Behavior:**
- Checks if `base_path/filename.extension` exists
- If it doesn't exist, returns that path
- If it exists, tries `filename_1.extension`, `filename_2.extension`, etc. until finding a unique name

### 2. Updated Performance Report Generation
**Location:** `cerebrus/ui/components.py` - `_handle_generate_perf_report()` function

**Logic:**
- **When `use_prefix_only` is TRUE:**
  - Filename format: `{output_file_name}_{csv_filename}.html`
  - Example: If output_file_name = "perf_report" and CSV = "data.csv"
    - Result: `perf_report_data.html`
- **When `use_prefix_only` is FALSE:**
  - Filename format: `{output_file_name}.html` (same name for all files from different CSVs)
  - Example: If output_file_name = "my_report" and processing multiple CSVs
    - Result: `my_report.html`, `my_report_1.html`, `my_report_2.html`, etc.

**File Protection:**
- Uses `_get_unique_output_path()` to prevent overwrites
- Existing files are preserved with new files getting sequential numbers

### 3. Updated Colored Logs Generation
**Location:** `cerebrus/ui/components.py` - `_handle_generate_colored_logs()` function

**Logic:**
- **When `use_prefix_only` is TRUE:**
  - Filename format: `{output_file_name}_{log_filename}.html`
  - Example: If output_file_name = "colored_log" and log = "app.log"
    - Result: `colored_log_app.html`
- **When `use_prefix_only` is FALSE:**
  - Filename format: `{output_file_name}.html`
  - Example: If output_file_name = "my_log" and processing multiple logs
    - Result: `my_log.html`, `my_log_1.html`, `my_log_2.html`, etc.

**File Protection:**
- Uses `_get_unique_output_path()` to prevent overwrites
- Existing files are preserved

### 4. Organized Output Subdirectories
Generated files are now saved to dedicated subdirectories within the Output Folder:
- **`Profiling/`**: Stores Performance Reports (`.html`).
- **`Logs/`**: Stores Colored Logs (`.html`).
- **`MemReports/`**: Stores Memory Reports (`.html`).

### 5. HTML Feature Injection
Values-added features are injected into generated Performance Reports:
- **Dark Mode Toggle**: CSS/JS based theme switching.
- **Scroll to Top**: Floating button for easy navigation.

### 4. Updated Tooltips
**Location:** `cerebrus/ui/components.py` - TOOLTIPS dictionary

- **output_file_name:** Now mentions that counters will be added if files exist
- **use_prefix_only:** Clarifies the difference between prefix mode (appends original filename) and exact filename mode (uses same name for all with counters)

## User-Facing Behavior

### Scenario 1: Prefix Mode (Checkbox CHECKED)
- Each source file gets its own unique output file
- Pattern: `{prefix}_{original_name}.html`
- No duplicates unless you run the process twice on the same files
- Example:
  ```
  Output File Name: "report"
  CSV files: game_data.csv, player_stats.csv
  Result: report_game_data.html, report_player_stats.html
  ```

### Scenario 2: Exact Filename Mode (Checkbox UNCHECKED)
- All outputs use the same base filename
- Counters are added automatically for duplicates
- Pattern: `{filename}.html`, `{filename}_1.html`, `{filename}_2.html`, etc.
- Example:
  ```
  Output File Name: "final_report"
  CSV files: game_data.csv, player_stats.csv
  Result: final_report.html, final_report_1.html
  ```

### Scenario 3: Re-running Generation
- If you run generation again with the same settings, existing files are NOT overwritten
- New files get incremented counters
- Example on second run:
  ```
  First run: report.html
  Second run: report_1.html
  Third run: report_2.html
  ```

## Technical Notes

1. **No Data Loss:** The implementation prevents any accidental file overwrites
2. **Sequential Numbers:** Counter starts at 1 and increments until finding an unused filename
3. **Extension Handling:** The helper function properly handles extensions with or without leading dots
4. **Cross-Function Consistency:** Both perf reports and colored logs use the same naming logic

## Testing Recommendations

To test this implementation:

1. **Test Prefix Mode:**
   - Set Output File Name to "test"
   - Check "Use as Prefix Only"
   - Generate reports from multiple CSV files
   - Verify each output has format: `test_{csvname}.html`

2. **Test Exact Filename Mode:**
   - Set Output File Name to "report"
   - Uncheck "Use as Prefix Only"
   - Generate reports from multiple CSV files
   - Verify outputs: `report.html`, `report_1.html`, etc.

3. **Test No Overwrite:**
   - Generate reports once
   - Without deleting files, generate again
   - Verify original files still exist and new files have counters

4. **Test Empty Output File Name:**
   - Leave Output File Name blank
   - Generate reports
   - Verify files use original CSV/log names as fallback
