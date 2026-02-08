# Code Standards for Project Cerebrus

This document defines the **mandatory** coding standards for all contributions to this repository. It is designed to facilitate **pure AI-driven development**, ensuring consistency, testability, and scalability.

This document takes precedence when there is ambiguity. When in doubt, favor consistency with existing code.

---

## 1. Core Principles

1.  **AI-First Readability**: Code must be explicit. Avoid "magic" behavior. Docstrings must explain *why*, not just *what*, to provide context for future AI sessions.
2.  **Immutability by Default**: Prefer immutable data structures (`FrozenSet`, `Tuple`, frozen `dataclass`) to simplify state management.
3.  **Fail Fast, Fail Loud**: Do not swallow errors. UI layers catch exceptions; logic layers raise them with context.
4.  **Clarity over Cleverness**: Prefer standard, readable patterns over complex "clever" solutions.
5.  **Small & Focused**: Aim for a single responsibility per function or class.
6.  **Design for Testability**: Separate pure logic from I/O and process invocation.
7.  **Future-Proofing**: Code must be written with the assumption that it will be extended via plugins or updated for newer Unreal versions.
8.  **Avoid Premature Optimization**: Optimize only when you have measurements.

---

## 2. Project Structure

- **`cerebrus/core`**: Orchestration, config, state models, and central business logic.
- **`cerebrus/ui`**: Dear PyGui UI, layout logic, and theme management.
  - **`components/dialogs`**: Organized by functional area (aws, profile, app).
  - **`components/panels`**: Modular panels (profiling, logs, config_sync).
- **`cerebrus/tools`**: Thin, testable wrappers around external tools (UAFT, CsvTools, PerfReportTool, etc.).
- **`cerebrus/config`**: Configuration loading, schema validation, and profile management.
- **`cerebrus/cache`**: Cache operations and clean-up routines.
- **`cerebrus/installers`**: Installer scripts and environment validation logic.
- **`tests`**: Mirrors source layout for unit and integration tests.

> **Strict Rule**: No module in `ui` may import `subprocess` or call external tools directly; this must go through `core` and `tools` via Commands or the Event Bus.

---

## 3. Python Style & Quality

### 3.1 General Style
- Follow **PEP 8** where practical.
- Use **Type Hints** everywhere for public signatures. Use `typing.Protocol` and `TypedDict` for complex interfaces.
- Use **Dataclasses** for simple data containers.
- Avoid global state; prefer explicit dependency passing or factories.

### 3.2 Imports
- Use **absolute imports** within the `cerebrus` package.
- Order: Standard library -> Third-party -> Local `cerebrus` imports.

```python
import pathlib
import subprocess
from dataclasses import dataclass

import imgui
import psutil

from cerebrus.core.device import Device
from cerebrus.tools.csv import collate
```

### 3.3 Style Tools
- **Format**: `black`
- **Import Order**: `isort`
- **Type Checking**: `mypy` (Strict mode preferred)
- **Linting**: `ruff` or `flake8`

---

## 4. System Interactions

### 4.1 External Tools Wrappers
- All external tools must:
  - Be wrapped in focused Python modules.
  - Use **dependency injection** for binary paths.
  - Expose high-level functions that accept data structures, not raw CLI argument lists.
- Do not construct command strings in the UI or core layers.

### 4.2 Error Handling
- **Never silently swallow exceptions**.
- Wrap external tool calls (`subprocess`) and:
  - Capture `stdout`, `stderr`, and exit code.
  - Raise structured exceptions or return structured results with status.
- UI layer translates exceptions into user-facing notifications; logic layers must remain UI-agnostic.

### 4.3 Logging
- Use the central logging facility in `cerebrus.core.logging`.
- Log entry/exit for major workflows, tool invocations (sanitized), and non-zero exit codes.
- Correctly use levels: `DEBUG` (detail), `INFO` (flow), `WARNING` (recoverable), `ERROR` (failure).

---

## 5. Testing Standards

All new code **must** be accompanied by tests.

### 5.1 Test Layout
- **Unit Tests (`tests/unit/`)**: Fast, mock-heavy. **No File I/O. No System Calls.**
- **Integration Tests (`tests/integration/`)**: Tool wrappers, filesystem interactions.
- Framework: `pytest`. Use Arrange-Act-Assert structure.

### 5.2 Mocking
- Use `unittest.mock` or `pytest-mock`.
- **Forbidden**: Mocking internal private methods.
- **Required**: Mocking external boundaries (`subprocess`, `shutil`, `pathlib.Path.open`).

### 5.3 Test Data
- **Location**: `tests/data/`
- **Synthetic First**: Prefer generating test data strings in code over reading static files.
- **Anonymization**: Scrub all real-world test data of PII, IP addresses, and proprietary paths.

---

## 6. Configuration & Cache

