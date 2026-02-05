from __future__ import annotations

import re
from typing import Any, Dict

import pytest

from cerebrus.tools.memreport.tabs.particle_stats import ParticleSystemsTab


@pytest.fixture
def tab() -> ParticleSystemsTab:
    return ParticleSystemsTab()


def test_should_handle_particle_command(tab: ParticleSystemsTab) -> None:
    assert tab.should_handle('MemReport: Begin command "listparticlesystems -alphasort"') is True
    assert tab.should_handle('  MemReport: Begin command "listparticlesystems -alphasort"  ') is True
    assert tab.should_handle('MemReport: Begin command "DumpParticleMem"') is False


def test_parse_particle_stats(tab: ParticleSystemsTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        'MemReport: Begin command "listparticlesystems -alphasort"',
        "122658,/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes,432,2376,40734,6,79116,38382",
        "50000,/Game/VFX/Fire/PS_Fire.PS_Fire,100,200,300,2,400,500",
        "172658,Total,532,2576,41034,8,79516,38882",
    ]

    for line in lines:
        tab.parse(line, context)

    stats = context.get("particle_stats")
    assert stats is not None
    # "Total" is also parsed into the list by the current implementation
    assert len(stats) == 3

    # Check first particle system
    ps1 = stats[0]
    assert ps1["Name"] == "/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes"
    assert ps1["Size"] == 122658
    assert ps1["ComponentCount"] == 6

    # Check total entry
    total = stats[2]
    assert total["Name"] == "Total"
    assert total["Size"] == 172658


def test_parse_invalid_line(tab: ParticleSystemsTab) -> None:
    context: Dict[str, Any] = {"particle_stats": []}
    tab.parse("invalid,line,data", context)
    assert len(context["particle_stats"]) == 0
