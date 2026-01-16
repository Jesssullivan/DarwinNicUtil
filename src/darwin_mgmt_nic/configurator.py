"""
Main configurator orchestrating USB NIC setup with safety checks
"""

import logging
import ipaddress
from typing import Optional

from rich.console import Console
from rich.prompt import Confirm

from .config import NetworkConfig, NetworkInterface
from .detectors import USBNICDetector
from .factory import USBNICDetectorFactory
from .network_manager import (
    ServiceOrderManager, WiFiMonitor, InterfaceScorer, RouteManager,
    InterferenceAssessor, NetworkDashboard
)

logger = logging.getLogger(__name__)
console = Console()


class USBNICConfigurator:
    """
    Main configurator for USB NIC setup with comprehensive safety checks.

    This class orchestrates the entire configuration workflow:
    1. Interface detection
    2. User confirmation
    3. IP configuration
    4. Route setup
    5. Connectivity testing

    Attributes:
        config: Network configuration to apply
        dry_run: If True, show what would be done without making changes
        detector: Platform-specific detector instance
    """

    def __init__(
        self,
        config: NetworkConfig,
        dry_run: bool = False,
        detector: Optional[USBNICDetector] = None,
        skip_confirmation: bool = False,
        preserve_wifi: bool = False,
        management_location: bool = False,
        show_dashboard: bool = False,
        forced_interface: Optional[str] = None
    ):
        """
        Initialize configurator.

        Args:
            config: Network configuration
            dry_run: Enable dry-run mode (no changes)
            detector: Optional detector (auto-created if not provided)
            skip_confirmation: Skip user confirmation prompt (for automated/guided flows)
        """
        self.config = config
        self.dry_run = dry_run
        self.skip_confirmation = skip_confirmation
        self.detector = detector or USBNICDetectorFactory.create()
        self.preserve_wifi = preserve_wifi
        self.management_location = management_location
        self.show_dashboard = show_dashboard
        self.forced_interface = forced_interface

        # Initialize network manager components
        self.service_order_manager = ServiceOrderManager()
        self.wifi_monitor = WiFiMonitor()
        self.interference_assessor = InterferenceAssessor()
        self.route_manager = RouteManager()

        self.interface_scorer = InterfaceScorer(self.wifi_monitor, self.interference_assessor)
        self.dashboard = NetworkDashboard(self.wifi_monitor, self.service_order_manager)

    def display_banner(self) -> None:
        """Display configuration banner with mode and settings"""
        mode = "[DRY-RUN MODE]" if self.dry_run else "[CONFIGURATION MODE]"
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║          USB Network Auto-Configuration (SAFE)                ║
║          {mode:^55}                     ║
║          Python 3.14 + Factory Pattern                        ║
╚═══════════════════════════════════════════════════════════════╝