### 6.1 Configuration Files
- Prefer **YAML** or **JSON**.
- Provide example files under `docs/config` or `config/examples`.
- Enforce schema validation before using config values.

### 6.2 Cache Management
- Use `cerebrus.cache.CacheManager` for any file-system level cache handling.
- Respect `max_entries` to avoid unbounded growth.
- New cache logic must include unit tests.

---

## 7. Local CI/CD Workflow

Before committing, run the local scripts to match the GitHub Actions pipeline:

- **Linting**: `./scripts/run_lint.ps1` (`black`, `isort`, `mypy`).
- **Preflight**: `./scripts/run_preflight.ps1` (Validates configuration wiring).
- **Testing**: `./scripts/run_tests.ps1` (Runs `pytest`).
- **Build**: `./scripts/build_pyinstaller.ps1` (Verifies binary creation).
- **Full Pipeline**: `./run_pipeline.ps1` (Sequential execution of all checks).

### 7.2 GitHub Actions Pipeline

The remote CI/CD pipeline executes three distinct stages on every Pull Request or Push to the **`dev-py`** branch or branches matching the **`Feat/*`** pattern:

1.  **Lint**: Enforces code style using `black --check`, `isort --check-only`, and strict `mypy` type checking.
2.  **Preflight**: Executes `python -m cerebrus.core.preflight` to ensure the core logic can initialize, configuration schemas are valid, and cache directories are correctly setup.
3.  **Unit Tests**: Executes the full `pytest` suite for the `tests/unit/` directory.

### 7.3 Release & Tagging System

Cerebrus uses a semi-automated release system:

- **Tagging**: Pushing a tag matching the `v*` (or `V*`) pattern (e.g., `v.2.1.0`) triggers the Production Release workflow.
- **Branch Restriction**: Releases are only generated if the tag is based on the **`main`** or **`dev-py`** branches.
- **Artifact Build**: GitHub Actions compiles the source into a standalone `.exe` using PyInstaller and wraps it into a `Cerebrus_Setup.exe` installer using Inno Setup.
- **Distribution**: The built installer and a source `.zip` are automatically attached to a new GitHub Release.
- **Update Notification**: The client application detects these new tags via the GitHub API and prompts users to update.

---

## 8. Tool & Parsing Standards (Modular Tool Pattern)

To support extensibility and automated analysis, all parsing logic must follow this pattern:

1.  **Raw Data Model**: A dataclass exactly mirroring the file structure.
2.  **Parser**: A pure function `str -> DataModel`.
    - Use **Named Regex Groups** (`(?P<name>...)`).
    - Handle partial/malformed lines gracefully (log warning, skip, continue).
3.  **Analyzer/Transformer**: `DataModel -> ReportViewModel`.
    - Implementation of sorting, filtering, and aggregation.
4.  **Renderer**: `ReportViewModel -> HTML/UI`.
    - **Strict Separation**: HTML generation must never call parsers directly.

---

## 9. Architecture & Roadmap Readiness

### 9.1 Plugin System
- All major components (Tabs, Tools, Devices) must be defined as `typing.Protocol` interfaces.
- Use registry patterns instead of hardcoded lists.

### 9.2 Modular UI
- UI components should be pure functions where possible (Input: `State` -> Output: `RenderArgs`).
- **Refactor Trigger**: If a `draw()` function exceeds 50 lines or contains business logic, it must be refactored.

### 9.3 UI Scaling
- Avoid magic pixels. Use relative sizes or scaling multipliers.

---

## 10. AI Collaboration & Commit Discipline

### 10.1 Refactoring Triggers

Refactor code when it becomes difficult to maintain, rather than following strict numerical limits. Suggest refactors if:

- **Indentation Depth**: A function has deeply nested loops or conditionals that make the logic hard to track at a glance.
- **Difficulty Testing**: If you find yourself needing to mock more than 3-4 internal components just to test a single function, the function is likely doing too much.
- **Over-reaching Modules**: If a single file starts handling multiple unrelated responsibilities (e.g., parsing AND UI rendering AND network calls), it should be split.
- **Duplication**: If the same logic is being copied and modified across different files, abstract it into `core` or `utils`.
- **"Spaghetti" Logic**: If a change in one place causes unexpected breakages in distant parts of the code, it's a sign that coupling is too high.

### 10.2 Commit Discipline
- **Feature-Centric**: Commits should include a complete logical unit (Parser + UI + Tests).
- **Avoid Partial States**: Do not commit broken builds.
- **Semantic Headers**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
- **Descriptive**: Include bullet points for key changes.

### 10.3 Documentation
- **Update on Write**: Behavior changes require immediate updates to `docs/developer/*.md`.

---

## 11. Languages and Versions

- **Python**: Target **3.12+**.
- **OS**: Windows 10/11 (64-bit).
- **Style Enforcement**: `black`, `isort`, `mypy` (Strict).
