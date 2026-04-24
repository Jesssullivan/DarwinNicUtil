"""
Darwin Management NIC Configurator - Application Entry Point

Subcommand dispatch for the darwin-nic CLI.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from typing import TYPE_CHECKING

from .settings import Settings, get_config_paths, init_config, load_settings

if TYPE_CHECKING:
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def cmd_configure(args: argparse.Namespace, settings: Settings) -> int | None:
    """Configure USB NIC using CLI mode."""
    from .cli import main as cli_main

    device_ip = args.device_ip
    laptop_ip = args.laptop_ip
    netmask = args.netmask
    mgmt_network = args.mgmt_network
    device_name = args.device_name

    if args.profile and args.profile in settings.profiles:
        profile = settings.profiles[args.profile]
        if device_ip == "__PROFILE__":
            device_ip = profile.device_ip
        if laptop_ip == "__PROFILE__":
            laptop_ip = profile.laptop_ip
        netmask = profile.netmask or netmask
        mgmt_network = profile.mgmt_network or mgmt_network
        device_name = profile.device_name or device_name
        print(f"[*] Using profile: {args.profile}")
    elif args.profile:
        print(f"[WARN] Profile '{args.profile}' not found, using provided values")

    if device_ip == "__PROFILE__" or laptop_ip == "__PROFILE__":
        print("[FAIL] --device-ip and --laptop-ip are required (or use --profile)")
        return 1

    sys.argv = [
        "darwin-mgmt-nic",
        "--device-ip",
        device_ip,
        "--laptop-ip",
        laptop_ip,
        "--netmask",
        netmask,
        "--mgmt-network",
        mgmt_network,
        "--device-name",
        device_name,
    ]

    if args.dry_run:
        sys.argv.append("--dry-run")
    if args.preserve_wifi:
        sys.argv.append("--preserve-wifi")
    if args.show_dashboard:
        sys.argv.append("--show-dashboard")

    cli_main()
    return None


def cmd_setup(args: argparse.Namespace) -> None:
    """Run interactive guided setup."""
    from .guided_setup import main as guided_main

    guided_main()


def cmd_status(args: argparse.Namespace) -> None:
    """Show current network status."""
    from rich.console import Console
    from rich.panel import Panel

    from .network_manager import NetworkDashboard, ServiceOrderManager, WiFiMonitor

    console = Console()
    wifi_monitor = WiFiMonitor()
    service_manager = ServiceOrderManager()
    dashboard = NetworkDashboard(wifi_monitor, service_manager)

    console.print(
        Panel(
            "[bold cyan]Network Status Dashboard[/bold cyan]",
            title="Darwin Management NIC",
            border_style="blue",
        )
    )

    dashboard.display_status()
    console.print("\n")
    dashboard.show_connectivity_metrics()
    print_bastion_diagnostics(console)


def print_bastion_diagnostics(console, detector=None) -> None:
    """Print high-signal bastion/OOB diagnostics when USB management state exists."""
    from rich.panel import Panel
    from rich.table import Table

    from .factory import USBNICDetectorFactory

    detector = detector or USBNICDetectorFactory.create()
    if not hasattr(detector, "get_bastion_diagnostics"):
        return

    diagnostics = detector.get_bastion_diagnostics()
    if not diagnostics.usb_interfaces_with_ip:
        return

    table = Table(box=None, show_header=False, pad_edge=False)
    table.add_column(style="cyan")
    table.add_column(style="white")
    table.add_row("USB OOB", ", ".join(diagnostics.usb_interfaces_with_ip))
    table.add_row(
        "NWI",
        ", ".join(diagnostics.nwi_interfaces) if diagnostics.nwi_interfaces else "none",
    )
    table.add_row(
        "Missing from NWI",
        ", ".join(diagnostics.missing_from_nwi) if diagnostics.missing_from_nwi else "none",
    )
    table.add_row(
        "Tailscale sysext",
        "active" if diagnostics.tailscale_extension_active else "inactive",
    )
    table.add_row(
        "Recent NECP drops",
        "yes" if diagnostics.recent_necp_drop else "no",
    )

    console.print(
        Panel(
            table,
            title="Bastion OOB Diagnostics",
            border_style="magenta",
        )
    )

    if diagnostics.missing_from_nwi and diagnostics.tailscale_extension_active:
        console.print(
            "[yellow]Warning:[/yellow] USB OOB interface is outside `scutil --nwi` "
            "while the Tailscale Network Extension is active. Ordinary sockets may be blocked."
        )
    if diagnostics.recent_necp_drop:
        console.print(
            "[yellow]Warning:[/yellow] Recent macOS logs show `reason: NECP` drops for outbound sockets."
        )


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Show real-time monitoring dashboard."""
    from .network_manager import NetworkDashboard, ServiceOrderManager, WiFiMonitor

    wifi_monitor = WiFiMonitor()
    service_manager = ServiceOrderManager()
    dashboard = NetworkDashboard(wifi_monitor, service_manager)

    if args.interference:
        duration = args.duration or 30
        dashboard.monitor_interference(duration)
    else:
        dashboard.display_status()


