"""
USB Network Interface Configurator Package
USB NIC detection and configuration with factory pattern

Version 2.0.0 - Python 3.14+ with modern type system
"""

__version__ = "2.0.0"

from .config import NetworkConfig, NetworkInterface
from .detectors import USBNICDetector
from .factory import USBNICDetectorFactory
from .configurator import USBNICConfigurator
from .settings import Settings, load_settings, init_config

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
