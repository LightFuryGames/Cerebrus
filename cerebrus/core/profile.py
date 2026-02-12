import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cerebrus.core.paths import get_app_data_dir

# Global config path
CONFIG_DIR = get_app_data_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class Profile:
    nickname: Optional[str] = None
    package_name: str = ""
    output_file_name: str = "perf_report"
    input_path: str = "C:/"
    output_path: str = "C:/"
    config_output_path: str = "C:/"
    use_prefix_only: bool = False

    move_logs_enabled: bool = True
    move_csv_enabled: bool = True
    move_memreport_enabled: bool = True
    generate_perf_report_enabled: bool = True
    generate_memreport_enabled: bool = False
    generate_colored_logs_enabled: bool = True
    
    aws_config_path: Optional[str] = None
    
    # Runtime only, not saved to JSON via asdict
    aws_config: Optional["AWSConfig"] = field(default=None, repr=False, compare=False)

    def validate(self) -> List[str]:
        errors = []
        if not self.package_name:
            errors.append("Package Name cannot be empty.")
        elif not self.package_name.startswith("com."):
            errors.append("Package Name must start with 'com.'.")
        return errors

    def save(self, path: Path) -> None:
        data = asdict(self)
        # Never save the runtime config object into the profile JSON
        if "aws_config" in data:
            del data["aws_config"]
            
        with open(path, "w") as f:
            json.dump(data, f, indent=4)

    @classmethod
    def load(cls, path: Path) -> "Profile":
        if not path.exists():
            raise FileNotFoundError(f"Profile not found at {path}")
        with open(path, "r") as f:
            data = json.load(f)
            
        # Filter to only use fields that exist in current Profile class (backward compatibility)
        valid_fields = {
            "nickname",
            "package_name",
            "output_file_name",
            "input_path",
            "output_path",
            "config_output_path",
            "use_prefix_only",
            "move_logs_enabled",
            "move_csv_enabled",
            "move_memreport_enabled",
            "generate_perf_report_enabled",
            "generate_memreport_enabled",
            "generate_colored_logs_enabled",
            "aws_config_path",
        }
        
        # Check for legacy AWS fields to help with migration
        legacy_aws_fields = {
            "remote_configs",
            "remote_config_base_url",
            "aws_access_key",
            "aws_secret_key",
            "aws_region",
            "aws_profile",
            "remote_manifest_url",
        }
        
        has_legacy = any(k in data for k in legacy_aws_fields)
        
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        profile = cls(**filtered_data)
        
        # If we have legacy data and NO aws_config_path, we might want to store it temporarily
        # or handle it in the ProfileManager. For now, let's just make sure it's accessible
        # if needed during a migration step, but we won't keep it in the Profile class.
        if has_legacy and not profile.aws_config_path:
            from cerebrus.core.aws_config import AWSConfig
            legacy_data = {k: v for k, v in data.items() if k in legacy_aws_fields}
            profile.aws_config = AWSConfig(**legacy_data)
            # Note: aws_config_path remains None until user saves it to a file
            
        return profile


class ProfileManager:
    def __init__(self) -> None:
        self._ensure_config_dir()
        self.current_profile: Optional[Profile] = None
        self.current_profile_path: Optional[Path] = None

    def _ensure_config_dir(self) -> None:
        if not CONFIG_DIR.exists():
            CONFIG_DIR.mkdir(parents=True)

    def get_last_used_profile_path(self) -> Optional[Path]:
        if not CONFIG_FILE.exists():
            return None
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                path_str = data.get("last_used_profile")
                if path_str:
                    path = Path(path_str)
                    if path.exists():
                        return path
        except Exception:
            pass
        return None

    def set_last_used_profile_path(self, path: Optional[Path]) -> None:
        data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
            except Exception:
                data = {}

        if path:
            data["last_used_profile"] = str(path.absolute())
        else:
            data.pop("last_used_profile", None)

        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def load_last_profile(self) -> Tuple[Profile, Optional[Path]]:
        path = self.get_last_used_profile_path()
        if path:
            try:
                profile = Profile.load(path)
                self._load_aws_config(profile)
                self.current_profile = profile
                self.current_profile_path = path
                return profile, path
            except Exception:
                # Failed to load, maybe deleted
                self.set_last_used_profile_path(None)

        # Try to load bundled default profile
        try:
            import sys

            if getattr(sys, "frozen", False):
                base_path = Path(getattr(sys, "_MEIPASS"))
                default_path = base_path / "cerebrus" / "resources" / "Titan.json"
                if not default_path.exists():
                    default_path = base_path / "resources" / "Titan.json"
            else:
                base_path = Path(__file__).resolve().parent.parent
                default_path = base_path / "resources" / "Titan.json"

            # Check for shadow default profile first (user cached settings for default)
            shadow_path = CONFIG_DIR / "default_profile.json"
            if shadow_path.exists():
                try:
                    profile = Profile.load(shadow_path)
                    self._load_aws_config(profile)
                    self.current_profile = profile
                    self.current_profile_path = None  # Treat as default
                    return profile, None
                except Exception:
                    pass  # Fallback to bundled

            if default_path.exists():
                profile = Profile.load(default_path)
                self._load_aws_config(profile)
                self.current_profile = profile
                # We don't set current_profile_path for the default bundled profile
                # to avoid overwriting it in the install dir.
                # It acts as a template until saved elsewhere.
                self.current_profile_path = None
                return profile, None
        except Exception as e:
            print(f"Failed to load default profile: {e}")

        # Fallback to empty profile
        default_profile = Profile(nickname="Titan", package_name="com.lightfury.titan")
        self.current_profile = default_profile
        self.current_profile_path = None
        return default_profile, None

    def create_new_profile(
        self, nickname: str, package_name: str, path: Path
    ) -> Profile:
        profile = Profile(nickname=nickname, package_name=package_name)
        # Validate before saving? User said "Package Name input field would be saved into the profile by the user and cannot be null..."
        # We'll assume the UI handles validation feedback, but we can check here too.
        profile.save(path)
        self.current_profile = profile
        self.current_profile_path = path
        self.set_last_used_profile_path(path)
        return profile

    def save_current_profile(self) -> None:
        if self.current_profile and self.current_profile_path:
            self.current_profile.save(self.current_profile_path)

    def _load_aws_config(self, profile: Profile) -> None:
        """Load AWS config from path if configured."""
        if not profile.aws_config_path:
            return
            
        from cerebrus.core.aws_config import AWSConfig
        try:
            path = Path(profile.aws_config_path)
            if path.exists():
                profile.aws_config = AWSConfig.load(path)
            else:
                msg = f"AWS Config file not found at {profile.aws_config_path}"
                print(f"Warning: {msg}")
                # We can initialize an empty config so the UI doesn't crash, 
                # but it won't have the path set in the config object itself if we had one there.
                # For now, let's just make sure the user knows.
                if not profile.aws_config:
                    profile.aws_config = AWSConfig()
        except Exception as e:
            print(f"Error loading AWS Config: {e}")
            if not profile.aws_config:
                profile.aws_config = AWSConfig()
