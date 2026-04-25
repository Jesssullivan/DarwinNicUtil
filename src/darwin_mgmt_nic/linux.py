"""
Linux-specific USB NIC detection and configuration (placeholder)
"""

import logging
from collections.abc import Sequence
from pathlib import Path

from .config import InterfaceName, IPAddress, NetworkInterface
from .detectors import USBNICDetector

logger = logging.getLogger(__name__)


class LinuxUSBNICDetector(USBNICDetector):
    """
    Linux-specific USB NIC detection (future implementation).

    TODO: Implement using:
    - /sys/class/net/ for interface enumeration
    - /sys/class/net/<iface>/carrier for link status
    - ip command for configuration
    - iproute2 for routing
    """

    def detect_interfaces(self) -> Sequence[NetworkInterface]:
        """Detect interfaces using /sys/class/net"""
        logger.warning("Linux support not yet implemented")
        return []

    def get_interface_status(self, interface: InterfaceName) -> bool:
        """Check carrier status via sysfs"""
        carrier_file = Path(f"/sys/class/net/{interface}/carrier")
        if carrier_file.exists():
            try:
                return carrier_file.read_text().strip() == "1"
            except Exception:
                return False
        return False

    def configure_interface(self, interface: InterfaceName, ip: IPAddress, netmask: str) -> bool:
        """Configure using ip command"""
        logger.warning("Linux support not yet implemented")
        return False

    def add_static_route(self, network: str, gateway: IPAddress) -> bool:
        """Add route using ip route"""
        logger.warning("Linux support not yet implemented")
        return False

    def test_connectivity(self, target_ip: IPAddress, count: int = 3, timeout: int = 2) -> bool:
        """Test connectivity using ping"""
        import subprocess

        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), target_ip],
                capture_output=True,
                timeout=count * timeout + 5,
            )
            return result.returncode == 0
        except Exception:
            return False
