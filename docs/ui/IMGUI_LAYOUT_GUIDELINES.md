# ImGui Layout Guidelines

Guidelines for constructing Dear ImGui layouts in Cerebrus.

## General Principles

- Use a **main dockspace** layout:
  - Top Bar: **Current Project / Profile** indicator (Critical for multi-project safety).
  - Left: Devices and project/config panels.
  - Center: Capture and report panels.
  - Bottom or right: Logs and diagnostics.
- Avoid deep nested trees; prefer flat sections with clear labels.

## Panels

Suggested layout:

- **Devices Panel**:
  - Table with device details and selection controls.
- **Capture Panel**:
  - Controls for capture type, profile, and run options.
- **Reports Panel**:
  - List of runs, report generation options, and quick links to outputs.
- **Config Panel**:
  - Editing of tool paths and profile selection.

## Interaction Patterns

- Each frame:
  - Read current state.
  - Draw UI.
  - Apply state changes after drawing logic.
- Avoid expensive operations in the rendering path; delegate to background tasks or triggered actions where possible.

## Consistency

- Reuse widgets for:
  - Device selectors.
  - Profile selectors.
  - File path pickers.
- Keep button text concise (e.g. “Capture”, “Generate Report”, “Open Folder”).

These guidelines will evolve as actual UI code is implemented.
