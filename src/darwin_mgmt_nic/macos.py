"""
macOS-specific USB NIC detection and configuration
"""

import subprocess
import re
import logging
import os
import sys
from typing import Optional, Sequence
from rich.console import Console
from rich.prompt import Prompt

from .detectors import USBNICDetector
from .config import NetworkInterface, InterfaceName, IPAddress

logger = logging.getLogger(__name__)
console = Console()


def run_sudo_command(cmd: Sequence[str], timeout: int = 30, check: bool = True) -> subprocess.CompletedProcess:
    """Run sudo command with proper password handling"""
    # Check if we're already root
    if os.geteuid() == 0:
        # Already root, run command directly
        return subprocess.run(cmd, timeout=timeout, check=check, capture_output=True, text=True)

    # For interactive use, we need to let sudo handle its own password prompt
    # The key is to NOT capture stdout/stderr when sudo needs password
    full_cmd = ["sudo"] + list(cmd)

    try:
        # First try without capturing to allow sudo password prompt
        result = subprocess.run(full_cmd, timeout=timeout, check=False, capture_output=False, text=False)

        if check and result.returncode != 0:
            # If it failed, run again with capture to get error details
            error_result = subprocess.run(full_cmd, timeout=timeout, check=False, capture_output=True, text=True)
            raise subprocess.CalledProcessError(result.returncode, full_cmd, error_result.stdout, error_result.stderr)

        # Return a mock CompletedProcess for consistency
        return subprocess.CompletedProcess(args=full_cmd, returncode=result.returncode, stdout="", stderr="")

    except KeyboardInterrupt:
        console.print("\n[yellow][!] Command cancelled by user[/yellow]")
        raise
    except subprocess.TimeoutExpired:
        console.print(f"[red][FAIL] Command timed out after {timeout} seconds[/red]")
        raise


def run_sudo_command_tui_safe(
    cmd: Sequence[str],
    timeout: int = 30,
    check: bool = True,
    tui_active: bool = False
) -> subprocess.CompletedProcess:
    """
    Run sudo command with TUI state management.

    When tui_active=True, this function ensures sudo commands don't
    corrupt Rich TUI displays. It assumes sudo credentials are already
    cached (via 'sudo -v'), so no password prompt should occur.

    Args:
        cmd: Command to run (without 'sudo' prefix)
        timeout: Command timeout in seconds
        check: Raise exception on non-zero exit
        tui_active: Whether Rich TUI is currently active

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
        subprocess.TimeoutExpired: If command times out
    """
    if tui_active:
        # If TUI is active and sudo prompts for password, it will corrupt the display
        # We assume sudo -v has been run before TUI started, so this should work
        # Use non-interactive mode to fail immediately if auth is needed
        full_cmd = ["sudo", "-n"] + list(cmd)
    else:
        full_cmd = ["sudo"] + list(cmd)

    try:
        # Run with output capture for TUI mode (prevents terminal corruption)
        result = subprocess.run(
            full_cmd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True
        )

        if check and result.returncode != 0:
            # Check if failure was due to sudo auth timeout
            if tui_active and "a password is required" in result.stderr.lower():
                raise RuntimeError(
                    "Sudo authentication expired during TUI operation. "
                    "This is a bug - sudo should have been pre-authenticated."
                )
            raise subprocess.CalledProcessError(
                result.returncode,
                full_cmd,
                result.stdout,
                result.stderr
            )

        return result

    except KeyboardInterrupt:
        if tui_active:
            # In TUI mode, let the caller handle the interruption
            raise
        else:
            console.print("\n[yellow][!] Command cancelled by user[/yellow]")
            raise
    except subprocess.TimeoutExpired:
        if not tui_active:
            console.print(f"[red][FAIL] Command timed out after {timeout} seconds[/red]")
        raise


