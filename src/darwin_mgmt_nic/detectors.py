"""
Abstract base classes and protocols for USB NIC detection
"""

from abc import ABC, abstractmethod
from typing import Protocol, Sequence
from collections.abc import Sequence as ABCSequence

from .config import NetworkInterface, InterfaceName, IPAddress


class NetworkDetector(Protocol):
    """
    Protocol for network interface detection (structural subtyping).

    This allows any class implementing these methods to be used
    without explicit inheritance.
    """

    def detect_interfaces(self) -> Sequence[NetworkInterface]: ...
    def get_interface_status(self, interface: InterfaceName) -> bool: ...
    def configure_interface(self, interface: InterfaceName, ip: IPAddress, netmask: str) -> bool: ...
    def add_static_route(self, network: str, gateway: IPAddress) -> bool: ...
    def test_connectivity(self, target_ip: IPAddress, count: int = 3) -> bool: ...


class USBNICDetector(ABC):
    """
    Abstract base class for platform-specific USB NIC detection.

    Subclasses must implement all abstract methods for their platform.
    Provides common protected interface list that applies across platforms.
    """

    # Protected interfaces that must NEVER be modified
    # This is a class attribute shared across all instances
    PROTECTED_INTERFACES: frozenset[InterfaceName] = frozenset({
        # macOS
        "en0",    # Primary WiFi
        "en1",    # Primary Ethernet
        "lo0",    # Loopback
        "awdl0",  # Apple Wireless Direct Link
        "llw0",   # Low Latency WLAN
        "utun0", "utun1", "utun2",  # VPN tunnels
        # Linux
        "eth0",   # Primary Ethernet
        "wlan0",  # Primary WiFi
        "lo",     # Loopback
        # Windows
        "Ethernet",
        "Wi-Fi",
    })

    @abstractmethod
    def detect_interfaces(self) -> Sequence[NetworkInterface]:
        """
        Detect all network interfaces and identify USB adapters.

        Returns:
            Sequence of NetworkInterface objects, sorted by suitability
            (USB first, active first, protected last)
        """
        ...

    @abstractmethod
    def get_interface_status(self, interface: InterfaceName) -> bool:
        """
        Check if interface has active carrier/link.

        Args:
            interface: Interface name to check

        Returns:
            True if interface has active link, False otherwise
        """
        ...

    @abstractmethod
    def configure_interface(
        self,
        interface: InterfaceName,
        ip: IPAddress,
        netmask: str
    ) -> bool:
        """
        Configure IP address on interface.

        Args:
            interface: Interface name to configure
            ip: IP address to assign
            netmask: Network mask (e.g., 255.255.255.0)

        Returns:
            True if configuration succeeded, False otherwise

        Raises:
            PermissionError: If insufficient privileges
            ValueError: If interface is protected
        """
        ...

    @abstractmethod
    def add_static_route(self, network: str, gateway: IPAddress) -> bool:
        """
        Add static route to routing table.

        Args:
            network: Network in CIDR notation (e.g., 198.51.100.0/24)
            gateway: Gateway IP address

        Returns:
            True if route added successfully, False otherwise
        """
        ...

    @abstractmethod
    def test_connectivity(
        self,
        target_ip: IPAddress,
        count: int = 3,
        timeout: int = 2
    ) -> bool:
        """
        Test ICMP connectivity to target.

        Args:
            target_ip: IP address to ping
            count: Number of ping packets
            timeout: Timeout per packet in seconds

        Returns:
            True if target is reachable, False otherwise
        """
        ...

    def is_protected_interface(self, interface: InterfaceName) -> bool:
        """
        Check if interface is in the protected list.

        Args:
            interface: Interface name to check

        Returns:
            True if interface is protected, False otherwise
        """
        return interface in self.PROTECTED_INTERFACES

    def validate_interface_for_config(self, interface: InterfaceName) -> None:
        """
        Validate that interface can be safely configured.

        Args:
            interface: Interface name to validate

        Raises:
            ValueError: If interface is protected or invalid
        """
        if self.is_protected_interface(interface):
            raise ValueError(
                f"Interface {interface} is protected and cannot be modified. "
                f"Protected interfaces: {', '.join(sorted(self.PROTECTED_INTERFACES))}"
            )
