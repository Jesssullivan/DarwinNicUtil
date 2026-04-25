"""
Tests for app-level operator diagnostics.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from darwin_mgmt_nic.app import (
    cmd_configure,
    cmd_dashboard,
    cmd_init_config,
    cmd_list_profiles,
    cmd_restore,
    cmd_show_config,
    cmd_status,
    cmd_test,
    main,
    print_bastion_diagnostics,
)
from darwin_mgmt_nic.macos import BastionDiagnostics
from darwin_mgmt_nic.settings import NetworkProfile, Settings


class FakeConsole:
    """Small console test double that records printed objects."""

    instances = []

    def __init__(self):
        self.printed = []
        self.__class__.instances.append(self)

    def print(self, *objects, **kwargs):
        self.printed.append(objects)


class TestPrintBastionDiagnostics:
    """Test status-surface bastion diagnostics."""

    def test_prints_high_signal_bastion_warnings(self):
        """Operator status should surface the same NECP/Tailscale hints we saw on pzm."""
        console = MagicMock()
        detector = MagicMock()
        detector.get_bastion_diagnostics.return_value = BastionDiagnostics(
            usb_interfaces_with_ip=["en9"],
            nwi_interfaces=["en1", "en0"],
            missing_from_nwi=["en9"],
            tailscale_extension_active=True,
            recent_necp_drop=True,
        )

        print_bastion_diagnostics(console, detector)

        panel = console.print.call_args_list[0].args[0]
        assert panel.title == "Bastion OOB Diagnostics"

        rendered = "\n".join(str(call.args[0]) for call in console.print.call_args_list[1:])
        assert "Tailscale" in rendered
        assert "NECP" in rendered

    def test_skips_output_without_usb_bastion_state(self):
        """No USB bastion state means no extra status noise."""
        console = MagicMock()
        detector = MagicMock()
        detector.get_bastion_diagnostics.return_value = BastionDiagnostics(
            usb_interfaces_with_ip=[],
            nwi_interfaces=["en1", "en0"],
            missing_from_nwi=[],
            tailscale_extension_active=False,
            recent_necp_drop=False,
        )

        print_bastion_diagnostics(console, detector)

        console.print.assert_not_called()


class TestCmdConfigure:
    """Test app-level configure dispatch into the CLI implementation."""

    def test_profile_configure_builds_cli_argv_with_preserve_wifi(self, monkeypatch):
        """Profile mode should pass resolved OOB values to the CLI surface."""
        called = {}

        def fake_cli_main():
            called["argv"] = list(sys.argv)
            return 7

        monkeypatch.setattr("darwin_mgmt_nic.cli.main", fake_cli_main)

        settings = Settings(
            profiles={
                "homelab": NetworkProfile(
                    device_ip="192.168.88.1",
                    laptop_ip="192.168.88.100",
                    mgmt_network="192.168.88.0/24",
                    device_name="Lab Management Device",
                )
            }
        )
        args = argparse.Namespace(
            profile="homelab",
            device_ip="__PROFILE__",
            laptop_ip="__PROFILE__",
            netmask="255.255.255.0",
            mgmt_network="198.51.100.0/24",
            device_name="Network Device",
            dry_run=True,
            preserve_wifi=True,
            show_dashboard=False,
        )

        assert cmd_configure(args, settings) == 7

        assert called["argv"] == [
            "darwin-mgmt-nic",
            "--device-ip",
            "192.168.88.1",
            "--laptop-ip",
            "192.168.88.100",
            "--netmask",
            "255.255.255.0",
            "--mgmt-network",
            "192.168.88.0/24",
            "--device-name",
            "Lab Management Device",
            "--dry-run",
            "--preserve-wifi",
        ]

    def test_configure_requires_ips_without_profile(self, capsys):
        """CLI mode should fail closed instead of invoking configure with placeholders."""
        args = argparse.Namespace(
            profile=None,
            device_ip="__PROFILE__",
            laptop_ip="__PROFILE__",
            netmask="255.255.255.0",
            mgmt_network="198.51.100.0/24",
            device_name="Network Device",
            dry_run=False,
            preserve_wifi=False,
            show_dashboard=False,
        )

        assert cmd_configure(args, Settings()) == 1
        assert "--device-ip and --laptop-ip are required" in capsys.readouterr().out


class TestStatusAndDashboardCommands:
    """Test non-mutating dashboard/status command wiring."""

    def test_status_builds_dashboard_and_prints_bastion_diagnostics(self, monkeypatch):
        calls = {}

        class FakeDashboard:
            def __init__(self, wifi_monitor, service_manager):
                calls["dashboard_args"] = (wifi_monitor, service_manager)
                calls["display_status"] = 0
                calls["connectivity"] = 0

            def display_status(self):
                calls["display_status"] += 1

            def show_connectivity_metrics(self):
                calls["connectivity"] += 1

        monkeypatch.setattr("rich.console.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.WiFiMonitor", lambda: "wifi-monitor")
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", lambda: "service-manager")
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.NetworkDashboard", FakeDashboard)
        monkeypatch.setattr(
            "darwin_mgmt_nic.app.print_bastion_diagnostics", lambda console: calls.setdefault("bastion", console)
        )
        FakeConsole.instances.clear()

        cmd_status(argparse.Namespace())

        assert calls["dashboard_args"] == ("wifi-monitor", "service-manager")
        assert calls["display_status"] == 1
        assert calls["connectivity"] == 1
        assert calls["bastion"] is FakeConsole.instances[0]
        assert FakeConsole.instances[0].printed

    def test_dashboard_defaults_to_static_status(self, monkeypatch):
        calls = {}

        class FakeDashboard:
            def __init__(self, wifi_monitor, service_manager):
                calls["dashboard_args"] = (wifi_monitor, service_manager)

            def display_status(self):
                calls["display_status"] = calls.get("display_status", 0) + 1

            def monitor_interference(self, duration):
                calls["monitor_interference"] = duration

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.WiFiMonitor", lambda: "wifi-monitor")
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", lambda: "service-manager")
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.NetworkDashboard", FakeDashboard)

        cmd_dashboard(argparse.Namespace(interference=False, duration=None))

        assert calls["dashboard_args"] == ("wifi-monitor", "service-manager")
        assert calls["display_status"] == 1
        assert "monitor_interference" not in calls

    def test_dashboard_interference_uses_default_duration(self, monkeypatch):
        calls = {}

        class FakeDashboard:
            def __init__(self, wifi_monitor, service_manager):
                pass

            def display_status(self):
                calls["display_status"] = True

            def monitor_interference(self, duration):
                calls["monitor_interference"] = duration

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.WiFiMonitor", lambda: object())
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", lambda: object())
        monkeypatch.setattr("darwin_mgmt_nic.network_manager.NetworkDashboard", FakeDashboard)

        cmd_dashboard(argparse.Namespace(interference=True, duration=None))

        assert calls["monitor_interference"] == 30
        assert "display_status" not in calls


class TestUtilityCommands:
    """Test app-level utility subcommands without touching host state."""

    def test_cmd_test_runs_expected_interface_and_ping_checks(self, monkeypatch):
        commands = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[0] == "ifconfig":
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
            if cmd[-1] == "192.0.2.1":
                return subprocess.CompletedProcess(cmd, 0, stdout="64 bytes time=12.3 ms", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="timeout")

        monkeypatch.setattr("rich.console.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.app.subprocess.run", fake_run)
        FakeConsole.instances.clear()

        cmd_test(argparse.Namespace())

        assert commands == [
            ["ifconfig", "en0"],
            ["ifconfig", "en1"],
            ["ifconfig", "en11"],
            ["ping", "-c", "1", "-W", "2", "192.0.2.1"],
            ["ping", "-c", "1", "-W", "2", "192.168.1.1"],
            ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
        ]
        assert len(FakeConsole.instances[0].printed) == 1

    def test_cmd_test_records_errors_without_raising(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise OSError("command unavailable")

        monkeypatch.setattr("rich.console.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.app.subprocess.run", fake_run)
        FakeConsole.instances.clear()

        cmd_test(argparse.Namespace())

        assert len(FakeConsole.instances[0].printed) == 1

    @pytest.mark.parametrize(
        ("restore_result", "expected"),
        [
            (True, "[OK] Service order restored"),
            (False, "[FAIL] Failed to restore service order"),
        ],
    )
    def test_restore_reports_service_order_result(self, monkeypatch, capsys, restore_result, expected):
        class FakeServiceOrderManager:
            def restore_service_order(self):
                return restore_result

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.ServiceOrderManager", FakeServiceOrderManager)

        cmd_restore(argparse.Namespace())

        output = capsys.readouterr().out
        assert "[*] Restoring network configuration..." in output
        assert expected in output
        assert "[OK] Configuration restore complete" in output

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

        monkeypatch.setattr("rich.console.Console", FakeConsole)
        monkeypatch.setattr("darwin_mgmt_nic.app.get_config_paths", lambda: [existing, missing])
        FakeConsole.instances.clear()

        cmd_show_config(settings)

        printed = "\n".join(str(item) for call in FakeConsole.instances[0].printed for item in call)
        assert "Configuration Sources" in printed
        assert str(existing) in printed
        assert str(missing) in printed
        assert "Current Settings" in printed
        assert "Available Profiles" in printed

    def test_init_config_reports_created_and_existing_config(self, monkeypatch, capsys):
        monkeypatch.setattr("darwin_mgmt_nic.app.init_config", lambda: Path("/tmp/darwin-nic/config.toml"))

        cmd_init_config()

        assert "Config file created: /tmp/darwin-nic/config.toml" in capsys.readouterr().out

        monkeypatch.setattr("darwin_mgmt_nic.app.init_config", lambda: None)

        cmd_init_config()

        assert "Config file already exists" in capsys.readouterr().out

    def test_list_profiles_reports_empty_state(self, monkeypatch):
        monkeypatch.setattr("rich.console.Console", FakeConsole)
        FakeConsole.instances.clear()

        cmd_list_profiles(Settings())

        printed = "\n".join(str(item) for call in FakeConsole.instances[0].printed for item in call)
        assert "No profiles configured" in printed
        assert "darwin-nic init-config" in printed

    def test_list_profiles_prints_profile_details(self, monkeypatch):
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
        monkeypatch.setattr("rich.console.Console", FakeConsole)
        FakeConsole.instances.clear()

        cmd_list_profiles(settings)

        printed = "\n".join(str(item) for call in FakeConsole.instances[0].printed for item in call)
        assert "Available Profiles" in printed
        assert "homelab" in printed
        assert "Lab Management Device" in printed
        assert "192.168.88.1 -> 192.168.88.100" in printed
        assert "USB OOB management path" in printed


class TestMainDispatch:
    """Test installed console-script dispatcher behavior."""

    def test_no_command_prints_help_and_returns_error(self, monkeypatch, capsys):
        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr(sys, "argv", ["darwin-nic"])

        assert main() == 1
        assert "Available commands" in capsys.readouterr().out

    @pytest.mark.parametrize(
        ("argv", "patched_name"),
        [
            (["darwin-nic", "setup"], "cmd_setup"),
            (["darwin-nic", "status"], "cmd_status"),
            (["darwin-nic", "test"], "cmd_test"),
            (["darwin-nic", "restore"], "cmd_restore"),
            (["darwin-nic", "config"], "cmd_show_config"),
            (["darwin-nic", "init-config"], "cmd_init_config"),
            (["darwin-nic", "profiles"], "cmd_list_profiles"),
            (["darwin-nic", "dashboard", "--interference", "--duration", "5"], "cmd_dashboard"),
        ],
    )
    def test_main_dispatches_subcommands(self, monkeypatch, argv, patched_name):
        calls = []

        def fake_command(*args):
            calls.append((patched_name, args))

        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr(f"darwin_mgmt_nic.app.{patched_name}", fake_command)
        monkeypatch.setattr(sys, "argv", argv)

        assert main() == 0
        assert calls

    def test_main_returns_configure_error_code(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.app.cmd_configure", lambda args, settings: 7)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "configure"])

        assert main() == 7

    def test_main_returns_success_when_configure_returns_none(self, monkeypatch):
        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.app.cmd_configure", lambda args, settings: None)
        monkeypatch.setattr(
            sys,
            "argv",
            ["darwin-nic", "configure", "--device-ip", "192.0.2.1", "--laptop-ip", "192.0.2.100"],
        )

        assert main() == 0

    def test_main_handles_keyboard_interrupt(self, monkeypatch, capsys):
        def raise_keyboard_interrupt(args):
            raise KeyboardInterrupt

        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.app.cmd_status", raise_keyboard_interrupt)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "status"])

        assert main() == 1
        assert "Operation cancelled by user" in capsys.readouterr().out

    def test_main_handles_unexpected_exception(self, monkeypatch, capsys):
        def raise_runtime_error(args):
            raise RuntimeError("boom")

        monkeypatch.setattr("darwin_mgmt_nic.app.load_settings", lambda: Settings())
        monkeypatch.setattr("darwin_mgmt_nic.app.cmd_status", raise_runtime_error)
        monkeypatch.setattr(sys, "argv", ["darwin-nic", "status"])

        assert main() == 1
        assert "[FAIL] Error: boom" in capsys.readouterr().out
