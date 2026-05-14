"""Coverage for the tier-resolution + GPU-heuristic fallback cascade."""

from __future__ import annotations

from pathlib import Path

import pytest

from cerebrus.plugins.analytics.core.device_profiles import (
    DeviceProfileReference,
    enrich_with_device_profile_tier,
    load_device_profile_reference,
)

# ---------------------------------------------------------------------------
# Helpers


@pytest.fixture
def ini(tmp_path: Path) -> Path:
    path = tmp_path / "BaseDeviceProfiles.ini"
    path.write_text(
        """
        [Android DeviceProfile]
        DeviceType=Android
        BaseProfileName=

        [Android_Low DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android

        [Android_Mid DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android

        [Android_High DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android

        [Android_Epic DeviceProfile]
        DeviceType=Android
        BaseProfileName=Android

        [Android_Adreno5xx DeviceProfile]
        BaseProfileName=Android_Low

        [Android_Adreno6xx DeviceProfile]
        BaseProfileName=Android_Mid

        [Android_Adreno6xx_Vulkan DeviceProfile]
        BaseProfileName=Android_Adreno6xx

        [Android_Adreno8xx DeviceProfile]
        BaseProfileName=Android_Epic

        [Android_Adreno8xx_Vulkan DeviceProfile]
        BaseProfileName=Android_Adreno8xx

        [Android_Made_Up DeviceProfile]
        BaseProfileName=Android_NonExistent
        """,
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Happy path: ini chain resolves


def test_ini_chain_low_tier(ini: Path) -> None:
    result = enrich_with_device_profile_tier(
        {"DeviceProfile": "Android_Adreno5xx"}, ini
    )
    assert result["scalability_tier"] == "Low"
    assert result["device_profile_chain"] == "Android_Adreno5xx -> Android_Low"
    assert result["device_profile_root"] == "Android_Low"
    assert result["device_profile_chain_depth"] == 2


def test_ini_chain_medium_tier_through_vulkan(ini: Path) -> None:
    result = enrich_with_device_profile_tier(
        {"DeviceProfile": "Android_Adreno6xx_Vulkan"}, ini
    )
    assert result["scalability_tier"] == "Medium"
    assert result["device_profile_chain_depth"] == 3
    assert "Android_Adreno6xx_Vulkan" in result["device_profile_chain"]
    assert result["device_profile_root"] == "Android_Mid"


def test_ini_chain_epic_tier(ini: Path) -> None:
    result = enrich_with_device_profile_tier(
        {"DeviceProfile": "Android_Adreno8xx_Vulkan"}, ini
    )
    assert result["scalability_tier"] == "Epic"
    assert result["device_profile_root"] == "Android_Epic"


# ---------------------------------------------------------------------------
# Fallback: GPU heuristic


def test_no_ini_uses_gpu_heuristic_for_adreno_840() -> None:
    result = enrich_with_device_profile_tier(
        {"cpu": "samsung|SM-S948U1|Adreno (TM) 840"}, None
    )
    assert result["scalability_tier"] == "Epic"
    assert result["device_profile_chain"] == ""


def test_bad_ini_path_falls_back_to_gpu_heuristic() -> None:
    result = enrich_with_device_profile_tier(
        {"cpu": "foo|bar|Mali-G710"}, "/does/not/exist.ini"
    )
    assert result["scalability_tier"] == "Epic"  # Mali-G710 -> Epic


def test_ini_unknown_profile_with_known_gpu(ini: Path) -> None:
    """ini loaded but DeviceProfile not in any tier chain - GPU fills the gap."""
    result = enrich_with_device_profile_tier(
        {"DeviceProfile": "Android_Made_Up", "cpu": "q|m|Adreno (TM) 740"},
        ini,
    )
    assert result["scalability_tier"] == "High"  # 7xx => High via heuristic
    # Chain still recorded because the ini knew about Android_Made_Up.
    assert "Android_Made_Up" in result["device_profile_chain"]


@pytest.mark.parametrize(
    "gpu,expected",
    [
        ("Adreno (TM) 660", "Medium"),
        ("Adreno (TM) 506", "Low"),
        ("Adreno (TM) 740", "High"),
        ("Adreno (TM) 850", "Epic"),
        ("Mali-G710", "Epic"),
        ("Mali-G77", "High"),
        ("Mali-G72", "Medium"),
        ("Mali-G31", "Low"),
        ("Mali-T880", "Low"),
        ("Samsung Xclipse 920", "High"),
        ("Samsung Xclipse 540", "Low"),
        ("PowerVR Rogue GM9446", "High"),
        ("PowerVR Rogue GT7400", "Medium"),
        ("PowerVR Rogue GE8320", "Medium"),
        ("PowerVR Rogue G6230", "Low"),
        ("NVIDIA Tegra", "High"),
    ],
)
def test_gpu_heuristic_mapping(gpu: str, expected: str) -> None:
    result = enrich_with_device_profile_tier({"cpu": f"x|y|{gpu}"}, None)
    assert result["scalability_tier"] == expected


# ---------------------------------------------------------------------------
# Fallback: total Unknown


def test_no_ini_no_gpu_returns_unknown() -> None:
    result = enrich_with_device_profile_tier({}, None)
    assert result["scalability_tier"] == "Unknown"
    assert result["device_profile_chain"] == ""
    assert result["device_profile_root"] == ""
    assert result["device_profile_chain_depth"] == 0


def test_completely_garbage_input_returns_unknown() -> None:
    result = enrich_with_device_profile_tier({"foo": "bar", "baz": 42}, None)
    assert result["scalability_tier"] == "Unknown"


# ---------------------------------------------------------------------------
# Reference loader + parsing


def test_load_reference_records_sha1(ini: Path) -> None:
    ref = load_device_profile_reference(ini)
    assert isinstance(ref, DeviceProfileReference)
    assert ref.path == ini
    assert len(ref.sha1) == 40  # SHA-1 hex digest
    assert "Android_Adreno8xx" in ref.base_profiles
    assert ref.base_profiles["Android_Adreno8xx"] == "Android_Epic"


def test_resolve_handles_cycle_safely(ini: Path) -> None:
    """If an ini has a profile that points back at itself, resolve must not loop."""
    bad_ini = ini.parent / "bad.ini"
    bad_ini.write_text(
        """
        [Android_Loop DeviceProfile]
        BaseProfileName=Android_Loop
        """,
        encoding="utf-8",
    )
    ref = load_device_profile_reference(bad_ini)
    resolution = ref.resolve("Android_Loop")
    assert resolution.chain == ("Android_Loop",)
    assert resolution.tier is None
