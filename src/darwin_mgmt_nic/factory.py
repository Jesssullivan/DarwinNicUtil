"""
Factory pattern for creating platform-specific USB NIC detectors
"""

import platform
import logging
from typing import Optional

from .config import OSType
from .detectors import USBNICDetector
from .macos import MacOSUSBNICDetector
from .linux import LinuxUSBNICDetector

logger = logging.getLogger(__name__)


class USBNICDetectorFactory:
    """
    Factory for creating platform-specific USB NIC detectors.

    Uses the factory pattern to provide appropriate detector implementation
    based on the operating system.

    Example:
        >>> detector = USBNICDetectorFactory.create()
        >>> interfaces = detector.detect_interfaces()
    """

    @staticmethod
    def create(os_type: Optional[OSType] = None, tui_mode: bool = False) -> USBNICDetector:
        """
        Create appropriate detector for specified or current platform.

        Args:
            os_type: Optional OS type. If None, auto-detect from platform.
            tui_mode: If True, use TUI-safe sudo (assumes pre-auth)

        Returns:
            Platform-specific USBNICDetector implementation

        Raises:
            NotImplementedError: If platform is not supported

        Example:
            >>> # Auto-detect platform
            >>> detector = USBNICDetectorFactory.create()

            >>> # For use in guided setup with TUI
            >>> detector = USBNICDetectorFactory.create(tui_mode=True)
        """
        if os_type is None:
            os_type = USBNICDetectorFactory._detect_os()

        match os_type:
            case OSType.MACOS:
                logger.info(f"Creating macOS USB NIC detector (TUI mode: {tui_mode})")
                return MacOSUSBNICDetector(tui_mode=tui_mode)

            case OSType.LINUX:
                logger.info("Creating Linux USB NIC detector (experimental)")
                return LinuxUSBNICDetector()

            case OSType.WINDOWS:
                raise NotImplementedError(
                    "Windows support not yet implemented. "
                    "Contributions welcome!"
                )

            case _:
                raise NotImplementedError(f"OS type {os_type} not supported")

    @staticmethod
    def _detect_os() -> OSType:
        """
        Auto-detect current operating system.

        Returns:
            Detected OSType

        Raises:
            NotImplementedError: If OS is not recognized
        """
        system = platform.system().lower()

        if system == "darwin":
            return OSType.MACOS
        elif system == "linux":
            return OSType.LINUX
        elif system in ("win32", "windows"):
            return OSType.WINDOWS
        else:
            raise NotImplementedError(
                f"Platform '{system}' not supported. "
                f"Supported platforms: macOS, Linux"
            )

    @staticmethod
    def is_supported(os_type: Optional[OSType] = None) -> bool:
        """
        Check if platform is supported.

        Args:
            os_type: OS type to check, or None for current platform

        Returns:
            True if platform is supported, False otherwise
        """
        try:
            if os_type is None:
                os_type = USBNICDetectorFactory._detect_os()

            # Currently only macOS is fully supported
            return os_type == OSType.MACOS
        except NotImplementedError:
            return False
