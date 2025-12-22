"""Data models for Cerebrus configuration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, cast


@dataclass
class CacheConfig:
    """Configuration for the cache directory used by Cerebrus."""

    directory: Path
    max_entries: int = 50

    @classmethod
    def from_mapping(
        cls, data: Mapping[str, object], default_directory: Path
    ) -> "CacheConfig":
        directory_value = Path(str(data.get("directory", default_directory)))
        max_entries_value = int(str(data.get("max_entries", cls.max_entries)))
        return cls(directory=directory_value, max_entries=max_entries_value)


@dataclass
class ProfileConfig:
    """Represents a profiling configuration entry."""

    name: str
    report_type: str
    nickname: str | None = None
    profile_path: Path | None = None
    package_name: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ProfileConfig":
        name = str(data.get("name", "default"))
        report_type = str(data.get("report_type", "summary"))
        nickname = data.get("nickname")
        profile_path = data.get("profile_path")
        package_name = data.get("package_name")
        return cls(
            name=name,
            report_type=report_type,
            nickname=str(nickname) if nickname is not None else None,
            profile_path=Path(str(profile_path)) if profile_path else None,
            package_name=str(package_name) if package_name else None,
        )


@dataclass
class AppConfig:
    """Top-level configuration for the Cerebrus application."""

    version: int = 1
    tool_paths: Dict[str, str] = field(default_factory=dict)
    profiles: List[ProfileConfig] = field(default_factory=list)
    cache: CacheConfig = field(
        default_factory=lambda: CacheConfig(directory=Path(".cerebrus-cache"))
    )

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "AppConfig":
        version_value = int(str(data.get("version", 1)))
        tool_paths_value = cast(Dict[str, str], data.get("tool_paths", {}))

        profile_entries = data.get("profiles", [])
        profiles_value = [
            ProfileConfig.from_mapping(entry) for entry in _as_iterable(profile_entries)
        ]

        cache_value = data.get("cache", {})
        cache_config = (
            CacheConfig.from_mapping(
                cache_value, default_directory=Path(".cerebrus-cache")
            )
            if isinstance(cache_value, Mapping)
            else CacheConfig(directory=Path(".cerebrus-cache"))
        )

        if not profiles_value:
            profiles_value.append(ProfileConfig(name="default", report_type="summary"))

        return cls(
            version=version_value,
            tool_paths=tool_paths_value,
            profiles=profiles_value,
            cache=cache_config,
        )


def _as_iterable(value: object) -> Iterable[Mapping[str, object]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Iterable):
        return [item for item in value if isinstance(item, Mapping)]
    return []
