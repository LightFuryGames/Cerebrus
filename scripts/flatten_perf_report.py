#!/usr/bin/env python3
"""
Flatten Cerebrus Performance Reports (HTML) into flattened JSON.
MATCHES OLD FORMAT EXACTLY (including flawed parsing and key order).
"""

import argparse
import glob
import json
import os
import re
from collections import OrderedDict


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&#44;", ",")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
    )
    return text.strip()


def parse_timestamp(content: str, filename: str) -> str:
    match = re.search(
        r"Profile\((\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\)", content
    )
    if not match:
        match = re.search(
            r"Profile\((\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\)", filename
        )
    if match:
        y, m, d, hh, mm, ss = match.groups()
        return f"{d}:{m}:{y}:{hh}:{mm}:{ss}"
    return ""


def extract_flawed_metadata(html_content: str) -> OrderedDict:
    match = re.search(
        r"\[HasHeaderRowAtEnd\],.*?(?=</pre>|\n\n|$)", html_content, re.DOTALL
    )
    if not match:
        return OrderedDict()

    line = match.group(0).strip()
    line = line.replace("&quot;", '"').replace("&amp;#44;", ",")
    parts = line.split(",")
    metadata = OrderedDict()

    for i in range(0, len(parts) - 1, 2):
        key = parts[i].strip()
        val = parts[i + 1].strip()

        if key == "[HasHeaderRowAtEnd]":
            key = "HasHeaderRowAtEnd"
        elif key == "[platform]":
            key = "platform"
        elif key == "[config]":
            key = "config"
        elif key == "[buildversion]":
            key = "Build Version"
        elif key == "[engineversion]":
            key = "engineversion"
        elif key == "[os]":
            key = "OS"
        elif key == "[cpu]":
            key = "CPU/Device"

        metadata[key] = val
    return metadata


def extract_summary_metrics(html_content: str) -> dict:
    metrics = {}
    fc_match = re.search(
        r"<tr><td[^>]*>Frame count</td><td>(.*?)</td></tr>", html_content, re.DOTALL
    )
    if fc_match:
        metrics["Frame count"] = clean_html(fc_match.group(1))

    fps_table_match = re.search(
        r"FPSChart</h2>.*?<table.*?>(.*?)</table>", html_content, re.DOTALL
    )
    if fps_table_match:
        table_content = fps_table_match.group(1)
        header_row = re.search(r"<tr>(.*?)</tr>", table_content, re.DOTALL)
        if header_row:
            headers = [
                clean_html(h)
                for h in re.findall(
                    r"<th[^>]*>(.*?)</th>", header_row.group(1), re.DOTALL
                )
            ]
            data_row = re.search(
                r"<tr><td>Entire Run</td>(.*?)</tr>", table_content, re.DOTALL
            )
            if data_row:
                cells = [
                    clean_html(c)
                    for c in re.findall(
                        r"<td[^>]*>(.*?)</td>", data_row.group(1), re.DOTALL
                    )
                ]
                for i, cell in enumerate(cells):
                    if i + 1 < len(headers):
                        metrics[headers[i + 1]] = cell

    sd_match = re.search(r"Standard Deviation \(SD\):\s*([\d.]+)", html_content)
    if sd_match:
        metrics["Standard Deviation (SD)"] = float(sd_match.group(1))
    iqr_match = re.search(r"Interquartile Range \(IQR\):\s*([\d.]+)", html_content)
    if iqr_match:
        metrics["Interquartile Range (IQR)"] = float(iqr_match.group(1))

    gauge_blocks = re.findall(
        r'<div class="gauge-wrapper".*?>(.*?)</div>\s*</div>', html_content, re.DOTALL
    )
    for block in gauge_blocks:
        title_match = re.search(r'class="gauge-title"[^>]*>(.*?),', block)
        value_match = re.search(r'<text x="100" y="85"[^>]*>(.*?)</text>', block)
        if title_match and value_match:
            t = title_match.group(1).strip()
            if t == "1st Percentile":
                t = "1th Percentile"
            metrics[t] = float(value_match.group(1).strip())

    hitch_section = re.search(
        r"Hitches</h2>.*?<table.*?>(.*?)</table>", html_content, re.DOTALL
    )
    if hitch_section:
        table_content = hitch_section.group(1)
        headers = [h.strip() for h in re.findall(r"<th>\s*>\s*(\d+ms)", table_content)]
        rows = re.findall(
            r"<tr><td><b>(.*?)</b></td>(.*?)</tr>", table_content, re.DOTALL
        )
        for row_name, row_content in rows:
            cells = [
                clean_html(c)
                for c in re.findall(r"<td[^>]*>(.*?)</td>", row_content, re.DOTALL)
            ]
            for i, cell in enumerate(cells):
                if i < len(headers):
                    metrics[f"{row_name}_>{headers[i]}"] = int(cell)

    return metrics