def cmd_test(args: argparse.Namespace) -> None:
    """Test connectivity to management networks."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    table = Table(title="Connectivity Test Results")
    table.add_column("Target", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Response Time", style="yellow")

    interfaces = ["en0", "en1", "en11"]
    for interface in interfaces:
        try:
            result = subprocess.run(
                ["ifconfig", interface], capture_output=True, text=True
            )
            if result.returncode == 0:
                table.add_row(f"Interface {interface}", "[OK] Active", "N/A")
            else:
                table.add_row(f"Interface {interface}", "[--] Inactive", "N/A")
        except Exception:
            table.add_row(f"Interface {interface}", "[??] Unknown", "N/A")

    test_ips = ["192.0.2.1", "192.168.1.1", "8.8.8.8"]
    for ip in test_ips:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", ip], capture_output=True, text=True
            )
            if result.returncode == 0:
                time_match = re.search(r"time=(\d+\.?\d*)", result.stdout)
                response_time = (
                    time_match.group(1) + " ms" if time_match else "Unknown"
                )
                table.add_row(ip, "[OK] Reachable", response_time)
            else:
                table.add_row(ip, "[--] Unreachable", "Timeout")
        except Exception:
            table.add_row(ip, "[??] Error", "N/A")

    console.print(table)


def cmd_restore(args: argparse.Namespace) -> None:
    """Restore backup configuration."""
    from .network_manager import ServiceOrderManager

    service_manager = ServiceOrderManager()
    print("[*] Restoring network configuration...")

    if service_manager.restore_service_order():
        print("[OK] Service order restored")
    else:
        print("[FAIL] Failed to restore service order")

    print("[OK] Configuration restore complete")


def cmd_show_config(settings: Settings) -> None:
    """Display current configuration and available profiles."""
    from rich import box
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print("[bold cyan]Configuration Sources[/bold cyan]")
    if settings.config_sources:
        for source in settings.config_sources:
            console.print(f"  [green][OK][/green] {source}")
    else:
        console.print("  [dim]No config files found (using built-in defaults)[/dim]")

    console.print()

    console.print("[bold cyan]Config Search Paths[/bold cyan]")
    for path in get_config_paths():
        exists = "[green][OK][/green]" if path.exists() else "[dim]--[/dim]"
        console.print(f"  {exists} {path}")

    console.print()

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

    if settings.profiles:
        console.print()
        console.print("[bold cyan]Available Profiles[/bold cyan]")
        profiles_table = Table(box=box.SIMPLE)
        profiles_table.add_column("Profile", style="cyan")
        profiles_table.add_column("Device IP", style="white")
        profiles_table.add_column("Device Name", style="dim")

        for name, profile in settings.profiles.items():
            default_marker = (
                " [yellow]*[/yellow]" if name == settings.default_profile else ""
            )
            profiles_table.add_row(
                f"{name}{default_marker}", profile.device_ip, profile.device_name
            )

        console.print(profiles_table)
        console.print("[dim]* = default profile[/dim]")


def cmd_init_config() -> None:
    """Initialize user config file with defaults."""
    config_path = init_config()
    if config_path:
        print(f"[OK] Config file created: {config_path}")
        print("\nEdit this file to add your network profiles.")
    else:
        print("[WARN] Config file already exists.")
        print("Use 'darwin-nic config' to view current settings.")


def cmd_list_profiles(settings: Settings) -> None:
    """List available profiles."""
    from rich.console import Console

    console = Console()

    if not settings.profiles:
        console.print("[yellow]No profiles configured.[/yellow]")
        console.print(
            "Run [cyan]darwin-nic init-config[/cyan] to create a config file."
        )
        return

    console.print("[bold cyan]Available Profiles[/bold cyan]\n")

    for name, profile in settings.profiles.items():
        default = (
            " [yellow](default)[/yellow]" if name == settings.default_profile else ""
        )
        console.print(f"[bold]{name}[/bold]{default}")
        console.print(f"  Device: {profile.device_name}")
        console.print(f"  IP: {profile.device_ip} -> {profile.laptop_ip}")
        console.print(f"  Mgmt: {profile.mgmt_network}")
        if profile.description:
            console.print(f"  [dim]{profile.description}[/dim]")
        console.print()


def main() -> int:
    """Main entry point for darwin-nic CLI."""
    from . import __version__

    settings = load_settings()

    parser = argparse.ArgumentParser(
        prog="darwin-nic",
        description="Darwin Management NIC Configurator - USB NIC setup with WiFi preservation",
        epilog="""