Target Device: {self.config.device_name}
Device IP:     {self.config.device_ip}
Laptop IP:     {self.config.laptop_ip}
Netmask:       {self.config.netmask}
Mgmt Network:  {self.config.mgmt_network}
""")

    def find_best_usb_interface(self) -> Optional[NetworkInterface]:
        """
        Find best USB interface for configuration.

        Returns:
            Best USB interface, or None if none found

        Display Format:
            Shows all interfaces with legend explaining icons
        """
        logger.info("Detecting network interfaces...")

        interfaces = self.detector.detect_interfaces()

        # If forced_interface is set, use it directly
        if self.forced_interface:
            for iface in interfaces:
                if iface.name == self.forced_interface:
                    logger.info(f"[OK] Using forced interface: {iface.name}")
                    self._display_interfaces(interfaces)
                    return iface
            logger.error(f"[FAIL] Forced interface {self.forced_interface} not found!")
            return None

        if not interfaces:
            logger.error("[FAIL] No network interfaces found!")
            return None

        # Display all interfaces
        self._display_interfaces(interfaces)

        # Filter for non-protected USB interfaces
        usb_interfaces = [
            iface for iface in interfaces
            if iface.is_usb and not iface.is_protected
        ]

        if not usb_interfaces:
            logger.error("[FAIL] No USB network interfaces found!")
            logger.warning("[!] Ensure USB adapter is connected and has link lights")
            return None

        # Use interface scorer for enhanced selection if WiFi preservation is enabled
        if self.preserve_wifi:
            scored_interfaces = self.interface_scorer.rank_interfaces(interfaces)
            usb_scored = [score for score in scored_interfaces if score.interface_name in [iface.name for iface in usb_interfaces]]
            
            if usb_scored:
                best_name = usb_scored[0].interface_name
                best = next(iface for iface in usb_interfaces if iface.name == best_name)
                logger.info(f"[OK] Selected best USB interface by score: {best.name} (score: {usb_scored[0].score:.1f})")
                return best

        # Fallback to original logic
        active_usb = [iface for iface in usb_interfaces if iface.is_active]

        if active_usb:
            best = active_usb[0]
            logger.info(f"[OK] Selected active USB interface: {best.name}")
            return best

        # Use first USB interface if none active
        best = usb_interfaces[0]
        logger.warning(f"[!] No active USB interfaces, trying: {best.name}")
        return best

    def _display_interfaces(self, interfaces: list[NetworkInterface]) -> None:
        """Display detected interfaces in formatted table"""
        print("\n╔═══════════════════════════════════════════════════════════════╗")
        print("║                   Detected Interfaces                         ║")
        print("╠═══════════════════════════════════════════════════════════════╣")
        print("║ Legend: [+]=Active [-]=Inactive [L]=Protected [U]=USB         ║")
        print("╠═══════════════════════════════════════════════════════════════╣")

        for iface in interfaces:
            print(f"║ {str(iface):61} ║")

        print("╚═══════════════════════════════════════════════════════════════╝\n")

    def confirm_configuration(self, interface: NetworkInterface) -> bool:
        """
        Get user confirmation before making changes.

        Args:
            interface: Interface to be configured

        Returns:
            True if user confirmed, False otherwise
        """
        # Skip confirmation if requested (for guided flows)
        if self.skip_confirmation:
            return True

        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                   CONFIGURATION CONFIRMATION                  ║
╠═══════════════════════════════════════════════════════════════╣
║ Selected Interface: {interface.name:41} ║
║ Hardware Port:      {interface.hardware_port[:41]:41} ║
║ Current IP:         {interface.current_ip or 'None':41} ║
║ MAC Address:        {interface.mac_address or 'Unknown':41} ║
║                                                               ║
║ Will Configure:                                               ║
║   IP Address: {self.config.laptop_ip:47} ║
║   Netmask:    {self.config.netmask:47} ║
║   Route:      {self.config.mgmt_network} via {self.config.device_ip:21} ║
╚═══════════════════════════════════════════════════════════════╝
""")

        if self.dry_run:
            print("[DRY-RUN MODE] No changes will be made\n")
            return True

        # CRITICAL: Double-check protected interfaces
        if interface.is_protected:
            logger.error(f"[FAIL] CRITICAL: {interface.name} is PROTECTED!")
            return False

        # Interactive confirmation using Rich
        if not Confirm.ask("Proceed with configuration?", default=True, console=console):
            logger.info("Configuration cancelled by user")
            return False

        return True

    def configure(self) -> bool:
        """
        Execute main configuration workflow.

        Workflow:
        1. Display banner
        2. Find USB interface
        3. Confirm with user
        4. Preserve WiFi settings (if enabled)
        5. Configure IP address
        6. Add static route
        7. Test connectivity
        8. Display results

        Returns:
            True if configuration succeeded and device is reachable
        """
        self.display_banner()

        # WiFi preservation setup
        if self.preserve_wifi:
            logger.info("[*] WiFi preservation mode enabled")

            # Prevent USB NIC from taking priority when plugged in
            if not self.service_order_manager.prevent_usb_priority_takeover():
                logger.warning("[!] Failed to prevent USB priority takeover")

            # Backup current service order
            self.service_order_manager.backup_service_order()

            # Set WiFi to highest priority
            if not self.service_order_manager.set_wifi_priority():
                logger.warning("[!] Failed to set WiFi priority")

            # Show WiFi status
            wifi_status = self.wifi_monitor.get_wifi_status()
            if wifi_status:
                logger.info(f"[i] WiFi Status: {wifi_status.status.value} ({wifi_status.ssid})")
                if wifi_status.status.value == "connected":
                    logger.info(f"[i] Signal: {wifi_status.signal_strength} dBm, SNR: {wifi_status.snr} dB")

            # Check for interference
            if self.wifi_monitor.detect_interference():
                logger.warning("[!] WiFi interference detected - consider mitigation strategies")
                for strategy in self.interference_assessor.suggest_mitigation_strategies():
                    logger.info(f"[i] {strategy}")



        # Find USB interface
        interface = self.find_best_usb_interface()
        if not interface:
            return False

        # Confirm before proceeding
        if not self.confirm_configuration(interface):
            return False

        if self.dry_run:
            logger.info("[DRY-RUN] Would configure interface")
            logger.info("[DRY-RUN] Would add static route")
            logger.info("[DRY-RUN] Would test connectivity")
            return True

        # Configure interface
        if not self.detector.configure_interface(
            interface.name,
            self.config.laptop_ip,
            self.config.netmask
        ):
            return False

        # Add management route (preserve default gateway)
        if self.preserve_wifi:
            self.route_manager.preserve_default_gateway()
        
        self.route_manager.add_management_route(
            self.config.mgmt_network,
            interface.name,
            self.config.device_ip
        )

        # Test connectivity
        device_ok = self.detector.test_connectivity(self.config.device_ip)

        # Test management network
        mgmt_ok = False
        if self.config.mgmt_network:
            mgmt_test_ip = self.config.get_mgmt_test_ip()
            logger.info(f"Testing management network ({mgmt_test_ip})...")
            mgmt_ok = self.detector.test_connectivity(mgmt_test_ip, count=2)

        # Display results
        self._display_results(interface, device_ok, mgmt_ok)

        # Show dashboard if requested
        if self.show_dashboard:
            logger.info("[*] Displaying network dashboard...")
            self.dashboard.display_status()
            self.dashboard.show_connectivity_metrics()

        return device_ok

    def _display_results(
        self,
        interface: NetworkInterface,
        device_ok: bool,
        mgmt_ok: bool
    ) -> None:
        """Display final configuration results"""
        print(f"""
╔═══════════════════════════════════════════════════════════════╗
║                  Configuration Complete                       ║
╠═══════════════════════════════════════════════════════════════╣
║ Interface:    {interface.name:47} ║
║ IP Address:   {self.config.laptop_ip:47} ║
║                                                               ║
║ Device:       {'[OK] REACHABLE' if device_ok else '[--] NOT REACHABLE':47} ║
║ Mgmt Network: {'[OK] REACHABLE' if mgmt_ok else '[!!] NOT REACHABLE':47} ║
╚═══════════════════════════════════════════════════════════════╝
""")

        if device_ok:
            print("""
Next Steps:
1. ansible all -m ping
2. ansible-playbook site.yml --tags wan,uplinks,internet
3. ansible-playbook site.yml --tags validation
""")
        else:
            print(f"""
Troubleshooting:
1. Check USB cable connection to {self.config.device_name}
2. Verify link lights on both ends
3. Ensure device is powered on
4. Try manual ping: ping {self.config.device_ip}
""")
