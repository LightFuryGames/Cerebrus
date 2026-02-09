# Native File Dialog and Open Folder Implementation

## Overview
Replaced the custom DearPyGui file dialog with Windows' native file explorer dialog and added "Open Folder" buttons for quick access to directories.

## Changes Made

### 1. **Native Windows File Dialog**
- **Replaced**: Custom DearPyGui file dialog
- **With**: Native Windows folder browser using `tkinter.filedialog`
- **Benefits**:
  - Familiar Windows interface
  - Better integration with the OS
  - Faster and more responsive
  - Supports all Windows features (favorites, recent folders, etc.)

### 2. **Open Folder Buttons**
- Added "Open Folder" buttons next to each "Browse" button
- Opens the directory directly in Windows Explorer
- Creates the folder if it doesn't exist
- Provides quick access to:
  - Move Files Folder Path
  - Output Folder Path

### 3. **Table Structure Update**
- **Before**: 3 columns (Label, Input, Browse)
- **After**: 4 columns (Label, Input, Browse, Open Folder)
- Column widths:
  - Column 1: 320px (Labels)
  - Column 2: 350px (Input fields)
  - Column 3: 90px (Browse buttons)
  - Column 4: 120px (Open Folder buttons)

## Technical Implementation

### New Dependencies
```python
import os
from tkinter import Tk, filedialog
```
- **tkinter**: Part of Python standard library (no additional installation needed)
- **os**: Part of Python standard library

### New Functions

#### `_browse_folder_native(state: UIState, path_type: str)`
- Opens native Windows folder selection dialog
- Parameters:
  - `state`: Application state
  - `path_type`: Either "input" or "output"
- Features:
  - Creates hidden Tk window
  - Sets dialog to topmost
  - Remembers last used directory
  - Updates state and UI on selection
  - Auto-saves profile
  - Handles device path appending for output

#### `_open_folder_in_explorer(folder_path: Path)`
- Opens specified folder in Windows Explorer
- Creates folder if it doesn't exist
- Uses `os.startfile()` (Windows-specific)

### UI Updates

**Before:**
```
[Label] [Input Field________________] [Browse]
```

**After:**
```
[Label] [Input Field________________] [Browse] [Open Folder]
```

## User Workflow

### Browsing for Folders
1. Click "Browse" button
2. Native Windows folder dialog appears
3. Navigate using familiar Windows interface
4. Select folder
5. Path updates automatically

### Opening Folders
1. Click "Open Folder" button
2. Windows Explorer opens to that location
3. If folder doesn't exist, it's created first

## Benefits

✅ **Native Experience**: Uses Windows' built-in file dialog  
✅ **Quick Access**: "Open Folder" buttons for instant navigation  
✅ **No Additional Dependencies**: Uses Python standard library  
✅ **Better UX**: Familiar interface for Windows users  
✅ **Automatic Folder Creation**: Opens even if folder doesn't exist yet  
✅ **Profile Integration**: Automatically saves selections to profile  

## Platform Note

The `os.startfile()` function is Windows-specific. For cross-platform support, you could add:

```python
import platform
import subprocess

def _open_folder_in_explorer(folder_path: Path) -> None:
    try:
        if not folder_path.exists():
            folder_path.mkdir(parents=True, exist_ok=True)
        
        if platform.system() == "Windows":
            os.startfile(str(folder_path))
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", str(folder_path)])
        else:  # Linux
            subprocess.run(["xdg-open", str(folder_path)])
    except Exception as e:
        print(f"Failed to open folder: {e}")
```

## Testing Checklist

- [x] Browse button opens native Windows dialog
- [x] Selected path updates in UI
- [x] Path is saved to profile
- [x] Open Folder button opens Windows Explorer
- [x] Non-existent folders are created
- [x] Device path appending works with new dialog
- [x] Table columns are properly aligned
- [x] All tooltips still work
