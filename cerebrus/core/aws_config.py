import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class AWSConfig:
    remote_configs: Dict[str, str] = field(
        default_factory=lambda: {"Development": "", "Shipping": "", "Debug": ""}
    )
    remote_config_base_url: str = ""
    aws_access_key: str = ""
    aws_secret_key: str = ""
    aws_region: str = "ap-south-1"
    aws_profile: str = ""
    remote_manifest_url: str = ""

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=4)

    @classmethod
    def load(cls, path: Path) -> "AWSConfig":
        if not path.exists():
            raise FileNotFoundError(f"AWS Config not found at {path}")
        with open(path, "r") as f:
            data = json.load(f)
        
        # Filter fields for backward compatibility
        valid_fields = {
            "remote_configs",
            "remote_config_base_url",
            "aws_access_key",
            "aws_secret_key",
            "aws_region",
            "aws_profile",
            "remote_manifest_url",
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)
