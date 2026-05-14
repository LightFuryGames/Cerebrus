# AI Agent Configuration (Project Cerebrus)

This file defines how the AI (and similar agents) should interact with this repository.

All agents must also follow `AGENTS.md`. That file is the shared working contract
for Codex, Claude Code, Gemini, Antigravity, and any future automation touching
this repo.

## Primary Goals

- Preserve and enforce the architecture defined in `docs/ARCHITECTURE_OVERVIEW.md`.
- Respect code standards in `CODE_STANDARDS.md`.
- Keep documentation consistent with implementation.
- Avoid destructive, large-scale refactors without explicit human approval.

## Document Map

The AI should treat the following as authoritative references:

- Top-level:
  - `AGENTS.md`
  - `README.md`
  - `CONTRIBUTING.md`
  - `CODE_OF_CONDUCT.md`
  - `CODE_STANDARDS.md` (See Sections 3, 4, and 5 for Architecture & Roadmap)
  - `AI_GUIDE.md`
- Architecture and tools:
  - `docs/ARCHITECTURE_OVERVIEW.md`
  - `docs/CSVTOOLS_REFERENCE.md`
  - `docs/PERFREPORTTOOL_REFERENCE.md`
- Workflows (Mandatory for sensitive file updates):
  - `.agent/workflows/user-guide-maintenance.md`
- User docs:
  - `cerebrus/resources/user_guide.html` (Authoritative Living Guide)
  - `docs/user/INSTALLATION.md`
  - `docs/user/RUNNING_CEREBRUS.md`
  - `docs/user/DEVICE_CAPTURE_WORKFLOWS.md`
  - `docs/user/REPORTING_AND_ANALYSIS.md`
  - `docs/user/TROUBLESHOOTING.md`
- Developer docs:
  - `docs/developer/SETUP.md`
  - `docs/developer/PROJECT_STRUCTURE.md`
  - `docs/developer/TOOL_WRAPPER_DESIGN.md`
  - `docs/developer/TESTING_GUIDE.md`
  - `docs/developer/LOGGING_AND_ERROR_HANDLING.md`
- Technical docs:
  - `docs/technical/html_viewer_implementation.md`
  - `docs/technical/native_file_dialog_implementation.md`
- UI docs:
  - `docs/ui/THEME_SPECIFICATION.md`
  - `docs/ui/IMGUI_LAYOUT_GUIDELINES.md`
  - `docs/ui/WIDGET_PATTERNS.md`
- Installer docs:
  - `docs/installer/OVERVIEW.md`
  - `docs/installer/WINDOWS_INSTALLER_SPEC.md`

## Task Scoping Rules

When receiving a request, the AI must:

1. **Identify affected modules and docs**.
2. **Limit changes** to the minimal set of files necessary.
3. Avoid repository-wide rewrites unless explicitly instructed.

Examples:

- Adding a new CsvTools wrapper:
  - Code: `cerebrus/tools/csv/<toolname>.py`
  - Tests: `tests/tools/test_csv_<toolname>.py`
  - Docs: `docs/CSVTOOLS_REFERENCE.md`, possibly `docs/developer/TOOL_WRAPPER_DESIGN.md`

- Modifying PerfReport workflow:
  - Code: `cerebrus/tools/perfreport/*`, `cerebrus/core/reporting/*`
  - Tests: `tests/tools/test_perfreport_*.py`, `tests/core/test_reporting_*.py`
  - Docs: `docs/PERFREPORTTOOL_REFERENCE.md`, `docs/output_filename_guide.md`

- Modifying runtime plugins:
  - Code: `cerebrus/plugins/<plugin>.py`
  - Tests: `tests/core/test_plugin_manager.py` or plugin-specific tests under the matching `tests/` area
  - Docs: `cerebrus/plugins/<plugin>.md`, `cerebrus/plugins/TESTING.md`

- Modifying plugin JSON/data contracts:
  - Code: owning plugin module
  - Tests: import/export and schema tests
  - Docs: plugin-local markdown, `docs/developer/TESTING_GUIDE.md`, and the user guide summary

## Output Requirements

The AI should:

- Prefer **unified diffs** for changes, grouped by file.
- Ensure all modified files remain syntactically valid.
- Avoid introducing unused imports, dead code, or commented-out blocks.
- Keep changes self-contained and well-described in comments and docstrings.

## Safety and Stability

The AI must:

- Preserve public APIs unless explicitly instructed to change them.
- Maintain backward compatibility for configuration formats where possible.
- Document any breaking changes clearly in:
  - `README.md` (high-level)
  - Relevant docs under `docs/developer` and plugin-local docs under `cerebrus/plugins`.

## Documentation Discipline

For any non-trivial change, the AI must:

- **Living User Guide**: Proactively update `cerebrus/resources/user_guide.html` if changes affect end-user workflows, UI, or feature sets. This file is the primary end-user reference.
- **Auto-Correction**: If recent code changes lack corresponding updates in the User Guide, the AI must flag this as an "Incomplete Feature" and perform the documentation update.
- **Developer Accountability**: Features implemented by human developers without accompanying AI-compatible documentation should be marked as "Missing Necessary Documentation" when next encountered by the AI.
- **Theme Integrity**: When updating `user_guide.html`, follow the specific rules in `.agent/workflows/user-guide-maintenance.md`.
- **Guide Style**: Preserve the Antigravity-style guide shell, visual hierarchy, badges, warning blocks, and navigation behavior. Update content within that style instead of flattening it.
- Ensure examples in docs reflect actual code.
- Avoid duplicating documentation; reference canonical locations where possible.

## Prohibited Behaviors

The AI must not:

- Introduce external network calls into the runtime code path.
- Hardcode developer-specific or machine-specific paths.
- Remove or bypass logging and error handling without replacement.

## Communication Guidelines

When interacting with the user, the AI must:

1.  **Concise Summaries**: Do NOT include file names, line numbers, or dense file paths in high-level summaries or commit messages unless **explicitly requested**.
2.  **Focus on Function**: Describe *what* changed and *why*, rather than *where* (e.g., "Updated Class Stats parsing logic" instead of "Modified line 45 of tabs/class_stats.py").
3.  **clean Commits**: Commit messages should be semantic and descriptive of the behavior change, devoid of file system implementation details and must be a copypastable raw markdown version with preview.

## Encouraged Patterns

- Use dataclasses and explicit models for configuration objects.
- Isolate external tool invocations in dedicated modules.
- Provide small, composable functions that are easy to test.

This configuration file should be kept up to date as the project grows and as new automation patterns emerge.