Examples:
  darwin-nic configure --profile homelab
  darwin-nic configure --device-ip 192.0.2.1 --laptop-ip 192.0.2.100
  darwin-nic setup
  darwin-nic status
  darwin-nic config
  darwin-nic profiles
  darwin-nic init-config
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Configure command
    configure_parser = subparsers.add_parser("configure", help="Configure USB NIC")
    configure_parser.add_argument(
        "--profile", metavar="NAME", help="Use named profile from config file"
    )
    configure_parser.add_argument(
        "--device-ip",
        default="__PROFILE__",
        help="Management device IP (required unless using --profile)",
    )
    configure_parser.add_argument(
        "--laptop-ip",
        default="__PROFILE__",
        help="Laptop USB NIC IP (required unless using --profile)",
    )
    configure_parser.add_argument(
        "--netmask", default="255.255.255.0", help="Network mask"
    )
    configure_parser.add_argument(
        "--mgmt-network", default="198.51.100.0/24", help="Management network"
    )
    configure_parser.add_argument(
        "--device-name", default="Network Device", help="Device name"
    )
    configure_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done"
    )
    configure_parser.add_argument(
        "--preserve-wifi", action="store_true", help="Preserve WiFi connectivity"
    )
    configure_parser.add_argument(
        "--show-dashboard", action="store_true", help="Show network dashboard"
    )

    # Other subcommands
    subparsers.add_parser("setup", help="Interactive guided setup")
    subparsers.add_parser("status", help="Show network status")

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="Show monitoring dashboard"
    )
    dashboard_parser.add_argument(
        "--interference", action="store_true", help="Monitor for interference"
    )
    dashboard_parser.add_argument(
        "--duration", type=int, help="Monitoring duration in seconds"
    )

    subparsers.add_parser("test", help="Test connectivity")
    subparsers.add_parser("restore", help="Restore backup configuration")
    subparsers.add_parser("config", help="Show current configuration and profiles")
    subparsers.add_parser("init-config", help="Initialize user config file")
    subparsers.add_parser("profiles", help="List available profiles")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "configure":
            result = cmd_configure(args, settings)
            if result:
                return result
        elif args.command == "setup":
            cmd_setup(args)
        elif args.command == "status":
            cmd_status(args)
        elif args.command == "dashboard":
            cmd_dashboard(args)
        elif args.command == "test":
            cmd_test(args)
        elif args.command == "restore":
            cmd_restore(args)
        elif args.command == "config":
            cmd_show_config(settings)
        elif args.command == "init-config":
            cmd_init_config()
        elif args.command == "profiles":
            cmd_list_profiles(settings)
        else:
            print(f"Unknown command: {args.command}")
            return 1
    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
