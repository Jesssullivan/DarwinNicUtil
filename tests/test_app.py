"""
Tests for app-level operator diagnostics.
"""

import argparse
import sys
from unittest.mock import MagicMock

from darwin_mgmt_nic.app import cmd_configure, print_bastion_diagnostics
from darwin_mgmt_nic.macos import BastionDiagnostics
from darwin_mgmt_nic.settings import NetworkProfile, Settings


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

        monkeypatch.setattr("darwin_mgmt_nic.cli.main", fake_cli_main)

        settings = Settings(
            profiles={
                "homelab": NetworkProfile(
                    device_ip="192.168.88.1",
                    laptop_ip="192.168.88.100",
                    mgmt_network="192.168.88.0/24",
                    device_name="CRS309 Bastion",
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

        assert cmd_configure(args, settings) is None

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
            "CRS309 Bastion",
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
