"""
Tests for factory pattern
"""

import pytest
from unittest.mock import patch

from darwin_mgmt_nic.factory import USBNICDetectorFactory
from darwin_mgmt_nic.config import OSType
from darwin_mgmt_nic.macos import MacOSUSBNICDetector
from darwin_mgmt_nic.linux import LinuxUSBNICDetector


class TestUSBNICDetectorFactory:
    """Test factory pattern implementation"""

    @patch('platform.system')
    def test_create_macos_detector(self, mock_system):
        """Test factory creates macOS detector"""
        mock_system.return_value = "Darwin"
        detector = USBNICDetectorFactory.create()
        assert isinstance(detector, MacOSUSBNICDetector)

    @patch('platform.system')
    def test_create_linux_detector(self, mock_system):
        """Test factory creates Linux detector"""
        mock_system.return_value = "Linux"
        detector = USBNICDetectorFactory.create()
        assert isinstance(detector, LinuxUSBNICDetector)

    @patch('platform.system')
    def test_create_unsupported_os(self, mock_system):
        """Test factory raises error for unsupported OS"""
        mock_system.return_value = "FreeBSD"
        with pytest.raises(NotImplementedError, match="not supported"):
            USBNICDetectorFactory.create()

    def test_create_with_explicit_os_type(self):
        """Test factory with explicit OS type"""
        detector = USBNICDetectorFactory.create(OSType.MACOS)
        assert isinstance(detector, MacOSUSBNICDetector)

    def test_create_macos_explicit(self):
        """Test explicit macOS detector creation"""
        detector = USBNICDetectorFactory.create(OSType.MACOS)
        assert isinstance(detector, MacOSUSBNICDetector)

    def test_create_linux_explicit(self):
        """Test explicit Linux detector creation"""
        detector = USBNICDetectorFactory.create(OSType.LINUX)
        assert isinstance(detector, LinuxUSBNICDetector)

    def test_create_windows_not_implemented(self):
        """Test Windows raises NotImplementedError"""
        with pytest.raises(NotImplementedError, match="Windows support"):
            USBNICDetectorFactory.create(OSType.WINDOWS)

    @patch('platform.system')
    def test_is_supported_macos(self, mock_system):
        """Test macOS is supported"""
        mock_system.return_value = "Darwin"
        assert USBNICDetectorFactory.is_supported()

    @patch('platform.system')
    def test_is_supported_linux(self, mock_system):
        """Test Linux is marked as supported (even if experimental)"""
        mock_system.return_value = "Linux"
        # Currently only macOS is fully supported
        assert not USBNICDetectorFactory.is_supported()

    @patch('platform.system')
    def test_is_supported_unknown_os(self, mock_system):
        """Test unknown OS is not supported"""
        mock_system.return_value = "FreeBSD"
        assert not USBNICDetectorFactory.is_supported()

    def test_detect_os_macos(self):
        """Test OS detection for macOS"""
        with patch('platform.system', return_value="Darwin"):
            os_type = USBNICDetectorFactory._detect_os()
            assert os_type == OSType.MACOS

    def test_detect_os_linux(self):
        """Test OS detection for Linux"""
        with patch('platform.system', return_value="Linux"):
            os_type = USBNICDetectorFactory._detect_os()
            assert OSType.LINUX

    def test_detect_os_windows(self):
        """Test OS detection for Windows"""
        with patch('platform.system', return_value="Windows"):
            os_type = USBNICDetectorFactory._detect_os()
            assert os_type == OSType.WINDOWS
