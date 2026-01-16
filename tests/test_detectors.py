"""
Tests for base detector functionality
"""

import pytest
from darwin_mgmt_nic.detectors import USBNICDetector
from darwin_mgmt_nic.macos import MacOSUSBNICDetector


class TestUSBNICDetectorBase:
    """Test abstract base class functionality"""

    def test_protected_interfaces_defined(self):
        """Test protected interfaces are defined"""
        assert "en0" in USBNICDetector.PROTECTED_INTERFACES
        assert "en1" in USBNICDetector.PROTECTED_INTERFACES
        assert "eth0" in USBNICDetector.PROTECTED_INTERFACES
        assert "wlan0" in USBNICDetector.PROTECTED_INTERFACES
        assert "lo0" in USBNICDetector.PROTECTED_INTERFACES

    def test_protected_interfaces_frozen(self):
        """Test protected interfaces list is immutable"""
        assert isinstance(USBNICDetector.PROTECTED_INTERFACES, frozenset)

    def test_is_protected_interface(self):
        """Test protected interface checking"""
        detector = MacOSUSBNICDetector()
        assert detector.is_protected_interface("en0")
        assert detector.is_protected_interface("en1")
        assert not detector.is_protected_interface("en7")

    def test_validate_interface_for_config_success(self):
        """Test validation passes for non-protected interface"""
        detector = MacOSUSBNICDetector()
        # Should not raise
        detector.validate_interface_for_config("en7")

    def test_validate_interface_for_config_failure(self):
        """Test validation fails for protected interface"""
        detector = MacOSUSBNICDetector()
        with pytest.raises(ValueError, match="protected"):
            detector.validate_interface_for_config("en0")

    def test_validate_interface_includes_list(self):
        """Test validation error includes list of protected interfaces"""
        detector = MacOSUSBNICDetector()
        with pytest.raises(ValueError, match="en0") as exc_info:
            detector.validate_interface_for_config("en0")
        assert "Protected interfaces:" in str(exc_info.value)

    def test_multiple_platforms_share_protected_list(self):
        """Test protected interfaces are shared across platforms"""
        from darwin_mgmt_nic.linux import LinuxUSBNICDetector
        macos_detector = MacOSUSBNICDetector()
        linux_detector = LinuxUSBNICDetector()

        assert macos_detector.PROTECTED_INTERFACES == linux_detector.PROTECTED_INTERFACES
