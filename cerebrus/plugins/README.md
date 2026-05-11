# Cerebrus Plugins

Plugin documentation lives beside the plugin code. Keep the detailed user and developer notes in this folder, then link to them from `README.md` and `docs/` instead of duplicating plugin behavior in many places.

## Simple Picture

Think of Cerebrus as a work table with slots.

- The main app owns the table: profiles, devices, logs, themes, and report generation.
- A plugin is a labeled tool tray that can be placed on that table.
- If the plugin is enabled, Cerebrus shows its tab and any menu actions.
- If the plugin is disabled, the tool tray stays closed until the user turns it on again.

## Current Runtime Plugins

| Plugin | File | User Purpose | Documentation |
| --- | --- | --- | --- |
| Profiling | `profiling_plugin.py` | Main device, capture, file move, and report workflow. | [profiling.md](profiling.md) |
| AWS Secrets | `aws_secrets.py` | Local key and bucket manager used by cloud plugins. | [aws_secrets.md](aws_secrets.md) |
| S3 Uploader - Profiling Reports | `s3_uploader.py` | Upload generated HTML profiling reports to mapped S3 buckets. | [s3_uploader.md](s3_uploader.md) |

The top-level `Plugins/ConversionTools` directory is not part of the runtime tab plugin system. Treat it as experimental or legacy conversion utility code until it is either moved under `cerebrus/plugins` with a `TabPlugin` wrapper or formally archived.

## Plugin Contract

Runtime UI plugins implement the `TabPlugin` protocol from `cerebrus.core.plugins`:

```python
class TabPlugin(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def build_tab(self, state: UIState) -> None: ...
```

Plugins that expose extra menu actions implement `MenuPlugin`:

```python
class MenuPlugin(TabPlugin, Protocol):
    def build_menu(self, state: UIState) -> None: ...
```

The main menu places `MenuPlugin` actions under `Settings -> Plugins -> <Plugin Name>`.

## Data-Driven Plugin Files

Prefer explicit JSON contracts for plugin state and transfer files:

- Runtime enablement cache: `%LOCALAPPDATA%/Cerebrus/plugins.json`
- AWS local secret store: `%LOCALAPPDATA%/Cerebrus/aws_secrets.json`
- AWS allowed regions: `%LOCALAPPDATA%/Cerebrus/aws_regions.json`
- AWS portable mappings: `.cbx` JSON with `schema_version` and `contains_secret_values`
- Plugin tooltip resources: `cerebrus/plugins/resources/*.json`

Do not encode behavior only in display strings when a JSON field can carry the meaning directly.

## Lifecycle

1. `CerebrusApp.build()` registers plugin instances.
2. `PluginManager.initialize()` loads the local plugin cache from `%LOCALAPPDATA%/Cerebrus/plugins.json`.
3. New plugins are enabled by default so users can see newly shipped features.
4. Explicitly disabled plugins stay disabled because the cache tracks known plugin IDs.
5. `render_tabs()` rebuilds the tab bar from enabled plugins.

## Documentation Rules

- Plugin-specific user help belongs in this folder.
- General docs should summarize plugin behavior and link here.
- End-user docs should explain the workflow plainly and avoid internal implementation details.
- Developer docs should describe the contract, lifecycle, packaging needs, and test expectations.

## Packaging Notes

Plugins that use data files must ensure those resources are bundled in PyInstaller builds. Current plugin tooltip JSON files live in `cerebrus/plugins/resources`; the packaging spec should include that folder before release validation.

## Test Index

The current and proposed test coverage for the plugin system is tracked in [TESTING.md](TESTING.md).
