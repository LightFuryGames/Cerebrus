# Product Roadmap

This document outlines the strategic direction for Project Cerebrus. It serves as a guide for both human developers and AI agents to prioritize work.

## Core Philosophy
Move from a "Local Script Wrapper" to a "Professional Game Development Tool" with a robust plugin architecture, highly responsive UI, and automated QA capabilities. The tool must function seamlessly across different Perforce streams and Unreal Engine versions (UE4/UE5).

---

## ✅ Completed (Recent Enhancements)
- **Advanced Memory Reporting**: Modular tool with 13 specialized tabs (Class Stats, Texture Stats, etc.).
- **Organized Output System**: Automatic sorting into `/Profiling` and `/MemReports`.
- **HTML Report Enhancements**: Dark Mode toggle and Scroll-to-Top functionality.
- **Native File Dialogs**: Transitioned to native OS dialogs for better UX.
- **Plugin Architecture**: Modular `PluginManager` with support for dynamic tab registration and custom menus.
- **AWS S3 Integration**: Secure credential management (AWS Secrets) and automated report uploading (S3 Uploader) with metadata-driven pathing.

## 🎨 Priority 2: Modular UI Refactor
*Objective: Decouple UI rendering from business logic to enable scaling and theming.*

- **Goal**: Refactor `components.py` into a "Functional UI" library.
- **Requirements**:
  - Components (Buttons, Tables, Trees) must be pure functions taking `State` and returning `Events`.
  - Elimination of immediate-mode spaghetti (logic mixed with `imgui.begin`).
  - Strict separation: `ui/` folder generally forbids `subprocess` imports.
- **Benefit**: Easier testing of UI logic, consistent styling.

## 🖥️ Priority 3: UI Scaling & DPI Support
*Objective: Ensure Cerebrus looks perfect on 4K monitors and high-DPI laptops.*

- **Goal**: Remove all hardcoded pixel values.
- **Requirements**:
  - Use ImGui style variables for padding/spacing based on font size.
  - Implement a global `ScaleFactor` multiplier in the Config.
  - Replace fixed-width columns with relative/weighted columns.
- **Benefit**: Professional polish and usability on diverse developer hardware.

## ⌨️ Priority 4: DevConsole & Debug Commands
*Objective: Power-user efficiency and automation groundwork.*

- **Goal**: Add a Quake-style drop-down console (`~` key).
- **Requirements**:
  - Implement **Command Pattern**: `Execute(cmd_name, args)`.
  - Expose core actions (Pull Logs, Gen Report) as text commands.
  - History, auto-completion, and command aliases.
- **Benefit**: rapid iteration for power users; foundation for Macros.

## 📉 Priority 5: Performance Diff Tab
*Objective: Automated regression testing for performance.*

- **Goal**: Compare two CSV or MemReport files effectively.
- **Requirements**:
  - Visual 'Diff' view: Red (worse), Green (better), Grey (same).
  - Tolerance configuration (e.g., "Ignore variance < 5%").
  - Export Diff Report to HTML.
- **Benefit**: Immediate visibility into performance regressions between builds.

## 🤖 Priority 6: QA Event Macro Recorder
*Objective: Deterministic reproduction of bugs and automated profiling loops.*

- **Goal**: Record user interactions and replay them.
- **Requirements**:
  - **Event Sourcing**: All state mutations must publish an event.
  - Recorder: Serialize event stream to JSON.
  - Player: Rehydrate state from JSON stream.
- **Benefit**: QA can record a "Capture Sequence" (Connect -> Launch -> Profiler Start -> Wait 10s -> Stop -> Pull) and devs can replay it exactly.

---

## 🧊 Backlog (Future)
- **Unreal Insights Integration**: Launch and control Insights from Cerebrus.
- **Linux Support**: Porting the fast-installer and UI to generic Linux.
