# Codex Guide for Project Cerebrus

Codex is the code-generation and refactoring engine used on this repository. This guide defines how to collaborate with Codex in a controlled, deterministic way.

## Core Principles

1. **Codex is an assistant, not an authority.**
   - Humans own architectural decisions.
   - Codex must work within the documented architecture.

2. **Tasks must be precise and scoped.**
   - Small, well-defined changes are easier to review and trust.

3. **Outputs must be reviewable.**
   - Codex must provide unified diffs and rationale where requested.
   - All changes go through regular code review.


## Preferred Output Format

Ask Codex to:

- Provide changes as unified diffs with `@@` hunk markers.
- Group diffs by file.
- Avoid mixing unrelated changes in a single diff.

Example request:

> “Update `cerebrus/tools/csv/collate.py` to add a `timeout_sec` parameter to the `run_collate` function. Provide the changes as a unified diff.”

## Documentation Expectations

For any substantive change, Codex should:

- Update relevant `.md` files.
- Add or update docstrings for new public classes and functions.
- Ensure examples in docs remain correct.

Examples:

- Wrapping a new CsvTools mode → update `docs/CSVTOOLS_REFERENCE.md`.
- Changing report generation behavior → update `docs/PERFREPORTTOOL_REFERENCE.md`.
- Adjusting module boundaries → update `docs/ARCHITECTURE_OVERVIEW.md`.

## Testing Expectations

Every new feature or bug fix implemented by Codex should include tests where practical:

- Unit tests for pure logic.
- Integration tests for wrappers around external tools (using lightweight, synthetic data where possible).

Codex tasks should include instructions like:

- “Add unit tests under `tests/tools/test_csv_collate.py` for the new behavior.”
- “Ensure tests cover failure modes such as missing binaries or invalid CSV inputs.”

## Review and Acceptance

Human reviewers must:

- Validate that Codex respected the constraints.
- Check for hidden assumptions and unhandled error cases.
- Confirm that logging is adequate for troubleshooting.
- Run tests and verify they pass.

If Codex output is not aligned, request a follow-up task with more explicit constraints or adjust the architecture documentation accordingly.
