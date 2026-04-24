"""
Tests for app-level operator diagnostics.
"""

from unittest.mock import MagicMock

from darwin_mgmt_nic.app import print_bastion_diagnostics
from darwin_mgmt_nic.macos import BastionDiagnostics


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
