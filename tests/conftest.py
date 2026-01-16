"""
Pytest configuration and shared fixtures
"""

import pytest
from unittest.mock import MagicMock, patch

from darwin_mgmt_nic.config import NetworkConfig, NetworkInterface, OSType
from darwin_mgmt_nic.factory import USBNICDetectorFactory


@pytest.fixture
def sample_network_config() -> NetworkConfig:
    """Sample valid network configuration"""
    return NetworkConfig(
        device_ip="192.0.2.1",
        laptop_ip="192.0.2.100",
        netmask="255.255.255.0",
        mgmt_network="198.51.100.0/24",
        device_name="Test Device"
    )


@pytest.fixture
def alt_network_config() -> NetworkConfig:
    """Alternative network configuration for secondary device"""
    return NetworkConfig(
        device_ip="198.51.100.10",
        laptop_ip="198.51.100.100",
        netmask="255.255.255.0",
        mgmt_network="203.0.113.0/24",
        device_name="Secondary Test Device"
    )


@pytest.fixture
def protected_interface() -> NetworkInterface:
    """Sample protected interface (WiFi)"""
    return NetworkInterface(
        name="en0",
        hardware_port="Wi-Fi",
        is_usb=False,
        is_active=True,
        is_protected=True,
        current_ip="192.168.1.100",
        mac_address="aa:bb:cc:dd:ee:ff"
    )


@pytest.fixture
def usb_interface_active() -> NetworkInterface:
    """Sample active USB interface"""
    return NetworkInterface(
        name="en7",
        hardware_port="USB 10/100/1000 LAN",
        is_usb=True,
        is_active=True,
        is_protected=False,
        current_ip=None,
        mac_address="11:22:33:44:55:66",
        vendor="Realtek"
    )


@pytest.fixture
def usb_interface_inactive() -> NetworkInterface:
    """Sample inactive USB interface"""
    return NetworkInterface(
        name="en9",
        hardware_port="USB Ethernet Adapter",
        is_usb=True,
        is_active=False,
        is_protected=False,
        current_ip=None,
        mac_address="77:88:99:aa:bb:cc",
        vendor="ASIX"
    )


@pytest.fixture
def mock_macos_detector():
    """Mock macOS detector with pre-configured interfaces"""
    with patch('darwin_mgmt_nic.macos.MacOSUSBNICDetector') as mock:
        detector = MagicMock()
        detector.detect_interfaces.return_value = [
            NetworkInterface(
                name="en0",
                hardware_port="Wi-Fi",
                is_usb=False,
                is_active=True,
                is_protected=True,
                current_ip="192.168.1.100",
                mac_address="aa:bb:cc:dd:ee:ff"
            ),
            NetworkInterface(
                name="en7",
                hardware_port="USB 10/100/1000 LAN",
                is_usb=True,
                is_active=True,
                is_protected=False,
                current_ip=None,
                mac_address="11:22:33:44:55:66",
                vendor="Realtek"
            ),
        ]
        detector.get_interface_status.return_value = True
        detector.configure_interface.return_value = True
        detector.add_static_route.return_value = True
        detector.test_connectivity.return_value = True

        mock.return_value = detector
        yield detector


@pytest.fixture
def mock_subprocess_networksetup():
    """Mock subprocess for networksetup command"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""Hardware Port: Wi-Fi
Device: en0
Ethernet Address: aa:bb:cc:dd:ee:ff

Hardware Port: USB 10/100/1000 LAN
Device: en7
Ethernet Address: 11:22:33:44:55:66
""",
            stderr=""
        )
        yield mock_run


@pytest.fixture
def mock_subprocess_ifconfig():
    """Mock subprocess for ifconfig command"""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""en7: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
\tether 11:22:33:44:55:66
\tinet 192.0.2.100 netmask 0xffffff00 broadcast 192.0.2.255
\tstatus: active
""",
            stderr=""
        )
        yield mock_run
