# Output File Name & Use as Prefix - User Guide

## Quick Start

The "Output File Name" and "Use as Prefix Only" settings control how your generated reports and colored logs are named.

> **Note**: Generated files are automatically organized into subdirectories (`Profiling/` or `MemReports/`) within your selected output path.

## Visual Examples

### Example 1: Use as Prefix (Checkbox CHECKED) ✓

**Settings:**
- Output File Name: `perf_report`
- Use as Prefix Only: ✓ CHECKED

**You have these CSV files:**
- `game_session_1.csv`
- `game_session_2.csv`
- `player_stats.csv`

**Generated files will be:**
- `perf_report_game_session_1.html`
- `perf_report_game_session_2.html`
- `perf_report_player_stats.html`

**Result:** Each file gets a unique name with your prefix

---

### Example 2: Exact Filename (Checkbox UNCHECKED) ☐

**Settings:**
- Output File Name: `final_report`
- Use as Prefix Only: ☐ UNCHECKED

**You have these CSV files:**
- `game_session_1.csv`
- `game_session_2.csv`
- `player_stats.csv`

**Generated files will be:**
- `final_report.html` (from game_session_1.csv)
- `final_report_1.html` (from game_session_2.csv)
- `final_report_2.html` (from player_stats.csv)

**Result:** All files use the same base name, with counters added

---

### Example 3: Re-running Generation (No Overwrites!)

**First run** with settings:
- Output File Name: `report`
- Use as Prefix Only: ☐ UNCHECKED
- CSV file: `data.csv`

**Result:** `report.html` is created

**Second run** (without deleting files):
- Output File Name: `report`
- Use as Prefix Only: ☐ UNCHECKED
- CSV file: `data.csv`

**Result:** `report_1.html` is created (original `report.html` is preserved!)

---

## Common Use Cases

### Use Case 1: Tracking Different Test Sessions
**Scenario:** You want to keep reports from different test sessions separate

**Recommendation:** Use Prefix Mode ✓
- Set Output File Name to the session identifier: `session_dec01`
- Each data file generates its own report: `session_dec01_frame_times.html`, `session_dec01_memory.html`

### Use Case 2: Creating a Single Master Report
**Scenario:** You want all data consolidated under one report name

**Recommendation:** Use Exact Filename Mode ☐
- Set Output File Name to: `master_report`
- All reports will be: `master_report.html`, `master_report_1.html`, etc.

### Use Case 3: Daily Report Archives
**Scenario:** You generate reports daily and want to keep historical data

**Recommendation:** Use Prefix Mode ✓ with dates
- Set Output File Name to: `daily_2024_12_01`
- Run generation multiple times without fear of overwriting
- Files are automatically numbered if you regenerate

### Use Case 4: Using Default Filenames
**Scenario:** You want to use the original CSV/log filenames

**Recommendation:** Leave Output File Name blank
- The system will use the source file names automatically
- Works in both Prefix and Exact modes

---

## Protection Against Data Loss

**Important:** The system NEVER overwrites existing files!

If you generate a file that would have the same name as an existing file:
1. The existing file is kept exactly as it is
2. The new file gets a number appended: `_1`, `_2`, `_3`, etc.
3. You'll see both files in your output folder

**Example:**
```
Output Folder:
├── Profiling/
│   ├── report.html          (from first run)
│   ├── report_1.html        (from second run)
│   ├── report_2.html        (from third run)
│   └── old_data.html        (your existing file, untouched)
```

---

## Tips and Best Practices

1. **Use descriptive prefixes** 
   - Good: `performance_test_build_v2`
   - Bad: `test` or `report`

2. **Include dates in prefix mode**
   - Example: `perf_2024_12_01` makes it easy to find reports later

3. **Keep output file names short**
   - Long names can cause issues with file path limits on Windows
   - Recommended: Under 50 characters

4. **Use prefix mode for batch processing**
   - When processing many files, prefix mode keeps everything organized
   - Each source file gets its own uniquely named output

5. **Use exact mode for consistency**
   - When you want all outputs to follow a single naming scheme
   - Good for automated pipelines where naming is controlled

---

## Troubleshooting

### Q: Why did my file get named `report_1.html` instead of `report.html`?
**A:** A file named `report.html` already exists in the output folder. The system added `_1` to prevent overwriting it.

### Q: Can I force overwriting of files?
**A:** No, this is intentional protection. Delete the old files first if you want to reuse the same names.

### Q: What happens if I leave "Output File Name" blank?
**A:** The system uses the source file name (CSV or log filename) instead.

### Q: The counter went from _2 to _5, skipping _3 and _4. Why?
**A:** The system finds the next available number. If `report_3.html` and `report_4.html` already exist in your folder, it will use `_5`.

---

## MemReport Automatic Naming

For **Memory Reports**, Cerebrus uses an automatic, metadata-driven naming scheme that overrides the "Output File Name" setting to ensure consistency across the team.

**Format:**
`{BuildConfig}_{DeviceMake}_{DeviceModel}_{Changelist}_{DateTime}.html`

**Example:**
`Development_Samsung_SM-G991B_123456_2026.05.07-12.00.00.html`

**Why?**
- **Collision Avoidance**: Prevents overwriting reports from different builds or devices.
- **S3 Integration**: This format is recognized by the S3 Uploader for automated path derivation. See `cerebrus/plugins/s3_uploader.md`.
- **Organization**: Makes it easy to sort and find specific reports in the `MemReports/` directory.

---

## Quick Reference Table

| Setting | Use as Prefix | Output Name | Source File | Result |
|---------|--------------|-------------|-------------|---------|
| Prefix Mode | ✓ | `perf` | `data.csv` | `perf_data.html` |
| Exact Mode | ☐ | `report` | `data.csv` | `report.html` |
| Prefix + Empty | ✓ | (blank) | `data.csv` | `data.html` |
| Exact + Empty | ☐ | (blank) | `data.csv` | `data.html` |
| File Exists | ✓ | `perf` | `data.csv` | `perf_data_1.html` |
| File Exists | ☐ | `report` | `data.csv` | `report_1.html` |
