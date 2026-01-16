"""
Tests for configuration models
"""

import pytest
from darwin_mgmt_nic.config import NetworkConfig, NetworkInterface, OSType


class TestNetworkConfig:
    """Test NetworkConfig dataclass"""

    def test_valid_config(self, sample_network_config):
        """Test creating valid network configuration"""
        assert sample_network_config.device_ip == "192.0.2.1"
        assert sample_network_config.laptop_ip == "192.0.2.100"
        assert sample_network_config.netmask == "255.255.255.0"
        assert sample_network_config.mgmt_network == "198.51.100.0/24"

    def test_invalid_device_ip(self):
        """Test invalid device IP raises ValueError"""
        with pytest.raises(ValueError, match="Invalid IP configuration"):
            NetworkConfig(
                device_ip="999.999.999.999",
                laptop_ip="192.0.2.100",
                netmask="255.255.255.0",
                mgmt_network="198.51.100.0/24",
                device_name="Test"
            )

    def test_invalid_laptop_ip(self):
        """Test invalid laptop IP raises ValueError"""
        with pytest.raises(ValueError, match="Invalid IP configuration"):
            NetworkConfig(
                device_ip="192.0.2.1",
                laptop_ip="not.an.ip.address",
                netmask="255.255.255.0",
                mgmt_network="198.51.100.0/24",
                device_name="Test"
            )

    def test_invalid_mgmt_network(self):
        """Test invalid management network raises ValueError"""
        with pytest.raises(ValueError, match="Invalid IP configuration"):
            NetworkConfig(
                device_ip="192.0.2.1",
                laptop_ip="192.0.2.100",
                netmask="255.255.255.0",
                mgmt_network="not.a.network/24",
                device_name="Test"
            )

    def test_get_mgmt_gateway(self, sample_network_config):
        """Test getting management network gateway"""
        gateway = sample_network_config.get_mgmt_gateway()
        assert gateway == "198.51.100.1"

    def test_get_mgmt_test_ip(self, sample_network_config):
        """Test getting management network test IP"""
        test_ip = sample_network_config.get_mgmt_test_ip()
        assert test_ip == "198.51.100.10"

    def test_config_is_frozen(self, sample_network_config):
        """Test that config is immutable (frozen)"""
        with pytest.raises(AttributeError):
            sample_network_config.device_ip = "10.0.0.1"


class TestNetworkInterface:
    """Test NetworkInterface dataclass"""

    def test_protected_interface(self, protected_interface):
        """Test protected interface properties"""
        assert protected_interface.name == "en0"
        assert protected_interface.is_protected
        assert not protected_interface.is_usb
        assert protected_interface.is_active

    def test_usb_interface_active(self, usb_interface_active):
        """Test active USB interface"""
        assert usb_interface_active.name == "en7"
        assert usb_interface_active.is_usb
        assert usb_interface_active.is_active
        assert not usb_interface_active.is_protected
        assert usb_interface_active.vendor == "Realtek"

    def test_usb_interface_inactive(self, usb_interface_inactive):
        """Test inactive USB interface"""
        assert usb_interface_inactive.name == "en9"
        assert usb_interface_inactive.is_usb
        assert not usb_interface_inactive.is_active
        assert usb_interface_inactive.vendor == "ASIX"

    def test_interface_str_representation(self, usb_interface_active):
        """Test string representation includes icons and info"""
        str_repr = str(usb_interface_active)
        assert "en7" in str_repr
        assert "USB 10/100/1000 LAN" in str_repr
        assert "[U]" in str_repr  # USB icon
        assert "[+]" in str_repr  # Active icon

    def test_protected_interface_str(self, protected_interface):
        """Test protected interface string includes lock icon"""
        str_repr = str(protected_interface)
        assert "[L]" in str_repr
        assert "en0" in str_repr

    def test_is_suitable_for_configuration(self, usb_interface_active, protected_interface):
        """Test suitability check for configuration"""
        assert usb_interface_active.is_suitable_for_configuration()
        assert not protected_interface.is_suitable_for_configuration()

    def test_inactive_usb_not_suitable(self, usb_interface_inactive):
        """Test inactive USB interface is not suitable"""
        assert not usb_interface_inactive.is_suitable_for_configuration()


class TestOSType:
    """Test OSType enum"""

    def test_os_types_exist(self):
        """Test all expected OS types are defined"""
        assert OSType.MACOS
        assert OSType.LINUX
        assert OSType.WINDOWS

    def test_os_type_values(self):
        """Test OS type values match platform.system() output"""
        assert OSType.MACOS.value == "darwin"
        assert OSType.LINUX.value == "linux"
        assert OSType.WINDOWS.value == "win32"
