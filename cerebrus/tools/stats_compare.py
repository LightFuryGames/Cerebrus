"""
stats_compare.py - Implements comparative statistical tests (T-Test, Mann-Whitney U-Test, F-Test)
for Unreal Engine Performance Report CSV datasets.
"""

import csv
import statistics
from pathlib import Path

import numpy as np
import scipy.stats as stats


def extract_fps_values(csv_path: Path) -> list[float]:
    fps_values = []
    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return []

            frame_time_idx = -1
            for i, col in enumerate(header):
                if col.strip().lower() == "frametime":
                    frame_time_idx = i
                    break

            if frame_time_idx == -1:
                return []

            for row in reader:
                if len(row) > frame_time_idx:
                    try:
                        ft = float(row[frame_time_idx].strip())
                        if ft > 0:
                            fps_values.append(1000.0 / ft)
                    except ValueError:
                        pass
    except Exception as e:
        print(f"Error reading {csv_path}: {e}")
    return fps_values


def generate_comparison_report(
    baseline_csv: Path, target_csv: Path, output_html: Path
) -> dict:
    """
    Reads two CSV files, extracts FPS, runs statistical tests, and generates an HTML report.
    Returns a dictionary of raw results.
    """
    baseline_fps = extract_fps_values(baseline_csv)
    target_fps = extract_fps_values(target_csv)

    if not baseline_fps or not target_fps:
        raise ValueError(
            "Could not extract comparable FPS data from one or both CSV files."
        )

    baseline_arr = np.array(baseline_fps)
    target_arr = np.array(target_fps)

    # 1. T-Test (Independent samples)
    t_stat, t_pvalue = stats.ttest_ind(baseline_arr, target_arr, equal_var=False)

    # 2. Mann-Whitney U Test (Non-parametric)
    u_stat, u_pvalue = stats.mannwhitneyu(
        baseline_arr, target_arr, alternative="two-sided"
    )

    # 3. F-Test / Levene's Test for Variance (Stability)
    levene_stat, levene_pvalue = stats.levene(baseline_arr, target_arr)

    # Summary stats
    b_mean = np.mean(baseline_arr)
    t_mean = np.mean(target_arr)
    b_sd = np.std(baseline_arr)
    t_sd = np.std(target_arr)

    def calc_iqr(arr):
        return np.percentile(arr, 75) - np.percentile(arr, 25)

    b_iqr = calc_iqr(baseline_arr)
    t_iqr = calc_iqr(target_arr)

    b_1low = np.percentile(baseline_arr, 1)
    t_1low = np.percentile(target_arr, 1)

    results = {
        "baseline_mean": b_mean,
        "target_mean": t_mean,
        "baseline_sd": b_sd,
        "target_sd": t_sd,
        "baseline_iqr": b_iqr,
        "target_iqr": t_iqr,
        "baseline_1low": b_1low,
        "target_1low": t_1low,
        "t_test": {"stat": float(t_stat), "pvalue": float(t_pvalue)},
        "u_test": {"stat": float(u_stat), "pvalue": float(u_pvalue)},
        "levene_test": {"stat": float(levene_stat), "pvalue": float(levene_pvalue)},
    }

    # Generate HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>A/B Performance Comparison</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; color: #333; }}
            .container {{ max-width: 900px; margin: auto; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; margin-bottom: 30px; }}
            th, td {{ padding: 12px; border: 1px solid #ddd; text-align: left; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            .sig {{ color: #27ae60; font-weight: bold; }}
            .not-sig {{ color: #c0392b; }}
            .card {{ background-color: #ecf0f1; border-radius: 8px; padding: 15px; margin-bottom: 20px; border-left: 5px solid #3498db; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>A/B Performance Comparison Report</h1>
            <p><strong>Baseline:</strong> {{baseline_csv.name}}</p>
            <p><strong>Target:</strong> {{target_csv.name}}</p>
            
            <div class="card">
                <h3>Summary of the Comparison</h3>
                <p>The target run has a mean FPS of <strong>{t_mean:.2f}</strong> vs baseline <strong>{b_mean:.2f}</strong>.</p>
                <p>Target SD is <strong>{t_sd:.2f}</strong> vs baseline <strong>{b_sd:.2f}</strong> (lower means more stable/less variance).</p>
            </div>
            
            <h2>Single-Run Metrics</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Baseline</th>
                    <th>Target</th>
                    <th>Diff</th>
                </tr>
                <tr>
                    <td>Mean FPS (Higher = Better)</td>
                    <td>{b_mean:.2f}</td>
                    <td>{t_mean:.2f}</td>
                    <td>{t_mean - b_mean:+.2f}</td>
                </tr>
                <tr>
                    <td>1% Lows (Higher = Better)</td>
                    <td>{b_1low:.2f}</td>
                    <td>{t_1low:.2f}</td>
                    <td>{t_1low - b_1low:+.2f}</td>
                </tr>
                <tr>
                    <td>Standard Deviation (Lower = Smoother)</td>
                    <td>{b_sd:.2f}</td>
                    <td>{t_sd:.2f}</td>
                    <td>{t_sd - b_sd:+.2f}</td>
                </tr>
                <tr>
                    <td>IQR (Lower = Smoother)</td>
                    <td>{b_iqr:.2f}</td>
                    <td>{t_iqr:.2f}</td>
                    <td>{t_iqr - b_iqr:+.2f}</td>
                </tr>
            </table>
            
            <h2>Statistical Tests (Significance)</h2>
            <p><em>Using α = 0.05 for statistical significance.</em></p>
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>P-Value</th>
                    <th>Result</th>
                    <th>Interpretation</th>
                </tr>
                <tr>
                    <td>Mann-Whitney U-Test (FPS Medians)</td>
                    <td>{u_pvalue:.4e}</td>
                    <td>{'<span class="sig">Significant Difference</span>' if u_pvalue < 0.05 else '<span class="not-sig">No Significant Difference</span>'}</td>
                    <td>Checks if target FPS distribution is shifted significantly from baseline.</td>
                </tr>
                <tr>
                    <td>Levene's Test (Variance/Stability)</td>
                    <td>{levene_pvalue:.4e}</td>
                    <td>{'<span class="sig">Significant Difference</span>' if levene_pvalue < 0.05 else '<span class="not-sig">No Significant Difference</span>'}</td>
                    <td>Checks if the variance (stutter/fluctuation) changed significantly.</td>
                </tr>
                <tr>
                    <td>T-Test (FPS Means)</td>
                    <td>{t_pvalue:.4e}</td>
                    <td>{'<span class="sig">Significant Difference</span>' if t_pvalue < 0.05 else '<span class="not-sig">No Significant Difference</span>'}</td>
                    <td>Parametric test for mean FPS difference (less reliable if not normally distributed).</td>
                </tr>
            </table>
        </div>
    </body>
    </html>
    """

    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A/B Compare Cerebrus CSVs")
    parser.add_argument(
        "--baseline", type=str, required=True, help="Path to baseline CSV"
    )
    parser.add_argument("--target", type=str, required=True, help="Path to target CSV")
    parser.add_argument(
        "--output", type=str, required=True, help="Path to output HTML report"
    )

    args = parser.parse_args()

    try:
        results = generate_comparison_report(
            Path(args.baseline), Path(args.target), Path(args.output)
        )
        print(f"Report generated successfully at: {args.output}")
    except Exception as e:
        print(f"Error: {e}")
