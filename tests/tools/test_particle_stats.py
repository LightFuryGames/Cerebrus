from __future__ import annotations

import re
from typing import Any, Dict

import pytest

from cerebrus.tools.memreport.tabs.particle_stats import ParticleSystemsTab


@pytest.fixture
def tab() -> ParticleSystemsTab:
    return ParticleSystemsTab()


def test_should_handle_particle_command(tab: ParticleSystemsTab) -> None:
    assert (
        tab.should_handle('MemReport: Begin command "listparticlesystems -alphasort"')
        is True
    )
    assert (
        tab.should_handle(
            '  MemReport: Begin command "listparticlesystems -alphasort"  '
        )
        is True
    )
    assert tab.should_handle('MemReport: Begin command "DumpParticleMem"') is True


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
    assert (
        ps1["Name"] == "/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes"
    )
    assert ps1["Size"] == 122658
    assert ps1["Component Count"] == 6

    # Check total entry
    total = stats[2]
    assert total["Name"] == "Total"
    assert total["Size"] == 172658


def test_parse_dynamic_particle_stats(tab: ParticleSystemsTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        'MemReport: Begin command "DumpParticleMem"',
        "Particle Dynamic Memory Stats",
        "Type,Count,MaxCount,Mem(Bytes),MaxMem(Bytes),GTMem(Bytes),GTMemMax(Bytes)",
        "Sprite,10,20,1024,2048,512,1024",
        "Mesh,5,10,2048,4096,1024,2048",
        "ParticleData,Total(Bytes),FMath::Max(Bytes)",
        "GameThread,5000,10000",
        "RenderThread,3000,6000",
        "Max wasted GT,100",
        "Largest single GT allocation,200",
        "Largest single RT allocation,300",
        'MemReport: End command "DumpParticleMem"',
    ]

    for line in lines:
        tab.parse(line, context)

    dyn = context.get("particle_dynamic_stats")
    assert dyn is not None
    assert len(dyn["types"]) == 2
    assert dyn["types"][0]["Type"] == "Sprite"
    assert dyn["types"][0]["Count"] == 10

    summary = dyn["summary"]
    assert summary["Game Thread"]["Total"] == 5000
    assert summary["Max wasted Game Thread"] == 100
    assert summary["Largest single Game Thread allocation"] == 200


def test_parse_mixed_particle_commands(tab: ParticleSystemsTab) -> None:
    context: Dict[str, Any] = {}
    lines = [
        'MemReport: Begin command "DumpParticleMem"',
        "Particle Dynamic Memory Stats",
        "Max wasted GT,100",
        'MemReport: End command "DumpParticleMem"',
        'MemReport: Begin command "listparticlesystems -alphasort"',
        "122658,/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes,432,2376,40734,6,79116,38382",
    ]

    for line in lines:
        tab.parse(line, context)

    # Verify dynamic stats
    dyn = context.get("particle_dynamic_stats")
    assert dyn["summary"]["Max wasted Game Thread"] == 100
    assert dyn["parsing_mode"] is None

    # Verify static stats
    static = context.get("particle_stats")
    assert len(static) == 1
    assert (
        static[0]["Name"]
        == "/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes"
    )


def test_parse_invalid_line(tab: ParticleSystemsTab) -> None:
    context: Dict[str, Any] = {
        "particle_stats": [],
        "particle_dynamic_stats": {"types": [], "summary": {}, "parsing_mode": None},
    }
    tab.parse("invalid,line,data", context)
    assert len(context["particle_stats"]) == 0
    assert len(context["particle_dynamic_stats"]["types"]) == 0
