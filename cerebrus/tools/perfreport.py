"""Wrapper around PerfReportTool.exe (Unreal CsvTools).

Pulled out of ``cerebrus/ui/components/file_manager.py`` per CODE_STANDARDS.md
§2 — UI must not invoke external tools directly.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PerfReportResult:
    returncode: int
    stdout: str
    stderr: str
    generated_html_path: Path


def find_perfreport_tool(repo_root: Path) -> Path:
    """Locate PerfReportTool.exe inside the repo's Binaries/CsvTools dir."""
    return repo_root / "Binaries" / "CsvTools" / "PerfReportTool.exe"


def run_perfreport_tool(
    tool_path: Path,
    csv_file: Path,
    output_dir: Path,
    report_type: str = "Default60fps",
) -> PerfReportResult:
    """Invoke PerfReportTool.exe on a single CSV and return run metadata.

    The tool writes ``<output_dir>/<csv_stem>.html`` by default. Caller is
    responsible for renaming/moving the artefact and for failure reporting.
    """
    cmd = [
        str(tool_path),
        "-csv",
        str(csv_file),
        "-reportType",
        report_type,
        "-o",
        str(output_dir),
        "-perfLog",
    ]
    startupinfo = None
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, startupinfo=startupinfo
    )
    return PerfReportResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        generated_html_path=output_dir / f"{csv_file.stem}.html",
    )
