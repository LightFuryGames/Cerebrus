# Testing Guide

This document outlines testing expectations and organization.

## Framework

- Use `pytest` as the primary test framework.

## Test Layout

The current repository mirrors the source layout directly under `tests/`.

```text
tests/
  cache/
  config/
  core/
  tools/
  ui/
```

## Internal vs External Tests

### Unit Tests
- **Goal**: Verify internal logic.
- **Scope**: Pure functions, config loaders, command builders.
- **Rule**: Prefer no external processes. Use `tmp_path` for file behavior.
- **Technique**: Mock `subprocess` and `pathlib` heavily.
- **Example**: Testing that `ClassStatsParser` correctly extracts "1024 KB" from a string line.

### Integration Tests
- **Goal**: Verify tool wrappers and file system interactions.
- **Rule**: Must separate creation, execution, and cleanup.
- **Technique**: Use `tmp_path` fixture.
- **Example**: Creating a dummy CSV, running `run_collate`, and asserting the output file exists.

## Plugin Tests

Plugin-specific test expectations live beside the plugin docs:

- `cerebrus/plugins/TESTING.md`
- `cerebrus/plugins/aws_secrets.md`
- `cerebrus/plugins/s3_uploader.md`
- `cerebrus/plugins/profiling.md`

Current plugin coverage includes:

- `tests/core/test_plugin_manager.py`
- `tests/core/test_aws_secrets_manager.py`
- `tests/core/test_s3_uploader.py`
- `tests/core/test_build_spec.py`

AWS Secrets still needs additional DPAPI round-trip and corrupt-cache tests. S3 Uploader still needs UI callback tests with Dear PyGui and `boto3.client` mocked.

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

On this Windows workspace, pytest's default temp/cache paths can hit ACL errors. `pyproject.toml` configures pytest to use a project-local temp directory and disables the pytest cache provider. For focused local runs, this should now be enough:

```powershell
python -m pytest <tests>
```

If an external runner ignores `pyproject.toml`, use the explicit workaround from `AGENTS.md`:

```powershell
$env:TEMP = (Join-Path (Get-Location).Path '.pytest_run_tmp')
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest -p no:cacheprovider --basetemp .pytest_run_tmp <tests>
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
3.  **Unit Tests**: Runs the repository `pytest` suite.

Integration tests may be skipped on PRs to save time, but run on `develop` merges.
