# Contributing to Project Cerebrus

This document defines how humans and Codex contribute to the Cerebrus repository.

The goals are:
- Deterministic, reproducible behavior.
- Clear ownership and module boundaries.
- High-quality documentation and tests.
- Minimal friction for profiling workflows.

## Branching Model

- `main`
  - Always stable.
  - Only fast-forwarded from tested `develop` commits or reviewed hotfixes.
- `develop`
  - Integration branch for new features.
  - May contain work in progress but should remain buildable.
- `feature/<area>-<short-description>`
  - All feature work and refactors.
  - Example: `feature/ui-device-panel`, `feature/tools-csv-wrapper`.
- `hotfix/<issue-id>-<short-description>`
  - Critical fixes against `main`.
  - Example: `hotfix/123-broken-installer`.

### Branch Rules

- No direct commits to `main`.
- Use pull requests (PRs) for all merges into `main` and `develop`.
- Rebase feature branches on `develop` when possible; avoid long-lived divergence.

## Commit Messages

Use concise, informative commit messages:

- Title: `area: short summary`
  - Example: `tools: add CsvTools wrapper for CSVCollate`
- Body:
  - Explain the motivation (the "why").
  - Mention any behavior changes or migrations.
  - Reference issue IDs if applicable.

Avoid noisy, uninformative messages like `fix` or `misc changes`.

## Pull Requests

Every PR should:

1. Describe the change clearly.
2. List affected modules (e.g. `core/device`, `tools/csv`, `ui/panels`).
3. Include tests or explain why tests are not applicable.
4. Update relevant documentation:
   - Architecture changes → `docs/ARCHITECTURE_OVERVIEW.md`
   - Tooling behavior changes → `docs/CSVTOOLS_REFERENCE.md` or `docs/PERFREPORTTOOL_REFERENCE.md`
   - Developer workflow changes → `CONTRIBUTING.md` or `CODEX_GUIDE.md`

### Review Checklist

Reviewers should verify:

- Architecture:
  - Module boundaries respected.
  - No cross-layer leakage (e.g. UI directly invoking raw tool binaries).
- Code:
  - Readable and maintainable.
  - Clear error handling and logging paths.
  - No hardcoded, machine-specific paths.
- Tests:
  - Happy-path and key failure modes covered.
- Docs:
  - Updated and accurate.

## Working with Codex

Codex is an integrated code-generation and refactoring engine. To keep Codex output aligned:

1. **Write precise tasks**
   - Example: “Add a wrapper module for CSVCollate with a function `run_collate(...)` that accepts a list of CSV paths and returns the output file path. Use dependency injection for the binary path.”

2. **Constrain scope**
   - Avoid asking Codex to “rewrite everything”.
   - Prefer: “Refactor `tools/csv/collate.py` to split CLI composition from process invocation.”

3. **Require diffs**
   - Ask Codex to output unified diffs with `@@` hunk headers.
   - Apply diffs locally using your preferred diff/merge tools.

4. **Enforce project rules**
   - No placeholders or “magic” behavior.
   - All new features must:
     - Log key operations.
     - Surface errors to the UI with actionable messages.
     - Allow paths and configuration to be controlled via config files.

See `CODEX_GUIDE.md` for detailed patterns and examples.

## Code Style

- Python:
  - Target Python 3.11+ on Windows.
  - Use type hints (`typing`) and `mypy`-friendly signatures.
  - Prefer composition over inheritance.
  - Keep functions small and single-responsibility.
- Layout:
  - Group modules by concern: `core`, `ui`, `tools`, `config`, `cache`, `installers`, `tests`.
- Formatting:
  - Use `black` and `isort` (or equivalent) for consistent formatting.
  - Run linting before sending PRs.

## Testing

- Use `pytest` for tests.
- Organize tests mirroring the source structure:
  - `tests/core/test_device_manager.py`
  - `tests/tools/test_csv_collate.py`, etc.
- Include:
  - Unit tests for pure logic.
  - Integration tests for tool wrappers that can run without a full UE environment (use temp directories and mocked paths).

## Adding New Tool Integrations

When integrating a new external tool (e.g. another Unreal utility):

1. Add a thin wrapper module under `cerebrus/tools/<toolname>.py`.
2. Define:
   - A configuration object for binary path and default arguments.
   - Functions that accept high-level arguments (no CLI assembly in callers).
   - Robust handling of process exit codes and stderr.
3. Document:
   - Usage pattern in `docs/<TOOLNAME>_REFERENCE.md`.
   - Any required environment variables or folder structures.

## Security and Privacy

- Do not commit:
  - API keys
  - Access tokens
  - Machine-specific credentials
- Use `.gitignore` to exclude:
  - Local config files containing secrets.
  - Generated reports and large transient profiling data.

## Large Files and Profiling Data

- Do **not** commit large CSVs, PRCs, or generated HTML reports.
- Instead:
  - Document sample commands and expected report locations.
  - Use small, synthetic examples for tests where necessary.

If in doubt, open a discussion or draft PR and request feedback.
