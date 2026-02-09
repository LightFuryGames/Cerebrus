# Tool Wrapper Design

This document describes the design principles for wrapping external tools.

## Goals

- Provide a stable, testable Python API for each tool.
- Handle command-line assembly internally.
- Capture and report errors in a structured way.

## Basic Pattern

Example for a command-line tool wrapper:

```python
def run_command(binary_path: pathlib.Path, args: list) -> subprocess.CompletedProcess:
    # Build argument list and execute
    cmd = [str(binary_path)] + args
    return subprocess.run(cmd, capture_output=True, text=True)
```

## Class-Based Wrappers (Preferred for Statefull Tools)

For more complex tools like `AdbClient`, use a class to manage state:

```python
class AdbClient:
    def __init__(self, adb_path: Path):
        self.adb_path = adb_path
        
    def shell_command(self, device_id: str, command: str) -> str:
        # Implementation...
```

## Error Handling

- On non-zero exit code:
  - Log full command (or sanitized version).
  - Include stderr in logs.
  - Raise a specific exception or return a result object with status.

## Testing

- Unit tests for command construction:
  - Use fake paths and verify `subprocess` is called with expected arguments.
- Integration tests (optional):
  - Run real tools against small sample data where available.

See `docs/CSVTOOLS_REFERENCE.md` and `docs/PERFREPORTTOOL_REFERENCE.md` for tool-specific argument details.
