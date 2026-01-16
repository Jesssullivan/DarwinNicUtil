"""
Terminal-filling TUI components for guided setup.

Provides a fixed-screen layout that updates in place rather than scrolling.
Uses Rich's Layout and Live to create a proper terminal application.

Uses alternate screen mode (like vim/emacs) - exits cleanly back to shell.
"""

import os
import sys
import tty
import termios
import signal
import shutil
import itertools
from typing import Optional, Iterator, Tuple
from rich.console import Console, RenderableType, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box


# Minimum terminal size requirements
MIN_WIDTH = 60
MIN_HEIGHT = 20


def get_terminal_size() -> Tuple[int, int]:
    """Get current terminal size (width, height)."""
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


def read_single_key() -> str:
    """
    Read a single keypress without requiring Enter.

    Works in raw terminal mode to capture single characters.
    Returns the character pressed.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle escape sequences (arrow keys, etc.)
        if ch == '\x1b':
            # Read additional chars for escape sequence
            try:
                import select
                # Check if more data is available (escape sequence)
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch2 = sys.stdin.read(1)
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch3 = sys.stdin.read(1)
                        return ch + ch2 + ch3
                    return ch + ch2
            except:
                pass
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


class ProgressIndicator:
    """
    Visual step progress indicator.

    Renders as: ● ● ● ○ ○ ○ ○
    With step names below.
    """

    STEPS = ["Baseline", "USB", "Cable", "Config", "Verify", "Monitor", "Done"]

    def __init__(self):
        self.current = 0

    def set_step(self, step: int) -> None:
        """Set current step (0-indexed)"""
        self.current = min(max(0, step), len(self.STEPS) - 1)

    def render(self) -> Text:
        """Render progress indicator"""
        result = Text()

        # Progress dots
        for i in range(len(self.STEPS)):
            if i < self.current:
                result.append("● ", style="green bold")
            elif i == self.current:
                result.append("◉ ", style="cyan bold")
            else:
                result.append("○ ", style="dim")

        result.append("\n")

        # Step names
        for i, step_name in enumerate(self.STEPS):
            if i < self.current:
                result.append(step_name, style="green")
            elif i == self.current:
                result.append(step_name, style="cyan bold")
            else:
                result.append(step_name, style="dim")

            if i < len(self.STEPS) - 1:
                result.append(" → ", style="dim")

        return result


class SpinnerState:
    """Manages animated spinner state"""

    FRAMES = ["◐", "◓", "◑", "◒"]

    def __init__(self):
        self._cycle: Iterator[str] = itertools.cycle(self.FRAMES)
        self.active = False
        self.message = ""

    def set(self, message: str, active: bool = True) -> None:
        """Set spinner message and state"""
        self.message = message
        self.active = active

    def clear(self) -> None:
        """Clear spinner"""
        self.active = False
        self.message = ""

    def render(self) -> Text:
        """Render current spinner frame with message"""
        result = Text()
        if self.active:
            frame = next(self._cycle)
            result.append(f" {frame} ", style="yellow bold")
            result.append(self.message, style="yellow")
        else:
            result.append(" ✓ ", style="green bold")
            result.append(self.message or "Ready", style="green")
        return result


class TUILayout:
    """
    Manages fixed-screen TUI layout with proper terminal bounds.

    Layout structure (dynamically sized to terminal):
    ┌─────────────────────────┐
    │  Header (3-4 lines)     │  <- Title & subtitle
    ├─────────────────────────┤
    │  Progress (3 lines)     │  <- Step indicator
    ├─────────────────────────┤
    │  Body (remaining)       │  <- Main content (scrollable if needed)
    ├─────────────────────────┤
    │  Status (1 line)        │  <- Spinner/status
    └─────────────────────────┘
    """

    def __init__(self, console: Console):
        self.console = console
        self.layout = Layout()
        self.progress = ProgressIndicator()
        self.spinner = SpinnerState()
        self._step_title = "Initializing..."
        self._body_content: RenderableType = Text("Starting setup...", style="dim")

        # Get terminal size and calculate layout
        self._width, self._height = get_terminal_size()
        self._setup_layout()

        # Initialize all regions
        self._update_header()
        self._update_progress_region()
        self._update_body_region()
        self._update_status_region()

    def _setup_layout(self) -> None:
        """Setup layout with sizes appropriate for terminal."""
        # Calculate sizes based on terminal height
        # Reserve: header(4) + progress(4) + status(1) = 9 lines minimum
        # Body gets the rest

        # For small terminals, use compact header
        if self._height < 25:
            header_size = 3
            progress_size = 3
        else:
            header_size = 4
            progress_size = 4

        self.layout.split(
            Layout(name="header", size=header_size),
            Layout(name="progress", size=progress_size),
            Layout(name="body", ratio=1),  # Takes remaining space
            Layout(name="status", size=3),  # Larger status bar for prompts
        )

    def resize(self) -> None:
        """Handle terminal resize."""
        new_width, new_height = get_terminal_size()
        if new_width != self._width or new_height != self._height:
            self._width = new_width
            self._height = new_height
            self._setup_layout()
            self._update_header()
            self._update_progress_region()
            self._update_body_region()
            self._update_status_region()

    def _update_header(self) -> None:
        """Update header region"""
        # Compact header for small terminals
        if self._height < 25:
            content = "[bold cyan]USB NIC Setup Wizard[/bold cyan]"
        else:
            content = (
                "[bold cyan]USB Management NIC - Guided Setup Wizard[/bold cyan]\n"
                "[dim]Interactive configuration for out-of-band network access[/dim]"
            )

        self.layout["header"].update(Panel(
            content,
            box=box.DOUBLE,
            border_style="cyan",
            padding=(0, 1),
        ))

    def _update_progress_region(self) -> None:
        """Update progress region"""
        step_text = Text(f"Step {self.progress.current + 1}/7: ", style="bold magenta")
        step_text.append(self._step_title, style="bold")

        if self._height < 25:
            # Compact: single line
            content = Group(step_text, self.progress.render())
        else:
            content = Group(step_text, Text(""), self.progress.render())

        self.layout["progress"].update(Panel(
            content,
            box=box.SIMPLE,
            border_style="magenta",
        ))

    def _update_body_region(self) -> None:
        """Update body region"""
        self.layout["body"].update(Panel(
            self._body_content,
            box=box.ROUNDED,
            border_style="white",
            padding=(0, 1),
        ))

    def _update_status_region(self) -> None:
        """Update status region with prominent styling"""
        self.layout["status"].update(Panel(
            self.spinner.render(),
            box=box.HEAVY,
            border_style="yellow",
            padding=(0, 1),
        ))

    def update_step(self, step: int, title: str) -> None:
        """
        Update current step display.

        Args:
            step: Step number (1-7, 1-indexed for display)
            title: Step title
        """
        self.progress.set_step(step - 1)  # Convert to 0-indexed
        self._step_title = title
        self._update_progress_region()

    def update_body(self, content: RenderableType) -> None:
        """
        Update body content.

        Args:
            content: Any Rich renderable (Text, Table, Group, etc.)
        """
        self._body_content = content
        self._update_body_region()

    def update_status(self, message: str, spinner: bool = False) -> None:
        """
        Update status bar.

        Args:
            message: Status message
            spinner: If True, show animated spinner
        """
        self.spinner.set(message, active=spinner)
        self._update_status_region()

    def show_error(self, title: str, message: str) -> None:
        """
        Display error in body region with red styling.

        Args:
            title: Error title
            message: Error details
        """
        error_content = Group(
            Text(f"✗ {title}", style="bold red"),
            Text(""),
            Text(message, style="red"),
        )
        self.layout["body"].update(Panel(
            error_content,
            box=box.HEAVY,
            border_style="red",
            padding=(1, 2),
        ))

    def show_success(self, title: str, message: str = "") -> None:
        """
        Display success in body region with green styling.

        Args:
            title: Success title
            message: Optional success details
        """
        content_parts = [Text(f"✓ {title}", style="bold green")]
        if message:
            content_parts.extend([Text(""), Text(message, style="green")])

        self.layout["body"].update(Panel(
            Group(*content_parts),
            box=box.ROUNDED,
            border_style="green",
            padding=(1, 2),
        ))

    def get_layout(self) -> Layout:
        """Get the layout object for Live display"""
        return self.layout


class TUIApp:
    """
    Main TUI application wrapper.

    Manages the Live context for full-screen display and provides
    methods to update regions and handle user input.

    Uses alternate screen mode (like vim/emacs) - stays in TUI until exit.
    Input is handled with raw keyboard reads to avoid exiting alternate screen.

    Usage:
        with TUIApp() as app:
            app.update_step(1, "Establish Baseline")
            app.update_body(content)
            if app.confirm("Continue?"):
                ...
    """

    def __init__(self, console: Optional[Console] = None):
        # Configure console for proper terminal detection
        # See: https://rich.readthedocs.io/en/stable/console.html
        if console is None:
            width, height = get_terminal_size()
            self.console = Console(
                force_terminal=True,  # Ensure terminal mode
                width=width,
                height=height,
                soft_wrap=True,  # Wrap long lines
            )
        else:
            self.console = console

        self.tui = TUILayout(self.console)
        self.live: Optional[Live] = None
        self._input_buffer = ""
        self._old_sigwinch = None

    def _handle_resize(self, signum, frame) -> None:
        """Handle terminal resize signal (SIGWINCH)."""
        # Update console size
        width, height = get_terminal_size()
        self.console.size = (width, height)
        # Update layout
        self.tui.resize()
        # Refresh display
        self._refresh()

    def check_terminal_size(self) -> Tuple[bool, str]:
        """
        Check if terminal meets minimum size requirements.

        Returns:
            (ok, message) - ok is True if size is acceptable
        """
        width, height = get_terminal_size()
        if width < MIN_WIDTH or height < MIN_HEIGHT:
            return False, f"Terminal too small ({width}x{height}). Need at least {MIN_WIDTH}x{MIN_HEIGHT}."
        return True, ""

    def __enter__(self) -> 'TUIApp':
        """Enter TUI context - start Live display in alternate screen"""
        # Check terminal size
        ok, msg = self.check_terminal_size()
        if not ok:
            raise RuntimeError(msg)

        # Install resize handler
        try:
            self._old_sigwinch = signal.signal(signal.SIGWINCH, self._handle_resize)
        except (ValueError, OSError):
            # SIGWINCH not available (e.g., Windows)
            pass

        # Configure Live with proper settings for fullscreen TUI
        # See: https://rich.readthedocs.io/en/stable/live.html
        self.live = Live(
            self.tui.get_layout(),
            console=self.console,
            screen=True,  # Use alternate screen buffer (like vim/emacs)
            refresh_per_second=10,  # Higher rate for smoother updates
            transient=False,
            vertical_overflow="crop",  # CRITICAL: prevent overflow/expansion
            auto_refresh=False,  # Manual refresh for less flicker
        )
        self.live.__enter__()
        # Do initial refresh
        self.live.refresh()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit TUI context - return to normal screen"""
        # Restore original signal handler
        if self._old_sigwinch is not None:
            try:
                signal.signal(signal.SIGWINCH, self._old_sigwinch)
            except (ValueError, OSError):
                pass
            self._old_sigwinch = None

        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)
            self.live = None

        # Ensure cursor is visible
        self.console.show_cursor(True)

    def update_step(self, step: int, title: str) -> None:
        """Update current step display"""
        self.tui.update_step(step, title)
        self._refresh()

    def update_body(self, content: RenderableType) -> None:
        """Update body content"""
        self.tui.update_body(content)
        self._refresh()

    def update_status(self, message: str, spinner: bool = False) -> None:
        """Update status bar"""
        self.tui.update_status(message, spinner)
        self._refresh()

    def show_error(self, title: str, message: str) -> None:
        """Display error in body region"""
        self.tui.show_error(title, message)
        self._refresh()

    def show_success(self, title: str, message: str = "") -> None:
        """Display success in body region"""
        self.tui.show_success(title, message)
        self._refresh()

    def _refresh(self) -> None:
        """Internal refresh - updates the Live display"""
        if self.live:
            self.live.refresh()

    def refresh(self) -> None:
        """Force refresh of the display (public API)"""
        self._refresh()

    def confirm(self, message: str, default: bool = False) -> bool:
        """
        Ask yes/no question using single keypress (stays in TUI).

        Args:
            message: Question to display
            default: Default answer if Enter pressed

        Returns:
            True for yes, False for no
        """
        hint = "[Y/n]" if default else "[y/N]"
        self.tui.update_status(f"{message} {hint}", spinner=False)
        self.refresh()

        while True:
            try:
                key = read_single_key()

                # Handle Ctrl+C
                if key == '\x03':
                    raise KeyboardInterrupt()

                # Handle response
                if key.lower() == 'y':
                    self.tui.update_status("Yes", spinner=False)
                    return True
                elif key.lower() == 'n':
                    self.tui.update_status("No", spinner=False)
                    return False
                elif key in ('\r', '\n'):  # Enter = default
                    self.tui.update_status("Yes" if default else "No", spinner=False)
                    return default
                elif key == 'q':  # q to quit
                    raise KeyboardInterrupt()
                # Ignore other keys, keep waiting
            except KeyboardInterrupt:
                raise

    def prompt_text(self, message: str, default: str = "") -> str:
        """
        Prompt for text input (stays in TUI).

        Uses a simple line editor with backspace support.

        Args:
            message: Prompt message
            default: Default value

        Returns:
            User input string
        """
        self._input_buffer = default
        self._update_prompt_display(message)

        while True:
            try:
                key = read_single_key()

                # Handle Ctrl+C
                if key == '\x03':
                    raise KeyboardInterrupt()

                # Handle Enter (submit)
                if key in ('\r', '\n'):
                    result = self._input_buffer
                    self._input_buffer = ""
                    self.tui.update_status(f"Entered: {result}", spinner=False)
                    return result

                # Handle backspace
                elif key in ('\x7f', '\x08'):  # DEL or BS
                    if self._input_buffer:
                        self._input_buffer = self._input_buffer[:-1]
                        self._update_prompt_display(message)

                # Handle Ctrl+U (clear line)
                elif key == '\x15':
                    self._input_buffer = ""
                    self._update_prompt_display(message)

                # Handle Escape (cancel, use default)
                elif key.startswith('\x1b'):
                    self._input_buffer = default
                    self.tui.update_status(f"Using default: {default}", spinner=False)
                    return default

                # Handle printable characters
                elif key.isprintable():
                    self._input_buffer += key
                    self._update_prompt_display(message)

            except KeyboardInterrupt:
                raise

    def _update_prompt_display(self, message: str) -> None:
        """Update status bar with current input buffer"""
        display = f"{message}: {self._input_buffer}_"
        self.tui.update_status(display, spinner=False)
        self.refresh()

    def wait_for_key(self, message: str = "Press any key to continue...") -> str:
        """
        Wait for any keypress.

        Args:
            message: Message to display

        Returns:
            The key that was pressed
        """
        self.tui.update_status(message, spinner=False)
        self.refresh()

        key = read_single_key()

        # Handle Ctrl+C
        if key == '\x03':
            raise KeyboardInterrupt()

        return key

    def run_with_spinner(self, message: str, func, *args, **kwargs):
        """
        Run a function while showing a spinner.

        Args:
            message: Spinner message to display
            func: Function to run
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result of func(*args, **kwargs)
        """
        self.update_status(message, spinner=True)
        try:
            result = func(*args, **kwargs)
        finally:
            self.update_status("Ready", spinner=False)
        return result


def build_content(*items) -> Group:
    """
    Build a Group of content items for the body region.

    Convenience function for creating body content.

    Usage:
        content = build_content(
            Text("Title", style="bold"),
            Text(""),
            "  • First point",
            "  • Second point",
            some_table,
        )
        app.update_body(content)
    """
    renderables = []
    for item in items:
        if isinstance(item, str):
            renderables.append(Text(item))
        else:
            renderables.append(item)
    return Group(*renderables)
