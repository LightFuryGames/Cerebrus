from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TIER_PROFILE_NAMES = {
    "Android_Low": "Low",
    "Android_Mid": "Medium",
    "Android_High": "High",
    "Android_Epic": "Epic",
}


# GPU-family heuristic. Last-resort fallback when the ini chain cannot resolve
# a tier (ini missing, profile unknown, or DeviceProfile row absent from the
# report footer). Order matters - more specific patterns first.
GPU_TIER_HEURISTIC: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Adreno.*?[\s(]8[0-9][0-9]", re.IGNORECASE), "Epic"),
    (re.compile(r"Adreno.*?[\s(]7[0-9][0-9]", re.IGNORECASE), "High"),
    (re.compile(r"Adreno.*?[\s(]6[0-9][0-9]", re.IGNORECASE), "Medium"),
    (re.compile(r"Adreno.*?[\s(][45][0-9][0-9]", re.IGNORECASE), "Low"),
    (re.compile(r"Mali[- ]?G(710|7[1-9][0-9]|9[0-9][0-9])", re.IGNORECASE), "Epic"),
    (re.compile(r"Mali[- ]?G(77|78)", re.IGNORECASE), "High"),
    (re.compile(r"Mali[- ]?G(71|72|76)", re.IGNORECASE), "Medium"),
    (re.compile(r"Mali[- ]?G[3-6][0-9]", re.IGNORECASE), "Low"),
    (re.compile(r"Mali[- ]?T[6-8][0-9][0-9]", re.IGNORECASE), "Low"),
    (re.compile(r"Samsung Xclipse 9[0-9][0-9]", re.IGNORECASE), "High"),
    (re.compile(r"Samsung Xclipse 5[0-9][0-9]", re.IGNORECASE), "Low"),
    (re.compile(r"PowerVR.*?GM9", re.IGNORECASE), "High"),
    (re.compile(r"PowerVR.*?GT7", re.IGNORECASE), "Medium"),
    (re.compile(r"PowerVR.*?GE8", re.IGNORECASE), "Medium"),
    (re.compile(r"PowerVR.*?G6", re.IGNORECASE), "Low"),
    (re.compile(r"NVIDIA Tegra", re.IGNORECASE), "High"),
)


@dataclass(frozen=True)
class DeviceProfileResolution:
    profile: str
    tier: str | None
    chain: tuple[str, ...]
    reference_path: str
    reference_sha1: str


@dataclass(frozen=True)
class DeviceProfileReference:
    path: Path
    sha1: str
    base_profiles: dict[str, str]

    def resolve(self, profile: str) -> DeviceProfileResolution:
        chain: list[str] = []
        seen: set[str] = set()
        current = profile.strip()
        tier: str | None = None

        while current and current not in seen:
            chain.append(current)
            seen.add(current)
            if current in TIER_PROFILE_NAMES:
                tier = TIER_PROFILE_NAMES[current]
                break
            current = self.base_profiles.get(current, "").strip()

        return DeviceProfileResolution(
            profile=profile,
            tier=tier,
            chain=tuple(chain),
            reference_path=str(self.path),
            reference_sha1=self.sha1,
        )


def load_device_profile_reference(path: str | Path) -> DeviceProfileReference:
    config_path = Path(path)
    content = config_path.read_text(encoding="utf-8", errors="ignore")
    sha1 = hashlib.sha1(content.encode("utf-8", errors="ignore")).hexdigest()
    return DeviceProfileReference(
        path=config_path,
        sha1=sha1,
        base_profiles=_parse_base_profiles(content),
    )


def _gpu_heuristic_tier(values: dict[str, Any]) -> str | None:
    gpu = _first_present_value(
        values,
        ("GPU", "gpu", "Device GPU", "device_gpu", "CPU/Device", "cpu", "[cpu]"),
    )
    if not gpu:
        return None
    text = str(gpu)
    for pattern, tier in GPU_TIER_HEURISTIC:
        if pattern.search(text):
            return tier
    return None


