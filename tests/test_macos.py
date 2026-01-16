"""
Tests for macOS-specific implementation
"""

import pytest
from unittest.mock import MagicMock, patch
from darwin_mgmt_nic.macos import MacOSUSBNICDetector


class TestMacOSUSBNICDetector:
    """Test macOS USB NIC detection"""

    def test_is_usb_adapter_with_keyword(self):
        """Test USB detection with vendor keyword"""
        detector = MacOSUSBNICDetector()
        assert detector._is_usb_adapter("USB 10/100/1000 LAN", "en7")
        assert detector._is_usb_adapter("Realtek USB Ethernet", "en9")
        assert detector._is_usb_adapter("ASIX USB Gigabit", "en11")

    def test_is_usb_adapter_protected_interface(self):
        """Test protected interfaces never classified as USB"""
        detector = MacOSUSBNICDetector()
        assert not detector._is_usb_adapter("USB Ethernet", "en0")
        assert not detector._is_usb_adapter("USB Ethernet", "en1")

    def test_is_usb_adapter_high_interface_number(self):
        """Test high interface number heuristic"""
        detector = MacOSUSBNICDetector()
        # High number + ethernet keyword = USB
        assert detector._is_usb_adapter("Ethernet Adapter", "en7")
        assert detector._is_usb_adapter("Network Adapter", "en9")

        # High number without ethernet keyword = not USB (safety)
        assert not detector._is_usb_adapter("Unknown Device", "en7")

    def test_is_usb_adapter_low_interface_number(self):
        """Test low interface numbers not classified as USB"""
        detector = MacOSUSBNICDetector()
        # Even with ethernet keyword, en0/en1 are protected
        assert not detector._is_usb_adapter("Ethernet", "en0")
        assert not detector._is_usb_adapter("Ethernet", "en1")

    def test_extract_vendor_realtek(self):
        """Test extracting Realtek vendor"""
        detector = MacOSUSBNICDetector()
        vendor = detector._extract_vendor("Realtek USB Ethernet")
        assert vendor == "Realtek"

    def test_extract_vendor_asix(self):
        """Test extracting ASIX vendor"""
        detector = MacOSUSBNICDetector()
        vendor = detector._extract_vendor("ASIX AX88179 USB 3.0 Gigabit")
        assert vendor == "ASIX"

    def test_extract_vendor_no_match(self):
        """Test no vendor extracted when no keywords match"""
        detector = MacOSUSBNICDetector()
        vendor = detector._extract_vendor("Unknown Network Device")
        assert vendor is None

    @patch('subprocess.run')
    def test_get_interface_ip(self, mock_run):
        """Test getting interface IP address"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="inet 192.0.2.100 netmask 0xffffff00"
        )

        detector = MacOSUSBNICDetector()
        ip = detector._get_interface_ip("en7")
        assert ip == "192.0.2.100"

    @patch('subprocess.run')
    def test_get_interface_ip_no_ip(self, mock_run):
        """Test interface with no IP"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ether 11:22:33:44:55:66\nstatus: active"
        )

        detector = MacOSUSBNICDetector()
        ip = detector._get_interface_ip("en7")
        assert ip is None

    @patch('subprocess.run')
    def test_get_mac_address(self, mock_run):
        """Test getting MAC address"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ether 11:22:33:44:55:66"
        )

        detector = MacOSUSBNICDetector()
        mac = detector._get_mac_address("en7")
        assert mac == "11:22:33:44:55:66"

    @patch('subprocess.run')
    def test_get_interface_status_active(self, mock_run):
        """Test checking active interface"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="status: active"
        )

        detector = MacOSUSBNICDetector()
        assert detector.get_interface_status("en7")

    @patch('subprocess.run')
    def test_get_interface_status_inactive(self, mock_run):
        """Test checking inactive interface"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="status: inactive"
        )

        detector = MacOSUSBNICDetector()
        assert not detector.get_interface_status("en7")

    @patch('subprocess.run')
    def test_configure_interface_protected(self, mock_run):
        """Test configuring protected interface raises error"""
        detector = MacOSUSBNICDetector()

        with pytest.raises(ValueError, match="protected"):
            detector.configure_interface("en0", "192.0.2.100", "255.255.255.0")

    @patch('subprocess.run')
    def test_add_static_route_already_exists(self, mock_run):
        """Test adding route that already exists"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="198.51.100.0/24        192.0.2.1       UGSc"
        )

        detector = MacOSUSBNICDetector()
        result = detector.add_static_route("198.51.100.0/24", "192.0.2.1")
        assert result is True

    @patch('subprocess.run')
    def test_test_connectivity_success(self, mock_run):
        """Test successful connectivity test"""
        mock_run.return_value = MagicMock(returncode=0)

        detector = MacOSUSBNICDetector()
        assert detector.test_connectivity("192.0.2.1")

    @patch('subprocess.run')
    def test_test_connectivity_failure(self, mock_run):
        """Test failed connectivity test"""
        mock_run.return_value = MagicMock(returncode=1)

        detector = MacOSUSBNICDetector()
        assert not detector.test_connectivity("192.0.2.1")
