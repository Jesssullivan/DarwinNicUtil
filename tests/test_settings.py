"""
Tests for TOML/env settings loading.
"""

import logging

from darwin_mgmt_nic.settings import NetworkProfile, init_config, load_settings


def write_config(path, content: str):
    path.write_text(content.strip() + "\n")
    return path


class TestNetworkProfile:
    """Test profile serialization contract used by declarative config generators."""

    def test_to_dict_uses_toml_schema_keys(self):
        profile = NetworkProfile(
            device_ip="192.168.88.1",
            laptop_ip="192.168.88.100",
            netmask="255.255.255.0",
            mgmt_network="192.168.88.0/24",
            device_name="Lab Management Device",
            description="USB OOB management path",
            device_type="network",
        )

        assert profile.to_dict() == {
            "device_ip": "192.168.88.1",
            "laptop_ip": "192.168.88.100",
            "netmask": "255.255.255.0",
            "mgmt_network": "192.168.88.0/24",
            "device_name": "Lab Management Device",
            "description": "USB OOB management path",
            "device_type": "network",
        }


class TestLoadSettings:
    """Test config precedence and profile application."""

    def test_load_settings_merges_configs_and_applies_default_profile(self, tmp_path, monkeypatch):
        base = write_config(
            tmp_path / "base.toml",
            """
            [defaults]
            device_ip = "192.0.2.1"
            laptop_ip = "192.0.2.100"
            netmask = "255.255.255.0"
            mgmt_network = "198.51.100.0/24"
            preserve_wifi = false

            [profiles.homelab]
            device_ip = "198.51.100.1"
            laptop_ip = "198.51.100.100"
            device_name = "Base Device"
            """,
        )
        local = write_config(
            tmp_path / "local.toml",
            """
            default_profile = "homelab"

            [defaults]
            netmask = "255.255.0.0"
            show_dashboard = true

            [profiles.homelab]
            device_ip = "192.168.88.1"
            laptop_ip = "192.168.88.100"
            mgmt_network = "192.168.88.0/24"
            device_name = "Lab Management Device"
            description = "USB OOB management path"
            device_type = "network"
            """,
        )
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_paths", lambda: [base, local])

        settings = load_settings()

        assert settings.config_sources == [str(base), str(local)]
        assert settings.default_profile == "homelab"
        assert settings.preserve_wifi is False
        assert settings.show_dashboard is True
        assert settings.device_ip == "192.168.88.1"
        assert settings.laptop_ip == "192.168.88.100"
        assert settings.netmask == "255.255.0.0"
        assert settings.mgmt_network == "192.168.88.0/24"
        assert settings.device_name == "Lab Management Device"
        assert settings.profiles["homelab"].description == "USB OOB management path"
        assert settings.profiles["homelab"].device_type == "network"

    def test_env_profile_selects_profile_and_boolean_overrides(self, tmp_path, monkeypatch):
        config = write_config(
            tmp_path / "config.toml",
            """
            default_profile = "default"

            [defaults]
            preserve_wifi = false
            dry_run = false
            show_dashboard = false

            [profiles.default]
            device_ip = "192.0.2.1"
            laptop_ip = "192.0.2.100"

            [profiles.env]
            device_ip = "203.0.113.1"
            laptop_ip = "203.0.113.100"
            mgmt_network = "203.0.113.0/24"
            device_name = "Env Selected Device"
            """,
        )
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_paths", lambda: [config])
        monkeypatch.setenv("DARWIN_NIC_PROFILE", "env")
        monkeypatch.setenv("DARWIN_NIC_PRESERVE_WIFI", "yes")
        monkeypatch.setenv("DARWIN_NIC_DRY_RUN", "1")
        monkeypatch.setenv("DARWIN_NIC_SHOW_DASHBOARD", "true")

        settings = load_settings()

        assert settings.default_profile == "env"
        assert settings.preserve_wifi is True
        assert settings.dry_run is True
        assert settings.show_dashboard is True
        assert settings.device_ip == "203.0.113.1"
        assert settings.laptop_ip == "203.0.113.100"
        assert settings.mgmt_network == "203.0.113.0/24"
        assert settings.device_name == "Env Selected Device"
        assert "env:DARWIN_NIC_PROFILE" in settings.config_sources
        assert "env:DARWIN_NIC_PRESERVE_WIFI" in settings.config_sources

    def test_explicit_profile_beats_default_and_env_profile(self, tmp_path, monkeypatch):
        config = write_config(
            tmp_path / "config.toml",
            """
            default_profile = "default"

            [profiles.default]
            device_ip = "192.0.2.1"
            laptop_ip = "192.0.2.100"

            [profiles.env]
            device_ip = "198.51.100.1"
            laptop_ip = "198.51.100.100"

            [profiles.cli]
            device_ip = "203.0.113.1"
            laptop_ip = "203.0.113.100"
            """,
        )
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_paths", lambda: [config])
        monkeypatch.setenv("DARWIN_NIC_PROFILE", "env")

        settings = load_settings(profile="cli")

        assert settings.default_profile == "env"
        assert settings.device_ip == "203.0.113.1"
        assert settings.laptop_ip == "203.0.113.100"

    def test_incomplete_profiles_are_skipped(self, tmp_path, monkeypatch, caplog):
        config = write_config(
            tmp_path / "config.toml",
            """
            [profiles.missing_laptop_ip]
            device_ip = "192.0.2.1"

            [profiles.complete]
            device_ip = "192.0.2.2"
            laptop_ip = "192.0.2.100"
            """,
        )
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_paths", lambda: [config])

        with caplog.at_level(logging.WARNING):
            settings = load_settings()

        assert "missing_laptop_ip" not in settings.profiles
        assert "complete" in settings.profiles
        assert "missing required fields" in caplog.text

    def test_malformed_config_is_skipped_and_later_config_still_loads(self, tmp_path, monkeypatch, caplog):
        bad = write_config(tmp_path / "bad.toml", "[defaults]\ndevice_ip =")
        good = write_config(
            tmp_path / "good.toml",
            """
            [defaults]
            device_ip = "192.0.2.10"
            laptop_ip = "192.0.2.110"
            """,
        )
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_paths", lambda: [bad, good])

        with caplog.at_level(logging.WARNING):
            settings = load_settings()

        assert settings.config_sources == [str(good)]
        assert settings.device_ip == "192.0.2.10"
        assert settings.laptop_ip == "192.0.2.110"
        assert f"Failed to load {bad}" in caplog.text


class TestInitConfig:
    """Test config file initialization."""

    def test_init_config_creates_file_and_respects_force(self, tmp_path, monkeypatch):
        config_dir = tmp_path / "darwin-nic"
        monkeypatch.setattr("darwin_mgmt_nic.settings.get_config_dir", lambda: config_dir)

        config_path = init_config()
        assert config_path == config_dir / "config.toml"
        assert config_path.exists()
        assert "[profiles.homelab]" in config_path.read_text()

        config_path.write_text("custom = true\n")
        assert init_config() is None
        assert config_path.read_text() == "custom = true\n"

        assert init_config(force=True) == config_path
        assert "[profiles.homelab]" in config_path.read_text()
