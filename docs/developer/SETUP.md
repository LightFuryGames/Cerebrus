# Developer Setup

This guide describes how to configure a development environment for Project Cerebrus.

## Clone and Environment

1. Clone the repository:

   ```bash
   git clone <REPO_URL> cerebrus
   cd cerebrus
   ```

2. Create a virtual environment:

   ```bash
   py -3 -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Development Tools

Recommended tools:

- Python 3.12 (64-bit).
- Visual Studio Code, PyCharm, or equivalent.
- Git with a graphical diff tool (e.g. Beyond Compare, WinMerge).
- Optional:
  - `pre-commit` for automated formatting and linting.

## Running Tests

- To run all tests:

  ```powershell
  ./scripts/run_unittests.ps1
  ```

- To run a subset:

  ```bash
  pytest tests/core/test_device_manager.py
  ```

## Helper Scripts

To simplify development, we provide PowerShell scripts that mirror our CI/CD pipeline. Always run these before pushing code.

- **Linting**:
  ```powershell
  ./scripts/run_lint.ps1
  ```
  Runs `black` (formatting), `isort` (import sorting), and `mypy` (type checking). This matches the GitHub `lint` workflow.

- **Preflight Checks**:
  ```powershell
  ./scripts/run_preflight.ps1
  ```
  Validates project structure, configuration schemas, and cache directories. Fail signatures here mean the app won't start effectively.

- **Unit Tests**:
  ```powershell
  ./scripts/run_unittests.ps1
  ```
  Runs the `pytest` suite under the current `tests/` tree.

- **Plugin Tests**:
  Plugin coverage expectations live in `cerebrus/plugins/TESTING.md`.

- **Full Pipeline**:
  ```powershell
  ./run_pipeline.ps1
  ```
  Executes the entire chain: Lint -> Preflight -> Tests -> Build. This is the ultimate "it works" check before pushing.

- **Dependencies**:
  ```powershell
  ./scripts/install_dependencies.ps1
  ```
  Ensures Python 3.12, ADB, and .NET runtimes are installed. Useful for setting up a new machine.

- **Building**:
  ```powershell
  ./scripts/build_pyinstaller.ps1
  ```
  creates a production-ready EXE and Installer locally.

## Static Checks

- Run `mypy` for type checking:

  ```bash
  mypy cerebrus
  ```

- Run `black` and `isort` to format code:

  ```bash
  black cerebrus tests
  isort cerebrus tests
  ```

Refer to `CODE_STANDARDS.md` for more details on the coding style.
