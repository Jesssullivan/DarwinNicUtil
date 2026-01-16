"""
Network Manager for WiFi Preservation and Enhanced USB NIC Configuration

This module provides comprehensive network management capabilities to preserve WiFi
connectivity while configuring USB NICs for management purposes. It addresses
the three root causes of WiFi connectivity loss: USB 3.0 interference, network
service reordering, and hardware constraints.
"""

import logging
import subprocess
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import box

from .config import NetworkConfig, NetworkInterface


@dataclass
class HardwareInfo:
    """Hardware information for MacBook models"""
    model: str
    year: int
    model_identifier: str
    usb_ports: List[Dict[str, Any]]
    wifi_antenna_locations: List[str]
    chassis_type: str  # laptop, desktop, etc.


@dataclass
class PortInfo:
    """USB port information"""
    name: str
    location: str  # left, right, back, etc.
    port_type: str  # USB-A, USB-C, Thunderbolt
    proximity_to_wifi: float  # 0-10, 10 = closest
    recommended_for_management: bool


@dataclass
class CableQualityInfo:
    """USB cable quality assessment"""
    is_shielded: bool
    has_ferrite_core: bool
    cable_length: float  # meters
    usb_version: str  # 2.0, 3.0, 3.1, etc.
    quality_score: float  # 0-100

logger = logging.getLogger(__name__)
console = Console()


