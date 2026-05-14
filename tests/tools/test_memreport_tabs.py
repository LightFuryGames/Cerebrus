from __future__ import annotations

from typing import Any, Dict

import pytest

from cerebrus.tools.memreport.tabs.memory_stats import MemoryStatsTab
from cerebrus.tools.memreport.tabs.obj_summary import ObjectSummaryTab
from cerebrus.tools.memreport.tabs.rhi_stats import RhiMemoryTab
from cerebrus.tools.memreport.utils import parse_memory_size_to_mb


def test_memory_stats_comma_handling():
    tab = MemoryStatsTab()
    context: Dict[str, Any] = {}

    # Test line with commas in memory values
    line = "Process Physical Memory 1,286.88 MB used, 1,363.36 MB peak"
    tab.parse(line, context)

    assert context.get("platform_phys_mem_used_mb") == 1286.88
    assert context.get("platform_phys_mem_peak_mb") == 1363.36

    # Verify the stat was added to the tree
    tree = context.get("memory_tree", [])
    gen_node = next((n for n in tree if n["name"] == "General Stats"), None)
    assert gen_node is not None
    stat = next(
        (s for s in gen_node["children"] if "Process Physical Memory" in s["name"]),
        None,
    )
    assert stat is not None
    assert "1,286.88 MB" in stat["value"]


def test_memory_stats_unit_parsing():
    assert parse_memory_size_to_mb("1024 KB") == 1.0
    assert parse_memory_size_to_mb("1 GB") == 1024.0
    assert parse_memory_size_to_mb("500 MB") == 500.0
    assert parse_memory_size_to_mb("1,024.50 MB") == 1024.5


def test_rhi_stats_parsing():
    tab = RhiMemoryTab()
    context: Dict[str, Any] = {}

    lines = [
        'MemReport: begin command "rhi.DumpMemory"',
        "   10.50 MB - IndexBuffer - STAT_IndexBufferMemory - STATGROUP_RHI",
        "  100.00 MB - VertexBuffer - STAT_StaticMeshVertexBufferMemory - STATGROUP_RHI",
        "  110.50 MB total",
        'MemReport: end command "rhi.DumpMemory"',
    ]

    for line in lines:
        tab.parse(line, context)

    data = context.get("rhi_memory_data", [])
    assert len(data) == 2
    assert data[0][0] == "IndexBuffer"
    assert data[0][2] == "10.50 MB"
    assert context.get("rhi_memory_total_val") == "110.50 MB"


def test_rhi_stats_gb_conversion_in_render():
    tab = RhiMemoryTab()

    # Safer mock that handles empty strings or unexpected values
    def safe_parse(val):
        if not val:
            return 0.0
        parts = val.split()
        if not parts:
            return 0.0
        try:
            return float(parts[0])
        except ValueError:
            return 0.0

    tab._parse_to_mb = safe_parse

    context: Dict[str, Any] = {
        "rhi_memory_data": [
            ["LargePool", "Texture", "2048.00 MB"],
            ["SmallPool", "Buffer", "512.00 MB"],
        ]
    }

    html = tab.render(context)
    # Check for GB conversion (2048 MB -> 2.00 GB)
    assert "2.00 GB" in html
    # Small pool should remain MB
    assert "512.00 MB" in html


def test_obj_summary_parsing():
    tab = ObjectSummaryTab()
    context: Dict[str, Any] = {}

    # Object summary parsing (obj list)
    lines = [
        'MemReport: begin command "obj list -resourcesizesort"',
        " 100 Objects (Total: 1047.81M / Max: 1047.81M / Res: 864.63M | ResDedSys: 864.55M / ResDedVid: 0.00M / ResUnknown: 0.08M)",
        "      Class Count NumKB MaxKB ResExcKB",
        " StaticMesh   100  1024   256      512",
        "    Texture   200  2048   512     1024",
    ]

    for line in lines:
        tab.parse(line, context)

    res = context.get("obj_summary", {})
    rows = res.get("rows", [])
    headers = res.get("headers", [])

    assert len(rows) == 2
    assert "Class" in headers
    assert "Instance Count" in headers

    # Verify parsing extracted data correctly
    assert any(row[0] == "StaticMesh" for row in rows)

    total_data = res.get("total_data", {})
    assert total_data["count"] == 100
    assert total_data["total"] == 1047.81
