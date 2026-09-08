"""Render a battery-thermal capture CSV as a self-contained HTML report.

Reads the CSV produced by `cerebrus.tools.thermal_capture.BatteryThermalSampler`
(Timestamp, ElapsedSeconds, BatteryTempC) and renders a single dependency-free
HTML file: an inline SVG line chart plus summary stats (min/max/avg temp,
duration, sample count). No CDN/JS charting library is used, so the report
opens correctly even with no internet access.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import List


@dataclass
class ThermalSample:
    timestamp: str
    elapsed_seconds: float
    temp_c: float


def _read_samples(csv_path: Path) -> List[ThermalSample]:
    samples: List[ThermalSample] = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                samples.append(
                    ThermalSample(
                        timestamp=row["Timestamp"],
                        elapsed_seconds=float(row["ElapsedSeconds"]),
                        temp_c=float(row["BatteryTempC"]),
                    )
                )
            except (KeyError, ValueError):
                continue
    return samples


# Thresholds used to color the summary stat and the chart's danger zone.
# These are conservative general-purpose Android battery guidelines, not
# device-specific - treat WARM/HOT as "worth a look", not a hard failure.
WARM_THRESHOLD_C = 40.0
HOT_THRESHOLD_C = 45.0


def _status_for_temp(temp_c: float) -> tuple[str, str]:
    """Return (label, color) for a given peak temperature."""
    if temp_c >= HOT_THRESHOLD_C:
        return "HOT", "#f87171"
    if temp_c >= WARM_THRESHOLD_C:
        return "WARM", "#fbbf24"
    return "NORMAL", "#4ade80"


def _build_svg_chart(
    samples: List[ThermalSample], width: int = 1100, height: int = 380, dark: bool = True
) -> str:
    """Build a self-contained inline SVG line chart, no JS required.

    Embeds its own <style> block with literal colors (not CSS variables),
    so the chart renders correctly regardless of what page it's dropped
    into - the standalone thermal report, a memreport tab, or injected
    into a PerfReportTool report that has its own unrelated theme.
    `dark` picks a palette suited to a dark or light surrounding page.
    """
    if dark:
        text_color = "#a0a0b0"
        gridline_color = "rgba(255,255,255,0.08)"
        axis_line_color = "rgba(255,255,255,0.3)"
        line_color = "#7dd3fc"
    else:
        text_color = "#555555"
        gridline_color = "rgba(0,0,0,0.08)"
        axis_line_color = "rgba(0,0,0,0.35)"
        line_color = "#2563eb"

    chart_style = f"""
    <style>
        .thermal-chart .gridline {{ stroke: {gridline_color}; stroke-width: 1; }}
        .thermal-chart .axis-line {{ stroke: {axis_line_color}; stroke-width: 1; }}
        .thermal-chart .axis-label {{ fill: {text_color}; font-size: 11px; font-family: sans-serif; }}
        .thermal-chart .temp-line {{
            fill: none;
            stroke: {line_color};
            stroke-width: 2.5;
            stroke-linejoin: round;
            stroke-linecap: round;
        }}
        .thermal-chart .threshold-line {{ stroke-width: 1; stroke-dasharray: 6 4; opacity: 0.7; }}
        .thermal-chart .threshold-label {{ font-size: 11px; font-weight: 600; font-family: sans-serif; }}
    </style>
    """
    margin_left, margin_right = 55, 20
    margin_top, margin_bottom = 20, 40
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom

    temps = [s.temp_c for s in samples]
    times = [s.elapsed_seconds for s in samples]
    min_temp, max_temp = min(temps), max(temps)
    # Pad the range a little so the line doesn't touch the plot edges.
    pad = max((max_temp - min_temp) * 0.15, 1.0)
    y_min, y_max = min_temp - pad, max_temp + pad
    x_max = max(times) if max(times) > 0 else 1.0

    def x_pos(t: float) -> float:
        return margin_left + (t / x_max) * plot_w

    def y_pos(temp: float) -> float:
        return margin_top + plot_h - ((temp - y_min) / (y_max - y_min)) * plot_h

    points = " ".join(f"{x_pos(s.elapsed_seconds):.1f},{y_pos(s.temp_c):.1f}" for s in samples)

    # Horizontal gridlines + Y axis labels (5 bands).
    gridlines = []
    y_labels = []
    band_count = 5
    for i in range(band_count + 1):
        temp = y_min + (y_max - y_min) * i / band_count
        y = y_pos(temp)
        gridlines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" '
            f'class="gridline" />'
        )
        y_labels.append(
            f'<text x="{margin_left - 8}" y="{y:.1f}" class="axis-label" text-anchor="end" '
            f'dominant-baseline="middle">{temp:.1f}&#176;C</text>'
        )

    # X axis labels (start, middle, end elapsed time).
    x_labels = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        t = x_max * frac
        x_labels.append(
            f'<text x="{x_pos(t):.1f}" y="{height - margin_bottom + 18}" class="axis-label" '
            f'text-anchor="middle">{t:.0f}s</text>'
        )

    # Threshold reference lines, only drawn if they fall within the visible range.
    threshold_lines = []
    for threshold, label, color in (
        (WARM_THRESHOLD_C, "Warm", "#fbbf24"),
        (HOT_THRESHOLD_C, "Hot", "#f87171"),
    ):
        if y_min <= threshold <= y_max:
            y = y_pos(threshold)
            threshold_lines.append(
                f'<line x1="{margin_left}" y1="{y:.1f}" x2="{width - margin_right}" y2="{y:.1f}" '
                f'class="threshold-line" stroke="{color}" />'
                f'<text x="{width - margin_right - 4}" y="{y - 4:.1f}" class="threshold-label" '
                f'text-anchor="end" fill="{color}">{label} ({threshold:.0f}&#176;C)</text>'
            )

    return f"""
