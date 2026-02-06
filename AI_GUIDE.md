# AI Guide for Project Cerebrus

The AI is the code-generation and refactoring engine used on this repository. This guide defines how to collaborate with the AI in a controlled, deterministic way.

## Core Principles

1. **The AI is an assistant, not an authority.**
   - Humans own architectural decisions.
   - The AI must work within the documented architecture.

2. **Context over Explicit Instruction.**
   - Users may be vague (e.g., "fix this", "update the docs").
   - The AI must infer intent from open files, cursor position, and project state.
   - Propose concrete actions rather than asking for step-by-step hand-holding.

3. **Think "Studio-Scale".**
   - The tool runs in diverse environments (different Perforce streams, different Projects).
   - Avoid hardcoding paths like `C:/UE5/`. Use stream-relative resolution logic.
   - Always ask: "Will this work if I switch from Project A to Project B?"

4. **Outputs must be reviewable.**
   - The AI must provide unified diffs and rationale where requested.
   - All changes go through regular code review.


## Handling Vague Requests

Real-world usage is often less formal than "update file X at line Y". The AI should:

1.  **Infer Context**:
    - If the user says "cleanup code", look at the active file for lint errors or unused imports.
    - If the user says "it's broken", check recent terminal errors or log files.
2.  **Be Proactive**:
    - Do not wait for perfect specs. Propose the most likely solution based on common patterns.
    - Example: User says "add a button". AI should add the button code *and* the callback skeleton, matching existing UI patterns.
3.  **Ask vs. Act**:
    - **Act** immediately on safe, reversible changes (adding files, updating docs, local fixes).
    - **Ask** only when high ambiguity poses a risk (e.g., "delete all temp files" - *which* temp files?).

## Preferred Output Format

Ask the AI to:

- Provide changes as unified diffs with `@@` hunk markers.
- Group diffs by file.
- Avoid mixing unrelated changes in a single diff.

### Examples of Intent-Based Requests

The AI adapts to the specificity of the request:

1. **High-Level (Preferred)**:
   > "Prevent the CSV collate tool from hanging indefinitely."
   *   **AI Action**: Finds `cerebrus/tools/csv/collate.py`, adds a timeout parameter, and updates docs.

2. **Low-Level (Specific)**:
   > "Add `timeout_sec` to `run_collate` in `collate.py`. Provide diffs."
   *   **AI Action**: Implements strictly as requested.

**Note on Summaries**: Unless explicitly asked, do **not** clutter responses with file paths or line numbers. Focus on feature-level or architecture-level explanations.

## Documentation Expectations

For any substantive change, the AI should:

- Update relevant `.md` files.
- Add or update docstrings for new public classes and functions.
- Ensure examples in docs remain correct.

Examples:

- Wrappers for complex tools (like `memreport`) should follow the **Modular Tool Pattern**:
  - `main.py`: Entry point and orchestration.
  - `parsing.py` / `tabs/`: Specialized parsing logic separated by concern.
  - `template.py`: HTML/Report templates.
- Wrapping a new CsvTools mode → update `docs/CSVTOOLS_REFERENCE.md`.
- Changing report generation behavior → update `docs/PERFREPORTTOOL_REFERENCE.md`.
- Adjusting module boundaries → update `docs/ARCHITECTURE_OVERVIEW.md`.

## Testing Expectations

Every new feature or bug fix implemented by the AI should include tests where practical:

- Unit tests for pure logic.
- Integration tests for wrappers around external tools (using lightweight, synthetic data where possible).

AI tasks should include instructions like:

- “Add unit tests under `tests/tools/test_csv_collate.py` for the new behavior.”
- “Ensure tests cover failure modes such as missing binaries or invalid CSV inputs.”

## Review and Acceptance

Human reviewers must:

- Validate that the AI respected the constraints.
- Check for hidden assumptions and unhandled error cases.
- Confirm that logging is adequate for troubleshooting.
- Run tests and verify they pass.

If AI output is not aligned, request a follow-up task with more explicit constraints or adjust the architecture documentation accordingly.
