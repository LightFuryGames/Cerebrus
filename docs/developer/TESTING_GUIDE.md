# Testing Guide

This document outlines testing expectations and organization.

## Framework

- Use `pytest` as the primary test framework.

## Test Layout

Tests are split by scope to ensure fast feedback loops (Unit) and robust verification (Integration).

```text
tests/
  unit/             # Fast, mock-heavy tests. NO I/O.
    core/
    tools/
    ui/
  integration/      # Slower, I/O allowed. Uses wrappers.
    tools/
  data/             # Test fixtures
    synthetic/     # Generators for fake logs/CSVs
    fixtures/      # Small (<50KB) static files
```

## Internal vs External Tests

### Unit Tests (`tests/unit`)
- **Goal**: Verify internal logic.
- **Scope**: Pure functions, config loaders, command builders.
- **Rule**: Must run in < 50ms per test. No external processes or file system side effects.
- **Technique**: Mock `subprocess` and `pathlib` heavily.
- **Example**: Testing that `ClassStatsParser` correctly extracts "1024 KB" from a string line.

### Integration Tests (`tests/integration`)
- **Goal**: Verify tool wrappers and file system interactions.
- **Rule**: Must separate creation, execution, and cleanup.
- **Technique**: Use `tmp_path` fixture.
- **Example**: Creating a dummy CSV, running `run_collate`, and asserting the output file exists.

## Test Data Strategy

**Do not commit real log files.** Real logs contain PII, IP addresses, and proprietary paths.

Instead, use **Functional Data Generation**:
```python
def create_dummy_memreport() -> str:
    return """
    MemReport: Begin command "obj list class=Actor -resourcesizesort"
    Class    Count   NumKB   MaxKB
    Actor    10      100.00  10.00
    """
```

## Running Tests

```powershell
./scripts/run_unittests.ps1
```

Or manually:

```bash
pytest
```

To see **stdout/stderr logs** during a test run (useful for debugging failed integration tests):
```bash
pytest -s -rP
```
- `-s`: Disable output capture (print to console).
- `-rP`: Show stdout/stderr for passed tests too.

To run the **full pipeline** locally (Lint + Preflight + Test):
```powershell
./scripts/run_unittests.ps1  # (If available) OR
pytest && ./scripts/run_lint.ps1
```

Before pushing, ensure you pass the full CI suite locally:

```powershell
./run_pipeline.ps1
```
This script combines linting, preflight checks, and unit tests.

## CI Integration

GitHub Actions executes:
1.  **Lint**: Enforces `black`, `isort`, `mypy`.
2.  **Preflight**: Validates config schemas.
3.  **Unit Tests**: Runs `tests/unit`.

Integration tests may be skipped on PRs to save time, but run on `develop` merges.
