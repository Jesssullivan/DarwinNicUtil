"""
Tests for the configure backend CLI.
"""

import logging
import subprocess
import sys
from pathlib import Path

import pytest

from darwin_mgmt_nic import cli
from darwin_mgmt_nic.settings import NetworkProfile, Settings


class FakeConsole:
    """Small console test double that records printed objects."""

    instances = []

    def __init__(self):
        self.printed = []
        self.__class__.instances.append(self)

    def print(self, *objects, **kwargs):
        self.printed.append(objects)


def rendered_console() -> str:
    """Return all text-ish objects printed through the latest FakeConsole."""
    return "\n".join(str(item) for call in FakeConsole.instances[-1].printed for item in call)


def install_fake_configurator(monkeypatch, *, result=True, exc=None):
    """Patch USBNICConfigurator and capture constructor inputs."""
    captured = {}

    class FakeConfigurator:
        def __init__(self, config, dry_run=False, preserve_wifi=True, show_dashboard=False):
            captured["config"] = config
            captured["dry_run"] = dry_run
            captured["preserve_wifi"] = preserve_wifi
            captured["show_dashboard"] = show_dashboard

        def configure(self):
            if exc:
                raise exc
            return result

    monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICConfigurator", FakeConfigurator)
    return captured


class TestParserAndDisplay:
    """Test parser defaults and config/profile display helpers."""

    def test_setup_logging_sets_expected_basic_config(self, monkeypatch):
        calls = []

        def fake_basic_config(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr("darwin_mgmt_nic.cli.logging.basicConfig", fake_basic_config)

        cli.setup_logging(verbose=True)
        cli.setup_logging(verbose=False)

        assert calls[0]["level"] == logging.DEBUG
        assert calls[1]["level"] == logging.INFO
        assert calls[0]["format"] == "[%(asctime)s] %(levelname)s: %(message)s"
        assert calls[0]["datefmt"] == "%Y-%m-%d %H:%M:%S"

    def test_create_parser_uses_settings_defaults(self):
        settings = Settings(
            device_ip="192.168.88.1",
            laptop_ip="192.168.88.100",
            netmask="255.255.0.0",
            mgmt_network="192.168.88.0/24",
            device_name="Lab Management Device",
            dry_run=True,
            preserve_wifi=False,
            show_dashboard=True,
        )

        parser = cli.create_parser(settings)
        args = parser.parse_args([])

        assert args.device_ip == "192.168.88.1"
        assert args.laptop_ip == "192.168.88.100"
        assert args.netmask == "255.255.0.0"
        assert args.mgmt_network == "192.168.88.0/24"
        assert args.device_name == "Lab Management Device"
        assert args.dry_run is True
        assert args.preserve_wifi is False
        assert args.show_dashboard is True

    def test_show_config_prints_sources_paths_settings_and_profiles(self, monkeypatch, tmp_path):
        existing = tmp_path / "config.toml"
        existing.write_text("[defaults]\n")
        missing = tmp_path / "missing.toml"
        settings = Settings(
            device_ip="192.168.88.1",
            laptop_ip="192.168.88.100",
            mgmt_network="192.168.88.0/24",
            default_profile="homelab",
            config_sources=[str(existing)],
            profiles={
                "homelab": NetworkProfile(
                    device_ip="192.168.88.1",
                    laptop_ip="192.168.88.100",
                    device_name="Lab Management Device",
                )
            },
        )
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.cli.get_config_paths", lambda: [existing, missing])
        FakeConsole.instances.clear()

        cli.show_config(settings)

        printed = rendered_console()
        assert "Configuration Sources" in printed
        assert str(existing) in printed
        assert str(missing) in printed
        assert "Current Settings" in printed
        assert "Available Profiles" in printed

    def test_list_profiles_reports_empty_state(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        FakeConsole.instances.clear()

        cli.list_profiles(Settings())

        printed = rendered_console()
        assert "No profiles configured" in printed
        assert "darwin-nic --init-config" in printed

    def test_list_profiles_prints_profile_details(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        FakeConsole.instances.clear()
        settings = Settings(
            default_profile="homelab",
            profiles={
                "homelab": NetworkProfile(
                    device_ip="192.168.88.1",
                    laptop_ip="192.168.88.100",
                    mgmt_network="192.168.88.0/24",
                    device_name="Lab Management Device",
                    description="USB OOB management path",
                )
            },
        )

        cli.list_profiles(settings)

        printed = rendered_console()
        assert "Available Profiles" in printed
        assert "homelab" in printed
        assert "Lab Management Device" in printed
        assert "192.168.88.1 -> 192.168.88.100" in printed
        assert "USB OOB management path" in printed


class TestMain:
    """Test CLI backend entrypoint behavior."""

    def test_main_init_config_created_and_existing(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.init_config", lambda: Path("/tmp/darwin-nic/config.toml"))
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--init-config"])
        FakeConsole.instances.clear()

        assert cli.main() == 0
        assert "Config file created: /tmp/darwin-nic/config.toml" in rendered_console()

        monkeypatch.setattr("darwin_mgmt_nic.cli.init_config", lambda: None)
        FakeConsole.instances.clear()

        assert cli.main() == 0
        assert "Config file already exists" in rendered_console()

    @pytest.mark.parametrize(
        ("argv", "patched_name"),
        [
            (["darwin-nic", "--show-config"], "show_config"),
            (["darwin-nic", "--list-profiles"], "list_profiles"),
        ],
    )
    def test_main_dispatches_config_management_commands(self, monkeypatch, argv, patched_name):
        calls = []

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr(f"darwin_mgmt_nic.cli.{patched_name}", lambda settings: calls.append(settings))
        monkeypatch.setattr(sys, "argv", argv)

        assert cli.main() == 0
        assert len(calls) == 1

    def test_main_returns_unsupported_platform_code_before_configuring(self, monkeypatch):
        captured = install_fake_configurator(monkeypatch)
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: False)
        monkeypatch.setattr(sys, "argv", ["darwin-nic"])

        assert cli.main() == 3
        assert captured == {}

    def test_main_configures_with_profile_values(self, monkeypatch):
        settings = Settings(
            profiles={
                "homelab": NetworkProfile(
                    device_ip="192.168.88.1",
                    laptop_ip="192.168.88.100",
                    netmask="255.255.255.0",
                    mgmt_network="192.168.88.0/24",
                    device_name="Lab Management Device",
                )
            }
        )
        load_calls = []
        captured = install_fake_configurator(monkeypatch, result=True)
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr(
            "darwin_mgmt_nic.cli.load_settings",
            lambda profile=None: load_calls.append(profile) or settings,
        )
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--profile", "homelab", "--dry-run", "--show-dashboard"])
        FakeConsole.instances.clear()

        assert cli.main() == 0
        assert load_calls == ["homelab"]
        assert captured["config"].device_ip == "192.168.88.1"
        assert captured["config"].laptop_ip == "192.168.88.100"
        assert captured["config"].mgmt_network == "192.168.88.0/24"
        assert captured["config"].device_name == "Lab Management Device"
        assert captured["dry_run"] is True
        assert captured["preserve_wifi"] is True
        assert captured["show_dashboard"] is True
        assert "Using profile: homelab" in rendered_console()

    def test_main_warns_for_missing_profile_and_uses_defaults(self, monkeypatch):
        settings = Settings(
            device_ip="192.0.2.1",
            laptop_ip="192.0.2.100",
            profiles={
                "known": NetworkProfile(
                    device_ip="198.51.100.1",
                    laptop_ip="198.51.100.100",
                )
            },
        )
        captured = install_fake_configurator(monkeypatch, result=True)
        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: settings)
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--profile", "missing"])
        FakeConsole.instances.clear()

        assert cli.main() == 0
        assert captured["config"].device_ip == "192.0.2.1"
        assert captured["config"].laptop_ip == "192.0.2.100"
        printed = rendered_console()
        assert "Profile 'missing' not found" in printed
        assert "known" in printed

    @pytest.mark.parametrize(("configure_result", "exit_code"), [(True, 0), (False, 1)])
    def test_main_returns_configurator_result(self, monkeypatch, configure_result, exit_code):
        install_fake_configurator(monkeypatch, result=configure_result)
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(
            sys,
            "argv",
            ["darwin-nic", "--device-ip", "192.0.2.1", "--laptop-ip", "192.0.2.100"],
        )

        assert cli.main() == exit_code

    def test_main_returns_configuration_error_code_for_invalid_network_config(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--device-ip", "not-an-ip"])

        assert cli.main() == 2

    def test_main_handles_keyboard_interrupt(self, monkeypatch):
        install_fake_configurator(monkeypatch, exc=KeyboardInterrupt())
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(sys, "argv", ["darwin-nic"])

        assert cli.main() == 130

    def test_main_handles_unexpected_exception(self, monkeypatch):
        install_fake_configurator(monkeypatch, exc=RuntimeError("boom"))
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--verbose"])

        assert cli.main() == 1

    def test_main_dispatches_vpn_repair_mode(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.cli.load_settings", lambda profile=None: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.cli.USBNICDetectorFactory.is_supported", lambda: True)
        monkeypatch.setattr("darwin_mgmt_nic.cli.handle_vpn_repair", lambda: 9)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "--fix-vpn-issues"])

        assert cli.main() == 9


class TestVpnRepair:
    """Test VPN repair workflow with all host operations mocked."""

    def test_handle_vpn_repair_success(self, monkeypatch):
        calls = []

        class FakeServiceOrderManager:
            def backup_service_order(self):
                calls.append("backup")

            def set_wifi_priority(self):
                calls.append("set_wifi_priority")
                return True

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)
        monkeypatch.setattr("darwin_mgmt_nic.cli.subprocess.run", fake_run)
        monkeypatch.setattr("darwin_mgmt_nic.cli.time.sleep", lambda seconds: calls.append(["sleep", seconds]))
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 0
        assert calls[0:2] == ["backup", "set_wifi_priority"]
        assert ["sleep", 3] in calls
        assert ["nslookup", "google.com"] in calls
        assert ["ping", "-c", "1", "-t", "5", "8.8.8.8"] in calls
        assert "Network repair completed successfully" in rendered_console()

    def test_handle_vpn_repair_stops_when_wifi_priority_fails(self, monkeypatch):
        class FakeServiceOrderManager:
            def backup_service_order(self):
                pass

            def set_wifi_priority(self):
                return False

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 1
        assert "Failed to restore WiFi priority" in rendered_console()

    def test_handle_vpn_repair_reports_dns_update_failure(self, monkeypatch):
        class FakeServiceOrderManager:
            def backup_service_order(self):
                pass

            def set_wifi_priority(self):
                return True

        def fake_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)
        monkeypatch.setattr("darwin_mgmt_nic.cli.subprocess.run", fake_run)
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 1
        assert "Failed to fix DNS" in rendered_console()

    def test_handle_vpn_repair_reports_verification_failure(self, monkeypatch):
        class FakeServiceOrderManager:
            def backup_service_order(self):
                pass

            def set_wifi_priority(self):
                return True

        def fake_run(cmd, **kwargs):
            returncode = 1 if cmd[0] == "ping" else 0
            return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr="")

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)
        monkeypatch.setattr("darwin_mgmt_nic.cli.subprocess.run", fake_run)
        monkeypatch.setattr("darwin_mgmt_nic.cli.time.sleep", lambda seconds: None)
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 1
        printed = rendered_console()
        assert "Network verification failed" in printed
        assert "DNS: Working" in printed
        assert "Internet: Broken" in printed

    def test_handle_vpn_repair_reports_verification_timeout(self, monkeypatch):
        class FakeServiceOrderManager:
            def backup_service_order(self):
                pass

            def set_wifi_priority(self):
                return True

        def fake_run(cmd, **kwargs):
            if cmd[0] == "nslookup":
                raise subprocess.TimeoutExpired(cmd, 10)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)
        monkeypatch.setattr("darwin_mgmt_nic.cli.subprocess.run", fake_run)
        monkeypatch.setattr("darwin_mgmt_nic.cli.time.sleep", lambda seconds: None)
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 1
        assert "Network verification timed out" in rendered_console()

    def test_handle_vpn_repair_handles_keyboard_interrupt(self, monkeypatch):
        class InterruptingServiceOrderManager:
            def __init__(self):
                raise KeyboardInterrupt

        monkeypatch.setattr("darwin_mgmt_nic.cli.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", InterruptingServiceOrderManager)
        FakeConsole.instances.clear()

        assert cli.handle_vpn_repair() == 130
        assert "VPN repair cancelled by user" in rendered_console()
