from __future__ import annotations

import re
from typing import Any, Dict

import pytest

from cerebrus.tools.memreport.tabs.render_target_pool import RenderTargetPoolTab


@pytest.fixture
def tab() -> RenderTargetPoolTab:
    return RenderTargetPoolTab()


def test_should_handle_correct_command(tab: RenderTargetPoolTab) -> None:
    assert tab.should_handle('MemReport: Begin command "r.DumpRenderTargetPoolMemory"') is True
    assert tab.should_handle('  MemReport: Begin command "r.DumpRenderTargetPoolMemory"  ') is True
    assert tab.should_handle('MemReport: Begin command "something else"') is False


def test_parse_pooled_render_targets(tab: RenderTargetPoolTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        'MemReport: Begin command "r.DumpRenderTargetPoolMemory"',
        "Pooled Render Targets:",
        "  10.500MB 1024x1024    1mip(s) SceneColor (PF_FloatRGBA) Unused frames: 5",
        "   2.000MB  512x 512    1mip(s) SceneDepth (PF_DepthStencil) Unused frames: 0",
        "  12.500MB total, 10.500MB used, 2.000MB unused, 2 render targets",
    ]

    for line in lines:
        tab.parse(line, context)

    data = context.get("render_target_pool")
    assert data is not None
    assert len(data["pooled"]) == 2
    assert data["summary"]["pooled_total_mb"] == 12.5
    assert data["summary"]["pooled_used_mb"] == 10.5
    assert data["summary"]["pooled_unused_mb"] == 2.0
    assert data["summary"]["pooled_count"] == 2

    # Check first entry
    rt1 = data["pooled"][0]
    assert rt1["name"] == "SceneColor"
    assert rt1["size_mb"] == 10.5
    assert rt1["width"] == 1024
    assert rt1["height"] == 1024
    assert rt1["format"] == "PF_FloatRGBA"
    assert rt1["unused_frames"] == 5


def test_parse_deferred_render_targets(tab: RenderTargetPoolTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        "Deferred Render Targets:",
        "   4.000MB 1024x1024    1mip(s) LightAttenuation (PF_R8G8B8A8)",
        "   4.000MB Deferred total",
    ]

    for line in lines:
        tab.parse(line, context)

    data = context.get("render_target_pool")
    assert data is not None
    assert len(data["deferred"]) == 1
    assert data["summary"]["deferred_mb"] == 4.0

    rt = data["deferred"][0]
    assert rt["name"] == "LightAttenuation"
    assert rt["size_mb"] == 4.0
    assert rt["format"] == "PF_R8G8B8A8"


def test_parse_complex_dimensions(tab: RenderTargetPoolTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        "Pooled Render Targets:",
        "   1.125MB  256x 256[  3]  1mip(s) CascadeShadowMap (PF_ShadowDepth) Unused frames: 12",
        "   0.063MB   64x  64cube  1mip(s) ReflectionCapture (PF_FloatRGBA) Unused frames: 120",
    ]

    for line in lines:
        tab.parse(line, context)

    pooled = context["render_target_pool"]["pooled"]
    
    # CascadeShadowMap (Array)
    # The current regex for array size is (?:\s*\[\s*(\d+)\])?
    # 256x 256[  3]
    rt1 = pooled[0]
    assert rt1["name"] == "CascadeShadowMap"
    assert rt1["is_array"] == "Yes"
    assert rt1["array_size"] == "3"

    # ReflectionCapture (Cube)
    # The current regex handles cube as part of height if not careful?
    # Match: ^\s*([\d\.]+)MB\s+(\d+)x\s*(\d+)(?:\s*x\s*(\d+))?(?:\s*\[\s*(\d+)\])?\s+(\d+)mip\(s\)\s+(.*)$
    # "  64cube" -> The \d+ for height might stop at the 'c'? 
    # Let's check the regex in render_target_pool.py
    # \d+ for width, \d+ for height.
    # If height is "64cube", \d+ matches "64". The "cube" becomes part of the remainder?
    # No, the regex says \s*(\d+)mip\(s\). 
    # Between height and mip(s) there can be optional depth and array size.
    # If "cube" is there, it might break the match if not handled.
