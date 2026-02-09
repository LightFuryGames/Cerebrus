# Theme Specification

This document specifies how themes are configured and applied in the Dear ImGui UI.

## Scope

- **Applies to**: The Desktop Application (Dear PyGui).
- **Related**: Generated Reports (HTML/CSS). While technically independent (`cerebrus/tools/memreport/templates/style.css`), report styling **MUST** mirror the application's aesthetic (fonts, button styles, panel layouts) to ensure a unified user experience.

## Goals

- **Visual Consistency**: Ensure buttons, panels, and typography look identical across the Desktop App and HTML Reports.
- **Unified Theming**: Provide a consistent "Cerebrus" look using shared color tokens where possible.
- **Flexibility**: Allow project-wide dark/light or custom themes.
- **Configurability**: Permit advanced users to tweak colors and metrics via config files.

## Theme Configuration

- Theme config files (e.g. `config/themes/default.json`) define:
  - Color palette (background, text, accents).
  - Widget styles (button rounding, border sizes).
  - Spacing and padding.

Example (conceptual):

```json
{
  "palette": "CerebrusDark",
  "mode": "Dark",
  "colors": {
    "mvThemeCol_WindowBg": [25, 25, 30, 255],
    "mvThemeCol_Text": [240, 240, 245, 255],
    "mvThemeCol_Button": [40, 40, 50, 255]
  },
  "label_colors": {
    "header": [120, 180, 255],
    "subheader": [200, 200, 200]
  },
  "profile_status_colors": {
    "DEFAULT": [255, 210, 120],
    "LOADED": [15, 240, 15]
  },
  "log_colors": {
    "INFO": [120, 200, 255],
    "ERROR": [255, 120, 120]
  }
}
```

## Application

- Theme loader module in `cerebrus/ui/themes.py`:
  - Loads theme config.
  - Applies settings to ImGui style object on startup.
  - Exposes a function to switch themes at runtime.

## Accessibility

- Provide high-contrast variants where possible.
- Avoid relying solely on color to communicate status; use icons or labels as well.

## DPI & Scaling

To support High-DPI displays (4K monitors):

- **No Magic Pixels**: Never use hardcoded pixel values (e.g., `width=300`) for structural layout.
- **Global Scale Factor**:
  - All padding, spacing, and font sizes must be multiplied by `State.scale_factor`.
  - Example: `ImGui.push_style_var(ImGui.StyleVar_FramePadding, (4 * scale, 2 * scale))`
- **Fonts**:
  - The theme loader must reload fonts with a higher base pixel size when the scale factor changes.
