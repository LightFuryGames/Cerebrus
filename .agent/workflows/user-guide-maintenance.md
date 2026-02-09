---
description: Maintain and update the Cerebrus User Guide (user_guide.html) while preserving theme, accessibility, and navigation features.
---

# Cerebrus User Guide Maintenance Workflow

This workflow provides instructions for AI agents on how to safely update the `user_guide.html` file.

## 1. Theme and Accessibility Consistency
- **Preserve CSS Variables**: Always work within the defined `:root` and `body.light-mode` CSS variables. Do not hardcode colors in the body unless absolutely necessary for specific highlights.
- **Maintain Contrast**: Ensure all manual style overrides (like `pre code`) maintain high contrast in both Light and Dark modes.
- **Check Theme Classes**: Use `.note-orange`, `.note-red`, `.warning-box`, and `.highlight-red` for consistent alerting.

## 2. Navigation and Scroll Spy
- **Sidebar Structure**: The `aside` element contains the Table of Contents (TOC). Ensure every `section` in the `main` content has a matching `id` linked in the `aside nav`.
- **Bottom Navigation**: Always keep the navigation spacer (`<div style="height: 50vh;"></div>`) at the end of the `main` content. This ensures that the last navigation links can reach the top of the viewport for the scroll-spy to activate.
- **Scroll Top Button**: Keep the `#scroll-top` button logic in the `<script>` tag intact.

## 4. Specific Highlighting Rules
- **Terminology & Convention**: 
    - **"Code highlight"** or **"code block highlight"**: Always use the `<code>` tag.
    - **"Color + Code highlight"** (e.g., "red code highlight"): Use the `<code>` tag combined with the appropriate semantic class (e.g., `<code class="highlight-red">`).
    - Use these conventions for all future iterations to ensure visual consistency with the existing design system.
- **Semantic Highlighting Classes**:
    - **Failure (<code class="highlight-red">red</code>)**: Mandatory for critical errors (e.g., "No", "Logging is disabled", "Incompatible", "Tool Not Found").
    - **Success (<code class="highlight-green">green</code>)**: Mandatory for positive states (e.g., "Yes", "Connected").
    - **Warning (<span class="highlight-orange">orange</span>)**: Used for optional steps, important caveats, or diagnostic notes.
    - **Info/Status (<span class="highlight-blue">blue</span>)**: Used for functional keywords defining state (e.g., `foreground`, `active`).
- **Links**: Ensure external links or internal jumps use the accent color variables.

## 5. Interactive Feature Documentation
- **Living Descriptions**: Always include specific highlights for advanced dashboard features:
    - `Actor Hierarchy`: Tree-view relationships.
    - `Threshold/Multi-toggle Filtration`: Logic for noise reduction.
    - `Report Validations`: Highlighting how `Warnings` and `Errors` help users.

## 5. Script Integrity
- Do not remove or break the `initTheme()`, `themeToggle`, or `window.onscroll` logic. These provide the core interactive features of the documentation.

## 6. Living Guide Policy (AI-Specific)
- **Mandatory Proactivity**: Whenever you (the AI) implement or modify a feature that affects the end-user (UI buttons, workflows, configuration options), you MUST update `user_guide.html` in the same session.
- **Documentation Audit**: If you encounter code changes in the repository that are not accurately reflected in the User Guide, treat this as a "Documentation Bug" and fix it immediately.
- **Reporting Incompleteness**: If a feature is missing documentation and cannot be adequately documented within the current context, flag it explicitly in your summary as "Incomplete Feature - Missing Documentation".
- **Living Reference**: Treat `user_guide.html` as the source of truth for the end-user. All descriptions must be technically accurate but accessible to non-engineers (e.g., Tech Art, QA).