<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" class="thermal-chart">
    {chart_style}
    {''.join(gridlines)}
    {''.join(threshold_lines)}
    <polyline points="{points}" class="temp-line" />
    <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{height - margin_bottom}" class="axis-line" />
    <line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - margin_right}" y2="{height - margin_bottom}" class="axis-line" />
    {''.join(y_labels)}
    {''.join(x_labels)}
</svg>
""".strip()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        :root {{
            --bg-color: #1e1e2e;
            --container-bg: rgba(255, 255, 255, 0.05);
            --text-color: #e0e0e0;
            --text-muted: #a0a0b0;
            --accent-color: #7dd3fc;
            --border-color: rgba(125, 211, 252, 0.2);
            --header-bg: rgba(255, 255, 255, 0.08);
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', 'Consolas', sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--container-bg);
            backdrop-filter: blur(10px);
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            color: var(--accent-color);
            margin-bottom: 8px;
            font-size: 26px;
            font-weight: 600;
        }}
        .subtitle {{ color: var(--text-muted); margin-bottom: 25px; font-size: 14px; }}
        .stats-row {{
            display: flex;
            gap: 16px;
            margin-bottom: 25px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: var(--header-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 14px 20px;
            min-width: 140px;
        }}
        .stat-card .label {{
            color: var(--text-muted);
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }}
        .stat-card .value {{ font-size: 24px; font-weight: 600; }}
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            color: #1e1e2e;
        }}
        .chart-container {{
            background: var(--header-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
        }}
        .thermal-chart {{ width: 100%; height: auto; }}
        .no-data {{ color: var(--text-muted); padding: 40px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Battery Thermal Report</h1>
        <div class="subtitle">{source_name}</div>
        {body}
    </div>
</body>
</html>
"""


def generate_thermal_html(csv_path: Path, output_path: Path | None = None) -> Path:
    """Generate a self-contained HTML thermal report from a capture CSV.

    Returns the path to the written HTML file.
    """
    if output_path is None:
        output_path = csv_path.with_suffix(".html")

    samples = _read_samples(csv_path)

    if not samples:
        body = '<div class="no-data">No thermal samples were recorded in this capture.</div>'
    else:
        temps = [s.temp_c for s in samples]
        min_temp, max_temp = min(temps), max(temps)
        avg_temp = sum(temps) / len(temps)
        duration = samples[-1].elapsed_seconds
        peak_label, peak_color = _status_for_temp(max_temp)

        stats_html = f"""
        <div class="stats-row">
            <div class="stat-card">
                <div class="label">Peak Temp</div>
                <div class="value">{max_temp:.1f}&#176;C
                    <span class="status-badge" style="background:{peak_color}">{peak_label}</span>
                </div>
            </div>
            <div class="stat-card">
                <div class="label">Min Temp</div>
                <div class="value">{min_temp:.1f}&#176;C</div>
            </div>
            <div class="stat-card">
                <div class="label">Average Temp</div>
                <div class="value">{avg_temp:.1f}&#176;C</div>
            </div>
            <div class="stat-card">
                <div class="label">Duration</div>
                <div class="value">{duration:.0f}s</div>
            </div>
            <div class="stat-card">
                <div class="label">Samples</div>
                <div class="value">{len(samples)}</div>
            </div>
        </div>
        """

        chart_svg = _build_svg_chart(samples)
        body = f'{stats_html}<div class="chart-container">{chart_svg}</div>'

    html = HTML_TEMPLATE.format(
        title=f"Battery Thermal - {escape(csv_path.stem)}",
        source_name=escape(csv_path.name),
        body=body,
    )

    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to the battery thermal CSV")
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output HTML path"
    )
    args = parser.parse_args()
    output = generate_thermal_html(args.csv_path, args.output)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
