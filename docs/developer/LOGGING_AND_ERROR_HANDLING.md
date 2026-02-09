# Logging and Error Handling

This document defines how logging and error handling should work across Cerebrus.

## Logging

- Provide a central logging utility in `cerebrus/core/logging.py`.
- Use Python’s `logging` module under the hood.
- Define loggers per module (`__name__`).

Log levels:

- `DEBUG` – detailed, low-level diagnostic information.
- `INFO` – high-level application flow.
- `WARNING` – recoverable issues that may need attention.
- `ERROR` – failures that likely affect user workflows.

## UI-Centric Logging

In the UI layer (`cerebrus/ui/components/`), use the `log_message(state: UIState, level: str, message: str)` helper. This ensures:
- The message appears in the application's **Logging Panel**.
- It is appropriately color-coded (SUCCESS, INFO, WARNING, ERROR).
- It is saved to the production log file if persistent logging is enabled.

## Error Handling Strategy

- Validate critical configuration at startup and fail fast.
- Wrap external tool invocations:
  - Handle `FileNotFoundError` separately for missing binaries.
  - Interpret non-zero exit codes as errors, not success.
- Use custom exception types for:
  - Configuration errors.
  - Tool invocation errors.
  - Device-related errors.

## UI Interaction

- Lower layers (core, tools) should raise exceptions or return structured error results.
- The UI translates these into:
  - Non-modal notifications for minor issues.
  - Modal dialogs for blocking failures.

- Error messages shown to users should:
  - Be concise and actionable.
  - Avoid overwhelming technical detail.
  - Offer clear next steps when possible.

Logging remains the place for full technical detail.
