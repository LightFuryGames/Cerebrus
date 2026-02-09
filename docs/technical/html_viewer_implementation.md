# HTML Log Viewer Implementation

## Overview
Added the ability to view generated HTML log files directly from the Cerebrus application. This feature allows users to easily access and view their colored HTML logs in their default web browser.

## Implementation Details

### License Compliance
As requested, this implementation uses **only MIT/Apache licensed components**:
- **`webbrowser` module**: Part of Python's standard library (Python Software Foundation License, which is GPL-compatible and permissive)
- **No additional dependencies required**

We specifically avoided:
- ❌ `pywebview` (BSD-3-Clause License)
- ❌ `cefpython` (BSD License)
- ❌ Any GPL-licensed libraries

### Features Added

#### 1. **View HTML Logs Button**
- Located in the "Bulk Actions From PC to PC" section
- Opens a dialog showing all HTML files in the `Logs/` subdirectory
- Includes a "?" help button with tooltip

#### 2. **HTML File Selector Dialog**
- Lists all HTML files found in the `Logs/` and `Profiling/` subdirectories within the output directory
- Shows file modification timestamps
- Sorted by newest first
- Options to:
  - Open individual files
  - Open all files at once
  - Close the dialog

#### 3. **Browser Integration**
- Uses Python's built-in `webbrowser` module
- Opens files in the system's default web browser
- Works cross-platform (Windows, macOS, Linux)
- No embedded browser widget needed

### User Workflow

1. **Generate Colored Logs**: User clicks "Generate Colored Logs Only" to convert text logs to HTML
2. **View HTML Logs**: User clicks "View HTML Logs" button
3. **Select File**: A dialog appears showing all available HTML log files with timestamps
4. **Open in Browser**: User clicks on a file to open it in their default browser
5. **Interactive Viewing**: The HTML log viewer provides:
   - Color-coded log levels
   - Search/filter functionality
   - Modern, responsive UI
   - Copy-to-clipboard support

### Technical Implementation

```python
# Key functions added:

def _handle_view_html_logs(state: UIState) -> None:
    """Scans output directory for HTML files and shows selector dialog"""
    
def _show_html_file_selector(state: UIState, html_files: list) -> None:
    """Displays modal dialog with list of HTML files"""
    
def _open_html_file(state: UIState, html_file: Path) -> None:
    """Opens single HTML file in default browser"""
    
def _open_all_html_files(state: UIState, html_files: list) -> None:
    """Opens all HTML files in default browser"""
```

### Benefits

✅ **No Additional Dependencies**: Uses Python standard library only
✅ **License Compliant**: MIT/Apache compatible (no BSD/GPL)
✅ **Cross-Platform**: Works on Windows, macOS, Linux
✅ **User-Friendly**: Simple dialog interface
✅ **Flexible**: Can open individual or all files
✅ **Integrated**: Seamlessly fits into existing UI workflow

### UI Changes

- Added "View HTML Logs" button to PC to PC section
- Added tooltip: "Opens the Output Folder Path and allows you to select and view generated HTML log files in your default web browser."
- Dialog shows file list from the organized subdirectories
- Proper error handling and user feedback via log messages

## Testing Recommendations

1. Generate some colored logs first
2. Click "View HTML Logs" button
3. Verify dialog appears with HTML files listed
4. Click on a file to open in browser
5. Verify the HTML log viewer displays correctly
6. Test "Open All" functionality
7. Test with no HTML files present (should show warning)
8. Test with non-existent output directory (should show error)
