"""
CLI interface for USB NIC configurator
"""

import sys
import logging
import argparse
import subprocess
import time
from rich.console import Console
from rich.table import Table
from rich import box

from .config import NetworkConfig
from .configurator import USBNICConfigurator
from .factory import USBNICDetectorFactory
from .settings import load_settings, init_config, get_config_paths, Settings


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def create_parser(settings: Settings) -> argparse.ArgumentParser:
    """Create CLI argument parser with defaults from settings."""
    parser = argparse.ArgumentParser(
        description="USB NIC Configurator for Out-of-Band Network Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (safe, no changes)
  %(prog)s --dry-run

  # Configure with custom IPs
  %(prog)s --device-ip 192.0.2.1 --laptop-ip 192.0.2.100

  # Use a saved profile
  %(prog)s --profile homelab

  # Show current configuration
  %(prog)s --show-config

  # Initialize config file
  %(prog)s --init-config
        """
    )

    # Config management
    parser.add_argument(
        "--profile",
        metavar="NAME",
        help="Use named profile from config file"
    )

    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Show current configuration and available profiles"
    )

    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Initialize user config file with defaults"
    )

    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List available profiles"
    )

    # Network configuration (defaults from settings)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=settings.dry_run,
        help="Show what would be done without making changes"
    )

    parser.add_argument(
        "--device-ip",
        default=settings.device_ip,
        help=f"Device IP address (default: {settings.device_ip})"
    )

    parser.add_argument(
        "--laptop-ip",
        default=settings.laptop_ip,
        help=f"Laptop IP address (default: {settings.laptop_ip})"
    )

    parser.add_argument(
        "--netmask",
        default=settings.netmask,
        help=f"Network mask (default: {settings.netmask})"
    )

    parser.add_argument(
        "--device-name",
        default=settings.device_name,
        help=f"Human-readable device name (default: {settings.device_name})"
    )

    parser.add_argument(
        "--mgmt-network",
        default=settings.mgmt_network,
        help=f"Management network for routing (default: {settings.mgmt_network})"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--preserve-wifi",
        action="store_true",
        default=settings.preserve_wifi,
        help="Preserve WiFi connectivity during USB NIC configuration"
    )

    parser.add_argument(
        "--show-dashboard",
        action="store_true",
        default=settings.show_dashboard,
        help="Display real-time network monitoring dashboard"
    )

    parser.add_argument(
        "--fix-vpn-issues",
        action="store_true",
        help="Fix network priority and DNS issues caused by VPN connections"
    )

    parser.add_argument(
        "--version",
        action="version",
        version="USB NIC Configurator 2.0.0"
    )

    return parser


def show_config(settings: Settings) -> None:
    """Display current configuration and available profiles."""
    console = Console()

    # Show config sources
    console.print("[bold cyan]Configuration Sources[/bold cyan]")
    if settings.config_sources:
        for source in settings.config_sources:
            console.print(f"  [green][OK][/green] {source}")
    else:
        console.print("  [dim]No config files found (using built-in defaults)[/dim]")

    console.print()

    # Show search paths
    console.print("[bold cyan]Config Search Paths[/bold cyan]")
    for path in get_config_paths():
        exists = "[green][OK][/green]" if path.exists() else "[dim]--[/dim]"
        console.print(f"  {exists} {path}")

    console.print()

    # Show current settings
    console.print("[bold cyan]Current Settings[/bold cyan]")
    settings_table = Table(box=box.SIMPLE)
    settings_table.add_column("Setting", style="cyan")
    settings_table.add_column("Value", style="white")

    settings_table.add_row("device_ip", settings.device_ip)
    settings_table.add_row("laptop_ip", settings.laptop_ip)
    settings_table.add_row("netmask", settings.netmask)
    settings_table.add_row("mgmt_network", settings.mgmt_network)
    settings_table.add_row("device_name", settings.device_name)
    settings_table.add_row("preserve_wifi", str(settings.preserve_wifi))
    settings_table.add_row("dry_run", str(settings.dry_run))

    if settings.default_profile:
        settings_table.add_row("default_profile", settings.default_profile)

    console.print(settings_table)

    # Show profiles
    if settings.profiles:
        console.print()
        console.print("[bold cyan]Available Profiles[/bold cyan]")
        profiles_table = Table(box=box.SIMPLE)
        profiles_table.add_column("Profile", style="cyan")
        profiles_table.add_column("Device IP", style="white")
        profiles_table.add_column("Device Name", style="dim")

        for name, profile in settings.profiles.items():
            default_marker = " [yellow]*[/yellow]" if name == settings.default_profile else ""
            profiles_table.add_row(
                f"{name}{default_marker}",
                profile.device_ip,
                profile.device_name
            )

        console.print(profiles_table)
        console.print("[dim]* = default profile[/dim]")


def list_profiles(settings: Settings) -> None:
    """List available profiles."""
    console = Console()

    if not settings.profiles:
        console.print("[yellow]No profiles configured.[/yellow]")
        console.print("Run [cyan]darwin-nic --init-config[/cyan] to create a config file.")
        return

    console.print("[bold cyan]Available Profiles[/bold cyan]\n")

    for name, profile in settings.profiles.items():
        default = " [yellow](default)[/yellow]" if name == settings.default_profile else ""
        console.print(f"[bold]{name}[/bold]{default}")
        console.print(f"  Device: {profile.device_name}")
        console.print(f"  IP: {profile.device_ip} -> {profile.laptop_ip}")
        console.print(f"  Mgmt: {profile.mgmt_network}")
        if profile.description:
            console.print(f"  [dim]{profile.description}[/dim]")
        console.print()


def main() -> int:
    """
    Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    console = Console()

    # Load settings first (before parsing args, so defaults come from config)
    # We need to do a preliminary parse just for --profile
    import sys
    profile_arg = None
    if "--profile" in sys.argv:
        try:
            idx = sys.argv.index("--profile")
            if idx + 1 < len(sys.argv):
                profile_arg = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass

    settings = load_settings(profile=profile_arg)

    # Now create parser with settings-based defaults
    parser = create_parser(settings)
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Handle config management commands first
    if args.init_config:
        config_path = init_config()
        if config_path:
            console.print(f"[green][OK][/green] Config file created: {config_path}")
            console.print("\nEdit this file to add your network profiles.")
        else:
            console.print("[yellow]Config file already exists.[/yellow]")
            console.print("Use --show-config to view current settings.")
        return 0

    if args.show_config:
        show_config(settings)
        return 0

    if args.list_profiles:
        list_profiles(settings)
        return 0

    # Check platform support
    if not USBNICDetectorFactory.is_supported():
        logger.error("[FAIL] Current platform is not supported")
        logger.error("Supported platforms: macOS, Linux (experimental)")
        return 3

    # Handle VPN fix mode
    if args.fix_vpn_issues:
        return handle_vpn_repair()

    # If a profile was specified, apply it to override args
    if args.profile and args.profile in settings.profiles:
        profile = settings.profiles[args.profile]
        # Only override if user didn't explicitly set these on CLI
        # (argparse doesn't distinguish between default and user-provided easily,
        # so we just apply profile values)
        args.device_ip = profile.device_ip
        args.laptop_ip = profile.laptop_ip
        args.netmask = profile.netmask
        args.mgmt_network = profile.mgmt_network
        args.device_name = profile.device_name
        console.print(f"[cyan]Using profile: {args.profile}[/cyan]")
    elif args.profile:
        console.print(f"[yellow]Warning: Profile '{args.profile}' not found[/yellow]")
        console.print("Available profiles:", ", ".join(settings.list_profiles()) or "(none)")

    try:
        # Create configuration
        config = NetworkConfig(
            device_ip=args.device_ip,
            laptop_ip=args.laptop_ip,
            netmask=args.netmask,
            mgmt_network=args.mgmt_network,
            device_name=args.device_name
        )

        # Create and run configurator
        configurator = USBNICConfigurator(
            config,
            dry_run=args.dry_run,
            preserve_wifi=args.preserve_wifi,
            show_dashboard=args.show_dashboard
        )
        success = configurator.configure()

        return 0 if success else 1

    except ValueError as e:
        logger.error(f"[FAIL] Configuration error: {e}")
        return 2
    except KeyboardInterrupt:
        logger.info("\n[!] Configuration cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"[FAIL] Unexpected error: {e}", exc_info=args.verbose)
        return 1


def handle_vpn_repair() -> int:
    """Handle VPN network repair functionality"""
    console = Console()
    logger = logging.getLogger(__name__)
    
    try:
        # Import here to avoid circular imports
        from .network_manager import ServiceOrderManager, WiFiMonitor
        
        console.print("[bold cyan]VPN Network Repair[/bold cyan]")
        console.print("Fixing network priority and DNS issues caused by VPN...\n")
        
        # Initialize managers
        service_manager = ServiceOrderManager()
        wifi_monitor = WiFiMonitor()
        
        # Create backup
        logger.info("Creating backup of current network settings...")
        service_manager.backup_service_order()
        
        # Fix WiFi priority
        logger.info("Restoring WiFi priority...")
        if service_manager.set_wifi_priority():
            console.print("[green][OK] WiFi priority restored[/green]")
        else:
            console.print("[red][FAIL] Failed to restore WiFi priority[/red]")
            return 1
        
        # Fix DNS
        logger.info("Fixing DNS configuration...")
        try:
            # Set reliable DNS servers
            subprocess.run(["networksetup", "-setdnsservers", "Wi-Fi", "8.8.8.8", "8.8.4.4", "1.1.1.1"],
                         check=True, capture_output=True, timeout=30)
            console.print("[green][OK] DNS servers updated[/green]")

            # Flush DNS cache
            subprocess.run(["dscacheutil", "-flushcache"], check=False)
            subprocess.run(["sudo", "killall", "-HUP", "mDNSResponder"], check=False)
            console.print("[green][OK] DNS cache flushed[/green]")

        except subprocess.CalledProcessError as e:
            console.print(f"[red][FAIL] Failed to fix DNS: {e}[/red]")
            return 1
        
        # Wait for network to stabilize
        console.print("[yellow]Waiting for network to stabilize...[/yellow]")
        time.sleep(3)
        
        # Verify connectivity
        logger.info("Verifying network connectivity...")
        try:
            # Test DNS resolution
            result = subprocess.run(["nslookup", "google.com"], 
                                  capture_output=True, text=True, timeout=10)
            dns_working = result.returncode == 0
            
            # Test internet connectivity
            result = subprocess.run(["ping", "-c", "1", "-t", "5", "8.8.8.8"], 
                                  capture_output=True, text=True, timeout=10)
            internet_working = result.returncode == 0
            
            if dns_working and internet_working:
                console.print("[bold green][OK] Network repair completed successfully![/bold green]")
                console.print("\n[cyan]What was fixed:[/cyan]")
                console.print("- WiFi priority restored over USB NIC")
                console.print("- DNS servers set to reliable public DNS")
                console.print("- DNS cache flushed")
                console.print("\n[yellow][i] If issues persist, try disconnecting and reconnecting to VPN[/yellow]")
                return 0
            else:
                console.print("[red][FAIL] Network verification failed[/red]")
                console.print(f"DNS: {'Working' if dns_working else 'Broken'}")
                console.print(f"Internet: {'Working' if internet_working else 'Broken'}")
                return 1
                
        except subprocess.TimeoutExpired:
            console.print("[red][FAIL] Network verification timed out[/red]")
            return 1

    except KeyboardInterrupt:
        console.print("\n[yellow][!] VPN repair cancelled by user[/yellow]")
        return 130
    except Exception as e:
        logger.error(f"[FAIL] VPN repair failed: {e}", exc_info=True)
        console.print(f"[red][FAIL] Unexpected error: {e}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