class MacOSUSBNICDetector(USBNICDetector):
    """
    macOS-specific USB NIC detection using networksetup and ifconfig.

    Detection Strategy:
    1. Use networksetup -listallhardwareports for hardware enumeration
    2. Cross-reference with ifconfig for interface status
    3. Apply strict USB identification heuristics
    4. Mark protected interfaces (en0, en1, etc.)
    """

    # USB NIC vendor identifiers (comprehensive list)
    USB_VENDOR_KEYWORDS: frozenset[str] = frozenset({
        "usb ethernet", "usb 10/100", "usb gigabit", "usb 2.5g", "usb 5g",
        "realtek", "asix", "apple usb", "belkin usb", "startech",
        "plugable", "cable matters", "anker usb", "tp-link usb",
        "ugreen", "j5create", "sabrent", "iogear", "trendnet usb",
        "monoprice", "insignia usb", "dell usb", "lenovo usb",
    })

    # Minimum interface number to consider as USB (heuristic)
    MIN_USB_INTERFACE_NUMBER = 5

    def __init__(self, tui_mode: bool = False):
        """
        Initialize detector.

        Args:
            tui_mode: If True, use TUI-safe sudo commands (assumes pre-auth)
        """
        self.tui_mode = tui_mode

    def detect_interfaces(self) -> Sequence[NetworkInterface]:
        """
        Detect all network interfaces using networksetup.

        Returns:
            List of NetworkInterface objects, sorted by suitability
        """
        interfaces: list[NetworkInterface] = []

        try:
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )

            current_port: Optional[str] = None
            current_device: Optional[InterfaceName] = None

            for line in result.stdout.splitlines():
                if line.startswith("Hardware Port:"):
                    current_port = line.replace("Hardware Port:", "").strip()
                elif line.startswith("Device:"):
                    current_device = line.replace("Device:", "").strip()

                    if current_port and current_device:
                        # Create interface object
                        interface = self._create_interface(current_port, current_device)
                        interfaces.append(interface)

                        current_port = None
                        current_device = None

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"networksetup detection failed: {e}")

        # Sort: USB + active first, protected last
        interfaces.sort(key=lambda iface: (
            not iface.is_usb,
            not iface.is_active,
            iface.is_protected,
            iface.name
        ))

        return interfaces

    def _create_interface(self, port_name: str, device_name: InterfaceName) -> NetworkInterface:
        """Create NetworkInterface object with all metadata"""
        is_protected = self.is_protected_interface(device_name)
        is_usb = self._is_usb_adapter(port_name, device_name)
        is_wifi = self._is_wifi_adapter(port_name, device_name)
        is_active = self.get_interface_status(device_name)
        current_ip = self._get_interface_ip(device_name)
        mac = self._get_mac_address(device_name)
        vendor = self._extract_vendor(port_name) if is_usb else None

        return NetworkInterface(
            name=device_name,
            hardware_port=port_name,
            is_usb=is_usb,
            is_wifi=is_wifi,
            is_active=is_active,
            is_protected=is_protected,
            current_ip=current_ip,
            mac_address=mac,
            vendor=vendor
        )

    def _is_usb_adapter(self, port_name: str, device_name: InterfaceName) -> bool:
        """
        Determine if interface is a USB adapter using strict heuristics.

        Safety:
        - ALWAYS returns False for protected interfaces
        - Requires explicit USB vendor keywords OR high interface number
        """
        # CRITICAL: Never classify protected interfaces as USB
        if self.is_protected_interface(device_name):
            return False

        port_lower = port_name.lower()

        # Primary: Strict USB vendor keyword matching
        for keyword in self.USB_VENDOR_KEYWORDS:
            if keyword in port_lower:
                logger.debug(f"USB adapter detected: {device_name} - keyword '{keyword}'")
                return True

        # Secondary: High interface numbers with ethernet indication
        match = re.match(r"en(\d+)", device_name)
        if match:
            num = int(match.group(1))
            if num >= self.MIN_USB_INTERFACE_NUMBER:
                # Require some ethernet indication for safety
                if "ethernet" in port_lower or "adapter" in port_lower or "usb" in port_lower:
                    logger.debug(f"USB adapter detected: {device_name} - interface number {num}")
                    return True

        return False

    def _is_wifi_adapter(self, port_name: str, device_name: InterfaceName) -> bool:
        """Determine if interface is a WiFi adapter"""
        port_lower = port_name.lower()
        
        # Check for WiFi keywords in port name
        wifi_keywords = ["wi-fi", "wifi", "airport", "wireless", "802.11"]
        for keyword in wifi_keywords:
            if keyword in port_lower:
                return True
        
        # Check common WiFi interface names
        if device_name in ["en0", "en1"]:  # Common WiFi interfaces on Mac
            return "wi-fi" in port_lower.lower()
        
        return False

    def _extract_vendor(self, port_name: str) -> Optional[str]:
        """Extract vendor name from hardware port string"""
        port_lower = port_name.lower()

        # Map keywords to vendor names
        vendor_map = {
            "realtek": "Realtek",
            "asix": "ASIX",
            "apple": "Apple",
            "belkin": "Belkin",
            "startech": "StarTech",
            "plugable": "Plugable",
            "cable matters": "Cable Matters",
            "anker": "Anker",
            "ugreen": "UGREEN",
            "j5create": "j5create",
        }

        for keyword, vendor in vendor_map.items():
            if keyword in port_lower:
                return vendor

        return None

    def _get_interface_ip(self, interface: InterfaceName) -> Optional[IPAddress]:
        """Get current IPv4 address of interface"""
        try:
            result = subprocess.run(
                ["ifconfig", interface],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            for line in result.stdout.splitlines():
                # Look for "inet <ip>" (not inet6)
                if line.strip().startswith("inet ") and "inet6" not in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return None

    def _get_mac_address(self, interface: InterfaceName) -> Optional[str]:
        """Get MAC address of interface"""
        try:
            result = subprocess.run(
                ["ifconfig", interface],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            for line in result.stdout.splitlines():
                if "ether" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        return None

    def get_interface_status(self, interface: InterfaceName) -> bool:
        """Check if interface has active carrier/link"""
        try:
            result = subprocess.run(
                ["ifconfig", interface],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            for line in result.stdout.splitlines():
                if "status:" in line.lower():
                    # Check for exact "active" status, not "inactive"
                    return "status: active" in line.lower()

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

        return False

    def cleanup_conflicting_ips(self, target_ip: IPAddress, exclude_interface: InterfaceName) -> None:
        """
        Remove the target IP from any interface except the one we're configuring.

        This prevents routing conflicts when the same IP is assigned to multiple interfaces.
        """
        interfaces = self.detect_interfaces()

        for iface in interfaces:
            if iface.name == exclude_interface:
                continue

            if iface.current_ip == target_ip:
                logger.info(f"[*] Removing conflicting IP {target_ip} from {iface.name}")
                try:
                    run_sudo_command_tui_safe(
                        ["ifconfig", iface.name, target_ip, "-alias"],
                        check=False,
                        timeout=10,
                        tui_active=self.tui_mode
                    )
                except Exception as e:
                    logger.warning(f"Failed to remove IP from {iface.name}: {e}")

    def configure_interface(
        self,
        interface: InterfaceName,
        ip: IPAddress,
        netmask: str
    ) -> bool:
        """Configure IP address on interface using ifconfig"""
        # Validate interface is safe to configure
        self.validate_interface_for_config(interface)

        # Clean up conflicting IPs from other interfaces first
        self.cleanup_conflicting_ips(ip, interface)

        try:
            # Remove existing IP if present
            existing_ip = self._get_interface_ip(interface)
            if existing_ip:
                logger.info(f"Removing existing IP {existing_ip} from {interface}")
                run_sudo_command_tui_safe(
                    ["ifconfig", interface, existing_ip, "-alias"],
                    check=False,
                    timeout=30,
                    tui_active=self.tui_mode
                )

            # Configure new IP
            logger.info(f"Configuring {interface}: {ip}/{netmask}")
            run_sudo_command_tui_safe(
                ["ifconfig", interface, ip, "netmask", netmask, "up"],
                timeout=30,
                tui_active=self.tui_mode
            )

            # Verify configuration
            configured_ip = self._get_interface_ip(interface)
            if configured_ip == ip:
                logger.info(f"[OK] {interface} configured successfully with {ip}")
                return True
            else:
                logger.error(f"[FAIL] IP verification failed for {interface}")
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"[FAIL] Failed to configure {interface}: {e}")
            return False

    def add_static_route(self, network: str, gateway: IPAddress) -> bool:
        """Add static route using route command"""
        try:
            # Check if route already exists
            result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )

            if network in result.stdout and gateway in result.stdout:
                logger.info(f"Route to {network} via {gateway} already exists")
                return True

            # Add route
            logger.info(f"Adding static route: {network} via {gateway}")
            run_sudo_command_tui_safe(
                ["route", "add", "-net", network, gateway],
                timeout=30,
                tui_active=self.tui_mode
            )

            logger.info(f"[OK] Static route added: {network} via {gateway}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"[FAIL] Failed to add route: {e}")
            return False

    def test_connectivity(
        self,
        target_ip: IPAddress,
        count: int = 3,
        timeout: int = 2
    ) -> bool:
        """Test ICMP connectivity to target"""
        try:
            logger.info(f"Testing connectivity to {target_ip}...")
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), target_ip],
                capture_output=True,
                text=True,
                timeout=count * timeout + 5
            )

            if result.returncode == 0:
                logger.info(f"[OK] {target_ip} reachable")
                return True
            else:
                logger.warning(f"[--] {target_ip} NOT reachable")
                return False

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            logger.error(f"[FAIL] Connectivity test failed: {e}")
            return False
