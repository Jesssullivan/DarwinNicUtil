"""
Configuration models and type definitions
Python 3.14+ with modern type system
"""

import ipaddress
from dataclasses import dataclass
from typing import Optional
from enum import Enum

# Python 3.14 type aliases
type InterfaceName = str
type IPAddress = str
type MACAddress = str


class OSType(Enum):
    """Supported operating systems"""
    MACOS = "darwin"
    LINUX = "linux"
    WINDOWS = "win32"


@dataclass(frozen=True, slots=True)
class NetworkConfig:
    """
    Immutable network configuration for OOB management.

    Attributes:
        device_ip: Target device IP (e.g., 192.0.2.1)
        laptop_ip: Local controller IP (e.g., 192.0.2.100)
        netmask: Network mask (e.g., 255.255.255.0)
        mgmt_network: Management network CIDR (e.g., 198.51.100.0/24)
        device_name: Human-readable device identifier

    Raises:
        ValueError: If IP addresses or networks are invalid
    """
    device_ip: IPAddress
    laptop_ip: IPAddress
    netmask: str
    mgmt_network: str
    device_name: str

    def __post_init__(self) -> None:
        """Validate IP addresses and networks"""
        try:
            ipaddress.ip_address(self.device_ip)
            ipaddress.ip_address(self.laptop_ip)
            ipaddress.ip_network(self.mgmt_network, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid IP configuration: {e}") from e

    def get_mgmt_gateway(self) -> IPAddress:
        """Get the management network gateway (typically .1)"""
        network = ipaddress.ip_network(self.mgmt_network, strict=False)
        return str(network.network_address + 1)

    def get_mgmt_test_ip(self) -> IPAddress:
        """Get a test IP in the management network (typically .10)"""
        network = ipaddress.ip_network(self.mgmt_network, strict=False)
        return str(network.network_address + 10)


@dataclass(slots=True)
class NetworkInterface:
    """
    Represents a detected network interface.

    Attributes:
        name: Interface name (e.g., en0, eth0)
        hardware_port: Hardware port description from OS
        is_usb: Whether interface is a USB adapter
        is_wifi: Whether interface is a WiFi adapter
        is_active: Whether interface has active link
        is_protected: Whether interface is protected from modification
        current_ip: Current IPv4 address if assigned
        mac_address: MAC address
        vendor: USB vendor if detected
    """
    name: InterfaceName
    hardware_port: str
    is_usb: bool
    is_wifi: bool = False
    is_active: bool = False
    is_protected: bool = False
    current_ip: Optional[IPAddress] = None
    mac_address: Optional[MACAddress] = None
    vendor: Optional[str] = None

    def __str__(self) -> str:
        """Human-readable interface representation with status icons"""
        status = "[+]" if self.is_active else "[-]"
        protected = "[L]" if self.is_protected else "   "
        usb = "[U]" if self.is_usb else "   "
        ip = self.current_ip or "None"
        # Truncate hardware port for display
        hw_port = self.hardware_port[:40] if len(self.hardware_port) > 40 else self.hardware_port
        return f"{status}{protected}{usb} {self.name:8} - {hw_port:40} (IP: {ip})"

    def is_suitable_for_configuration(self) -> bool:
        """Check if interface is suitable for configuration"""
        return self.is_usb and not self.is_protected and self.is_active
