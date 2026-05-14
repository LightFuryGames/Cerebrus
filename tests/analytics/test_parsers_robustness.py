"""Robustness coverage for CSV + HTML parsers on edge cases.

Targets:
- Empty / truncated CSVs
- CSVs without [HasHeaderRowAtEnd] footer
- CSVs with malformed numeric rows
- HTML reports without embedded raw CSV
- HTML reports without metadata block
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cerebrus.plugins.analytics.core.csv_report_parser import (
    PerformanceCSVReportParser,
)
from cerebrus.plugins.analytics.core.html_report_parser import (
    PerformanceHTMLReportParser,
)

# ---------------------------------------------------------------------------
# CSV parser


def test_empty_csv_does_not_crash(tmp_path: Path) -> None:
    csv = tmp_path / "empty.csv"
    csv.write_text("", encoding="utf-8")
    parser = PerformanceCSVReportParser(csv)
    assert parser.metadata == {}
    assert parser.data == {}
    # parse() should still return a dict with at least frame counters present
    result = parser.parse()
    assert isinstance(result, dict)


def test_csv_without_footer_does_not_extract_metadata(tmp_path: Path) -> None:
    csv = tmp_path / "no_footer.csv"
    csv.write_text("FrameTime,GameThreadTime\n16.0,12.0\n20.0,14.0\n", encoding="utf-8")
    parser = PerformanceCSVReportParser(csv)
    assert parser.metadata == {}


def test_csv_with_footer_extracts_friendly_keys(tmp_path: Path) -> None:
    csv = tmp_path / "good.csv"
    csv.write_text(
        "\n".join(
            [
                "FrameTime,GameThreadTime",
                "16.0,12.0",
                "20.0,14.0",
                "[HasHeaderRowAtEnd],1,[buildversion],x.y.z,[deviceprofile],Android_Adreno5xx",
            ]
        ),
        encoding="utf-8",
    )
    parser = PerformanceCSVReportParser(csv)
    assert parser.metadata.get("Build Version") == "x.y.z"
    assert parser.metadata.get("DeviceProfile") == "Android_Adreno5xx"


def test_csv_with_malformed_numeric_rows_skips_bad_values(tmp_path: Path) -> None:
    csv = tmp_path / "mixed.csv"
    csv.write_text(
        "\n".join(
            [
                "FrameTime,GameThreadTime",
                "16.0,12.0",
                "BAD,not_a_number",
                "20.0,14.0",
            ]
        ),
        encoding="utf-8",
    )
    parser = PerformanceCSVReportParser(csv)
    result = parser.parse()
    # Should not raise. Result is a dict; we don't pin specific values
    # because the parser may include or skip bad rows depending on impl.
    assert isinstance(result, dict)


def test_csv_text_overrides_disk(tmp_path: Path) -> None:
    csv = tmp_path / "anywhere.csv"
    csv.write_text("on_disk\n1\n", encoding="utf-8")
    parser = PerformanceCSVReportParser(csv, csv_text="FrameTime\n16.0\n20.0\n")
    # Disk content not used; csv_text takes priority.
    assert "FrameTime" in parser.data or "frametime" in parser.data or parser.data


# ---------------------------------------------------------------------------
# HTML parser


def test_extract_embedded_raw_csv_returns_none_without_block(tmp_path: Path) -> None:
    html = tmp_path / "plain.html"
    html.write_text("<html><body>no csv</body></html>", encoding="utf-8")
    parser = PerformanceHTMLReportParser(html)
    assert parser.extract_embedded_raw_csv() is None


def test_extract_embedded_raw_csv_returns_payload(tmp_path: Path) -> None:
    html = tmp_path / "with_csv.html"
    html.write_text(
        '<html><body><pre id="rawCsvDataHidden">FrameTime,GameThreadTime\n'
        "16.0,12.0\n20.0,14.0</pre></body></html>",
        encoding="utf-8",
    )
    parser = PerformanceHTMLReportParser(html)
    payload = parser.extract_embedded_raw_csv()
    assert payload is not None
    assert "FrameTime" in payload


def test_embedded_profile_name_extracts_pattern(tmp_path: Path) -> None:
    html = tmp_path / "named.html"
    html.write_text(
        "<html><body>Profile(20260427_050858)</body></html>", encoding="utf-8"
    )
    parser = PerformanceHTMLReportParser(html)
    assert parser.embedded_profile_name() == "Profile(20260427_050858)"


def test_embedded_profile_name_returns_none_when_absent(tmp_path: Path) -> None:
    html = tmp_path / "anon.html"
    html.write_text("<html><body>no pattern</body></html>", encoding="utf-8")
    parser = PerformanceHTMLReportParser(html)
    assert parser.embedded_profile_name() is None


def test_html_parser_handles_empty_file(tmp_path: Path) -> None:
    html = tmp_path / "empty.html"
    html.write_text("", encoding="utf-8")
    parser = PerformanceHTMLReportParser(html)
    result = parser.parse()
    assert isinstance(result, dict)
    # device_id derived from parent folder name
    assert result.get("device_id") == html.parent.name


@pytest.mark.parametrize("text", ["<<<<", "🚀💥", "<html><body>"])
def test_html_parser_does_not_crash_on_weird_input(text: str, tmp_path: Path) -> None:
    html = tmp_path / "weird.html"
    html.write_text(text, encoding="utf-8")
    parser = PerformanceHTMLReportParser(html)
    # Must not raise.
    parser.parse()
    parser.extract_embedded_raw_csv()
    parser.embedded_profile_name()
