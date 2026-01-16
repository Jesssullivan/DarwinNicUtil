"""
Guided Setup for USB NIC Configuration with Rich TUI

This module provides an interactive, step-by-step setup wizard that:
1. Establishes baseline (no USB NIC connected)
2. Guides user to insert USB NIC (no cable)
3. Detects the new interface
4. Guides user to connect cable to target device
5. Configures the interface
6. Verifies connectivity

Uses a terminal-filling TUI that updates in place (no scrolling).
"""

import sys
import time
import logging
import json
from pathlib import Path
from typing import Set, Optional
from dataclasses import dataclass, field
from enum import IntEnum

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from rich import box

from .config import NetworkConfig
from .configurator import USBNICConfigurator
from .factory import USBNICDetectorFactory
from .detectors import NetworkInterface
from .network_manager import (
    ServiceOrderManager, WiFiMonitor, InterfaceScorer, RouteManager,
    InterferenceAssessor, NetworkDashboard
)
from .tui import TUIApp, build_content
from .settings import load_settings, Settings


class SetupStep(IntEnum):
    """Setup workflow steps"""
    INITIAL = 0
    BASELINE_COMPLETE = 1
    USB_DETECTED = 2
    CABLE_CONNECTED = 3
    CONFIGURED = 4
    VERIFIED = 5
    MONITORING_SHOWN = 6
    COMPLETE = 7

    @property
    def display_name(self) -> str:
        """Human-readable step name"""
        names = {
            SetupStep.INITIAL: "Not started",
            SetupStep.BASELINE_COMPLETE: "Baseline established",
            SetupStep.USB_DETECTED: "USB NIC detected",
            SetupStep.CABLE_CONNECTED: "Cable connected",
            SetupStep.CONFIGURED: "Network configured",
            SetupStep.VERIFIED: "Connectivity verified",
            SetupStep.MONITORING_SHOWN: "Dashboard shown",
            SetupStep.COMPLETE: "Setup complete",
        }
        return names.get(self, str(self.name))

    def can_transition_to(self, target: 'SetupStep') -> bool:
        """Check if transition to target step is valid"""
        # Can always go back to INITIAL (reset)
        if target == SetupStep.INITIAL:
            return True
        # Normal forward progression: must be at previous step
        if target.value == self.value + 1:
            return True
        # Can skip to same step (no-op)
        if target == self:
            return True
        return False


