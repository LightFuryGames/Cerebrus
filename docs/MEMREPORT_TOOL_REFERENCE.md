# MemReport Tool Reference

The **MemReport** tool is a component of Cerebrus designed to parse, analyze, and visualize Unreal Engine `.memreport` and `obj list` dumps.

## Architecture: The Modular Tool Pattern

The tool follows a strict **Data -> Parser -> Analyzer -> Renderer** pipeline to ensure extensibility.

### 1. Tab Definition
Each "View" in the report is a separate `ReportTab` subclass located in `cerebrus/tools/memreport/tabs/`. These tabs look for specific sections/markers in the log file.

| Tab Name | Source File | Targets Command | Purpose / Optimization Value |
| :--- | :--- | :--- | :--- |
| **Object Summary** | `obj_summary.py` | `obj list -alphasort` | **High-Level Overview**. Shows total memory by class. Vital for spotting which *types* of assets (e.g., StaticMesh vs Texture) are consuming the most memory globally. |
| **Class Stats** | `class_stats.py` | `obj list class=...` | **Specific Instance Tracking**. Detailed list of every instance of a specific class. Used to find "Leaks" (too many instances) or "Heavy Assets" (instances that are unexpectedly large). |
| **Persistent Actors** | `persistent_actors_stats.py` | `obj list -persistent` | **Level Overhead**. Lists actors specifically in the Persistent Level. critical for optimizing the "base cost" of a map that is always loaded. |
| **Textures** | `texture_stats.py` | `listtextures` | **VRAM Usage**. Lists all loaded textures, their format, and dimensions. Critical for spotting 4K textures that should be 512x, or uncompressed UI assets. |
| **RHI Stats** | `rhi_stats.py` | `stat RHI` | **GPU/Render Resource Limits**. Tracks Vertex buffers, Index buffers, and Draw Calls. Essential for diagnosing "Out of Video Memory" crashes or render thread bottlenecks. |
| **Render Targets** | `render_target_pool.py` | `rhi.DumpRenderTargetPool` | **Transient GPU Memory**. Analyzes temporary buffers used for Post Processing. Helps identify if the pool is too large or if passes are not being reused correctly. |
| **Particles** | `particle_stats.py` | `ParticleSystem` | **FX Cost**. Tracks active particle systems. vital for CPU simulation cost and memory usage of visual effects. |
| **Level Loading** | `level_stats.py` | `LogOutStatLevels` | **Streaming Performance**. Analyzing how long levels make to load and their memory footprint. Important for open-world streaming optimization. |
| **Config Cache** | `config_cache_memory_stats.py` | `Config Cache Stuff` | **System Overhead**. Tracks memory used by the detailed configuration cache (INI files). |
| **Detailed Lists** | `detailed_lists.py` | (Various) | **Deep Dives**. Special handling for specific complex object lists not covered by generic summaries. |

### 2. Parsing Logic
Parsers must be robust against partial lines and version differences (UE4 vs UE5).

- **Regex**: Use named groups for clarity.
  ```python
  # Good
  re.search(r"Class:\s+(?P<class_name>\w+)", line)
  ```
- **State**: Parsers are stateful per-file but should reset cleanly between files.

### 3. HTML Generation
We use a template-based approach to generate self-contained HTML files.
- **Dependencies**: The HTML output is "Zero-Dependency" (inline CSS/JS).
- **Interactivity**: JS filters (Search/Sort) are embedded in the HTML.
- **Embedded Metadata**: Every report now includes a `<script type="application/json" id="cerebrus-metadata">` block. This block contains the Build Config, Device Make/Model, Changelist, and Date. This allows plugin tools such as the S3 Uploader to process the report without re-parsing visible text. S3 details live in `cerebrus/plugins/s3_uploader.md`.

### 4. Automatic Naming
To ensure reports are easily manageable in bulk, the tool automatically names outputs using the following pattern:
`{BuildConfig}_{DeviceMake}_{DeviceModel}_{Changelist}_{DateTime}.html`

This naming is deterministic and derived directly from the `metadata` context.

## Adding a New Tab

To add support for a new section (e.g., `obj list class=ParticleSystem`):

1.  **Create Module**: `cerebrus/tools/memreport/tabs/particle_stats.py`.
2.  **Inherit**: `class ParticleStatsTab(ReportTab)`.
3.  **Implement `should_handle(line)`**: Return `True` when you see the start code.
4.  **Implement `parse(line)`**: Extract data into the context.
5.  **Implement `render()`**: Return HTML string for the tab content.
6.  **Register**: Add to `cerebrus/tools/memreport/main.py`.

## Supported Commands & Analysis Goals

The tool parses various specific Unreal Engine console commands. Here is what a developer looks for in each:

-   **`memreport -full`**: The "Kitchen Sink" dump.
    -   *Why it's important*: Top-level snapshot of the entire game state.
    -   *Look for*: Global memory pressure, platform limits.
-   **`obj list -alphasort`**:
    -   *Why it's important*: Grouping by class reveals outlier counts.
    -   *Look for*: "Do we really need 50,000 instances of `BP_Coin_C`?"
-   **`obj list -resourcesizesort`**:
    -   *Why it's important*: Sorting by size reveals heavy assets.
    -   *Look for*: Single Assets > 50MB (likely uncompressed audio or raw textures).
-   **`rhiitargets` (Render Targets)**:
    -   *Why it's important*: High-res render targets consume massive VRAM separate from textures.
    -   *Look for*: Duplicate 4K buffers or unused buffers in the pool.

## Configuration

Feature flags for MemReport can be found in `config/memreport_config.yaml` (if implemented). Currently, most configuration is implied by the active Profile.
