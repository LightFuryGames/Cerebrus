# Plugin Test Plan

This file is the source of truth for plugin-related test expectations.

## Existing Coverage

### Plugin Manager

`tests/core/test_plugin_manager.py` covers:

- New registered plugins are enabled by default.
- Previously known disabled plugins stay disabled when loaded from cache.
- `MenuPlugin` marks plugins that provide `Settings -> Plugins` menu actions.

### AWS Secrets Manager

`tests/core/test_aws_secrets_manager.py` covers:

- `.cbx` export JSON never includes AWS access key IDs or secret access keys.
- Importing mappings preserves existing local credentials.
- Bucket display labels include region.
- New key persistence is refused when local encryption is unavailable.

### S3 Uploader Helpers

`tests/core/test_s3_uploader.py` covers:

- Metadata extraction from embedded JSON.
- Metadata fallback from legacy visible stat cards.
- Destination path derivation and sanitization.
- `upload_file` call construction with and without `ContentType`.

### Packaging Contract

`tests/core/test_build_spec.py` covers:

- `cerebrus/plugins/resources` is collected by the PyInstaller spec.
- `boto3` and `botocore` data files remain collected.

### Profiling Plugin Dependencies

The default Profiling plugin is indirectly covered by:

- `tests/core/test_devices.py`
- `tests/tools/test_adb.py`
- `tests/ui/test_file_manager.py`
- `tests/ui/test_output_naming.py`

## Missing Coverage

### Plugin Manager

Add tests for:

- Saving cache after `set_enabled`.
- Corrupt `plugins.json` fallback.
- Multiple plugin registration order.
- Optional `build_menu` support in menu rendering, with Dear PyGui mocked.
- Registered plugin metadata version written to cache.

### AWS Secrets Plugin

Add tests listed in [aws_secrets.md](aws_secrets.md). The short version:

- Key CRUD.
- Bucket mapping CRUD.
- Region persistence.
- Credential lookup.
- Import/export.
- Encryption fallback and corrupt cache recovery.
- Legacy `.cbx` import behavior.

### S3 Uploader Plugin

Add tests listed in [s3_uploader.md](s3_uploader.md). The short version:

- Validation warnings.
- Dear PyGui form behavior with mocked UI calls.
- Full callback flow with mocked `boto3.client`.

### Packaging

Keep release/build checks that verify:

- `cerebrus/plugins/resources/aws_secrets_tooltips.json` is bundled.
- `cerebrus/plugins/resources/s3_uploader_tooltips.json` is bundled.
- `boto3` and `botocore` data files are still collected.

## Test Style

- Use `pytest`.
- Use `tmp_path` for file persistence tests.
- Mock Dear PyGui for UI tests.
- Mock `boto3.client`; no unit test should reach the network.
- Keep sample AWS keys fake and obvious, such as `AKIA_TEST_ONLY`.

## Current Local Test Caveat

In restricted Windows sandboxes, pytest temp folders may fail with `PermissionError`. That is an environment issue, not a product behavior test. Prefer running the suite in the project virtual environment or CI runner where temp directory creation is allowed.

On this workspace, use the shared multi-agent command shape from `AGENTS.md`:

```powershell
$env:TEMP = (Join-Path (Get-Location).Path '.pytest_run_tmp')
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest -p no:cacheprovider --basetemp .pytest_run_tmp <tests>
```
