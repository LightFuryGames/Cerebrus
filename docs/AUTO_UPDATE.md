# Auto-Update & Release Process

Cerebrus uses a **Tag-Based** release workflow powered by GitHub Actions.

## The Release Flow

1.  **Tagging**: A developer pushes a tag matching `v.*.*.*` (e.g., `v.2.0.0.1`).
2.  **Validation**: CI ensures the commit passes Linting and Tests.
3.  **Build**:
    - `PyInstaller` compiles the source into a standalone `.exe`.
    - `Inno Setup` wraps dependencies (ADB helpers, .NET checks) into `Cerebrus_Setup.exe`.
4.  **Draft Release**: A GitHub Release is created with the artifacts attached.
5.  **Auto-Update**: The client application checks the GitHub API for newer tags.

## Client-Side Update Mechanism

The client (running on user machine) performs checks on startup:
1.  **Poll**: Queries `https://api.github.com/repos/LightFuryGames/Cerebrus/releases/latest`.
2.  **Compare**: Checks `latest_tag` > `current_version`.
3.  **Prompt**: If new version exists, prompts user.
4.  **Download**: Pulls the `Setup.exe` to `%TEMP%`.
5.  **Execute**: Silent install / relaunch.

## Troubleshooting

### "Update Detected" but fails to install
- **Cause**: User lacks Admin rights or File is locked.
- **Fix**: Run as Admin manually.

### "Version Mismatch"
- **Cause**: The internal version string in `cerebrus/__init__.py` was not bumped to match the Git Tag.
- **Fix**: Ensure the `release.yml` workflow correctly injects the version, or update `__init__.py` manualy before tagging.
