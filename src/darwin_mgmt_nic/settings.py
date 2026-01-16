"""
Configuration loading for darwin-nic

Search order (later overrides earlier):
1. Built-in defaults (RFC 5737 documentation IPs)
2. /etc/darwin-nic/config.toml (system-wide)
3. ~/.config/darwin-nic/config.toml (user global)
4. ./.darwin-nic.toml (local directory - adjacent invocation)
5. Environment variables (DARWIN_NIC_*)
6. CLI arguments (highest priority)

Profile support allows named configurations for different environments.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

# Python 3.11+ has tomllib in stdlib
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found]


logger = logging.getLogger(__name__)

# Config file names
CONFIG_FILENAME = "config.toml"
LOCAL_CONFIG_FILENAME = ".darwin-nic.toml"
ALT_LOCAL_CONFIG = "darwin-nic.toml"

# Environment variable prefix
ENV_PREFIX = "DARWIN_NIC_"


def get_config_dir() -> Path:
    """Get user config directory (XDG-compliant)."""
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "darwin-nic"
    return Path.home() / ".config" / "darwin-nic"


def get_config_paths() -> list[Path]:
    """
    Return list of config paths to check, in precedence order (lowest first).

    Returns paths that WOULD be checked - caller should verify existence.
    """
    paths: list[Path] = []

    # 1. System-wide config
    paths.append(Path("/etc/darwin-nic") / CONFIG_FILENAME)

    # 2. User global config (XDG)
    paths.append(get_config_dir() / CONFIG_FILENAME)

    # 3. Legacy user config (dotfile in home)
    paths.append(Path.home() / ".darwin-nic.toml")

    # 4. Local directory config (adjacent invocation pattern)
    cwd = Path.cwd()
    paths.append(cwd / LOCAL_CONFIG_FILENAME)
    paths.append(cwd / ALT_LOCAL_CONFIG)  # Also check without leading dot

    return paths


@dataclass
class NetworkProfile:
    """A named network configuration profile."""
    device_ip: str
    laptop_ip: str
    netmask: str = "255.255.255.0"
    mgmt_network: str = "198.51.100.0/24"
    device_name: str = "Network Device"

    # Optional metadata
    description: str = ""
    device_type: str = ""  # e.g., "mikrotik", "cisco", "juniper"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "device_ip": self.device_ip,
            "laptop_ip": self.laptop_ip,
            "netmask": self.netmask,
            "mgmt_network": self.mgmt_network,
            "device_name": self.device_name,
            "description": self.description,
            "device_type": self.device_type,
        }


@dataclass
class Settings:
    """
    Merged configuration settings from all sources.

    Attributes represent the final resolved values after merging
    all config files, environment variables, and CLI arguments.
    """
    # Network defaults (RFC 5737 documentation IPs as fallback)
    device_ip: str = "192.0.2.1"
    laptop_ip: str = "192.0.2.100"
    netmask: str = "255.255.255.0"
    mgmt_network: str = "198.51.100.0/24"
    device_name: str = "Network Device"

    # Behavior defaults
    preserve_wifi: bool = True
    dry_run: bool = False
    show_dashboard: bool = False
    skip_confirmation: bool = False

    # Profile management
    default_profile: str | None = None
    profiles: dict[str, NetworkProfile] = field(default_factory=dict)

    # Metadata
    config_sources: list[str] = field(default_factory=list)

    def get_profile(self, name: str) -> NetworkProfile | None:
        """Get a named profile."""
        return self.profiles.get(name)

    def apply_profile(self, name: str) -> bool:
        """
        Apply a named profile to current settings.

        Returns True if profile was found and applied.
        """
        profile = self.profiles.get(name)
        if not profile:
            return False

        self.device_ip = profile.device_ip
        self.laptop_ip = profile.laptop_ip
        self.netmask = profile.netmask
        self.mgmt_network = profile.mgmt_network
        self.device_name = profile.device_name
        return True

    def list_profiles(self) -> list[str]:
        """List available profile names."""
        return list(self.profiles.keys())


def _merge_defaults(settings: Settings, data: dict[str, Any]) -> None:
    """Merge [defaults] section into settings."""
    defaults = data.get("defaults", {})

    if "device_ip" in defaults:
        settings.device_ip = defaults["device_ip"]
    if "laptop_ip" in defaults:
        settings.laptop_ip = defaults["laptop_ip"]
    if "netmask" in defaults:
        settings.netmask = defaults["netmask"]
    if "mgmt_network" in defaults:
        settings.mgmt_network = defaults["mgmt_network"]
    if "device_name" in defaults:
        settings.device_name = defaults["device_name"]
    if "preserve_wifi" in defaults:
        settings.preserve_wifi = defaults["preserve_wifi"]
    if "dry_run" in defaults:
        settings.dry_run = defaults["dry_run"]
    if "show_dashboard" in defaults:
        settings.show_dashboard = defaults["show_dashboard"]
    if "skip_confirmation" in defaults:
        settings.skip_confirmation = defaults["skip_confirmation"]


def _merge_profiles(settings: Settings, data: dict[str, Any]) -> None:
    """Merge [profiles.*] sections into settings."""
    profiles_data = data.get("profiles", {})

    for name, profile_data in profiles_data.items():
        if not isinstance(profile_data, dict):
            continue

        # Require at minimum device_ip and laptop_ip
        if "device_ip" not in profile_data or "laptop_ip" not in profile_data:
            logger.warning(f"Profile '{name}' missing required fields, skipping")
            continue

        profile = NetworkProfile(
            device_ip=profile_data["device_ip"],
            laptop_ip=profile_data["laptop_ip"],
            netmask=profile_data.get("netmask", settings.netmask),
            mgmt_network=profile_data.get("mgmt_network", settings.mgmt_network),
            device_name=profile_data.get("device_name", name),
            description=profile_data.get("description", ""),
            device_type=profile_data.get("device_type", ""),
        )
        settings.profiles[name] = profile


def _merge_config(settings: Settings, data: dict[str, Any], source: str) -> None:
    """Merge a config dict into settings."""
    settings.config_sources.append(source)

    # Top-level default_profile
    if "default_profile" in data:
        settings.default_profile = data["default_profile"]

    # Merge sections
    _merge_defaults(settings, data)
    _merge_profiles(settings, data)


def _apply_env_overrides(settings: Settings) -> None:
    """Apply environment variable overrides."""
    env_mappings = {
        f"{ENV_PREFIX}DEVICE_IP": "device_ip",
        f"{ENV_PREFIX}LAPTOP_IP": "laptop_ip",
        f"{ENV_PREFIX}NETMASK": "netmask",
        f"{ENV_PREFIX}MGMT_NETWORK": "mgmt_network",
        f"{ENV_PREFIX}DEVICE_NAME": "device_name",
        f"{ENV_PREFIX}PROFILE": "default_profile",
    }

    bool_mappings = {
        f"{ENV_PREFIX}PRESERVE_WIFI": "preserve_wifi",
        f"{ENV_PREFIX}DRY_RUN": "dry_run",
        f"{ENV_PREFIX}SHOW_DASHBOARD": "show_dashboard",
        f"{ENV_PREFIX}SKIP_CONFIRMATION": "skip_confirmation",
    }

    for env_var, attr in env_mappings.items():
        value = os.environ.get(env_var)
        if value:
            setattr(settings, attr, value)
            settings.config_sources.append(f"env:{env_var}")

    for env_var, attr in bool_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            setattr(settings, attr, value.lower() in ("1", "true", "yes"))
            settings.config_sources.append(f"env:{env_var}")


def load_settings(profile: str | None = None) -> Settings:
    """
    Load and merge settings from all config sources.

    Args:
        profile: Optional profile name to apply after loading.
                 If None and default_profile is set in config, uses that.

    Returns:
        Merged Settings object with all values resolved.
    """
    settings = Settings()

    # Load from each config path that exists
    for config_path in get_config_paths():
        if config_path.exists():
            try:
                with open(config_path, "rb") as f:
                    data = tomllib.load(f)
                _merge_config(settings, data, str(config_path))
                logger.debug(f"Loaded config from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load {config_path}: {e}")

    # Apply environment overrides
    _apply_env_overrides(settings)

    # Apply profile if specified (CLI arg takes precedence)
    active_profile = profile or settings.default_profile
    if active_profile:
        if settings.apply_profile(active_profile):
            logger.debug(f"Applied profile: {active_profile}")
        else:
            logger.warning(f"Profile not found: {active_profile}")

    return settings


def ensure_config_dir() -> Path:
    """Ensure user config directory exists and return its path."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_default_config_content() -> str:
    """Return default config file content as a string."""
    return '''# Darwin Management NIC Configurator - User Configuration
# Place this file at: ~/.config/darwin-nic/config.toml
# Or use a local override: ./.darwin-nic.toml

# Default profile to use when none specified via CLI
# default_profile = "homelab"

# Global defaults applied to all operations
[defaults]
netmask = "255.255.255.0"
preserve_wifi = true
dry_run = false

# Named profiles for different environments
# Use with: darwin-nic configure --profile homelab

[profiles.homelab]
device_ip = "192.168.88.1"
laptop_ip = "192.168.88.100"
mgmt_network = "192.168.10.0/24"
device_name = "Bastion Switch"
description = "Home lab management network"
# device_type = "mikrotik"  # Optional: for future device-specific features

[profiles.homelab-secondary]
device_ip = "192.168.88.2"
laptop_ip = "192.168.88.100"
mgmt_network = "192.168.10.0/24"
device_name = "Secondary Switch"
description = "Secondary management target"

# Example: datacenter profile
# [profiles.datacenter]
# device_ip = "10.200.0.1"
# laptop_ip = "10.200.0.100"
# mgmt_network = "10.200.0.0/24"
# device_name = "DC Core Switch"
'''


def init_config(force: bool = False) -> Path | None:
    """
    Initialize user config file with defaults.

    Args:
        force: If True, overwrite existing config.

    Returns:
        Path to created config file, or None if it already exists and force=False.
    """
    config_dir = ensure_config_dir()
    config_path = config_dir / CONFIG_FILENAME

    if config_path.exists() and not force:
        return None

    config_path.write_text(get_default_config_content())
    return config_path
