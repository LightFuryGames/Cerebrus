"""Build cerebrus/resources/user_guide_v2.html.

Reuses the head/style block from user_guide.html, then writes a re-organized
body with a tighter editorial pass.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "cerebrus" / "resources" / "user_guide.html"
OUT = ROOT / "cerebrus" / "resources" / "user_guide_v2.html"

# Pull head + <style> ... </style> from original (lines 1..658 inclusive).
head_lines = SRC.read_text(encoding="utf-8").splitlines()
HEAD = "\n".join(head_lines[:658])

BODY = r"""
    <title>Cerebrus User Guide v2 (Editorial Pass) | Unreal Engine Android Profiling</title>
</head>

<body>
    <button id="theme-toggle" title="Toggle Light/Dark Mode">☀️</button>
    <button id="scroll-top" title="Back to Top">↑</button>

    <aside>
        <div class="logo">
            <img src="icon.png" alt="Cerebrus Logo" style="width: 32px; height: 32px; border-radius: 6px;">
            <span>Cerebrus <code style="font-size:0.7rem;background:#3b82f6;color:#fff;padding:2px 6px;border-radius:3px;">v2</code></span>
        </div>
        <nav>
            <div class="toc-title">Quick Start</div>
            <ul class="toc-list">
                <li class="toc-item"><a href="#hero" class="toc-link"><span>The 60-second tour</span></a></li>
                <li class="toc-item"><a href="#whats-new" class="toc-link"><span>What's New (v3.0)</span></a></li>
                <li class="toc-item"><a href="#five-min" class="toc-link"><span>5-minute Quick Start</span></a></li>
            </ul>
            <div class="toc-title" style="margin-top:1rem;">Core Workflows</div>
            <ul class="toc-list">
                <li class="toc-item"><a href="#first-time" class="toc-link"><span>First-Time Setup</span></a></li>
                <li class="toc-item"><a href="#daily-loop" class="toc-link"><span>Daily Capture Loop</span></a></li>
                <li class="toc-item"><a href="#multi-device" class="toc-link"><span>Multi-Device Captures</span></a></li>
                <li class="toc-item"><a href="#analyze" class="toc-link"><span>Analyze Existing Data</span></a></li>
            </ul>
            <div class="toc-title" style="margin-top:1rem;">Reports</div>
            <ul class="toc-list">
                <li class="toc-item"><a href="#perfreport" class="toc-link"><span>Performance Report</span></a></li>
                <li class="toc-item"><a href="#memreport" class="toc-link"><span>Memory Report</span></a></li>
                <li class="toc-item"><a href="#color-logs" class="toc-link"><span>Colored Logs</span></a></li>
                <li class="toc-item"><a href="#analytics" class="toc-link"><span>Analytics JSON</span></a></li>
            </ul>
            <div class="toc-title" style="margin-top:1rem;">Plugins &amp; Cloud</div>
            <ul class="toc-list">
                <li class="toc-item"><a href="#plugins" class="toc-link"><span>Plugin System</span></a></li>
                <li class="toc-item"><a href="#aws-secrets" class="toc-link"><span>AWS Secrets</span></a></li>
                <li class="toc-item"><a href="#s3-upload" class="toc-link"><span>S3 Uploader</span></a></li>
                <li class="toc-item"><a href="#grafana" class="toc-link"><span>Grafana &amp; Elasticsearch</span></a></li>
            </ul>
            <div class="toc-title" style="margin-top:1rem;">Reference</div>
            <ul class="toc-list">
                <li class="toc-item"><a href="#concepts" class="toc-link"><span>Concepts &amp; Vocabulary</span></a></li>
                <li class="toc-item"><a href="#profiles" class="toc-link"><span>Profile Management</span></a></li>
                <li class="toc-item"><a href="#devices" class="toc-link"><span>Device Compatibility</span></a></li>
                <li class="toc-item"><a href="#settings" class="toc-link"><span>Tools &amp; Settings</span></a></li>
                <li class="toc-item"><a href="#best-practices" class="toc-link"><span>Best Practices</span></a></li>
                <li class="toc-item"><a href="#faq" class="toc-link"><span>FAQ</span></a></li>
                <li class="toc-item"><a href="#troubleshoot" class="toc-link"><span>Troubleshooting</span></a></li>
                <li class="toc-item"><a href="#known-issues" class="toc-link"><span>Known Issues</span></a></li>
            </ul>
        </nav>
    </aside>

    <main>
        <section id="hero">
            <h2>Cerebrus</h2>
            <h1>One toolkit. Every Unreal Android capture, polished.</h1>
            <p>Cerebrus pulls profiling CSVs, memory dumps and logs off Android devices, turns them into
                annotated HTML reports, and ships flat JSON straight into Elasticsearch + Grafana for
                cross-build trend analysis. No terminal gymnastics, no spreadsheet stitching.</p>

            <div class="features-grid">
                <div class="card"><div class="feature-item"><div class="feature-icon">⚡</div><div>
                    <h4 class="highlight">One-click bulk</h4>
                    <p>Pull CSV + MemReport + logs, generate every report, in sequence, with one button.</p>
                </div></div></div>
                <div class="card"><div class="feature-item"><div class="feature-icon">🧩</div><div>
                    <h4 class="highlight">Plugin-first</h4>
                    <p>Profiling, AWS Secrets, S3 Uploader, Analytics — each tab is a discrete plugin.</p>
                </div></div></div>
                <div class="card"><div class="feature-item"><div class="feature-icon">📊</div><div>
                    <h4 class="highlight">Trend-ready</h4>
                    <p>Flat analytics JSON with stable schema (<code>v2</code>) and a built-in Grafana weight.</p>
                </div></div></div>
                <div class="card"><div class="feature-item"><div class="feature-icon">🎚️</div><div>
                    <h4 class="highlight">Tier-aware</h4>
                    <p>Auto-classifies captures into Low / Medium / High / Epic from <code>BaseDeviceProfiles.ini</code>.</p>
                </div></div></div>
                <div class="card"><div class="feature-item"><div class="feature-icon">🛡️</div><div>
                    <h4 class="highlight">Quality-guarded</h4>
                    <p>Missing fields surface as red banners + explicit sentinels — no silent gaps.</p>
                </div></div></div>
                <div class="card"><div class="feature-item"><div class="feature-icon">🌗</div><div>
                    <h4 class="highlight">Light + Dark</h4>
                    <p>Theme toggles across the app, logs viewer, and memreport dashboards.</p>
                </div></div></div>
            </div>
        </section>

        <section id="whats-new">
            <h2>What's New</h2>
            <h1>v3.0 — major leap from v2.4</h1>
            <p>Daily flow hasn't moved. Buttons sit where they were. The new pieces plug in around what
                already worked, so first-time and long-time users can both jump straight in.</p>

            <div class="features-grid">
                <div class="card">
                    <h4 class="highlight">📊 Analytics Pipeline</h4>
                    <p>Every CSV/HTML report becomes a <strong>flat JSON</strong> doc ready for Elasticsearch
                        + Grafana. Schema is single-level (<code>build_*</code>, <code>device_*</code>,
                        <code>metrics_*</code>) — trend dashboards just work.</p>
                </div>
                <div class="card">
                    <h4 class="highlight">⭐ Report Value (1-100)</h4>
                    <p>One integer per report combining capture length, duration, FPS consistency, and
                        completeness. Grafana uses it as a weight — long, clean captures dominate trends
                        instead of getting averaged against 5-second blips.</p>
                </div>
                <div class="card">
                    <h4 class="highlight">🎚️ Scalability Tier</h4>
                    <p>Cerebrus reads <code>BaseDeviceProfiles.ini</code> and tags every report with
                        Low / Medium / High / Epic. Full inheritance chain captured for audits.</p>
                </div>
                <div class="card">
                    <h4 class="highlight">🛡️ Data Quality Banner</h4>
                    <p>Missing fields trigger a red warning row at the top of the HTML. JSON gets sentinels
                        (<code>-1</code>, <code>"Unknown"</code>, <code>2000-01-01T00:00:00Z</code>). Never
                        silent.</p>
                </div>
                <div class="card">
                    <h4 class="highlight">🧩 Plugin Reorg</h4>
                    <p>Profiling, AWS Secrets, S3 Uploader, Analytics — self-contained plugins with their
                        own version, docs and tests. Disable any you don't use.</p>
                </div>
                <div class="card">
                    <h4 class="highlight">☁️ AWS Workflow</h4>
                    <p>Replaces the old AWS Sync dialog with two clean tabs. <strong>AWS Secrets</strong>
                        for credentials. <strong>S3 Uploader</strong> for pushing reports.</p>
                </div>
            </div>

            <h3 style="margin-top:2rem;">Pipeline at a glance</h3>
            <div class="card">
                <p>Connect a phone. Hit <strong>Generate</strong>. Then:</p>
                <ol style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li><strong>PerfReportTool</strong> turns the CSV into base HTML charts.</li>
                    <li>Cerebrus injects metadata rows (device, build, tier, <strong>Report Value</strong>).</li>
                    <li>FPS Avg column, percentile gauges, embedded raw CSV are stitched in.</li>
                    <li>Analytics plugin emits a flat JSON keyed by <code>report_fingerprint</code> (SHA-256).</li>
                    <li>Same fingerprint becomes the ES <code>_id</code> — re-uploads dedup automatically.</li>
                </ol>
                <p>Grafana reads the index, applies <code>report_value</code> as the weight, and the trend
                    line is biased toward captures with the most evidence.</p>
            </div>
        </section>

        <section id="five-min">
            <h2>5-Minute Quick Start</h2>
            <p>From install to first report. No detours.</p>
            <div class="card">
                <ol class="steps">
                    <li class="step-item"><h4 class="highlight">Launch Cerebrus</h4>
                        <p>ADB ships with the installer; nothing else to install.</p></li>
                    <li class="step-item"><h4 class="highlight">Plug in a device</h4>
                        <p>USB debugging on. Click <code>List Devices</code>. Pick the row.</p></li>
                    <li class="step-item"><h4 class="highlight">Set output folder</h4>
                        <p>Anywhere on disk. Cerebrus creates per-device subfolders automatically.</p></li>
                    <li class="step-item"><h4 class="highlight">Tick the boxes you want</h4>
                        <p>Move CSV, Move Logs, Move MemReport, Generate Perf Report, Generate Mem Report.</p></li>
                    <li class="step-item"><h4 class="highlight">Click Generate</h4>
                        <p>HTML reports land in <code>OutputPath/Make_Model/Profiling/</code>.</p></li>
                </ol>
                <div class="warning-box warning-orange" style="margin-top:1rem;">
                    <p><strong>One-time bonus.</strong> Open <code>Settings → Analytics</code> and point
                        Cerebrus at <code>BaseDeviceProfiles.ini</code>. Every future report gets a tier
                        label automatically — needed for trend dashboards.</p>
                </div>
            </div>
        </section>

        <section id="first-time">
            <h2>First-Time Setup</h2>
            <div class="card">
                <ol class="steps">
                    <li class="step-item"><h4 class="highlight">Create a profile</h4>
                        <p><code>File → New Profile</code>. A profile is a named bundle of settings
                            (package name, paths, plugin enablement).</p></li>
                    <li class="step-item"><h4 class="highlight">Set the package name</h4>
                        <p>Format <code>com.publisher.product</code>. The last segment is your Unreal
                            project folder name; Cerebrus uses it to locate captures on the device.</p></li>
                    <li class="step-item"><h4 class="highlight">Pick output paths</h4>
                        <p>Defaults to <code>C:\</code>. Recommend a dedicated folder like
                            <code>D:\GameTelemetry\</code>.</p></li>
                    <li class="step-item"><h4 class="highlight">Configure plugins</h4>
                        <p><code>Settings → Plugins</code>. Disable the ones you don't need; reorder tabs
                            to taste. Settings persist per machine.</p></li>
                    <li class="step-item"><h4 class="highlight">Point at BaseDeviceProfiles.ini</h4>
                        <p>Analytics tab → settings cog. Cerebrus uses this to resolve Scalability Tier
                            for every report.</p></li>
                </ol>
            </div>
        </section>

        <section id="daily-loop">
            <h2>Daily Capture Loop</h2>
            <p>For teams running daily profiling passes across one or more devices.</p>
            <div class="card">
                <ol class="steps">
                    <li class="step-item"><h4 class="highlight">List Devices</h4>
                        <p>Refresh the device list. Cerebrus shows which devices have the target package
                            installed.</p></li>
                    <li class="step-item"><h4 class="highlight">Pick a device row</h4>
                        <p>Output paths auto-update to <code>OutputPath/Make_Model/</code>.</p></li>
                    <li class="step-item"><h4 class="highlight">Tick bulk actions</h4>
                        <p>Move CSV, Move Logs, Move MemReport, Generate Perf Report, Generate Mem Report,
                            Generate Colored Logs.</p></li>
                    <li class="step-item"><h4 class="highlight">Generate</h4>
                        <p>The progress log scrolls in real time. Reports open from
                            <code>View HTML Files</code> when finished.</p></li>
                    <li class="step-item"><h4 class="highlight">(Optional) Upload to S3</h4>
                        <p>Switch to the <strong>S3 Uploader</strong> tab. Select a bucket → drop a file →
                            <code>Upload</code>. Metadata-driven paths keep S3 tidy.</p></li>
                </ol>
            </div>
        </section>

        <section id="multi-device">
            <h2>Multi-Device Captures</h2>
            <div class="card">
                <p>Cerebrus targets one device at a time on purpose. Captures are device-specific; mixing
                    them silently distorts averages.</p>
                <p>To capture across many devices in one session:</p>
                <ol style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li>Plug in all devices.</li>
                    <li>Click <code>List Devices</code> once.</li>
                    <li>For each row: select → tick bulk actions → <code>Generate</code> → repeat.</li>
                    <li>Output paths auto-isolate by device folder.</li>
                </ol>
                <p>For dashboard comparison across devices, ingest the resulting JSONs into Elasticsearch.
                    Grafana's <code>$device</code> + <code>$tier</code> variables handle cross-device views
                    natively.</p>
            </div>
        </section>

        <section id="analyze">
            <h2>Analyze Existing Data</h2>
            <div class="card">
                <p>Existing CSVs or HTML reports on disk can be processed without touching a device.</p>
                <ol class="steps">
                    <li class="step-item"><h4 class="highlight">Skip the Move steps</h4>
                        <p>Untick all the "Move *" checkboxes.</p></li>
                    <li class="step-item"><h4 class="highlight">Point at the source folder</h4>
                        <p>Set <code>Input Path</code> to where the CSVs already live. Cerebrus discovers
                            them recursively.</p></li>
                    <li class="step-item"><h4 class="highlight">Tick the Generate boxes</h4>
                        <p>Pick the report types you want. Old data still gets the v2 schema treatment.</p></li>
                </ol>
            </div>
        </section>

        <section id="perfreport">
            <h2>Performance Report (HTML)</h2>
            <div class="card">
                <p>Generated by the bundled <strong>PerfReportTool.exe</strong>, then post-processed by
                    Cerebrus injectors:</p>
                <ol style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li><strong>Metadata rows.</strong> Configuration, OS, CPU/Device, DeviceProfile,
                        Scalability Tier, DeviceProfile Chain, Capture Duration, Features, Target FPS,
                        <strong>Report Value</strong>.</li>
                    <li><strong>FPS Avg column.</strong> Derived from Frametime, colour-coded by health
                        band.</li>
                    <li><strong>Percentile gauges.</strong> P01 / P05 / P50 / P95 fan-out at the top.</li>
                    <li><strong>Embedded raw CSV.</strong> The capture data is folded into the HTML so the
                        report is self-contained — no external CSV needed for re-analysis.</li>
                    <li><strong>Cerebrus metadata JSON.</strong> Hidden <code>&lt;script
                            id="cerebrus-metadata"&gt;</code> block that the analytics plugin reads when
                        converting back to JSON.</li>
                </ol>
            </div>
        </section>

        <section id="memreport">
            <h2>Memory Report Analyzer</h2>
            <div class="card">
                <p>Memory dumps from the <code>memreport -full</code> console command get parsed into a
                    multi-tab HTML dashboard.</p>
                <p>Tabs include: Memory Stats, Texture Stats, Texture Pool, Class Stats, Particle Stats,
                    RHI Stats, Render Target Pool, and more.</p>
                <p><strong>Filename convention:</strong>
                    <code>[BuildConfig]_[DeviceMake]_[DeviceModel]_[CL]_[Date].html</code> — predictable so
                    your team can find a report without opening every file.</p>
            </div>
        </section>

        <section id="color-logs">
            <h2>Colored Logs</h2>
            <div class="card">
                <p>Raw <code>*.log</code> files get converted into colour-coded HTML. Errors red, warnings
                    orange, info blue. Filters across log level and category. Dark mode default.</p>
            </div>
        </section>

        <section id="analytics">
            <h2>Analytics JSON</h2>
            <div class="card">
                <p>The trend-ready output that Elasticsearch and Grafana consume.</p>
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li><strong>Flat schema.</strong> <code>build_config</code>, not
                        <code>build.config</code>. No nested objects.</li>
                    <li><strong>Stable fingerprint.</strong> <code>report_fingerprint</code> is a SHA-256
                        of the identifying fields. Use it as the ES <code>_id</code> to dedup.</li>
                    <li><strong>Sentinels.</strong> Missing fields become explicit values
                        (<code>-1</code>, <code>"Unknown"</code>, <code>2000-01-01T00:00:00Z</code>) so the
                        ES mapping stays stable.</li>
                    <li><strong>Report Value.</strong> A 1-100 integer Grafana uses as a
                        <code>weighted_avg</code> weight.</li>
                    <li><strong>Data quality flags.</strong> <code>data_quality_has_corruption</code>,
                        <code>data_quality_missing_count</code>,
                        <code>data_quality_missing_fields</code>. Filter dashboards with
                        <code>data_quality_has_corruption:0</code>.</li>
                </ul>
                <p>Full schema + ingest playbook: <a
                        href="../../docs/user/GRAFANA_ELASTICSEARCH_INTEGRATION.md">Grafana &amp;
                        Elasticsearch Integration Guide</a>.</p>
            </div>
        </section>

        <section id="plugins">
            <h2>Plugin System</h2>
            <div class="card">
                <p>Every tab is a plugin. <code>Settings → Plugins</code> lets you:</p>
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li>Enable / disable any plugin (state persists per machine).</li>
                    <li>Reorder the tabs to match your workflow.</li>
                    <li>See plugin version + ID for support tickets.</li>
                </ul>
                <p>Core plugins shipped with v3.0: <code>profiling</code>, <code>aws_secrets</code>,
                    <code>s3_uploader</code>, <code>analytics</code>.</p>
            </div>
        </section>

        <section id="aws-secrets">
            <h2>AWS Secrets</h2>
            <div class="card">
                <p>Stores AWS credentials securely with local encryption + per-bucket naming.</p>
                <ol class="steps">
                    <li class="step-item"><h4 class="highlight">Add a key</h4>
                        <p>Bucket name, Access Key ID, Secret Access Key, Region. Save.</p></li>
                    <li class="step-item"><h4 class="highlight">Map a friendly name</h4>
                        <p>e.g. <code>prod-eu</code> for <code>cerebrus-builds-eu-west-1</code>. Used by
                            S3 Uploader as a dropdown.</p></li>
                    <li class="step-item"><h4 class="highlight">Test</h4>
                        <p>Click <code>Verify</code>. Cerebrus issues a <code>ListBuckets</code> call to
                            confirm the credentials work.</p></li>
                </ol>
                <div class="warning-box warning-blue" style="margin-top:1rem;">
                    <p><strong>Security note.</strong> Credentials are encrypted at rest with a
                        machine-bound key. Don't commit the cerebrus secrets file. Use IAM least-privilege
                        — Cerebrus only needs <code>s3:PutObject</code> + <code>s3:ListBuckets</code>.</p>
                </div>
            </div>
        </section>

        <section id="s3-upload">
            <h2>S3 Uploader</h2>
            <div class="card">
                <p>Push generated reports to S3 without leaving Cerebrus.</p>
                <ol style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li>Pick a bucket from the dropdown (populated from AWS Secrets).</li>
                    <li>Pick the source file (HTML/JSON/MemReport).</li>
                    <li>Optional: override the destination directory inside the bucket.</li>
                    <li>Click <code>Upload</code>. Progress + result land in the log panel.</li>
                </ol>
                <p>Cerebrus uses metadata-driven paths by default:
                    <code>{Date}/{BuildConfig}/{DeviceTier}/{DeviceModel}/{filename}</code>.</p>
            </div>
        </section>

        <section id="grafana">
            <h2>Grafana &amp; Elasticsearch</h2>
            <div class="card">
                <p>Cerebrus emits JSON; your indexing layer puts it in ES; Grafana queries the index.</p>
                <p><strong>Required ES config:</strong></p>
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li>Index template with explicit mappings for <code>@timestamp</code>,
                        <code>device_*</code>, <code>build_*</code>, and dynamic templates for
                        <code>metrics_*</code> / <code>threshold_counts_*</code>.</li>
                    <li>Use <code>report_fingerprint</code> as the doc <code>_id</code>. Re-uploads upsert.</li>
                    <li>Set <code>date_detection: false</code> so only <code>@timestamp</code> is parsed as
                        a date.</li>
                </ul>
                <p><strong>Grafana variables to define:</strong></p>
                <p><code>$device</code>, <code>$tier</code>, <code>$gpu</code>, <code>$branch</code>,
                    <code>$config</code>, <code>$min_frames</code>, <code>$min_report_value</code>.</p>
                <p>Detailed setup, dashboard recipes, ILM, alert rules: <a
                        href="../../docs/user/GRAFANA_ELASTICSEARCH_INTEGRATION.md">docs/user/GRAFANA_ELASTICSEARCH_INTEGRATION.md</a>.</p>
            </div>
        </section>

        <section id="concepts">
            <h2>Concepts &amp; Vocabulary</h2>
            <div class="features-grid">
                <div class="card"><h4 class="highlight">Capture</h4>
                    <p>One profiling session on one device. Produces one CSV + supporting files.</p></div>
                <div class="card"><h4 class="highlight">Tier</h4>
                    <p>Low / Medium / High / Epic. Resolved from <code>BaseDeviceProfiles.ini</code>.</p></div>
                <div class="card"><h4 class="highlight">DeviceProfile Chain</h4>
                    <p>The walk from the device's profile up to a tier sentinel. Trace-friendly.</p></div>
                <div class="card"><h4 class="highlight">Report Value</h4>
                    <p>1-100 weight per run. Volume + duration + consistency + completeness.</p></div>
                <div class="card"><h4 class="highlight">Fingerprint</h4>
                    <p>SHA-256 of identifying fields. Stable across re-uploads. Used as ES <code>_id</code>.</p></div>
                <div class="card"><h4 class="highlight">Sentinel</h4>
                    <p>Explicit placeholder for missing data. Keeps ES mapping stable, dashboards clean.</p></div>
            </div>
        </section>

        <section id="profiles">
            <h2>Profile Management</h2>
            <div class="card">
                <p>A profile bundles: nickname, package name, input path, output path,
                    <code>device_profile_config_path</code>, prefix/output naming preferences,
                    bulk-action defaults, plugin enablement.</p>
                <p>Profiles live in JSON files at <code>%APPDATA%/Cerebrus/profiles/</code>. Switch from
                    <code>File → Open Profile</code>.</p>
            </div>
        </section>

        <section id="devices">
            <h2>Device Compatibility</h2>
            <div class="card">
                <p>Officially tested: Android 9+, USB debugging enabled, target Unreal app built with
                    <code>Test</code> or <code>Development</code> config (Shipping won't emit profiling
                    CSVs).</p>
                <div class="warning-box warning-orange">
                    <p><strong>Heads up.</strong> Some devices need the app to be force-stopped between
                        captures or the CSV writer doesn't flush. If you see truncated CSVs, kill the app
                        first.</p>
                </div>
            </div>
        </section>

        <section id="settings">
            <h2>Tools &amp; Settings</h2>
            <div class="card">
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li><strong>File menu.</strong> New / Open / Save profile. Open output folder.</li>
                    <li><strong>Settings menu.</strong> Plugins (enable/reorder), Theme, Auto-update.</li>
                    <li><strong>Tools menu.</strong> Remote Console, Analytics Settings (ini + ES URL),
                        Cache cleanup.</li>
                    <li><strong>Help menu.</strong> User Guide (this doc), Check for Updates, About.</li>
                </ul>
            </div>
        </section>

        <section id="best-practices">
            <h2>Best Practices &amp; Accuracy</h2>
            <div class="card">
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li><strong>Capture for at least 2 minutes</strong> per run. Anything shorter caps
                        Report Value below 25.</li>
                    <li><strong>Match the target framerate</strong> in your test scenario. Wildly
                        off-target captures lose the consistency component.</li>
                    <li><strong>Don't compare across tiers</strong> in a single chart. Use Grafana's
                        <code>$tier</code> variable to split.</li>
                    <li><strong>Always set <code>report_fingerprint</code> as ES <code>_id</code></strong>.
                        Saves you from chasing duplicates later.</li>
                    <li><strong>Cycle the app between captures</strong> if you see truncated CSVs.</li>
                </ul>
            </div>
        </section>

        <section id="faq">
            <h2>FAQ</h2>
            <div class="card">
                <h4 class="highlight">Why does my Report Value cap at 25?</h4>
                <p>Short capture. The volume + duration components saturate around the 10-minute / 36k
                    frames mark; a 30-second capture caps at ~5% of each.</p>
                <h4 class="highlight" style="margin-top:1rem;">Why is my Scalability Tier "Unknown"?</h4>
                <p>Either <code>BaseDeviceProfiles.ini</code> isn't configured in Cerebrus, or the CSV
                    footer is missing <code>[deviceprofile]</code>. Check the red banner row in the HTML.</p>
                <h4 class="highlight" style="margin-top:1rem;">My ES has duplicate docs. Why?</h4>
                <p>Your ingest path isn't setting <code>_id = report_fingerprint</code>. Default ES
                    behaviour generates a random UUID per upload. See the integration guide for
                    Logstash/Filebeat snippets.</p>
                <h4 class="highlight" style="margin-top:1rem;">Can I disable a plugin?</h4>
                <p>Yes — <code>Settings → Plugins</code>. State persists per machine.</p>
                <h4 class="highlight" style="margin-top:1rem;">Where do credentials live?</h4>
                <p><code>%APPDATA%/Cerebrus/secrets/</code>, encrypted with a machine-bound key. Don't
                    copy that folder between machines.</p>
            </div>
        </section>

        <section id="troubleshoot">
            <h2>Troubleshooting</h2>
            <div class="card">
                <h4 class="highlight">No devices listed</h4>
                <p>Run <code>adb devices</code> in a terminal. If empty: enable USB debugging, accept the
                    fingerprint prompt on the phone, swap cables.</p>
                <h4 class="highlight" style="margin-top:1rem;">Move CSV says "Source not found"</h4>
                <p>The app didn't write profiling data yet. Launch the build, run for ~30s with profiling
                    enabled, then Move.</p>
                <h4 class="highlight" style="margin-top:1rem;">Parsing failed for CSV</h4>
                <p>Footer marker probably missing. Open the CSV in a text editor; if there's no
                    <code>[HasHeaderRowAtEnd]</code> line at the bottom, the capture was truncated. Kill
                    the app + re-capture.</p>
                <h4 class="highlight" style="margin-top:1rem;">"Tier: Unknown" everywhere</h4>
                <p>Open <code>Settings → Analytics</code>, point at <code>BaseDeviceProfiles.ini</code>.
                    Re-run conversion.</p>
            </div>
        </section>

        <section id="known-issues">
            <h2>Known Issues</h2>
            <div class="card">
                <ul style="margin:0.5rem 0 0.5rem 1.5rem;">
                    <li>Performance Report HTML does not currently support theme toggle or scroll-to-top
                        (these live in MemReport + Color Log viewers only).</li>
                    <li>Filebeat / Logstash auto-id generation conflicts with Cerebrus dedup — must
                        manually wire <code>document_id</code>.</li>
                    <li>Very large CSVs (&gt; 500 MB) can hit the PerfReportTool memory ceiling. Split
                        captures or run on a machine with more RAM.</li>
                </ul>
            </div>

            <div style="height: 50vh;"></div>
        </section>
    </main>

    <script>
        const themeToggle = document.getElementById('theme-toggle');
        const body = document.body;
        function updateTheme(isLight) {
            if (isLight) { body.classList.add('light-mode'); themeToggle.innerText = '☀️'; }
            else { body.classList.remove('light-mode'); themeToggle.innerText = '🌙'; }
        }
        themeToggle.addEventListener('click', () => {
            const isLight = !body.classList.contains('light-mode');
            updateTheme(isLight);
            localStorage.setItem('docs-theme-pref', isLight ? 'light' : 'dark');
        });
        const savedTheme = localStorage.getItem('docs-theme-pref') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        updateTheme(savedTheme === 'light');

        const scrollTopBtn = document.getElementById('scroll-top');
        const links = document.querySelectorAll('.toc-link');
        const scrollTargets = Array.from(links).map(link => document.querySelector(link.getAttribute('href'))).filter(el => el);
        window.onscroll = () => {
            if (window.pageYOffset > 500) scrollTopBtn.style.display = "flex";
            else scrollTopBtn.style.display = "none";
            let current = "";
            scrollTargets.forEach(target => {
                if (window.pageYOffset >= target.offsetTop - 200) current = target.getAttribute('id');
            });
            links.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === "#" + current) link.classList.add('active');
            });
        };
        scrollTopBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
    </script>
</body>
</html>
"""

OUT.write_text(HEAD + BODY, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(BODY.splitlines())} body lines)")
