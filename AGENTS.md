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

## Communication Style

- Default to token-efficient technical communication: direct answer first,
  compact bullets or tables, minimal filler, and no repeated caveats.
- For code/debugging, prefer cause -> fix -> exact patch/command ->
  verification.
- Preserve exact names, paths, commands, API names, code symbols, and version
  numbers.
- Ask clarification only when the task cannot proceed safely or correctly.
- If the user asks for "caveman mode", compress further with fragments,
  arrows, and only meaning-critical words.
- If the user asks to "explain fully", return to clear normal explanation.

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

## Background Work and the Job System

- All non-trivial blocking work (network I/O, ADB, subprocess invocation,
  large file copies) MUST be dispatched through
  `cerebrus.core.jobs.JobScheduler` rather than being run inline on the
  DPG callback thread. The UI freezes for the duration of any work that
  runs on a callback, so audits flag every sync I/O call there as a
  bug.
- Use `cerebrus.core.jobs.get_default_scheduler()` to reach the
  process-wide scheduler; construct your own only in tests.
- Prefer atomics over mutexes. Python's GIL makes single attribute writes
  atomic; rely on that for status/state reads from foreign threads
  rather than wrapping each access in a `threading.Lock`. Use
  `threading.Event` for completion signalling.
- Declare dependencies via `Job.depends_on` so the Resource-Allocation-
  Graph cycle detector can reject cyclic submissions before they hit a
  worker. Treat `CyclicDependencyError` from `JobScheduler.submit` as a
  programming error, not a runtime exception.
- Long-running subprocesses must pass through `_silent_subprocess_kwargs`
  on Windows so console windows never flash on screen, and must declare
  a timeout. See `cerebrus/tools/adb.py` for the canonical pattern.

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

## Code-Audit Cycles

- All multi-agent audit artefacts (briefs, per-agent round reports,
  cross-review reports, mutual conclusions) live under `CodeAuditReview/`.
  Layout, severity legend, and the cycle phases (brief -> parallel audit ->
  cross-review -> mutual synthesis -> optional post-fix consent) are
  documented in `CodeAuditReview/README.md`.
- Reviewers: Claude Code (`cavecrew-reviewer` subagent) and Codex CLI
  (`codex exec`) run in parallel. Single-agent audits overfit to brief
  language; the cross-review step exists to catch that.
- Mutual conclusion files (`02_mutual_*.md` / `03_mutual_*.md`) are the
  ground truth, not individual agents' opinions. Treat them as the unit
  of work.
- Findings always anchor to `path:line` and carry a 🔴 / 🟡 / 🟢 severity
  emoji.
- Loose `.audit_*.md` at the repo root is gitignored so reviewers can
  scratch drafts without committing them. Durable artefacts MUST be moved
  under `CodeAuditReview/<YYYY-MM>-<scope>/` to be tracked.
