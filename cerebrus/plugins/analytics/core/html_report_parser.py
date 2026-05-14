from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any


def _clean_html_fragment(value: str) -> str:
    text = re.sub(r"<[^>]*>", "", value)
    return re.sub(r"\s+", " ", html.unescape(html.unescape(text))).strip()


class PerformanceHTMLReportParser:
    """Parse Unreal/Cerebrus performance HTML reports into flat report values."""

    def __init__(self, html_path: str | Path):
        self.html_path = Path(html_path)
        self.content = self.html_path.read_text(encoding="utf-8", errors="ignore")

    def parse(self) -> dict[str, Any]:
        values: dict[str, Any] = {"device_id": self.html_path.parent.name}
        values.update(self._extract_metadata())
        values.update(self._extract_fps_chart())

        for row_name, cols in self._extract_hitches().items():
            for col_name, value in cols.items():
                values[f"{row_name}_{col_name}"] = value

        stats = self._extract_statistics()
        percentiles = stats.pop("Percentiles", {})
        for percentile, value in percentiles.items():
            values[f"{percentile} Percentile"] = value
        values.update(stats)
        return values

    def extract_embedded_raw_csv(self) -> str | None:
        """Return the embedded Raw CSV payload when Cerebrus injected one."""
        match = re.search(
            r'<pre id="rawCsvDataHidden"[^>]*>(.*?)</pre>',
            self.content,
            re.DOTALL | re.IGNORECASE,
        )
        if not match:
            return None
        return html.unescape(html.unescape(match.group(1))).strip()

    def embedded_profile_name(self) -> str | None:
        """Return the Profile(YYYYMMDD_HHMMSS) name shown in the HTML report."""
        match = re.search(r"Profile\(\d{8}_\d{6}\)", self.content)
        if not match:
            return None
        return match.group(0)

    def _extract_metadata(self) -> dict[str, str]:
        metadata: dict[str, str] = {}
        patterns = [
            r"<tr><td bgcolor='#F0F0F0'>(.*?)</td><td>(?:<b>)?(.*?)(?:</b>)?</td></tr>",
            r"<tr><td>(Configuration|OS|CPU/Device|Device Manufacturer|Device Model|Device GPU|Capture Duration|Command Line|Features|Target Framerate|DeviceProfile|Scalability Tier)</td><td>(?:<b>)?(.*?)(?:</b>)?</td></tr>",
        ]
        for pattern in patterns:
            for key, value in re.findall(pattern, self.content, re.DOTALL):
                metadata[_clean_html_fragment(key)] = _clean_html_fragment(value)
        return metadata

    def _extract_fps_chart(self) -> dict[str, Any]:
        header_match = re.search(
            r"<tr>\s*<th>Section Name</th>(.*?)</tr>",
            self.content,
            re.DOTALL,
        )
        if not header_match:
            return {}

        headers = ["Section Name"]
        headers.extend(
            _clean_html_fragment(cell).replace("<wbr>", "")
            for cell in re.findall(
                r"<th.*?>(.*?)</th>", header_match.group(1), re.DOTALL
            )
        )

        row_match = re.search(
            r"<tr>\s*<td>Entire Run</td>(.*?)</tr>",
            self.content,
            re.DOTALL,
        )
        if not row_match:
            return {}

        values = [
            _clean_html_fragment(cell)
            for cell in re.findall(r"<td.*?>(.*?)</td>", row_match.group(1), re.DOTALL)
        ]

        fps_data: dict[str, Any] = {}
        for index, value in enumerate(values):
            if index + 1 >= len(headers):
                continue
            key = headers[index + 1]
            try:
                fps_data[key] = float(value) if value else None
            except ValueError:
                fps_data[key] = value
        return fps_data

    def _extract_hitches(self) -> dict[str, dict[str, Any]]:
        header_match = re.search(
            r"<tr>\s*<td></td>\s*(.*?)</tr>",
            self.content,
            re.DOTALL,
        )
        columns = []
        if header_match:
            columns = [
                _clean_html_fragment(cell)
                for cell in re.findall(
                    r"<th.*?>(.*?)</th>", header_match.group(1), re.DOTALL
                )
                if _clean_html_fragment(cell)
            ]
        if not columns:
            columns = [
                ">60ms",
                ">150ms",
                ">250ms",
                ">500ms",
                ">750ms",
                ">1000ms",
                ">2000ms",
            ]

        hitches: dict[str, dict[str, Any]] = {}
        for row_name in [
            "FrameTime",
            "GameThreadTime",
            "RenderThreadTime",
            "RHIThreadTime",
            "GPUTime",
        ]:
            match = re.search(
                rf"<tr>\s*<td>\s*<b>{row_name}</b>\s*</td>(.*?)</tr>",
                self.content,
                re.DOTALL,
            )
            if not match:
                continue
            row_data: dict[str, Any] = {}
            for index, cell in enumerate(
                re.findall(r"<td.*?>(.*?)</td>", match.group(1), re.DOTALL)
            ):
                if index >= len(columns):
                    continue
                value = _clean_html_fragment(cell)
                try:
                    row_data[columns[index]] = int(value)
                except ValueError:
                    row_data[columns[index]] = value
            hitches[row_name] = row_data
        return hitches

    def _extract_statistics(self) -> dict[str, Any]:
        stats: dict[str, Any] = {"Percentiles": {}}
        sd_match = re.search(r"Standard Deviation \(SD\): ([\d.]+) FPS", self.content)
        if sd_match:
            stats["Standard Deviation (SD)"] = float(sd_match.group(1))

        iqr_match = re.search(
            r"Interquartile Range \(IQR\): ([\d.]+) FPS", self.content
        )
        if iqr_match:
            stats["Interquartile Range (IQR)"] = float(iqr_match.group(1))

        gauge_pattern = (
            r"<div class=\"gauge-title\".*?>(.*?) Percentile.*?</div>"
            r".*?<text x=\"100\" y=\"85\".*?>(.*?)</text>"
        )
        for name, value in re.findall(gauge_pattern, self.content, re.DOTALL):
            stats["Percentiles"][_clean_html_fragment(name)] = float(
                _clean_html_fragment(value)
            )
        return stats