def flatten_report(file_path: str) -> OrderedDict:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    metadata = extract_flawed_metadata(content)
    summary = extract_summary_metrics(content)

    result = OrderedDict()

    device_id = filename.split(".")[0]
    if device_id.endswith("_1"):
        device_id = device_id[:-2]
    result["device_id"] = device_id
    result["Profiling Timestamp"] = parse_timestamp(content, filename)

    for k, v in metadata.items():
        result[k] = v

    summary_map = [
        ("Frame count", "Frame count"),
        ("Total Time (s)", "Total Time (s)"),
        ("Frametime Avg", "Frametime Avg"),
        ("FPS Avg", "FPS Avg"),
        ("Hitches/Min", "Hitches/Min"),
        ("HitchTimePercent", "HitchTimePercent"),
        ("MVP60", "MVP60"),
        ("Standard Deviation (SD)", "Standard Deviation (SD)"),
        ("Interquartile Range (IQR)", "Interquartile Range (IQR)"),
        ("1th Percentile", "1th Percentile"),
        ("5th Percentile", "5th Percentile"),
        ("50th Percentile", "50th Percentile"),
        ("90th Percentile", "90th Percentile"),
        ("95th Percentile", "95th Percentile"),
        ("99th Percentile", "99th Percentile"),
        ("GameThreadtime Avg", "GameThreadTime Avg"),
        ("RenderThreadtime Avg", "RenderThreadTime Avg"),
        ("RHIThreadTime Avg", "RHIThreadTime Avg"),
        ("GPUtime Avg", "GPUTime Avg"),
    ]

    for in_k, out_k in summary_map:
        val = summary.get(in_k)
        if val is not None:
            try:
                if isinstance(val, (int, float)):
                    result[out_k] = val
                else:
                    result[out_k] = float(str(val).replace(",", ""))
            except:
                result[out_k] = val

    hitch_rows = [
        "FrameTime",
        "GameThreadTime",
        "RenderThreadTime",
        "RHIThreadTime",
        "GPUTime",
    ]
    thresholds = ["60ms", "150ms", "250ms", "500ms", "750ms", "1000ms", "2000ms"]
    for row in hitch_rows:
        for t in thresholds:
            key = f"{row}_>{t}"
            result[key] = summary.get(key, 0)

    result["MemoryFreeMB Min"] = float(
        str(summary.get("MemoryFreeMB Min", 0)).replace(",", "")
    )
    result["PhysicalUsedMB Max"] = float(
        str(summary.get("PhysicalUsedMB Max", 0)).replace(",", "")
    )
    result["RHI/Drawcalls Avg"] = float(
        str(summary.get("RHI/Drawcalls Avg", 0)).replace(",", "")
    )

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output_dir")
    args = parser.parse_args()

    files = (
        glob.glob(os.path.join(args.input, "*.html"))
        if os.path.isdir(args.input)
        else [args.input]
    )

    for f in files:
        try:
            data = flatten_report(f)
            with open(f, "r", encoding="utf-8", errors="ignore") as html_f:
                content = html_f.read()
            ts_match = re.search(r"Profile\((\d{8}_\d{6})\)", content)
            base_name = (
                f"Profile({ts_match.group(1)})"
                if ts_match
                else os.path.splitext(os.path.basename(f))[0]
            )
            if f.endswith("_1.html") and not base_name.endswith("_1"):
                base_name += "_1"

            out_dir = args.output_dir if args.output_dir else os.path.dirname(f)
            if not os.path.exists(out_dir):
                os.makedirs(out_dir)
            out_path = os.path.join(out_dir, f"{base_name}.json")

            with open(out_path, "w", encoding="utf-8") as out_f:
                json.dump(data, out_f, indent=2)
            print(f"Converted {f} -> {out_path}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
