# Cerebrus Plugins

Plugin documentation lives beside the plugin code. Each runtime plugin owns a
subdirectory under `cerebrus/plugins/<plugin_id>/`; keep detailed user and
developer notes there, then link to them from this overview and `docs/` instead
of duplicating plugin behavior in many places.

## Simple Picture

Think of Cerebrus as a work table with slots.

- The main app owns the table: profiles, devices, logs, themes, and report generation.
- A plugin is a labeled tool tray that can be placed on that table.
- If the plugin is enabled, Cerebrus shows its tab and any menu actions.
- If the plugin is disabled, the tool tray stays closed until the user turns it on again.

## Current Runtime Plugins

| Plugin | Package | User Purpose | Documentation |
| --- | --- | --- | --- |
| Profiling | `profiling/plugin.py` | Main device, capture, file move, and report workflow. | [profiling/README.md](profiling/README.md) |
| AWS Secrets | `aws_secrets/plugin.py` | Local key and bucket manager used by cloud plugins. | [aws_secrets/README.md](aws_secrets/README.md) |
| S3 Uploader - Profiling Reports | `s3_uploader/plugin.py` | Upload generated HTML profiling reports to mapped S3 buckets. | [s3_uploader/README.md](s3_uploader/README.md) |
| Analytics & Trends | `analytics/plugin.py` | Normalize generated reports into trend, comparison, and Elasticsearch-ready analytics files. | [analytics/README.md](analytics/README.md) |

Plugin-owned support code should stay inside that plugin directory. For example,
Analytics conversion/parsing code lives under `analytics/core` because it exists
to support the Analytics plugin rather than a shared core application workflow.

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
- Plugin tooltip resources: `cerebrus/plugins/<plugin_id>/resources/tooltips.json`

Do not encode behavior only in display strings when a JSON field can carry the meaning directly.

## Lifecycle

1. `CerebrusApp.build()` registers plugin instances.
2. `PluginManager.initialize()` loads the local plugin cache from `%LOCALAPPDATA%/Cerebrus/plugins.json`.
3. New plugins are enabled by default so users can see newly shipped features.
4. Explicitly disabled plugins stay disabled because the cache tracks known plugin IDs.
5. `render_tabs()` rebuilds the tab bar from enabled plugins.
6. Users can reorder tabs from `Settings -> Plugins`; the order is cached in
   `%LOCALAPPDATA%/Cerebrus/plugins.json`.

## Documentation Rules

- Plugin-specific user help belongs in this folder.
- General docs should summarize plugin behavior and link here.
- End-user docs should explain the workflow plainly and avoid internal implementation details.
- Developer docs should describe the contract, lifecycle, packaging needs, and test expectations.

## Packaging Notes

Plugins that use data files must keep those files under their own plugin
directory so PyInstaller can bundle them with the rest of the plugin package.
Current plugin tooltip JSON files live at
`cerebrus/plugins/<plugin_id>/resources/tooltips.json`.

## Test Index

The current and proposed test coverage for the plugin system is tracked in [TESTING.md](TESTING.md).