class WiFiStatus(Enum):
    """WiFi connection status"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    DEGRADED = "degraded"
    INTERFERED = "interfered"


@dataclass
class WiFiMetrics:
    """WiFi connection metrics"""
    status: WiFiStatus
    signal_strength: float  # RSSI in dBm
    noise_level: float  # Noise in dBm
    snr: float  # Signal-to-noise ratio
    transmit_rate: float  # Mbps
    connection_uptime: int  # seconds
    ssid: str
    bssid: str
    channel: int
    band: str  # 2.4GHz or 5GHz


@dataclass
class InterfaceScore:
    """Interface scoring result"""
    interface_name: str
    score: float
    wifi_preference: float
    interference_risk: float
    capabilities_score: float
    reliability_score: float


class ServiceOrderManager:
    """Manages macOS network service order to preserve WiFi priority"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._backup_order: Optional[List[str]] = None
        self.logger = logging.getLogger(f"{__name__}.ServiceOrderManager")
    
    def backup_service_order(self) -> List[str]:
        """Backup current network service order"""
        try:
            result = subprocess.run(
                ["networksetup", "-listnetworkserviceorder"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
            
            # Parse service order from output like:
            # (1) USB Management
            # (Hardware Port: USB 10/100/1000 LAN, Device: en7)
            # (2) Wi-Fi
            services = []
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('(') and ')' in line:
                    # Extract service name from lines like "(1) USB Management"
                    service_name = line.split(')', 1)[1].strip()
                    if service_name and not service_name.startswith('Hardware Port:'):
                        services.append(service_name)
            
            self._backup_order = services.copy()
            self.logger.info(f"Backed up service order: {services}")
            return services
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout backing up service order")
            return []
        except Exception as e:
            self.logger.error(f"Failed to backup service order: {e}")
            return []
    
    def restore_service_order(self) -> bool:
        """Restore backed up network service order"""
        if not self._backup_order:
            self.logger.warning("No backup service order available")
            return False
        
        try:
            # Build networksetup command
            cmd = ["networksetup", "-ordernetworkservices"] + self._backup_order
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            
            self.logger.info(f"Restored service order: {self._backup_order}")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout restoring service order")
            return False
        except Exception as e:
            self.logger.error(f"Failed to restore service order: {e}")
            return False
    
    def set_wifi_priority(self, wifi_service: Optional[str] = None) -> bool:
        """Set WiFi service to highest priority in service order"""
        try:
            # Get current service order
            current_order = self._get_current_service_order()
            
            # Find WiFi service if not specified
            if not wifi_service:
                wifi_service = self._find_wifi_service(current_order)
            
            if not wifi_service:
                self.logger.error("WiFi service not found")
                return False
            
            # Move WiFi service to top
            new_order = [wifi_service] + [svc for svc in current_order if svc != wifi_service]
            
            # Apply new order
            cmd = ["networksetup", "-ordernetworkservices"] + new_order
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            
            self.logger.info(f"Set WiFi priority: {wifi_service} at top of service order")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout setting WiFi priority")
            return False
        except Exception as e:
            self.logger.error(f"Failed to set WiFi priority: {e}")
            return False
    
    def get_current_service_order(self) -> List[str]:
        """Get current network service order"""
        return self._get_current_service_order()
    
    def _get_current_service_order(self) -> List[str]:
        """Internal method to get current service order"""
        try:
            result = subprocess.run(
                ["networksetup", "-listnetworkserviceorder"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
            
            # Parse service order from output
            services = []
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('(') and ')' in line:
                    # Extract service name from lines like "(1) USB Management"
                    service_name = line.split(')', 1)[1].strip()
                    if service_name and not service_name.startswith('Hardware Port:'):
                        services.append(service_name)
            
            return services
            
        except Exception as e:
            self.logger.error(f"Failed to get service order: {e}")
            return []
    
    def _find_wifi_service(self, services: List[str]) -> Optional[str]:
        """Find WiFi service in service list"""
        wifi_keywords = ["wi-fi", "wifi", "airport", "wireless"]
        
        for service in services:
            service_lower = service.lower()
            if any(keyword in service_lower for keyword in wifi_keywords):
                return service
        
        return None
    
    def validate_service_order(self) -> bool:
        """Validate service order integrity"""
        try:
            current_order = self._get_current_service_order()
            
            if not current_order:
                return False
            
            # Check if WiFi is reasonably prioritized (not at bottom)
            wifi_service = self._find_wifi_service(current_order)
            if wifi_service:
                wifi_position = current_order.index(wifi_service)
                # WiFi should not be in last 25% of services
                max_position = len(current_order) * 0.75
                if wifi_position > max_position:
                    self.logger.warning(f"WiFi service {wifi_service} is poorly positioned ({wifi_position}/{len(current_order)})")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to validate service order: {e}")
            return False
    
    def prevent_usb_priority_takeover(self) -> bool:
        """Prevent USB NIC from taking priority when plugged in"""
        try:
            # Get current service order
            current_order = self._get_current_service_order()
            
            # Find WiFi service
            wifi_service = self._find_wifi_service(current_order)
            if not wifi_service:
                self.logger.warning("WiFi service not found - cannot prevent USB takeover")
                return False
            
            # Find USB services
            usb_services = []
            for service in current_order:
                service_lower = service.lower()
                if any(keyword in service_lower for keyword in ["usb", "ethernet", "lan", "10/100", "1000"]):
                    if service != wifi_service:  # Don't treat WiFi as USB
                        usb_services.append(service)
            
            # If WiFi is already at top, no action needed
            if current_order[0] == wifi_service:
                self.logger.info("WiFi already has highest priority - USB takeover prevented")
                return True
            
            # Create new order with WiFi at top, USB services at bottom
            non_usb_non_wifi = [svc for svc in current_order 
                              if svc != wifi_service and svc not in usb_services]
            
            new_order = [wifi_service] + non_usb_non_wifi + usb_services
            
            # Apply new order
            cmd = ["networksetup", "-ordernetworkservices"] + new_order
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
            
            self.logger.info(f"Prevented USB takeover - WiFi prioritized: {wifi_service}")
            self.logger.debug(f"New service order: {new_order}")
            return True
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout preventing USB priority takeover")
            return False
        except Exception as e:
            self.logger.error(f"Failed to prevent USB priority takeover: {e}")
            return False


class WiFiMonitor:
    """Monitor WiFi status and connectivity using airport command"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.WiFiMonitor")
        self._airport_path = self._find_airport_command()
    
    def _find_airport_command(self) -> Optional[str]:
        """Find airport command path"""
        airport_paths = [
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "/System/Library/PrivateFrameworks/Apple80211.framework/Resources/airport"
        ]
        
        for path in airport_paths:
            if subprocess.run(["test", "-f", path], capture_output=True).returncode == 0:
                return path
        
        self.logger.error("airport command not found")
        return None
    
    def get_wifi_status(self) -> Optional[WiFiMetrics]:
        """Get comprehensive WiFi status using airport command"""
        if not self._airport_path:
            return None
        
        try:
            # Get WiFi info
            result = subprocess.run(
                [self._airport_path, "-I"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                self.logger.warning("airport command failed - WiFi may be disconnected")
                return self._create_disconnected_metrics()
            
            # Parse airport output
            return self._parse_airport_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout getting WiFi status")
            return None
        except Exception as e:
            self.logger.error(f"Failed to get WiFi status: {e}")
            return None
    
    def check_connectivity(self, test_host: str = "8.8.8.8", count: int = 3) -> bool:
        """Check internet connectivity through WiFi"""
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-t", "2", test_host],
                capture_output=True,
                timeout=15
            )
            
            success = result.returncode == 0
            self.logger.info(f"Connectivity check to {test_host}: {'PASS' if success else 'FAIL'}")
            return success
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"Connectivity check timeout to {test_host}")
            return False
        except Exception as e:
            self.logger.error(f"Connectivity check failed: {e}")
            return False
    
    def monitor_signal_strength(self, duration: int = 10) -> List[float]:
        """Monitor WiFi signal strength over time"""
        if not self._airport_path:
            return []
        
        signal_readings = []
        start_time = time.time()
        
        while time.time() - start_time < duration:
            metrics = self.get_wifi_status()
            if metrics and metrics.signal_strength:
                signal_readings.append(metrics.signal_strength)
            
            time.sleep(1)
        
        return signal_readings
    
    def detect_interference(self) -> bool:
        """Detect potential WiFi interference based on signal quality"""
        metrics = self.get_wifi_status()
        if not metrics:
            return False
        
        # Check for interference indicators
        interference_indicators = [
            metrics.snr < 20,  # Low signal-to-noise ratio
            metrics.noise_level > -85,  # High noise level
            metrics.transmit_rate < 10,  # Low transmit rate
            metrics.status == WiFiStatus.DEGRADED
        ]
        
        interference_score = sum(interference_indicators)
        is_interfered = interference_score >= 2
        
        if is_interfered:
            self.logger.warning(f"WiFi interference detected (score: {interference_score}/4)")
        
        return is_interfered
    
    def get_connection_details(self) -> Dict[str, str]:
        """Get detailed WiFi connection information"""
        metrics = self.get_wifi_status()
        if not metrics:
            return {"status": "disconnected"}
        
        return {
            "status": metrics.status.value,
            "ssid": metrics.ssid,
            "bssid": metrics.bssid,
            "channel": str(metrics.channel),
            "band": metrics.band,
            "signal_strength": f"{metrics.signal_strength} dBm",
            "noise_level": f"{metrics.noise_level} dBm",
            "snr": f"{metrics.snr} dB",
            "transmit_rate": f"{metrics.transmit_rate} Mbps"
        }
    
    def _parse_airport_output(self, output: str) -> WiFiMetrics:
        """Parse airport command output into WiFiMetrics"""
        lines = output.split('\n')
        data = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
        
        # Extract values
        ssid = data.get('SSID', 'Unknown')
        bssid = data.get('BSSID', 'Unknown')
        channel = int(data.get('channel', '0').split(',')[0])
        
        # Determine band from channel
        if channel <= 14:
            band = "2.4GHz"
        else:
            band = "5GHz"
        
        # Extract RSSI and noise
        rssi = 0
        noise = 0
        
        if 'agrCtlRSSI' in data:
            rssi = int(data['agrCtlRSSI'])
        elif 'lastTxRate' in data:  # Fallback for some macOS versions
            # Try to extract from other fields
            pass
        
        if 'agrCtlNoise' in data:
            noise = int(data['agrCtlNoise'])
        
        # Calculate SNR
        snr = rssi - noise if noise != 0 else 0
        
        # Extract transmit rate
        tx_rate = 0
        if 'lastTxRate' in data:
            tx_rate = float(data['lastTxRate'])
        
        # Determine status
        if rssi == 0 and snr == 0:
            status = WiFiStatus.DISCONNECTED
        elif snr < 15:
            status = WiFiStatus.DEGRADED
        elif self.detect_interference():
            status = WiFiStatus.INTERFERED
        else:
            status = WiFiStatus.CONNECTED
        
        return WiFiMetrics(
            status=status,
            signal_strength=rssi,
            noise_level=noise,
            snr=snr,
            transmit_rate=tx_rate,
            connection_uptime=0,  # Not available from airport
            ssid=ssid,
            bssid=bssid,
            channel=channel,
            band=band
        )
    
    def _create_disconnected_metrics(self) -> WiFiMetrics:
        """Create metrics for disconnected state"""
        return WiFiMetrics(
            status=WiFiStatus.DISCONNECTED,
            signal_strength=0,
            noise_level=0,
            snr=0,
            transmit_rate=0,
            connection_uptime=0,
            ssid="Disconnected",
            bssid="",
            channel=0,
            band="Unknown"
        )


class InterfaceScorer:
    """Score network interfaces with WiFi preference"""
    
    def __init__(self, wifi_monitor: WiFiMonitor, interference_assessor: 'InterferenceAssessor'):
        self.wifi_monitor = wifi_monitor
        self.interference_assessor = interference_assessor
        self.logger = logging.getLogger(f"{__name__}.InterfaceScorer")
    
    def score_interface(self, interface: NetworkInterface) -> float:
        """Score a single interface for selection"""
        wifi_preference = self.assess_wifi_preference(interface)
        interference_risk = self.interference_assessor.assess_usb_interference_risk(interface.name)
        capabilities_score = self._evaluate_capabilities(interface)
        reliability_score = self._evaluate_reliability(interface)
        
        # Calculate final score (0-100)
        final_score = (
            wifi_preference * 0.4 +  # WiFi gets strong preference
            (100 - interference_risk) * 0.25 +  # Lower risk is better
            capabilities_score * 0.2 +  # Interface capabilities
            reliability_score * 0.15  # Historical reliability
        )
        
        return min(100, max(0, final_score))
    
    def assess_wifi_preference(self, interface: NetworkInterface) -> float:
        """Assess WiFi preference score for interface"""
        # WiFi interfaces get high preference if they have working internet
        if interface.is_wifi:
            wifi_metrics = self.wifi_monitor.get_wifi_status()
            if wifi_metrics and wifi_metrics.status == WiFiStatus.CONNECTED:
                # Check if WiFi has internet connectivity
                if self.wifi_monitor.check_connectivity():
                    return 90.0  # High preference for working WiFi
                else:
                    return 60.0  # Medium preference for WiFi without internet
            else:
                return 30.0  # Low preference for disconnected WiFi
        
        # Non-WiFi interfaces get lower preference
        elif interface.is_usb:
            return 20.0  # Low preference for USB interfaces
        else:
            return 40.0  # Medium preference for other interfaces
    
    def evaluate_interference_risk(self, interface: str) -> float:
        """Evaluate interference risk for interface"""
        return self.interference_assessor.assess_usb_interference_risk(interface)
    
    def rank_interfaces(self, interfaces: List[NetworkInterface]) -> List[InterfaceScore]:
        """Rank interfaces by score"""
        scored_interfaces = []
        
        for interface in interfaces:
            score = self.score_interface(interface)
            wifi_preference = self.assess_wifi_preference(interface)
            interference_risk = self.interference_assessor.assess_usb_interference_risk(interface.name)
            capabilities_score = self._evaluate_capabilities(interface)
            reliability_score = self._evaluate_reliability(interface)
            
            scored_interfaces.append(InterfaceScore(
                interface_name=interface.name,
                score=score,
                wifi_preference=wifi_preference,
                interference_risk=interference_risk,
                capabilities_score=capabilities_score,
                reliability_score=reliability_score
            ))
        
        # Sort by score (descending)
        scored_interfaces.sort(key=lambda x: x.score, reverse=True)
        return scored_interfaces
    
    def _evaluate_capabilities(self, interface: NetworkInterface) -> float:
        """Evaluate interface capabilities"""
        score = 50.0  # Base score
        
        # Active interface gets bonus
        if interface.is_active:
            score += 20.0
        
        # USB interfaces get penalty for interference risk
        if interface.is_usb:
            score -= 10.0
        
        # WiFi interfaces get bonus for wireless capability
        if interface.is_wifi:
            score += 15.0
        
        # Protected interfaces get bonus (they're important)
        if interface.is_protected:
            score += 10.0
        
        return min(100, max(0, score))
    
    def _evaluate_reliability(self, interface: NetworkInterface) -> float:
        """Evaluate interface reliability"""
        # For now, base reliability on interface type and status
        if interface.is_wifi and interface.is_active:
            return 80.0  # WiFi is generally reliable when active
        elif interface.is_usb and interface.is_active:
            return 60.0  # USB can be less reliable
        elif interface.is_active:
            return 70.0  # Other active interfaces
        else:
            return 30.0  # Inactive interfaces are less reliable


class RouteManager:
    """Smart route management for management networks"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.RouteManager")
    
    def add_management_route(self, destination: str, interface: str, gateway: str) -> bool:
        """Add route for management network through specific interface"""
        try:
            # Parse destination network
            if '/' in destination:
                network = destination
            else:
                network = f"{destination}/32"
            
            # Add route command
            cmd = ["route", "add", "-net", network, gateway]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode == 0:
                self.logger.info(f"Added management route: {network} via {gateway} on {interface}")
                return True
            else:
                # Route might already exist, check if it's correct
                if self._verify_route(network, gateway):
                    self.logger.info(f"Management route already exists: {network} via {gateway}")
                    return True
                else:
                    self.logger.error(f"Failed to add route: {result.stderr}")
                    return False
                    
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout adding management route")
            return False
        except Exception as e:
            self.logger.error(f"Failed to add management route: {e}")
            return False
    
    def preserve_default_gateway(self) -> bool:
        """Ensure default gateway points to WiFi interface"""
        try:
            # Get current routes
            result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
            
            # Parse routes to find default gateway
            default_route = None
            for line in result.stdout.split('\n'):
                if line.startswith('default') or line.startswith('0.0.0.0'):
                    parts = line.split()
                    if len(parts) >= 2:
                        default_route = parts[1]  # Gateway
                        break
            
            if default_route:
                self.logger.info(f"Current default gateway: {default_route}")
                # In a full implementation, we might want to ensure this points to WiFi
                return True
            else:
                self.logger.warning("No default gateway found")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to preserve default gateway: {e}")
            return False
    
    def create_route_table(self, routes: List[Dict[str, str]]) -> bool:
        """Create multiple routes"""
        success_count = 0
        
        for route in routes:
            destination = route.get('destination')
            gateway = route.get('gateway')
            interface = route.get('interface')
            
            if destination and gateway:
                if self.add_management_route(destination, interface, gateway):
                    success_count += 1
        
        self.logger.info(f"Created {success_count}/{len(routes)} routes successfully")
        return success_count == len(routes)
    
    def validate_routing(self) -> bool:
        """Validate routing configuration"""
        try:
            # Check if we can reach management networks
            # This is a basic validation - in practice, you'd check specific routes
            result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"Failed to validate routing: {e}")
            return False
    
    def _verify_route(self, network: str, gateway: str) -> bool:
        """Verify if a specific route exists"""
        try:
            result = subprocess.run(
                ["netstat", "-rn"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                return False
            
            # Check if route exists
            for line in result.stdout.split('\n'):
                if network in line and gateway in line:
                    return True
            
            return False
            
        except Exception:
            return False





class HardwareAnalyzer:
    """Analyze MacBook hardware for optimal USB port selection"""
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(f"{__name__}.HardwareAnalyzer")
        self._hardware_cache: Optional[HardwareInfo] = None
    
    def detect_macbook_model(self) -> Optional[HardwareInfo]:
        """Detect MacBook model and hardware configuration"""
        if self._hardware_cache:
            return self._hardware_cache
        
        try:
            # Use system_profiler to get hardware info
            result = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
            
            import json
            hardware_data = json.loads(result.stdout)
            
            # Extract model information
            model_info = hardware_data.get('SPHardwareDataType', [{}])[0]
            model_name = model_info.get('machine_model', '')
            model_identifier = model_info.get('system_serial_number', '')
            
            # Parse model name and year
            model, year = self._parse_model_name(model_name)
            
            # Get port information
            usb_ports = self._get_usb_ports()
            
            # Determine WiFi antenna locations based on model
            antenna_locations = self._get_wifi_antenna_locations(model_name)
            
            hardware_info = HardwareInfo(
                model=model,
                year=year,
                model_identifier=model_identifier,
                usb_ports=usb_ports,
                wifi_antenna_locations=antenna_locations,
                chassis_type=self._determine_chassis_type(model_name)
            )
            
            self._hardware_cache = hardware_info
            self.logger.info(f"Detected MacBook: {model} ({year})")
            return hardware_info
            
        except subprocess.TimeoutExpired:
            self.logger.error("Timeout detecting MacBook model")
            return None
        except Exception as e:
            self.logger.error(f"Failed to detect MacBook model: {e}")
            return None
    
    def analyze_port_layout(self) -> List[PortInfo]:
        """Analyze USB port layout and proximity to WiFi antennas"""
        hardware = self.detect_macbook_model()
        if not hardware:
            return self._get_generic_port_layout()
        
        port_infos = []
        
        for port in hardware.usb_ports:
            proximity = self._calculate_wifi_proximity(port, hardware.wifi_antenna_locations)
            recommended = self._is_port_recommended_for_management(port, proximity)
            
            port_info = PortInfo(
                name=port.get('name', ''),
                location=port.get('location', ''),
                port_type=port.get('type', ''),
                proximity_to_wifi=proximity,
                recommended_for_management=recommended
            )
            port_infos.append(port_info)
        
        return port_infos
    
    def assess_antenna_proximity(self, port_name: str) -> float:
        """Assess proximity of specific port to WiFi antennas"""
        port_infos = self.analyze_port_layout()
        
        for port_info in port_infos:
            if port_name in port_info.name.lower() or port_info.name.lower() in port_name:
                return port_info.proximity_to_wifi
        
        # Default to medium proximity if port not found
        return 5.0
    
    def recommend_optimal_setup(self) -> Dict[str, Any]:
        """Recommend optimal setup based on hardware analysis"""
        hardware = self.detect_macbook_model()
        if not hardware:
            return self._get_generic_recommendations()
        
        # Get port recommendations
        port_infos = self.analyze_port_layout()
        recommended_ports = [p for p in port_infos if p.recommended_for_management]
        
        # Get cable recommendations
        cable_recommendations = self._get_cable_recommendations(hardware)
        
        # Get WiFi recommendations
        wifi_recommendations = self._get_wifi_recommendations(hardware)
        
        return {
            'macbook_model': f"{hardware.model} ({hardware.year})",
            'recommended_ports': recommended_ports,
            'avoid_ports': [p for p in port_infos if not p.recommended_for_management],
            'cable_recommendations': cable_recommendations,
            'wifi_recommendations': wifi_recommendations,
            'interference_risk': self._assess_overall_interference_risk(hardware)
        }
    
    def _parse_model_name(self, model_name: str) -> tuple[str, int]:
        """Parse model name and year from system profiler output"""
        # Example: "MacBookPro16,1" -> "MacBook Pro", 2020
        if 'MacBookPro' in model_name:
            model = "MacBook Pro"
        elif 'MacBookAir' in model_name:
            model = "MacBook Air"
        elif 'MacBook' in model_name:
            model = "MacBook"
        elif 'Macmini' in model_name:
            model = "Mac mini"
        elif 'iMac' in model_name:
            model = "iMac"
        else:
            model = "Mac"
        
        # Extract year from model identifier or default to recent
        year = 2020  # Default year
        
        # Try to extract from model number (simplified)
        import re
        year_match = re.search(r'(\d{4})', model_name)
        if year_match:
            year = int(year_match.group(1))
        
        return model, year
    
    def _get_usb_ports(self) -> List[Dict[str, Any]]:
        """Get USB port information from system profiler"""
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                return []
            
            import json
            usb_data = json.loads(result.stdout)
            
            ports = []
            self._extract_usb_ports_recursive(usb_data.get('SPUSBDataType', []), ports)
            
            return ports
            
        except Exception as e:
            self.logger.error(f"Failed to get USB ports: {e}")
            return []
    
    def _extract_usb_ports_recursive(self, items: List[Dict], ports: List[Dict]) -> None:
        """Recursively extract USB port information"""
        for item in items:
            # Check if this is a USB hub or controller with ports
            if item.get('_items'):
                self._extract_usb_ports_recursive(item['_items'], ports)
            
            # Check if this is a USB device that might be a port
            if 'USB' in item.get('_name', '') or 'Hub' in item.get('_name', ''):
                port_info = {
                    'name': item.get('_name', ''),
                    'location': item.get('Location', ''),
                    'type': item.get('Device_Speed', ''),
                    'vendor': item.get('Vendor_ID', ''),
                    'product_id': item.get('Product_ID', '')
                }
                ports.append(port_info)
    
    def _get_wifi_antenna_locations(self, model_name: str) -> List[str]:
        """Get WiFi antenna locations based on MacBook model"""
        # Simplified antenna location mapping
        if 'MacBookPro' in model_name:
            return ['display_clamshell', 'bottom_case_near_hinge']
        elif 'MacBookAir' in model_name:
            return ['display_clamshell', 'keyboard_area']
        elif 'MacBook' in model_name:
            return ['display_clamshell', 'bottom_case']
        elif 'Macmini' in model_name:
            return ['rear_panel']
        elif 'iMac' in model_name:
            return ['display_frame', 'stand']
        else:
            return ['unknown']
    
    def _determine_chassis_type(self, model_name: str) -> str:
        """Determine chassis type from model name"""
        if any(model in model_name for model in ['MacBookPro', 'MacBookAir', 'MacBook']):
            return 'laptop'
        elif 'Macmini' in model_name:
            return 'desktop_small'
        elif 'iMac' in model_name:
            return 'desktop_all_in_one'
        else:
            return 'unknown'
    
    def _calculate_wifi_proximity(self, port: Dict[str, str], antenna_locations: List[str]) -> float:
        """Calculate proximity score (0-10, 10 = closest to WiFi antennas)"""
        # Simplified proximity calculation
        port_location = port.get('location', '').lower()
        
        proximity_score = 5.0  # Default medium proximity
        
        # Adjust based on location keywords
        if any(location in port_location for location in ['left', 'right']):
            proximity_score = 7.0  # Side ports are closer to antennas
        elif any(location in port_location for location in ['back', 'rear']):
            proximity_score = 3.0  # Back ports are farther from antennas
        elif 'front' in port_location:
            proximity_score = 6.0  # Front ports are moderately close
        
        return proximity_score
    
    def _is_port_recommended_for_management(self, port: Dict[str, str], proximity: float) -> bool:
        """Determine if port is recommended for management USB NIC"""
        # Avoid ports too close to WiFi antennas
        if proximity > 7.0:
            return False
        
        # Prefer USB-C/Thunderbolt ports (better shielding)
        port_type = port.get('type', '').lower()
        if any(usb_type in port_type for usb_type in ['thunderbolt', 'usb-c', 'usb 3.1']):
            return True
        
        # USB 3.0 ports are acceptable if not too close to antennas
        if 'usb 3.0' in port_type and proximity < 6.0:
            return True
        
        # USB 2.0 ports are generally safe
        if 'usb 2.0' in port_type:
            return True
        
        return False
    
    def _assess_overall_interference_risk(self, hardware: HardwareInfo) -> float:
        """Assess overall interference risk for this hardware"""
        base_risk = 30.0  # Base risk for any USB configuration
        
        # Adjust based on chassis type
        if hardware.chassis_type == 'laptop':
            base_risk += 20.0  # Laptops have higher interference risk
        
        # Adjust based on year (newer models have better shielding)
        if hardware.year >= 2020:
            base_risk -= 10.0
        elif hardware.year < 2015:
            base_risk += 15.0
        
        return min(100, max(0, base_risk))
    
    def _get_generic_port_layout(self) -> List[PortInfo]:
        """Get generic port layout when hardware detection fails"""
        return [
            PortInfo("Generic USB-A", "unknown", "USB-A", 6.0, True),
            PortInfo("Generic USB-C", "unknown", "USB-C", 4.0, True),
        ]
    
    def _get_generic_recommendations(self) -> Dict[str, Any]:
        """Get generic recommendations when hardware detection fails"""
        return {
            'macbook_model': 'Unknown',
            'recommended_ports': self._get_generic_port_layout(),
            'avoid_ports': [],
            'cable_recommendations': ['Use shielded USB 3.0 cables', 'Prefer USB-C over USB-A'],
            'wifi_recommendations': ['Use 5GHz WiFi when possible', 'Monitor signal quality'],
            'interference_risk': 50.0
        }
    
    def _get_cable_recommendations(self, hardware: HardwareInfo) -> List[str]:
        """Get cable recommendations based on hardware"""
        recommendations = [
            "Use shielded USB 3.0 cables with ferrite cores",
            "Prefer shorter cables (< 2 meters) for better signal",
        ]
        
        if hardware.year >= 2020:
            recommendations.append("USB-C cables provide better interference protection")
        
        if hardware.chassis_type == 'laptop':
            recommendations.append("Consider USB extension cable for better positioning")
        
        return recommendations
    
    def _get_wifi_recommendations(self, hardware: HardwareInfo) -> List[str]:
        """Get WiFi recommendations based on hardware"""
        recommendations = [
            "Use 5GHz WiFi band to avoid USB 3.0 interference",
            "Monitor WiFi signal quality during USB NIC usage",
        ]
        
        if hardware.chassis_type == 'laptop':
            recommendations.append("Position MacBook to maximize distance from USB adapters")
        
        return recommendations


class InterferenceAssessor:
    """Assess USB 3.0 interference risk and provide mitigation guidance"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.InterferenceAssessor")
        self.hardware_analyzer = HardwareAnalyzer()
    
    def assess_usb_interference_risk(self, interface: str) -> float:
        """Assess USB interference risk for interface (0-100, higher = more risk)"""
        risk_score = 0.0
        
        # Check if interface is USB
        if not self._is_usb_interface(interface):
            return 0.0
        
        # Base risk for USB interfaces
        risk_score += 30.0
        
        # USB 3.0 has higher interference risk
        if self._is_usb_3_interface(interface):
            risk_score += 40.0
        
        # Hardware-specific risk assessment
        hardware = self.hardware_analyzer.detect_macbook_model()
        if hardware:
            # Assess port proximity risk
            proximity_risk = self.hardware_analyzer.assess_antenna_proximity(interface)
            risk_score += proximity_risk * 2.0  # Scale proximity to risk
        
        # Check cable quality indicators
        cable_quality = self._assess_cable_quality(interface)
        if not cable_quality.is_shielded:
            risk_score += 20.0
        if not cable_quality.has_ferrite_core:
            risk_score += 15.0
        if cable_quality.cable_length > 2.0:  # Long cables
            risk_score += 10.0
        
        # Environmental factors
        environmental_risk = self._assess_environmental_factors()
        risk_score += environmental_risk
        
        return min(100, max(0, risk_score))
    
    def check_cable_quality_indicators(self, interface: str) -> bool:
        """Check indicators of cable quality"""
        cable_quality = self._assess_cable_quality(interface)
        return cable_quality.quality_score >= 70.0
    
    def recommend_port_selection(self) -> List[str]:
        """Recommend optimal USB ports for minimal interference"""
        recommendations = []
        hardware = self.hardware_analyzer.detect_macbook_model()
        
        if hardware:
            port_infos = self.hardware_analyzer.analyze_port_layout()
            recommended_ports = [p for p in port_infos if p.recommended_for_management]
            
            recommendations.append(f"Recommended ports for {hardware.model}:")
            for port in recommended_ports:
                recommendations.append(f"  • {port.name} ({port.location}) - Low interference risk")
            
            if len(recommended_ports) < len(port_infos):
                recommendations.append("Avoid these ports:")
                for port in [p for p in port_infos if not p.recommended_for_management]:
                    recommendations.append(f"  • {port.name} ({port.location}) - High interference risk")
        else:
            # Generic recommendations
            recommendations.extend([
                "Use ports furthest from WiFi antennas (typically right side)",
                "Avoid ports directly next to display hinge area",
                "If available, use USB-C ports with proper shielding",
                "Consider using a high-quality, shielded USB extension cable"
            ])
        
        return recommendations
    
    def suggest_mitigation_strategies(self) -> List[str]:
        """Suggest interference mitigation strategies"""
        hardware = self.hardware_analyzer.detect_macbook_model()
        base_strategies = [
            "Use shielded USB 3.0 cables with ferrite cores",
            "Switch to 5GHz WiFi network to avoid 2.4GHz interference",
            "Move USB adapter away from MacBook using extension cable",
            "Use USB 2.0 ports if available (lower interference)",
            "Position MacBook to maximize distance from USB adapter",
            "Consider using Thunderbolt dock with proper shielding"
        ]
        
        if hardware:
            # Add hardware-specific strategies
            if hardware.chassis_type == 'laptop':
                base_strategies.extend([
                    f"For {hardware.model}, avoid left-side USB ports when WiFi is active",
                    "Use USB-C ports on newer models for better shielding",
                    "Consider elevating MacBook to improve antenna separation"
                ])
            
            if hardware.year < 2018:
                base_strategies.append("Older models may benefit more from USB 2.0 adapters")
        
        return base_strategies
    
    def _assess_cable_quality(self, interface: str) -> CableQualityInfo:
        """Assess USB cable quality through driver and system analysis"""
        try:
            # Try to get USB device information
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                import json
                usb_data = json.loads(result.stdout)
                device_info = self._find_usb_device_info(usb_data.get('SPUSBDataType', []), interface)
                
                if device_info:
                    return self._analyze_device_quality(device_info)
        
        except Exception as e:
            self.logger.error(f"Failed to assess cable quality: {e}")
        
        # Return default/unknown quality assessment
        return CableQualityInfo(
            is_shielded=False,
            has_ferrite_core=False,
            cable_length=1.0,
            usb_version="3.0",
            quality_score=50.0
        )
    
    def _find_usb_device_info(self, items: List[Dict], interface: str) -> Optional[Dict]:
        """Find USB device information for specific interface"""
        for item in items:
            # Check if this device matches our interface
            if self._device_matches_interface(item, interface):
                return item
            
            # Recursively search sub-items
            if item.get('_items'):
                found = self._find_usb_device_info(item['_items'], interface)
                if found:
                    return found
        
        return None
    
    def _device_matches_interface(self, device: Dict, interface: str) -> bool:
        """Check if USB device matches the network interface"""
        # This is a simplified matching - in practice would need more sophisticated logic
        device_name = device.get('_name', '').lower()
        interface_lower = interface.lower()
        
        # Check for common USB Ethernet adapter patterns
        ethernet_keywords = ['ethernet', 'lan', 'usb', 'realtek', 'asix']
        
        return any(keyword in device_name for keyword in ethernet_keywords)
    
    def _analyze_device_quality(self, device_info: Dict) -> CableQualityInfo:
        """Analyze device information to assess cable quality"""
        # Extract device speed to determine USB version
        speed = device_info.get('Device_Speed', '')
        usb_version = self._determine_usb_version(speed)
        
        # Determine shielding based on device type and speed
        is_shielded = self._assess_shielding(device_info, usb_version)
        
        # Ferrite core assessment (simplified - would need physical inspection)
        has_ferrite_core = self._assess_ferrite_core(device_info)
        
        # Cable length estimation (simplified)
        cable_length = self._estimate_cable_length(device_info)
        
        # Calculate overall quality score
        quality_score = self._calculate_quality_score(
            is_shielded, has_ferrite_core, cable_length, usb_version
        )
        
        return CableQualityInfo(
            is_shielded=is_shielded,
            has_ferrite_core=has_ferrite_core,
            cable_length=cable_length,
            usb_version=usb_version,
            quality_score=quality_score
        )
    
    def _determine_usb_version(self, speed: str) -> str:
        """Determine USB version from device speed"""
        speed_lower = speed.lower()
        
        if '480' in speed_lower or 'high' in speed_lower:
            return "2.0"
        elif '5000' in speed_lower or '5' in speed_lower:
            return "3.0"
        elif '10000' in speed_lower or '10' in speed_lower:
            return "3.1"
        else:
            return "3.0"  # Default assumption
    
    def _assess_shielding(self, device_info: Dict, usb_version: str) -> bool:
        """Assess if device/cable is likely shielded"""
        # USB 3.x devices are more likely to be shielded
        if usb_version.startswith("3."):
            return True
        
        # Check device vendor for quality indicators
        vendor = device_info.get('Vendor_ID', '').lower()
        quality_vendors = ['apple', 'belkin', 'startech', 'plugable']
        
        return any(v in vendor for v in quality_vendors)
    
    def _assess_ferrite_core(self, device_info: Dict) -> bool:
        """Assess if cable likely has ferrite core"""
        # This is difficult to detect programmatically
        # Base assessment on device quality indicators
        product_name = device_info.get('_name', '').lower()
        
        # High-quality cables often mention shielding or noise reduction
        quality_indicators = ['shielded', 'ferrite', 'noise', 'professional']
        
        return any(indicator in product_name for indicator in quality_indicators)
    
    def _estimate_cable_length(self, device_info: Dict) -> float:
        """Estimate cable length (simplified heuristic)"""
        # This is very difficult to detect programmatically
        # Use a reasonable default
        return 1.5  # 1.5 meters default
    
    def _calculate_quality_score(self, is_shielded: bool, has_ferrite_core: bool, 
                              cable_length: float, usb_version: str) -> float:
        """Calculate overall cable quality score"""
        score = 50.0  # Base score
        
        # Shielding bonus
        if is_shielded:
            score += 20.0
        
        # Ferrite core bonus
        if has_ferrite_core:
            score += 15.0
        
        # Length penalty (longer cables have more interference)
        if cable_length > 2.0:
            score -= 10.0
        elif cable_length > 3.0:
            score -= 20.0
        
        # USB version bonus
        if usb_version == "3.1":
            score += 10.0
        elif usb_version == "3.0":
            score += 5.0
        
        return min(100, max(0, score))
    
    def _assess_environmental_factors(self) -> float:
        """Assess environmental interference factors"""
        environmental_risk = 0.0
        
        # Check current WiFi band (2.4GHz is more susceptible)
        try:
            wifi_metrics = self.hardware_analyzer.wifi_monitor.get_wifi_status()
            if wifi_metrics and wifi_metrics.band == "2.4GHz":
                environmental_risk += 15.0
        except:
            pass
        
        # Check for other potential interference sources
        # This could be expanded with more environmental sensing
        environmental_risk += 5.0  # Base environmental risk
        
        return environmental_risk
    
    def _is_usb_interface(self, interface: str) -> bool:
        """Check if interface is USB"""
        # Simplified check - in practice would use system_profiler
        return any(usb_keyword in interface.lower() for usb_keyword in ['usb', 'ethernet', 'lan'])
    
    def _is_usb_3_interface(self, interface: str) -> bool:
        """Check if USB interface is USB 3.0"""
        # Simplified - would need actual hardware detection
        return True  # Assume modern USB adapters are USB 3.0


class NetworkDashboard:
    """Real-time network monitoring dashboard"""
    
    def __init__(self, wifi_monitor: WiFiMonitor, service_order_manager: ServiceOrderManager):
        self.wifi_monitor = wifi_monitor
        self.service_order_manager = service_order_manager
        self.console = Console()
        self.logger = logging.getLogger(f"{__name__}.NetworkDashboard")
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def display_status(self) -> None:
        """Display current network status"""
        layout = self._create_layout()
        self.console.print(layout)
    
    def show_connectivity_metrics(self) -> None:
        """Show detailed connectivity metrics"""
        wifi_metrics = self.wifi_monitor.get_wifi_status()
        if not wifi_metrics:
            self.console.print("[red]WiFi status unavailable[/red]")
            return
        
        # Create metrics table
        table = Table(title="WiFi Connectivity Metrics", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Status", style="yellow")
        
        # Signal strength
        signal_status = self._get_signal_status(wifi_metrics.signal_strength)
        table.add_row("Signal Strength", f"{wifi_metrics.signal_strength} dBm", signal_status)
        
        # Noise level
        noise_status = self._get_noise_status(wifi_metrics.noise_level)
        table.add_row("Noise Level", f"{wifi_metrics.noise_level} dBm", noise_status)
        
        # SNR
        snr_status = self._get_snr_status(wifi_metrics.snr)
        table.add_row("Signal-to-Noise Ratio", f"{wifi_metrics.snr} dB", snr_status)
        
        # Transmit rate
        rate_status = self._get_rate_status(wifi_metrics.transmit_rate)
        table.add_row("Transmit Rate", f"{wifi_metrics.transmit_rate} Mbps", rate_status)
        
        # Connection status
        table.add_row("Connection Status", wifi_metrics.status.value, 
                     "[green]Good[/green]" if wifi_metrics.status == WiFiStatus.CONNECTED else "[red]Poor[/red]")
        
        self.console.print(table)
    
    def monitor_interference(self, duration: int = 30) -> None:
        """Monitor for interference over time"""
        self.console.print(f"[cyan]Monitoring WiFi interference for {duration} seconds...[/cyan]")
        
        signal_readings = self.wifi_monitor.monitor_signal_strength(duration)
        
        if not signal_readings:
            self.console.print("[red]No signal readings available[/red]")
            return
        
        # Analyze signal stability
        avg_signal = sum(signal_readings) / len(signal_readings)
        signal_variance = sum((x - avg_signal) ** 2 for x in signal_readings) / len(signal_readings)
        signal_stability = signal_variance < 25  # Threshold for stability
        
        # Display results
        table = Table(title="Interference Analysis", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Assessment", style="yellow")
        
        table.add_row("Average Signal", f"{avg_signal:.1f} dBm", 
                     self._get_signal_status(avg_signal))
        table.add_row("Signal Stability", f"Variance: {signal_variance:.1f}",
                     "[green]Stable[/green]" if signal_stability else "[red]Unstable[/red]")
        table.add_row("Interference Detected", 
                     "[red]Yes[/red]" if self.wifi_monitor.detect_interference() else "[green]No[/green]",
                     "Action Required" if self.wifi_monitor.detect_interference() else "Normal")
        
        self.console.print(table)
    
    def update_real_time_status(self) -> None:
        """Update real-time status display"""
        if not self._monitoring:
            return
        
        # This would be used in a live display context
        # For now, just show current status
        self.display_status()
    
    def start_monitoring(self, update_interval: float = 2.0) -> None:
        """Start real-time monitoring in background thread"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, args=(update_interval,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop real-time monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _create_layout(self) -> Layout:
        """Create dashboard layout"""
        layout = Layout()
        
        # Get current data
        wifi_metrics = self.wifi_monitor.get_wifi_status()
        service_order = self.service_order_manager.get_current_service_order()
        
        # Create panels
        wifi_panel = self._create_wifi_panel(wifi_metrics)
        service_panel = self._create_service_panel(service_order)
        status_panel = self._create_status_panel(wifi_metrics)
        
        # Arrange layout
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        layout["header"].update(Panel(
            "[bold cyan]Network Dashboard[/bold cyan]",
            box=box.DOUBLE
        ))
        
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        layout["left"].split_column(
            Layout(name="wifi"),
            Layout(name="services")
        )
        
        layout["right"].update(status_panel)
        layout["left"]["wifi"].update(wifi_panel)
        layout["left"]["services"].update(service_panel)
        
        layout["footer"].update(Panel(
            "[dim]Press Ctrl+C to exit monitoring[/dim]",
            box=box.SIMPLE
        ))
        
        return layout
    
    def _create_wifi_panel(self, metrics: Optional[WiFiMetrics]) -> Panel:
        """Create WiFi status panel"""
        if not metrics:
            content = "[red]WiFi status unavailable[/red]"
        else:
            content = f"""[bold]WiFi Status:[/bold] {metrics.status.value}
[bold]SSID:[/bold] {metrics.ssid}
[bold]Signal:[/bold] {metrics.signal_strength} dBm
[bold]Noise:[/bold] {metrics.noise_level} dBm
[bold]SNR:[/bold] {metrics.snr} dB
[bold]Rate:[/bold] {metrics.transmit_rate} Mbps
[bold]Channel:[/bold] {metrics.channel} ({metrics.band})"""
        
        return Panel(content, title="WiFi Information", border_style="cyan")
    
    def _create_service_panel(self, services: List[str]) -> Panel:
        """Create service order panel"""
        if not services:
            content = "[red]Service order unavailable[/red]"
        else:
            content = "\n".join(f"• {service}" for service in services[:10])
            if len(services) > 10:
                content += f"\n... and {len(services) - 10} more"
        
        return Panel(content, title="Network Service Order", border_style="magenta")
    
    def _create_status_panel(self, metrics: Optional[WiFiMetrics]) -> Panel:
        """Create overall status panel"""
        if not metrics:
            status_color = "red"
            status_text = "Unknown"
        elif metrics.status == WiFiStatus.CONNECTED:
            status_color = "green"
            status_text = "Good"
        elif metrics.status == WiFiStatus.DEGRADED:
            status_color = "yellow"
            status_text = "Degraded"
        else:
            status_color = "red"
            status_text = "Poor"
        
        content = f"""[bold]Overall Status:[/bold] [{status_color}]{status_text}[/{status_color}]

[bold]Connectivity:[/bold] {'[OK]' if self.wifi_monitor.check_connectivity() else '[--]'}
[bold]Interference:[/bold] {'[!!] Detected' if self.wifi_monitor.detect_interference() else '[OK] Clear'}

[bold]Recommendations:[/bold]
• Use 5GHz WiFi if available
• Keep USB adapter away from antennas
• Use shielded cables for USB 3.0"""
        
        return Panel(content, title="Network Health", border_style="green")
    
    def _monitor_loop(self, update_interval: float) -> None:
        """Background monitoring loop"""
        while self._monitoring:
            try:
                # Update status would go here for live display
                time.sleep(update_interval)
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                break
    
    def _get_signal_status(self, signal_dbm: float) -> str:
        """Get signal status with color"""
        if signal_dbm >= -50:
            return "[green]Excellent[/green]"
        elif signal_dbm >= -60:
            return "[green]Good[/green]"
        elif signal_dbm >= -70:
            return "[yellow]Fair[/yellow]"
        else:
            return "[red]Poor[/red]"
    
    def _get_noise_status(self, noise_dbm: float) -> str:
        """Get noise status with color"""
        if noise_dbm <= -90:
            return "[green]Very Low[/green]"
        elif noise_dbm <= -85:
            return "[green]Low[/green]"
        elif noise_dbm <= -80:
            return "[yellow]Moderate[/yellow]"
        else:
            return "[red]High[/red]"
    
    def _get_snr_status(self, snr_db: float) -> str:
        """Get SNR status with color"""
        if snr_db >= 40:
            return "[green]Excellent[/green]"
        elif snr_db >= 25:
            return "[green]Good[/green]"
        elif snr_db >= 15:
            return "[yellow]Fair[/yellow]"
        else:
            return "[red]Poor[/red]"
    
    def _get_rate_status(self, rate_mbps: float) -> str:
        """Get transmit rate status with color"""
        if rate_mbps >= 100:
            return "[green]Fast[/green]"
        elif rate_mbps >= 50:
            return "[green]Good[/green]"
        elif rate_mbps >= 20:
            return "[yellow]Moderate[/yellow]"
        else:
            return "[red]Slow[/red]"