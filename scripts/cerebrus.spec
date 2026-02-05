# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for building Cerebrus executable."""

from pathlib import Path
import sys

# Get the root directory
spec_path = Path(SPECPATH).resolve()
root_dir = spec_path.parent
if not (root_dir / "cerebrus").exists():
    root_dir = root_dir.parent

print(f"DEBUG: Resolved root_dir={root_dir}")
cerebrus_dir = root_dir / "cerebrus"
binaries_dir = root_dir / "Binaries"
resources_dir = cerebrus_dir / "resources"

# Collect all resource files
datas = []

# Add resources (icons, etc.)
if resources_dir.exists():
    for resource_file in resources_dir.iterdir():
        if resource_file.is_file() and not resource_file.name.endswith('~'):
            datas.append((str(resource_file), 'cerebrus/resources'))

# Add Binaries folder if it exists
binaries = []
if binaries_dir.exists():
    for binary_file in binaries_dir.rglob('*'):
        if binary_file.is_file():
            rel_path = binary_file.relative_to(binaries_dir)
            datas.append((str(binary_file), f'Binaries/{rel_path.parent}'))

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'dearpygui',
    'dearpygui.dearpygui',
    'psutil',
    'win32api',
    'win32con',
    'win32gui',
    'pywintypes',
    'yaml',
    'requests',
]

a = Analysis(
    [str(cerebrus_dir / '__main__.py')],
    pathex=[str(root_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'mypy', 'black', 'isort'],  # Exclude dev dependencies
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# Get version from cerebrus module
version_file = cerebrus_dir / '_version.py'
version = '0.0.0'
if version_file.exists():
    version_content = version_file.read_text()
    for line in version_content.split('\n'):
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

# Version info for Windows executable
version_info_content = (
    f'VSVersionInfo(\n'
    f'  ffi=FixedFileInfo(\n'
    f'    filevers=({version.replace(".", ", ")}, 0),\n'
    f'    prodvers=({version.replace(".", ", ")}, 0),\n'
    f'    mask=0x3f,\n'
    f'    flags=0x0,\n'
    f'    OS=0x40004,\n'
    f'    fileType=0x1,\n'
    f'    subtype=0x0,\n'
    f'    date=(0, 0)\n'
    f'  ),\n'
    f'  kids=[\n'
    f'    StringFileInfo(\n'
    f'      [\n'
    f'      StringTable(\n'
    f'        u\'040904B0\',\n'
    f'        [StringStruct(u\'CompanyName\', u\'LeagueX Gaming Private Limited\'),\n'
    f'        StringStruct(u\'FileDescription\', u\'Cerebrus - Unreal Engine Android Profiling Tool\'),\n'
    f'        StringStruct(u\'FileVersion\', u\'{version}\'),\n'
    f'        StringStruct(u\'InternalName\', u\'Cerebrus\'),\n'
    f'        StringStruct(u\'LegalCopyright\', u\'© 2025 LeagueX Gaming Private Limited. All rights reserved.\'),\n'
    f'        StringStruct(u\'OriginalFilename\', u\'Cerebrus.exe\'),\n'
    f'        StringStruct(u\'ProductName\', u\'Cerebrus\'),\n'
    f'        StringStruct(u\'ProductVersion\', u\'{version}\')])\n'
    f'      ]), \n'
    f'    VarFileInfo([VarStruct(u\'Translation\', [1033, 1200])])\n'
    f'  ]\n'
    f')'
)

# Write version info to a temporary file
version_file = root_dir / 'build' / 'version_info.txt'
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(version_info_content, encoding='utf-8')

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Cerebrus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(resources_dir / 'icon256x256.ico') if (resources_dir / 'icon256x256.ico').exists() else None,
    version=str(version_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Cerebrus',
)
