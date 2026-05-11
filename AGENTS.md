# Cerebrus Multi-Agent Working Rules

This repository is edited by multiple AI agents, including Codex, Claude Code,
Gemini, and Antigravity. Treat this file as the shared operating contract.

## Before Editing

- Run `git status --short --branch` before making changes.
- Do not overwrite, revert, or reformat another agent's uncommitted work unless
  the user explicitly asks for that.
- Keep work scoped by category: runtime code, tests, docs, build/package, or
  generated artifacts.
- Preserve the Antigravity-style `cerebrus/resources/user_guide.html` visual
  system. Update content inside that style instead of flattening the guide.

## Plugin System Rules

- Runtime plugins live under `cerebrus/plugins`.
- Plugin-specific markdown lives with the plugin under `cerebrus/plugins`.
- Plugin resources live under `cerebrus/plugins/resources` and must be included
  in frozen builds.
- Plugin behavior should be data-driven where practical. Prefer explicit JSON
  schema fields over implicit string formats.
- Plugins that expose tab UI implement `TabPlugin`.
- Plugins that expose `Settings -> Plugins` menu actions implement `MenuPlugin`.

## AWS And Secret Handling

- Never commit AWS keys, `.cbx` files, local secret JSON files, or generated
  credential exports.
- `.cbx` files are portable JSON bucket/key-alias maps. They must not contain
  access key IDs or secret access keys.
- Local AWS key storage requires DPAPI encryption. If DPAPI is unavailable, the
  app must refuse to persist new AWS keys instead of writing plaintext secrets.
- Imported AWS aliases may require credential re-entry after import.

## Testing

- On this Windows workspace, default pytest temp/cache paths can hit ACL errors.
  `pyproject.toml` already sets pytest to use `.pytest_run_tmp` and disables
  the cache provider. A normal focused run should be:

```powershell
python -m pytest <tests>
```

- If an external runner ignores `pyproject.toml`, use this command shape:

```powershell
$env:TEMP = (Join-Path (Get-Location).Path '.pytest_run_tmp')
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
python -m pytest -p no:cacheprovider --basetemp .pytest_run_tmp <tests>
```

- Remove `.pytest_run_tmp` after test runs.
- Do not claim full-suite success unless the full suite actually ran.

## Documentation

- The HTML user guide is the end-user guided tour.
- Plugin markdown is the detailed plugin-local reference.
- Developer docs explain architecture, build, tests, and agent process.
- When code behavior changes, update the relevant plugin markdown, user-facing
  summary, and tests together.