def _unknown_payload() -> dict[str, Any]:
    return {
        "Scalability Tier": "Unknown",
        "DeviceProfile Chain": "",
        "scalability_tier": "Unknown",
        "device_profile_chain": "",
        "device_profile_chain_depth": 0,
        "device_profile_root": "",
    }


def enrich_with_device_profile_tier(
    values: dict[str, Any], config_path: str | Path | None
) -> dict[str, Any]:
    """Resolve scalability tier with a three-tier fallback.

    1. ini_chain     - walk BaseProfileName in BaseDeviceProfiles.ini.
    2. gpu_heuristic - regex GPU family when ini lookup fails.
    3. unknown       - emit Unknown tier so the ES field is never null.
    """
    profile_raw = _first_present_value(
        values,
        (
            "DeviceProfile",
            "deviceprofile",
            "Device Profile",
            "[deviceprofile]",
            "[DeviceProfile]",
        ),
    )
    profile = str(profile_raw).strip() if profile_raw else ""

    path = Path(config_path) if config_path else None
    ini_ok = path is not None and path.is_file()

    resolution = None
    if ini_ok and profile:
        assert path is not None  # narrowed by ini_ok
        try:
            reference = load_device_profile_reference(path)
            resolution = reference.resolve(profile)
        except OSError:
            resolution = None

        if resolution and resolution.tier:
            chain_str = " -> ".join(resolution.chain)
            return {
                "DeviceProfile": resolution.profile,
                "Scalability Tier": resolution.tier,
                "DeviceProfile Chain": chain_str,
                "DeviceProfile Reference": resolution.reference_path,
                "DeviceProfile Reference SHA1": resolution.reference_sha1,
                "device_profile": resolution.profile,
                "scalability_tier": resolution.tier,
                "device_profile_chain": chain_str,
                "device_profile_chain_depth": len(resolution.chain),
                "device_profile_root": resolution.chain[-1] if resolution.chain else "",
                "device_profile_reference": resolution.reference_path,
                "device_profile_reference_sha1": resolution.reference_sha1,
            }

        # ini loaded but chain didn't reach a tier sentinel - try GPU heuristic.
        heuristic = _gpu_heuristic_tier(values)
        if heuristic and resolution:
            chain_str = " -> ".join(resolution.chain)
            return {
                "DeviceProfile": resolution.profile,
                "Scalability Tier": heuristic,
                "DeviceProfile Chain": chain_str,
                "DeviceProfile Reference": resolution.reference_path,
                "DeviceProfile Reference SHA1": resolution.reference_sha1,
                "device_profile": resolution.profile,
                "scalability_tier": heuristic,
                "device_profile_chain": chain_str,
                "device_profile_chain_depth": len(resolution.chain),
                "device_profile_root": resolution.chain[-1] if resolution.chain else "",
                "device_profile_reference": resolution.reference_path,
                "device_profile_reference_sha1": resolution.reference_sha1,
            }

    # No ini or no DeviceProfile field - pure GPU fallback.
    heuristic = _gpu_heuristic_tier(values)
    if heuristic:
        return {
            "Scalability Tier": heuristic,
            "DeviceProfile Chain": "",
            "scalability_tier": heuristic,
            "device_profile_chain": "",
            "device_profile_chain_depth": 0,
            "device_profile_root": "",
        }

    return _unknown_payload()


def _parse_base_profiles(content: str) -> dict[str, str]:
    base_profiles: dict[str, str] = {}
    current_profile: str | None = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue

        section_match = re.fullmatch(r"\[([^\]]+?)\s+DeviceProfile\]", line)
        if section_match:
            current_profile = section_match.group(1).strip()
            continue

        if current_profile is None:
            continue

        base_match = re.fullmatch(r"BaseProfileName\s*=\s*(.*)", line)
        if base_match:
            base_profiles[current_profile] = base_match.group(1).strip()

    return base_profiles


def _first_present_value(values: dict[str, Any], keys: tuple[str, ...]) -> Any:
    normalized = {str(key).lower(): value for key, value in values.items()}
    for key in keys:
        value = normalized.get(key.lower())
        if value not in (None, ""):
            return value
    return None
