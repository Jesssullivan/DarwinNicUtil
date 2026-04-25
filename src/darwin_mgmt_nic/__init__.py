"""
USB Network Interface Configurator Package
USB NIC detection and configuration with factory pattern

Version 2.1.0 - Python 3.14+ with modern type system
"""

__version__ = "2.1.0"

from .config import NetworkConfig, NetworkInterface
from .configurator import USBNICConfigurator
from .detectors import USBNICDetector
from .factory import USBNICDetectorFactory
from .settings import Settings, init_config, load_settings

__all__ = [
    "NetworkConfig",
    "NetworkInterface",
    "USBNICDetector",
    "USBNICDetectorFactory",
    "USBNICConfigurator",
    "Settings",
    "load_settings",
    "init_config",
]