@dataclass
class SetupState:
    """Track setup progress state"""
    current_step: int = 0
    baseline_interfaces: Set[str] = field(default_factory=set)
    detected_usb_nic: Optional[str] = None
    config: Optional[NetworkConfig] = None
    configured: bool = False
    verified: bool = False
    timestamp: float = 0.0

    def to_json(self) -> str:
        """Serialize state to JSON string"""
        state_dict = {
            "current_step": self.current_step,
            "baseline_interfaces": list(self.baseline_interfaces),
            "detected_usb_nic": self.detected_usb_nic,
            "config": None if self.config is None else {
                "device_ip": self.config.device_ip,
                "laptop_ip": self.config.laptop_ip,
                "netmask": self.config.netmask,
                "mgmt_network": self.config.mgmt_network,
                "device_name": self.config.device_name,
            },
            "configured": self.configured,
            "verified": self.verified,
            "timestamp": self.timestamp,
        }
        return json.dumps(state_dict, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'SetupState':
        """Deserialize state from JSON string"""
        data = json.loads(json_str)

        # Reconstruct config if present
        config = None
        if data.get("config"):
            config = NetworkConfig(
                device_ip=data["config"]["device_ip"],
                laptop_ip=data["config"]["laptop_ip"],
                netmask=data["config"]["netmask"],
                mgmt_network=data["config"]["mgmt_network"],
                device_name=data["config"]["device_name"],
            )

        return cls(
            current_step=data.get("current_step", 0),
            baseline_interfaces=set(data.get("baseline_interfaces", [])),
            detected_usb_nic=data.get("detected_usb_nic"),
            config=config,
            configured=data.get("configured", False),
            verified=data.get("verified", False),
            timestamp=data.get("timestamp", 0.0),
        )


class GuidedSetup:
    """Interactive guided setup using Rich TUI"""

    # State file location in /tmp (auto-cleaned on reboot)
    STATE_FILE = Path("/tmp/darwin-nic-setup-state.json")

    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.logger = logging.getLogger(__name__)
        self.state = SetupState()

        # TUI app (set during run())
        self.tui: Optional[TUIApp] = None

        # Load settings from config files
        self.settings = load_settings()

        # Initialize network manager components
        self.service_order_manager = ServiceOrderManager()
        self.wifi_monitor = WiFiMonitor()
        self.interference_assessor = InterferenceAssessor()
        self.route_manager = RouteManager()

        self.interface_scorer = InterfaceScorer(self.wifi_monitor, self.interference_assessor)
        self.dashboard = NetworkDashboard(self.wifi_monitor, self.service_order_manager)

    def save_state(self) -> bool:
        """
        Save current state to disk.

        Returns:
            True if save successful, False otherwise
        """
        try:
            self.state.timestamp = time.time()
            state_json = self.state.to_json()
            self.STATE_FILE.write_text(state_json)
            self.logger.debug(f"State saved to {self.STATE_FILE}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
            return False

    def load_state(self) -> Optional[SetupState]:
        """
        Load state from disk if it exists.

        Returns:
            SetupState if file exists and is valid, None otherwise
        """
        try:
            if not self.STATE_FILE.exists():
                return None

            state_json = self.STATE_FILE.read_text()
            loaded_state = SetupState.from_json(state_json)

            # Validate state is recent (within 24 hours)
            if loaded_state.timestamp > 0:
                age_hours = (time.time() - loaded_state.timestamp) / 3600
                if age_hours > 24:
                    self.logger.warning(f"State file is {age_hours:.1f} hours old, ignoring")
                    return None

            self.logger.info("Loaded previous setup state")
            return loaded_state

        except Exception as e:
            self.logger.error(f"Failed to load state: {e}")
            return None

    def clear_state(self) -> None:
        """Remove state file from disk"""
        try:
            if self.STATE_FILE.exists():
                self.STATE_FILE.unlink()
                self.logger.debug("State file removed")
        except Exception as e:
            self.logger.error(f"Failed to remove state file: {e}")

    def check_resume(self) -> bool:
        """
        Check for previous incomplete setup and offer to resume.

        Returns:
            True if resuming from previous state, False for fresh start
        """
        from rich.prompt import Confirm
        from datetime import datetime

        previous_state = self.load_state()
        if previous_state is None:
            return False

        if previous_state.current_step == 0:
            # No progress made, start fresh
            self.clear_state()
            return False

        # Show previous state info
        self.console.print()
        self.console.print("[bold yellow]Previous incomplete setup found![/bold yellow]")
        self.console.print()

        # Format timestamp
        if previous_state.timestamp > 0:
            dt = datetime.fromtimestamp(previous_state.timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            self.console.print(f"  Last activity: [cyan]{time_str}[/cyan]")

        self.console.print(f"  Progress: Step [cyan]{previous_state.current_step}[/cyan] of 7")

        if previous_state.detected_usb_nic:
            self.console.print(f"  Detected NIC: [cyan]{previous_state.detected_usb_nic}[/cyan]")

        if previous_state.config:
            self.console.print(f"  Target device: [cyan]{previous_state.config.device_ip}[/cyan]")

        self.console.print()

        if Confirm.ask("Resume from previous state?", default=True):
            self.state = previous_state
            self.print_success(f"Resuming from step {self.state.current_step + 1}")
            return True
        else:
            self.clear_state()
            self.print_info("Starting fresh setup")
            return False

    def suggest_rollback(self) -> None:
        """Suggest rollback commands to user (manual rollback per user preference)"""
        # Build rollback instructions
        lines = ["To revert network changes:", ""]

        if self.state.detected_usb_nic and self.state.config:
            lines.append("  # Remove IP from USB NIC")
            lines.append(f"  sudo ifconfig {self.state.detected_usb_nic} down")
            lines.append("")

        if self.state.config:
            lines.append("  # Remove management route")
            lines.append(f"  sudo route delete -net {self.state.config.mgmt_network}")
            lines.append("")

        lines.append("  # Or use the restore command:")
        lines.append("  ./darwin-nic restore")

        # Display through TUI if active, otherwise direct to console
        if self.tui:
            content = build_content(
                Text("Rollback Instructions", style="bold yellow"),
                Text(""),
                *[Text(line, style="cyan" if line.startswith("  sudo") or line.startswith("  ./") else "white")
                  for line in lines],
            )
            self.tui.update_body(content)
            self.tui.update_status("Configuration failed - see rollback instructions")
        else:
            self.console.print()
            self.console.print("[bold yellow]To revert network changes:[/bold yellow]")
            for line in lines:
                if line.startswith("  sudo") or line.startswith("  ./"):
                    self.console.print(f"[cyan]{line}[/cyan]")
                else:
                    self.console.print(line)
            self.console.print()

    def rollback_configuration(self) -> bool:
        """
        Rollback network configuration changes.

        This method undoes changes made during step 4 (configure).
        It's called when setup fails after configuration was applied.

        Returns:
            True if rollback successful, False otherwise
        """
        import subprocess

        success = True

        # Display rollback status through TUI if active
        if self.tui:
            self.tui.update_status("Rolling back configuration changes...", spinner=True)
        else:
            self.console.print()
            self.print_info("Rolling back configuration changes...")

        # Collect rollback results for TUI display
        results = []

        # Restore service order
        if self.service_order_manager._backup_order:
            if self.service_order_manager.restore_service_order():
                results.append(("[OK]", "Service order restored"))
            else:
                results.append(("[FAIL]", "Failed to restore service order"))
                success = False

        # Remove IP from interface
        if self.state.detected_usb_nic and self.state.config:
            try:
                subprocess.run(
                    ["sudo", "-n", "ifconfig", self.state.detected_usb_nic, "down"],
                    capture_output=True,
                    timeout=10
                )
                results.append(("[OK]", f"Interface {self.state.detected_usb_nic} disabled"))
            except Exception as e:
                results.append(("[FAIL]", f"Failed to disable interface: {e}"))
                success = False

        # Remove management route
        if self.state.config and self.state.config.mgmt_network:
            try:
                subprocess.run(
                    ["sudo", "-n", "route", "delete", "-net", self.state.config.mgmt_network],
                    capture_output=True,
                    timeout=10
                )
                results.append(("[OK]", "Management route removed"))
            except Exception as e:
                # Route might not exist, that's OK
                self.logger.debug(f"Route removal: {e}")

        # Display results through TUI or console
        if self.tui:
            items = [Text("Rollback Results:", style="bold cyan"), Text("")]
            for status, msg in results:
                style = "green" if status == "[OK]" else "yellow"
                items.append(Text(f"  {status} {msg}", style=style))

            if success:
                items.append(Text(""))
                items.append(Text("Rollback complete", style="bold green"))
            else:
                items.append(Text(""))
                items.append(Text("Rollback completed with warnings", style="bold yellow"))

            content = build_content(*items)
            self.tui.update_body(content)
            self.tui.update_status("Rollback complete" if success else "Rollback completed with warnings")
        else:
            for status, msg in results:
                if status == "[OK]":
                    self.print_success(msg)
                else:
                    self.print_warning(msg)

            if success:
                self.print_success("Rollback complete")
            else:
                self.print_warning("Rollback completed with warnings")
                self.suggest_rollback()

        return success

    def run_step_with_retry(
        self,
        step_func,
        step_name: str,
        max_retries: int = 2,
        allow_skip: bool = False
    ) -> bool:
        """
        Run a setup step with retry capability.

        Args:
            step_func: The step function to run
            step_name: Human-readable step name for messages
            max_retries: Maximum number of retry attempts
            allow_skip: Whether to allow skipping this step

        Returns:
            True if step succeeded (or was skipped), False if failed all retries
        """
        for attempt in range(max_retries + 1):
            try:
                if step_func():
                    return True

                # Step returned False
                if attempt < max_retries:
                    if self.tui:
                        self.tui.update_status(f"{step_name} failed - retry available")
                        content = build_content(
                            Text(f"{step_name} failed", style="bold yellow"),
                            Text(""),
                            Text(f"  Attempt {attempt + 1} of {max_retries + 1}", style="dim"),
                        )
                        self.tui.update_body(content)
                    else:
                        self.print_warning(f"{step_name} failed")

                    if self.confirm(f"Retry {step_name}?", default=True):
                        continue
                    elif allow_skip and self.confirm("Skip this step?", default=False):
                        if self.tui:
                            self.tui.update_status(f"Skipping {step_name}")
                        else:
                            self.print_info(f"Skipping {step_name}")
                        return True
                    else:
                        return False
                else:
                    if self.tui:
                        self.tui.show_error(
                            f"{step_name} failed",
                            f"Failed after {max_retries + 1} attempts"
                        )
                    else:
                        self.print_error(f"{step_name} failed after {max_retries + 1} attempts")
                    return False

            except Exception as e:
                self.logger.exception(f"{step_name} raised exception")
                if attempt < max_retries:
                    if self.tui:
                        self.tui.show_error(f"{step_name} error", str(e))
                    else:
                        self.print_error(f"{step_name} error: {e}")
                    if not self.confirm("Retry?", default=True):
                        return False
                else:
                    raise

        return False

    def _check_sudo_available(self) -> tuple[bool, bool, str]:
        """
        Check sudo availability without prompting.

        Returns:
            (has_access, can_have_access, error_message)
            - has_access: True if already authenticated
            - can_have_access: True if user can sudo (just needs password)
            - error_message: Error text if sudo check failed
        """
        import subprocess

        # Check if already authenticated
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return (True, True, "")
        except subprocess.TimeoutExpired:
            pass

        # Check if user can sudo at all
        try:
            result = subprocess.run(
                ["sudo", "-n", "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            stderr = result.stderr.lower() if result.stderr else ""

            if "may not run sudo" in stderr:
                return (False, False, result.stderr)
            else:
                # "a password is required" or similar = user CAN sudo
                return (False, True, "")
        except subprocess.TimeoutExpired:
            return (False, False, "timeout")

    def _detect_abr(self) -> bool:
        """Check if Admin By Request is installed"""
        import shutil
        abr_app = Path("/Applications/Admin By Request.app")
        return shutil.which("adminbyrequest") is not None or abr_app.exists()

    def _try_open_abr(self) -> bool:
        """Attempt to open Admin By Request app"""
        import subprocess
        try:
            subprocess.run(
                ["open", "-a", "Admin By Request"],
                capture_output=True,
                timeout=5
            )
            return True
        except Exception:
            return False

    def ensure_sudo_authenticated(self) -> bool:
        """
        Ensure sudo is authenticated before starting TUI.

        This pre-caches sudo credentials for ~5 minutes to prevent
        password prompts from breaking Rich TUI state during setup.

        Handles Admin By Request (ABR) and similar privilege elevation tools
        with automatic detection and retry flow.

        Returns:
            True if sudo authentication successful, False otherwise
        """
        import subprocess
        from rich.prompt import Confirm

        self.console.print()
        self.console.print("[yellow][WARN] This tool requires sudo access to configure network interfaces[/yellow]")

        max_attempts = 3
        for attempt in range(max_attempts):
            has_access, can_have_access, error_msg = self._check_sudo_available()

            if has_access:
                self.print_success("Sudo access confirmed")
                self.console.print()
                return True

            if can_have_access:
                # User can sudo, just needs to authenticate
                self.console.print("[dim]You will be prompted for your password...[/dim]")
                self.console.print()

                try:
                    result = subprocess.run(
                        ["sudo", "-v"],
                        capture_output=False,
                        timeout=60
                    )

                    if result.returncode == 0:
                        self.print_success("Sudo authentication successful")
                        self.console.print()
                        return True
                    else:
                        self.print_error("Sudo authentication failed")
                        if attempt < max_attempts - 1:
                            if not Confirm.ask("Try again?", default=True):
                                return False
                        continue

                except subprocess.TimeoutExpired:
                    self.print_error("Sudo authentication timed out")
                    return False
                except KeyboardInterrupt:
                    self.console.print()
                    self.print_warning("Sudo authentication cancelled")
                    return False

            else:
                # User cannot sudo - check for ABR
                self.console.print()
                self.print_warning("Sudo access not currently available")

                if self._detect_abr():
                    self.console.print()
                    self.console.print("[bold cyan]Admin By Request detected[/bold cyan]")
                    self.console.print()

                    # Try to open ABR
                    self.console.print("Opening Admin By Request...")
                    self._try_open_abr()

                    self.console.print()
                    self.console.print("Please request admin access in the ABR window/menu bar,")
                    self.console.print("then press Enter to continue...")
                    self.console.print()

                    try:
                        input()  # Wait for user
                    except KeyboardInterrupt:
                        self.console.print()
                        self.print_warning("Cancelled")
                        return False

                    # Loop will retry sudo check
                    continue

                else:
                    # No ABR, no sudo access
                    self.console.print()
                    self.console.print("Your account doesn't have sudo privileges.")
                    self.console.print()
                    self.console.print("Options:")
                    self.console.print("  1. Contact your IT administrator for sudo access")
                    self.console.print("  2. If you have a privilege elevation tool, activate it first")
                    self.console.print()
                    return False

        self.print_error(f"Failed to obtain sudo access after {max_attempts} attempts")
        return False

    def cleanup_terminal(self) -> None:
        """
        Clean terminal state after errors or interruptions.

        Clears any lingering Rich UI elements (progress bars, panels, etc.)
        and ensures a clean terminal state for error messages.
        """
        # Add spacing to separate from any corrupted output
        self.console.print("\n")

        # Reset any active Live displays (though context managers should handle this)
        # This is a safety measure for edge cases

        # Print a visual separator
        self.console.print("[dim]" + "─" * 60 + "[/dim]")

    # ────────────────────────────────────────────────────────────────
    # TUI-aware input helpers (stays in alternate screen mode)
    # ────────────────────────────────────────────────────────────────

    def confirm(self, message: str, default: bool = False) -> bool:
        """
        Ask for confirmation within TUI context.

        Uses single-key input (y/n) without exiting alternate screen.
        """
        if self.tui:
            return self.tui.confirm(message, default=default)
        else:
            return Confirm.ask(message, default=default, console=self.console)

    def prompt(self, message: str, default: str = "") -> str:
        """
        Ask for text input within TUI context.

        Uses inline text editing without exiting alternate screen.
        """
        if self.tui:
            return self.tui.prompt_text(message, default=default)
        else:
            return Prompt.ask(message, default=default, console=self.console)

    def wait_for_key(self, message: str = "Press any key to continue...") -> None:
        """
        Wait for user to press any key.
        """
        if self.tui:
            self.tui.wait_for_key(message)
        else:
            input(message)

    def print_header(self, title: str, subtitle: str = "") -> None:
        """Print a formatted header"""
        content = f"[bold cyan]{title}[/bold cyan]"
        if subtitle:
            content += f"\n[dim]{subtitle}[/dim]"

        self.console.print(
            Panel(
                content,
                box=box.DOUBLE,
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def print_step(self, step: int, total: int, title: str, description: str = "") -> None:
        """Print a step header"""
        step_text = f"[bold magenta]Step {step}/{total}:[/bold magenta] [bold]{title}[/bold]"
        if description:
            step_text += f"\n[dim]{description}[/dim]"

        self.console.print()
        self.console.print(Panel(step_text, border_style="magenta", padding=(0, 2)))

    def print_success(self, message: str) -> None:
        """Print a success message"""
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message"""
        self.console.print(f"[bold yellow]⚠[/bold yellow]  {message}")

    def print_error(self, message: str) -> None:
        """Print an error message"""
        self.console.print(f"[bold red]✗[/bold red] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message"""
        self.console.print(f"[cyan]ℹ[/cyan]  {message}")

    def get_current_interfaces(self) -> Set[str]:
        """Get current set of network interfaces"""
        try:
            detector = USBNICDetectorFactory.create(tui_mode=True)
            interfaces = detector.detect_interfaces()
            return {iface.name for iface in interfaces}
        except Exception as e:
            self.logger.error(f"Failed to detect interfaces: {e}")
            return set()

    def get_interface_details(self, interface_name: str) -> Optional[NetworkInterface]:
        """Get details for a specific interface"""
        try:
            detector = USBNICDetectorFactory.create(tui_mode=True)
            interfaces = detector.detect_interfaces()
            for iface in interfaces:
                if iface.name == interface_name:
                    return iface
            return None
        except Exception as e:
            self.logger.error(f"Failed to get interface details: {e}")
            return None

    def step1_baseline(self) -> bool:
        """Step 1: Establish baseline with NO USB NIC connected"""
        if self.tui:
            self.tui.update_step(1, "Establish Baseline")

            # Show instructions
            content = build_content(
                Text("Before we begin:", style="bold yellow"),
                Text(""),
                Text("  • Ensure your management USB-to-Ethernet adapter is ", style="white") +
                    Text("DISCONNECTED", style="bold red"),
                Text("  • Do NOT connect any cables yet", style="white"),
                Text("  • We need to establish a baseline of existing interfaces", style="white"),
            )
            self.tui.update_body(content)

            # Get confirmation
            if not self.confirm("Is your management USB NIC DISCONNECTED?", default=False):
                self.tui.show_error("Setup Cancelled", "Please disconnect the USB NIC and try again")
                return False

            # Detect baseline with spinner
            self.tui.update_status("Detecting existing interfaces...", spinner=True)
            time.sleep(1)  # Give system time to settle
            self.state.baseline_interfaces = self.get_current_interfaces()
            self.tui.update_status("Ready")

            # Show results
            table = Table(title="Existing Interfaces (Baseline)", box=box.SIMPLE)
            table.add_column("Interface", style="cyan")
            for iface in sorted(self.state.baseline_interfaces):
                table.add_row(iface)

            content = build_content(
                Text(f"✓ Baseline established: {len(self.state.baseline_interfaces)} interfaces detected",
                     style="bold green"),
                Text(""),
                table,
            )
            self.tui.update_body(content)
        else:
            # Fallback for non-TUI mode
            self.print_step(1, 7, "Establish Baseline", "Ensure NO management USB NIC is connected")
            self.console.print()
            self.print_warning("Before we begin:")
            self.console.print("  • Ensure your management USB-to-Ethernet adapter is [bold red]DISCONNECTED[/bold red]")

            if not Confirm.ask("Is your management USB NIC DISCONNECTED?", default=False):
                self.print_error("Please disconnect the USB NIC and try again")
                return False

            time.sleep(1)
            self.state.baseline_interfaces = self.get_current_interfaces()
            self.print_success(f"Baseline established: {len(self.state.baseline_interfaces)} interfaces detected")

        return True

    def step2_insert_usb(self) -> bool:
        """Step 2: Guide user to insert USB NIC (no cable)"""
        if self.tui:
            self.tui.update_step(2, "Insert USB NIC")

            # Show instructions
            content = build_content(
                Text("Now we'll detect your management USB NIC:", style="bold cyan"),
                Text(""),
                Text("  1. ") + Text("Connect", style="bold cyan") +
                    Text(" your USB-to-Ethernet adapter to your Mac"),
                Text("  2. ") + Text("Do NOT", style="bold yellow") +
                    Text(" plug in the ethernet cable yet"),
                Text("  3. Wait for the adapter to be recognized (LED may light up)"),
            )
            self.tui.update_body(content)

            # Get confirmation
            if not self.confirm("Have you connected the USB adapter (without cable)?", default=False):
                self.tui.show_error("Setup Cancelled", "USB NIC detection cancelled")
                return False

            # Poll for new interface with spinner
            self.tui.update_status("Polling for new USB interface...", spinner=True)

            for attempt in range(30):  # 30 seconds max
                # Update body with countdown
                content = build_content(
                    Text("Scanning for new interfaces...", style="cyan"),
                    Text(""),
                    Text(f"  Elapsed: {attempt + 1}s / 30s", style="dim"),
                    Text(""),
                    Text("  Plug in your USB adapter if you haven't already.", style="yellow"),
                )
                self.tui.update_body(content)

                time.sleep(1)
                current_interfaces = self.get_current_interfaces()
                new_interfaces = current_interfaces - self.state.baseline_interfaces

                if new_interfaces:
                    self.state.detected_usb_nic = list(new_interfaces)[0]
                    break
            else:
                self.tui.update_status("Detection failed")
                self.tui.show_error(
                    "Timeout: No new USB interface detected",
                    "Try unplugging and replugging the USB adapter"
                )
                return False

            self.tui.update_status("USB NIC detected!")

            # Show interface details
            iface_details = self.get_interface_details(self.state.detected_usb_nic)
            details_table = Table(title=f"Interface Details: {self.state.detected_usb_nic}", box=box.ROUNDED)
            details_table.add_column("Property", style="cyan")
            details_table.add_column("Value", style="white")
            if iface_details:
                details_table.add_row("Name", iface_details.name)
                details_table.add_row("Hardware Port", iface_details.hardware_port or "Unknown")
                details_table.add_row("MAC Address", iface_details.mac_address or "Unknown")
                details_table.add_row("Type", "USB" if iface_details.is_usb else "Other")
            else:
                details_table.add_row("Name", self.state.detected_usb_nic)

            content = build_content(
                Text(f"✓ USB NIC detected: ", style="bold green") +
                    Text(self.state.detected_usb_nic, style="bold cyan"),
                Text(""),
                details_table,
            )
            self.tui.update_body(content)
        else:
            # Fallback for non-TUI mode
            self.print_step(2, 7, "Insert USB NIC", "Connect USB adapter WITHOUT ethernet cable")
            self.console.print()
            self.print_info("Now we'll detect your management USB NIC:")
            self.console.print("  1. [bold cyan]Connect[/bold cyan] your USB-to-Ethernet adapter to your Mac")

            if not Confirm.ask("Have you connected the USB adapter (without cable)?", default=False):
                self.print_error("Setup cancelled")
                return False

            for attempt in range(30):
                time.sleep(1)
                current_interfaces = self.get_current_interfaces()
                new_interfaces = current_interfaces - self.state.baseline_interfaces
                if new_interfaces:
                    self.state.detected_usb_nic = list(new_interfaces)[0]
                    break
            else:
                self.print_error("Timeout: No new USB interface detected")
                return False

            self.print_success(f"USB NIC detected: {self.state.detected_usb_nic}")

        return True

    def step3_connect_cable(self) -> bool:
        """Step 3: Guide user to connect ethernet cable"""
        if self.tui:
            self.tui.update_step(3, "Connect Ethernet Cable")

            # Show instructions
            content = build_content(
                Text("Now connect the ethernet cable:", style="bold cyan"),
                Text(""),
                Text("  1. Locate the ") + Text("management port", style="bold cyan") +
                    Text(" on your ") + Text("target network device", style="bold"),
                Text("     (Typically an RJ45 ethernet port)", style="dim"),
                Text("  2. ") + Text("Connect", style="bold cyan") +
                    Text(" an ethernet cable from your USB adapter to the device"),
                Text("  3. Wait for link lights on both ends"),
                Text(""),
                Text("Important:", style="bold yellow"),
                Text("  • Target device must be powered on", style="white"),
                Text("  • Cable must be securely connected on both ends", style="white"),
                Text("  • You should see link LEDs on both the USB adapter and device", style="white"),
            )
            self.tui.update_body(content)

            # Get confirmation
            if not self.confirm("Is the ethernet cable connected to target device?", default=False):
                self.tui.show_error("Setup Cancelled", "Cable connection cancelled")
                return False

            # Check for link
            self.tui.update_status("Verifying physical link...", spinner=True)
            time.sleep(2)  # Give link time to establish

            iface_details = self.get_interface_details(self.state.detected_usb_nic)
            if iface_details and iface_details.is_active:
                self.tui.update_status("Link established!")
                content = build_content(
                    Text("✓ Physical link established", style="bold green"),
                    Text(""),
                    Text(f"  Interface {self.state.detected_usb_nic} is active", style="white"),
                )
                self.tui.update_body(content)
            else:
                self.tui.update_status("No link detected", spinner=False)
                content = build_content(
                    Text("⚠ Interface shows as inactive", style="bold yellow"),
                    Text(""),
                    Text("  Cable may not be connected properly.", style="white"),
                    Text("  Check both ends of the cable and ensure target device is powered on.", style="dim"),
                )
                self.tui.update_body(content)

                if not self.confirm("Continue anyway?", default=False):
                    return False
        else:
            # Fallback for non-TUI mode
            self.print_step(3, 7, "Connect Ethernet Cable", "Connect cable between USB NIC and target device")
            self.console.print()
            self.print_info("Now connect the ethernet cable:")

            if not Confirm.ask("Is the ethernet cable connected to the target device?", default=False):
                self.print_error("Setup cancelled")
                return False

            time.sleep(2)
            iface_details = self.get_interface_details(self.state.detected_usb_nic)
            if iface_details and iface_details.is_active:
                self.print_success("Physical link established")
            else:
                self.print_warning("Interface shows as inactive")
                if not Confirm.ask("Continue anyway?", default=False):
                    return False

        return True

    def step4_configure(self) -> bool:
        """Step 4: Get configuration and apply"""
        if self.tui:
            self.tui.update_step(4, "Configure IP Address")

            # Show initial prompt with config source info
            config_source = ""
            if self.settings.config_sources:
                config_source = f"  [dim](defaults from: {self.settings.config_sources[0]})[/dim]"

            content = build_content(
                Text("Network Configuration:", style="bold cyan"),
                Text(""),
                Text("  Enter the IP addresses for your management network.", style="white"),
                Text("  Press Enter to accept defaults or type new values.", style="dim"),
                Text(config_source) if config_source else Text(""),
            )
            self.tui.update_body(content)

            # Get configuration details using settings as defaults
            device_ip = self.prompt("Target device IP", default=self.settings.device_ip)
            laptop_ip = self.prompt("Your laptop IP", default=self.settings.laptop_ip)
            netmask = self.prompt("Netmask", default=self.settings.netmask)
            mgmt_network = self.prompt("Management network (for routing)", default=self.settings.mgmt_network)

            # Create configuration
            self.state.config = NetworkConfig(
                device_ip=device_ip,
                laptop_ip=laptop_ip,
                netmask=netmask,
                mgmt_network=mgmt_network,
                device_name=self.settings.device_name
            )

            # Show configuration summary
            config_table = Table(title="Configuration Summary", box=box.DOUBLE_EDGE)
            config_table.add_column("Setting", style="cyan", no_wrap=True)
            config_table.add_column("Value", style="green")
            config_table.add_row("Interface", self.state.detected_usb_nic or "Unknown")
            config_table.add_row("Laptop IP", laptop_ip)
            config_table.add_row("Target Device IP", device_ip)
            config_table.add_row("Netmask", netmask)
            config_table.add_row("Mgmt Network Route", mgmt_network)

            content = build_content(
                Text("Review your configuration:", style="bold cyan"),
                Text(""),
                config_table,
            )
            self.tui.update_body(content)

            # Confirm
            if not self.confirm("Apply this configuration?", default=True):
                self.tui.show_error("Configuration Cancelled", "No changes were made")
                return False

            # Apply configuration
            self.tui.update_status("Applying network configuration...", spinner=True)

            try:
                configurator = USBNICConfigurator(
                    self.state.config,
                    dry_run=False,
                    skip_confirmation=True,
                    preserve_wifi=True,
                    management_location=False,
                    show_dashboard=False,
                    forced_interface=self.state.detected_usb_nic
                )
                success = configurator.configure()

                if success:
                    self.tui.update_status("Configuration applied!")
                    self.state.configured = True
                    content = build_content(
                        Text("✓ Network configuration applied successfully", style="bold green"),
                        Text(""),
                        config_table,
                    )
                    self.tui.update_body(content)
                    return True
                else:
                    self.tui.update_status("Configuration failed")
                    self.tui.show_error("Configuration Failed", "Failed to apply network settings")
                    return False

            except Exception as e:
                self.tui.update_status("Configuration failed")
                self.tui.show_error("Configuration Error", str(e))
                return False
        else:
            # Fallback for non-TUI mode
            self.print_step(4, 7, "Configure IP Address", "Set static IP on USB NIC")
            self.console.print()
            self.print_info("Network Configuration:")
            if self.settings.config_sources:
                self.console.print(f"  [dim](defaults from: {self.settings.config_sources[0]})[/dim]")

            device_ip = Prompt.ask("  Target device IP", default=self.settings.device_ip, console=self.console)
            laptop_ip = Prompt.ask("  Your laptop IP", default=self.settings.laptop_ip, console=self.console)
            netmask = Prompt.ask("  Netmask", default=self.settings.netmask, console=self.console)
            mgmt_network = Prompt.ask("  Management network", default=self.settings.mgmt_network, console=self.console)

            self.state.config = NetworkConfig(
                device_ip=device_ip, laptop_ip=laptop_ip, netmask=netmask,
                mgmt_network=mgmt_network, device_name=self.settings.device_name
            )

            if not Confirm.ask("Apply this configuration?", default=True):
                self.print_error("Configuration cancelled")
                return False

            try:
                configurator = USBNICConfigurator(
                    self.state.config, dry_run=False, skip_confirmation=True,
                    preserve_wifi=True, management_location=False, show_dashboard=False,
                    forced_interface=self.state.detected_usb_nic
                )
                if configurator.configure():
                    self.print_success("Network configuration applied successfully")
                    self.state.configured = True
                    return True
                else:
                    self.print_error("Failed to apply configuration")
                    return False
            except Exception as e:
                self.print_error(f"Configuration failed: {e}")
                return False

    def step5_verify(self) -> bool:
        """Step 5: Verify connectivity"""
        import subprocess

        if not self.state.config:
            if self.tui:
                self.tui.show_error("No Configuration", "No configuration available")
            else:
                self.print_error("No configuration available")
            return False

        if self.tui:
            self.tui.update_step(5, "Verify Connectivity")

            content = build_content(
                Text(f"Testing connectivity to target device at {self.state.config.device_ip}...", style="cyan"),
            )
            self.tui.update_body(content)
            self.tui.update_status("Pinging target device...", spinner=True)

            try:
                result = subprocess.run(
                    ["ping", "-c", "3", "-t", "2", self.state.config.device_ip],
                    capture_output=True,
                    timeout=10
                )

                if result.returncode == 0:
                    self.tui.update_status("Target device reachable!")
                    self.state.verified = True
                    content = build_content(
                        Text(f"✓ Target device is reachable at {self.state.config.device_ip}", style="bold green"),
                        Text(""),
                        Text("  Connectivity verified successfully.", style="white"),
                    )
                    self.tui.update_body(content)
                    return True
                else:
                    self.tui.update_status("Target device not reachable")
                    content = build_content(
                        Text(f"✗ Target device NOT reachable at {self.state.config.device_ip}", style="bold red"),
                        Text(""),
                        Text("Troubleshooting:", style="bold yellow"),
                        Text("  • Verify target device is powered on", style="white"),
                        Text("  • Check cable connections", style="white"),
                        Text(f"  • Verify target device is configured with {self.state.config.device_ip}", style="white"),
                        Text("  • Try accessing via vendor management tool to check configuration", style="white"),
                    )
                    self.tui.update_body(content)
                    return False

            except subprocess.TimeoutExpired:
                self.tui.update_status("Ping timeout")
                self.tui.show_error("Connectivity Test Failed", "Ping timed out")
                return False
            except Exception as e:
                self.tui.update_status("Test failed")
                self.tui.show_error("Connectivity Test Failed", str(e))
                return False
        else:
            # Fallback for non-TUI mode
            self.print_step(5, 7, "Verify Connectivity", "Test connection to target device")
            self.console.print()
            self.print_info(f"Testing connectivity to target device at {self.state.config.device_ip}...")

            try:
                result = subprocess.run(
                    ["ping", "-c", "3", "-t", "2", self.state.config.device_ip],
                    capture_output=True, timeout=10
                )

                if result.returncode == 0:
                    self.print_success(f"Target device is reachable at {self.state.config.device_ip}")
                    self.state.verified = True
                    return True
                else:
                    self.print_error(f"Target device NOT reachable at {self.state.config.device_ip}")
                    return False

            except (subprocess.TimeoutExpired, Exception) as e:
                self.print_error(f"Connectivity test failed: {e}")
                return False

    def step6_network_monitoring(self) -> None:
        """Step 6: Show network monitoring dashboard"""
        if self.tui:
            self.tui.update_step(6, "Network Monitoring")
            self.tui.update_status("Checking network status...", spinner=True)

            try:
                # Gather network status info
                wifi_status = self.wifi_monitor.get_status()
                interference = self.wifi_monitor.detect_interference()
                service_order_ok = self.service_order_manager.validate_service_order()

                # Build status content
                items = [
                    Text("Network Status:", style="bold cyan"),
                    Text(""),
                ]

                # WiFi status
                if wifi_status.get("connected"):
                    items.append(Text(f"  WiFi: ", style="white") +
                                Text("Connected", style="bold green") +
                                Text(f" ({wifi_status.get('ssid', 'Unknown')})", style="dim"))
                else:
                    items.append(Text("  WiFi: ", style="white") +
                                Text("Disconnected", style="bold yellow"))

                # Interference check
                if interference:
                    items.append(Text("  Interference: ", style="white") +
                                Text("Detected", style="bold yellow"))
                    items.append(Text(""))
                    items.append(Text("  Mitigation suggestions:", style="yellow"))
                    for strategy in self.interference_assessor.suggest_mitigation_strategies()[:3]:
                        items.append(Text(f"    • {strategy}", style="dim"))
                else:
                    items.append(Text("  Interference: ", style="white") +
                                Text("None detected", style="bold green"))

                # Service order
                items.append(Text(""))
                if service_order_ok:
                    items.append(Text("  Service Order: ", style="white") +
                                Text("Optimal", style="bold green"))
                else:
                    items.append(Text("  Service Order: ", style="white") +
                                Text("May need adjustment", style="bold yellow"))

                content = build_content(*items)
                self.tui.update_body(content)
                self.tui.update_status("Network status checked")

            except Exception as e:
                self.tui.show_error("Dashboard Error", str(e))
        else:
            # Fallback for non-TUI mode
            self.print_step(6, 7, "Network Monitoring Dashboard", "Real-time WiFi and network status")
            self.console.print()

            try:
                self.dashboard.display_status()
                if self.wifi_monitor.detect_interference():
                    self.print_warning("WiFi interference detected!")
                if self.service_order_manager.validate_service_order():
                    self.print_success("Network service order is optimal")
            except Exception as e:
                self.print_error(f"Dashboard display failed: {e}")

    def step7_summary(self) -> None:
        """Step 7: Show final summary"""
        # Build status table
        status_table = Table(title="Setup Status", box=box.HEAVY_EDGE)
        status_table.add_column("Component", style="cyan")
        status_table.add_column("Status", justify="center")

        status_table.add_row(
            "USB NIC Detected",
            "[bold green]✓[/bold green]" if self.state.detected_usb_nic else "[bold red]✗[/bold red]"
        )
        status_table.add_row(
            "Network Configured",
            "[bold green]✓[/bold green]" if self.state.configured else "[bold red]✗[/bold red]"
        )
        status_table.add_row(
            "Target Reachable",
            "[bold green]✓[/bold green]" if self.state.verified else "[bold yellow]⚠[/bold yellow]"
        )

        # Build connection details table
        conn_table = None
        if self.state.config:
            conn_table = Table(title="Connection Details", box=box.ROUNDED)
            conn_table.add_column("Property", style="cyan")
            conn_table.add_column("Value", style="white")
            conn_table.add_row("Interface", self.state.detected_usb_nic or "N/A")
            conn_table.add_row("Your IP", self.state.config.laptop_ip)
            conn_table.add_row("Target IP", self.state.config.device_ip)
            conn_table.add_row("Netmask", self.state.config.netmask)
            conn_table.add_row("Mgmt Network", self.state.config.mgmt_network)

        # Build next steps
        device_ip = self.state.config.device_ip if self.state.config else "192.0.2.1"
        next_steps = [
            Text("Next Steps:", style="bold cyan"),
            Text(""),
            Text(f"  1. Test SSH: ") + Text(f"ssh admin@{device_ip}", style="bold"),
            Text(f"  2. Test Ansible: ") + Text("ansible target-device -m ping", style="bold"),
            Text("  3. If target device not reachable, check interface configuration"),
            Text("  4. Once target responds, test access to other network devices"),
        ]

        if self.tui:
            self.tui.update_step(7, "Setup Complete")
            self.tui.update_status("Setup complete!" if self.state.verified else "Setup finished with warnings")

            items = [
                status_table,
                Text(""),
            ]
            if conn_table:
                items.append(conn_table)
                items.append(Text(""))
            items.extend(next_steps)

            content = build_content(*items)
            self.tui.update_body(content)
        else:
            # Fallback for non-TUI mode
            self.print_step(7, 7, "Setup Complete", "Configuration summary and next steps")
            self.console.print()
            self.console.print(status_table)
            if conn_table:
                self.console.print()
                self.console.print(conn_table)
            self.console.print()
            self.console.print(Panel(
                "\n".join([
                    "[bold cyan]Next Steps:[/bold cyan]",
                    "",
                    f"1. Test SSH: [bold]ssh admin@{device_ip}[/bold]",
                    "2. Test Ansible: [bold]ansible target-device -m ping[/bold]",
                    "3. If target device not reachable, check interface configuration",
                    "4. Once target responds, test access to other network devices",
                ]),
                title="What's Next?",
                border_style="green" if self.state.verified else "yellow",
                padding=(1, 2)
            ))

    def run(self) -> int:
        """Run the guided setup workflow"""
        # ──────────────────────────────────────────────────────────────
        # Pre-TUI setup (runs in normal scrolling mode)
        # ──────────────────────────────────────────────────────────────

        self.console.clear()
        self.print_header(
            "USB Management NIC - Guided Setup Wizard",
            "Interactive step-by-step configuration for out-of-band network access"
        )

        # Check platform support
        if not USBNICDetectorFactory.is_supported():
            self.print_error("Current platform is not supported")
            self.print_info("Supported platforms: macOS, Linux (experimental)")
            return 1

        # Check for previous incomplete setup (before TUI)
        resuming = self.check_resume()

        # Pre-authenticate sudo to prevent TUI corruption during setup
        if not self.ensure_sudo_authenticated():
            return 1

        # ──────────────────────────────────────────────────────────────
        # TUI mode - full-screen terminal-filling display
        # ──────────────────────────────────────────────────────────────

        try:
            # Check terminal size before entering TUI
            from .tui import get_terminal_size, MIN_WIDTH, MIN_HEIGHT
            width, height = get_terminal_size()
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                self.print_error(f"Terminal too small ({width}x{height})")
                self.print_info(f"Please resize to at least {MIN_WIDTH}x{MIN_HEIGHT}")
                return 1

            with TUIApp(console=self.console) as app:
                self.tui = app

                # Step 1: Baseline (no retry - user controlled)
                if self.state.current_step < 1:
                    if not self.step1_baseline():
                        self.save_state()
                        return 1
                    self.state.current_step = 1
                    self.save_state()
                elif resuming:
                    self.tui.update_status("Skipping Step 1 (already completed)")
                    time.sleep(0.5)

                # Step 2: Insert USB NIC (with retry - detection can fail)
                if self.state.current_step < 2:
                    if not self.run_step_with_retry(
                        self.step2_insert_usb,
                        "USB NIC detection",
                        max_retries=2
                    ):
                        self.save_state()
                        return 1
                    self.state.current_step = 2
                    self.save_state()
                elif resuming:
                    self.tui.update_status("Skipping Step 2 (already completed)")
                    time.sleep(0.5)

                # Step 3: Connect cable (with retry - link can take time)
                if self.state.current_step < 3:
                    if not self.run_step_with_retry(
                        self.step3_connect_cable,
                        "Cable connection",
                        max_retries=1
                    ):
                        self.save_state()
                        return 1
                    self.state.current_step = 3
                    self.save_state()
                elif resuming:
                    self.tui.update_status("Skipping Step 3 (already completed)")
                    time.sleep(0.5)

                # Step 4: Configure (with retry - network ops can fail)
                if self.state.current_step < 4:
                    if not self.run_step_with_retry(
                        self.step4_configure,
                        "Network configuration",
                        max_retries=1
                    ):
                        self.save_state()
                        self.suggest_rollback()
                        return 1
                    self.state.current_step = 4
                    self.save_state()
                elif resuming:
                    self.tui.update_status("Skipping Step 4 (already completed)")
                    time.sleep(0.5)

                # Step 5: Verify (with retry, allow skip - verification is non-fatal)
                if self.state.current_step < 5:
                    self.run_step_with_retry(
                        self.step5_verify,
                        "Connectivity verification",
                        max_retries=2,
                        allow_skip=True
                    )
                    self.state.current_step = 5
                    self.save_state()
                elif resuming:
                    self.tui.update_status("Skipping Step 5 (already completed)")
                    time.sleep(0.5)

                # Step 6: Network Monitoring Dashboard
                if self.state.current_step < 6:
                    self.step6_network_monitoring()
                    self.state.current_step = 6
                    self.save_state()

                # Step 7: Summary
                self.step7_summary()
                self.state.current_step = 7

                # Show final state and wait for user acknowledgment
                self.wait_for_key("Press any key to exit...")

            # Clear TUI reference after exiting context
            self.tui = None

            # Clear state on successful completion
            self.clear_state()

            # Print final message after TUI exits
            self.console.print()
            if self.state.verified:
                self.print_success("Setup completed successfully!")
            else:
                self.print_warning("Setup completed with connectivity issues.")
                self.print_info("Try checking target device interface configuration.")

            return 0 if self.state.verified else 2

        except KeyboardInterrupt:
            self.tui = None  # Clear TUI reference
            self.cleanup_terminal()
            self.print_warning("Setup cancelled by user")
            self.save_state()  # Save progress
            self.console.print()
            self.print_info("Progress saved. Run again to resume, or 'darwin-nic restore' to revert")
            return 130
        except Exception as e:
            self.tui = None  # Clear TUI reference
            self.cleanup_terminal()
            self.print_error(f"Unexpected error: {e}")
            self.logger.exception("Setup failed with exception")
            self.save_state()  # Save progress
            self.console.print()
            self.print_info("Progress saved. Run again to resume, or 'darwin-nic restore' to revert")
            return 1


def main() -> int:
    """Main entry point for guided setup"""
    # Route logging to file during TUI mode to prevent display corruption
    # Logs are written to /tmp/darwin-nic.log
    log_file = Path("/tmp/darwin-nic.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
        ]
    )

    # Suppress some noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    console = Console()
    setup = GuidedSetup(console=console)

    return setup.run()


if __name__ == "__main__":
    sys.exit(main())
