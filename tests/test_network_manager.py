"""
Tests for network manager parsing, scoring, and safety helpers.
"""

import subprocess

from darwin_mgmt_nic.config import NetworkInterface
from darwin_mgmt_nic.network_manager import (
    CableQualityInfo,
    HardwareAnalyzer,
    HardwareInfo,
    InterfaceScorer,
    InterferenceAssessor,
    NetworkDashboard,
    PortInfo,
    RouteManager,
    ServiceOrderManager,
    WiFiMetrics,
    WiFiMonitor,
    WiFiStatus,
)

SERVICE_ORDER_OUTPUT = """
An asterisk (*) denotes that a network service is disabled.
(1) USB Management
(Hardware Port: USB 10/100/1000 LAN, Device: en7)
(2) Wi-Fi
(Hardware Port: Wi-Fi, Device: en0)
(3) Thunderbolt Bridge
(Hardware Port: Thunderbolt Bridge, Device: bridge0)
"""


def completed(cmd, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)


class FakeConsole:
    """Rich console test double."""

    instances = []

    def __init__(self):
        self.printed = []
        self.__class__.instances.append(self)

    def print(self, *objects, **kwargs):
        self.printed.append(objects)


class TestServiceOrderManager:
    """Test macOS service-order parsing and safety logic."""

    def test_backup_and_get_current_service_order_parse_networksetup_output(self, monkeypatch):
        commands = []

        def fake_run(cmd, **kwargs):
            commands.append(cmd)
            return completed(cmd, stdout=SERVICE_ORDER_OUTPUT)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)
        manager = ServiceOrderManager(timeout=3)

        assert manager.backup_service_order() == ["USB Management", "Wi-Fi", "Thunderbolt Bridge"]
        assert manager.get_current_service_order() == ["USB Management", "Wi-Fi", "Thunderbolt Bridge"]
        assert commands == [
            ["networksetup", "-listnetworkserviceorder"],
            ["networksetup", "-listnetworkserviceorder"],
        ]

    def test_backup_service_order_handles_command_failure_and_timeout(self, monkeypatch):
        manager = ServiceOrderManager()
        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, returncode=1, stderr="nope"),
        )

        assert manager.backup_service_order() == []

        def raise_timeout(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 10)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", raise_timeout)

        assert manager.backup_service_order() == []

    def test_restore_service_order_requires_backup_and_applies_order(self, monkeypatch):
        manager = ServiceOrderManager()

        assert manager.restore_service_order() is False

        calls = []
        manager._backup_order = ["Wi-Fi", "Thunderbolt Bridge", "USB Management"]

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return completed(cmd)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)

        assert manager.restore_service_order() is True
        assert calls == [["networksetup", "-ordernetworkservices", "Wi-Fi", "Thunderbolt Bridge", "USB Management"]]

    def test_find_wifi_service_matches_common_names(self):
        manager = ServiceOrderManager()

        assert manager._find_wifi_service(["Ethernet", "Wi-Fi"]) == "Wi-Fi"
        assert manager._find_wifi_service(["Airport", "Ethernet"]) == "Airport"
        assert manager._find_wifi_service(["USB LAN"]) is None

    def test_set_wifi_priority_moves_wifi_to_front(self, monkeypatch):
        manager = ServiceOrderManager()
        monkeypatch.setattr(manager, "_get_current_service_order", lambda: ["USB Management", "Wi-Fi", "VPN"])
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return completed(cmd)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)

        assert manager.set_wifi_priority() is True
        assert calls == [["networksetup", "-ordernetworkservices", "Wi-Fi", "USB Management", "VPN"]]

    def test_validate_service_order_rejects_empty_or_poor_wifi_position(self, monkeypatch):
        manager = ServiceOrderManager()
        monkeypatch.setattr(manager, "_get_current_service_order", lambda: [])
        assert manager.validate_service_order() is False

        monkeypatch.setattr(manager, "_get_current_service_order", lambda: ["USB", "VPN", "Bridge", "LAN", "Wi-Fi"])
        assert manager.validate_service_order() is False

        monkeypatch.setattr(manager, "_get_current_service_order", lambda: ["Wi-Fi", "USB", "VPN", "Bridge"])
        assert manager.validate_service_order() is True

    def test_prevent_usb_priority_takeover_reorders_wifi_first_usb_last(self, monkeypatch):
        manager = ServiceOrderManager()
        monkeypatch.setattr(manager, "_get_current_service_order", lambda: ["USB Ethernet", "VPN", "Wi-Fi", "LAN"])
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return completed(cmd)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)

        assert manager.prevent_usb_priority_takeover() is True
        assert calls == [["networksetup", "-ordernetworkservices", "Wi-Fi", "VPN", "USB Ethernet", "LAN"]]

    def test_prevent_usb_priority_takeover_noops_when_wifi_already_first(self, monkeypatch):
        manager = ServiceOrderManager()
        monkeypatch.setattr(manager, "_get_current_service_order", lambda: ["Wi-Fi", "USB Ethernet"])

        assert manager.prevent_usb_priority_takeover() is True


class TestWiFiMonitor:
    """Test Wi-Fi parsing and metric helpers."""

    def test_find_airport_command_returns_first_existing_path(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return completed(cmd, returncode=0 if "Current/Resources/airport" in cmd[-1] else 1)

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)

        monitor = WiFiMonitor()

        assert monitor._airport_path.endswith("Current/Resources/airport")

    def test_parse_airport_output_builds_metrics(self, monkeypatch):
        monitor = WiFiMonitor.__new__(WiFiMonitor)
        monitor.timeout = 10
        monkeypatch.setattr(monitor, "detect_interference", lambda: False)

        metrics = monitor._parse_airport_output(
            """
            agrCtlRSSI: -55
            agrCtlNoise: -92
            lastTxRate: 144.0
            SSID: labwifi
            BSSID: aa:bb:cc:dd:ee:ff
            channel: 149,1
            """
        )

        assert metrics.status == WiFiStatus.CONNECTED
        assert metrics.signal_strength == -55
        assert metrics.noise_level == -92
        assert metrics.snr == 37
        assert metrics.transmit_rate == 144.0
        assert metrics.ssid == "labwifi"
        assert metrics.band == "5GHz"

    def test_parse_airport_output_marks_degraded_and_24ghz(self, monkeypatch):
        monitor = WiFiMonitor.__new__(WiFiMonitor)
        monitor.timeout = 10
        monkeypatch.setattr(monitor, "detect_interference", lambda: False)

        metrics = monitor._parse_airport_output(
            """
            agrCtlRSSI: -80
            agrCtlNoise: -90
            lastTxRate: 8
            SSID: slowwifi
            channel: 6
            """
        )

        assert metrics.status == WiFiStatus.DEGRADED
        assert metrics.snr == 10
        assert metrics.band == "2.4GHz"

    def test_get_wifi_status_handles_missing_command_failure_timeout_and_success(self, monkeypatch):
        monitor = WiFiMonitor.__new__(WiFiMonitor)
        monitor.timeout = 10
        monitor.logger = WiFiMonitor().logger
        monitor._airport_path = None
        assert monitor.get_wifi_status() is None

        monitor._airport_path = "/airport"
        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, returncode=1),
        )
        disconnected = monitor.get_wifi_status()
        assert disconnected.status == WiFiStatus.DISCONNECTED

        monkeypatch.setattr(monitor, "_parse_airport_output", lambda output: "parsed")
        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, stdout="airport output"),
        )
        assert monitor.get_wifi_status() == "parsed"

    def test_connectivity_and_details_helpers(self, monkeypatch):
        monitor = WiFiMonitor.__new__(WiFiMonitor)
        monitor.timeout = 10
        monitor.logger = WiFiMonitor().logger
        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, returncode=0),
        )
        assert monitor.check_connectivity("1.1.1.1", count=1) is True

        metrics = WiFiMetrics(
            status=WiFiStatus.CONNECTED,
            signal_strength=-55,
            noise_level=-92,
            snr=37,
            transmit_rate=144,
            connection_uptime=0,
            ssid="labwifi",
            bssid="aa:bb:cc:dd:ee:ff",
            channel=149,
            band="5GHz",
        )
        monkeypatch.setattr(monitor, "get_wifi_status", lambda: metrics)
        details = monitor.get_connection_details()

        assert details["status"] == "connected"
        assert details["ssid"] == "labwifi"
        assert details["signal_strength"] == "-55 dBm"
        assert monitor.detect_interference() is False

        degraded = WiFiMetrics(
            status=WiFiStatus.DEGRADED,
            signal_strength=-80,
            noise_level=-70,
            snr=10,
            transmit_rate=4,
            connection_uptime=0,
            ssid="badwifi",
            bssid="",
            channel=6,
            band="2.4GHz",
        )
        monkeypatch.setattr(monitor, "get_wifi_status", lambda: degraded)
        assert monitor.detect_interference() is True

        monkeypatch.setattr(monitor, "get_wifi_status", lambda: None)
        assert monitor.get_connection_details() == {"status": "disconnected"}


class TestInterfaceScorer:
    """Test interface scoring and ranking."""

    def test_scores_and_ranks_interfaces(self):
        wifi_metrics = WiFiMetrics(
            status=WiFiStatus.CONNECTED,
            signal_strength=-50,
            noise_level=-90,
            snr=40,
            transmit_rate=300,
            connection_uptime=0,
            ssid="labwifi",
            bssid="",
            channel=149,
            band="5GHz",
        )

        class FakeWiFiMonitor:
            def get_wifi_status(self):
                return wifi_metrics

            def check_connectivity(self):
                return True

        class FakeInterferenceAssessor:
            def assess_usb_interference_risk(self, interface):
                return 70.0 if interface == "en7" else 0.0

        scorer = InterfaceScorer(FakeWiFiMonitor(), FakeInterferenceAssessor())
        wifi = NetworkInterface("en0", "Wi-Fi", is_usb=False, is_wifi=True, is_active=True, is_protected=True)
        usb = NetworkInterface("en7", "USB Ethernet", is_usb=True, is_active=True)
        inactive = NetworkInterface("en9", "USB Ethernet", is_usb=True, is_active=False)

        ranked = scorer.rank_interfaces([usb, wifi, inactive])

        assert ranked[0].interface_name == "en0"
        assert scorer.assess_wifi_preference(wifi) == 90.0
        assert scorer.assess_wifi_preference(usb) == 20.0
        assert scorer.evaluate_interference_risk("en7") == 70.0
        assert scorer._evaluate_capabilities(wifi) == 95.0
        assert scorer._evaluate_reliability(inactive) == 30.0


class TestRouteManager:
    """Test route management helpers."""

    def test_add_management_route_success_and_existing_route(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if cmd[0] == "route":
                return completed(cmd, returncode=1, stderr="exists")
            return completed(cmd, stdout="198.51.100.0/24 192.0.2.1 UGSc en7")

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)
        manager = RouteManager()

        assert manager.add_management_route("198.51.100.0/24", "en7", "192.0.2.1") is True
        assert calls[0] == ["route", "add", "-net", "198.51.100.0/24", "192.0.2.1"]

    def test_add_management_route_failure_and_host_route_normalization(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return completed(cmd, returncode=1, stderr="failed")

        monkeypatch.setattr("darwin_mgmt_nic.network_manager.subprocess.run", fake_run)
        manager = RouteManager()

        assert manager.add_management_route("192.0.2.1", "en7", "192.0.2.100") is False
        assert calls[0] == ["route", "add", "-net", "192.0.2.1/32", "192.0.2.100"]

    def test_preserve_default_gateway_and_validate_routing(self, monkeypatch):
        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, stdout="default 192.168.1.1 UGSc en0\n"),
        )
        manager = RouteManager()

        assert manager.preserve_default_gateway() is True
        assert manager.validate_routing() is True

        monkeypatch.setattr(
            "darwin_mgmt_nic.network_manager.subprocess.run",
            lambda cmd, **kwargs: completed(cmd, stdout=""),
        )
        assert manager.preserve_default_gateway() is False

    def test_create_route_table_requires_all_routes_to_succeed(self, monkeypatch):
        manager = RouteManager()
        monkeypatch.setattr(
            manager,
            "add_management_route",
            lambda destination, interface, gateway: destination != "bad",
        )

        assert (
            manager.create_route_table(
                [
                    {"destination": "198.51.100.0/24", "gateway": "192.0.2.1", "interface": "en7"},
                    {"destination": "bad", "gateway": "192.0.2.1", "interface": "en7"},
                    {"destination": "missing"},
                ]
            )
            is False
        )


class TestHardwareAndInterferenceHelpers:
    """Test hardware analysis and interference heuristics."""

    def test_hardware_model_and_port_helpers(self):
        analyzer = HardwareAnalyzer.__new__(HardwareAnalyzer)

        assert analyzer._parse_model_name("MacBookPro16,1 2020") == ("MacBook Pro", 2020)
        assert analyzer._parse_model_name("Macmini9,1") == ("Mac mini", 2020)
        assert analyzer._determine_chassis_type("MacBookAir10,1") == "laptop"
        assert analyzer._determine_chassis_type("iMac21,1") == "desktop_all_in_one"
        assert analyzer._get_wifi_antenna_locations("Macmini9,1") == ["rear_panel"]
        assert analyzer._calculate_wifi_proximity({"location": "rear panel"}, ["rear_panel"]) == 3.0
        assert analyzer._is_port_recommended_for_management({"type": "USB 2.0"}, 8.0) is False
        assert analyzer._is_port_recommended_for_management({"type": "Thunderbolt"}, 4.0) is True

        analyzer_with_layout = HardwareAnalyzer.__new__(HardwareAnalyzer)
        analyzer_with_layout.analyze_port_layout = lambda: []
        assert analyzer_with_layout.assess_antenna_proximity("unknown") == 5.0

    def test_hardware_recommendations_use_generic_fallback(self, monkeypatch):
        analyzer = HardwareAnalyzer.__new__(HardwareAnalyzer)
        analyzer.logger = HardwareAnalyzer().logger
        analyzer.timeout = 10
        monkeypatch.setattr(analyzer, "detect_macbook_model", lambda: None)

        ports = analyzer.analyze_port_layout()
        recs = analyzer.recommend_optimal_setup()

        assert all(isinstance(port, PortInfo) for port in ports)
        assert recs["macbook_model"] == "Unknown"
        assert recs["interference_risk"] == 50.0

    def test_interference_quality_and_matching_helpers(self):
        assessor = InterferenceAssessor.__new__(InterferenceAssessor)

        assert assessor._device_matches_interface({"_name": "Realtek USB LAN"}, "en7") is True
        assert assessor._device_matches_interface({"_name": "Keyboard"}, "en7") is False
        assert assessor._determine_usb_version("Up to 480 Mb/s") == "2.0"
        assert assessor._determine_usb_version("Up to 5 Gb/s") == "3.0"
        assert assessor._determine_usb_version("Up to 10 Gb/s") == "3.1"
        assert assessor._assess_shielding({"Vendor_ID": "Apple"}, "2.0") is True
        assert assessor._assess_ferrite_core({"_name": "Shielded ferrite adapter"}) is True
        assert assessor._estimate_cable_length({}) == 1.5
        assert assessor._calculate_quality_score(True, True, 1.5, "3.1") == 95.0
        assessor._assess_cable_quality = lambda interface: CableQualityInfo(False, False, 1.0, "3.0", 50.0)
        assert assessor.check_cable_quality_indicators("en7") is False

    def test_interference_risk_and_recommendations(self, monkeypatch):
        assessor = InterferenceAssessor.__new__(InterferenceAssessor)
        assessor.logger = InterferenceAssessor().logger
        hardware = HardwareInfo(
            model="MacBook Pro",
            year=2021,
            model_identifier="MacBookPro18,3",
            usb_ports=[],
            wifi_antenna_locations=["display_clamshell"],
            chassis_type="laptop",
        )
        assessor.hardware_analyzer = HardwareAnalyzer.__new__(HardwareAnalyzer)
        monkeypatch.setattr(assessor.hardware_analyzer, "detect_macbook_model", lambda: hardware)
        monkeypatch.setattr(assessor.hardware_analyzer, "assess_antenna_proximity", lambda interface: 5.0)
        monkeypatch.setattr(assessor.hardware_analyzer, "analyze_port_layout", lambda: [])
        monkeypatch.setattr(
            assessor,
            "_assess_cable_quality",
            lambda interface: CableQualityInfo(False, False, 3.0, "3.0", 40.0),
        )
        monkeypatch.setattr(assessor, "_assess_environmental_factors", lambda: 20.0)

        assert assessor.assess_usb_interference_risk("usb-ethernet") == 100
        assert assessor.assess_usb_interference_risk("en0") == 0.0
        assert "Recommended ports for MacBook Pro:" in assessor.recommend_port_selection()
        assert any("MacBook Pro" in strategy for strategy in assessor.suggest_mitigation_strategies())


class TestNetworkDashboardHelpers:
    """Test dashboard status labels and rendering branches."""

    def test_status_label_helpers(self):
        dashboard = NetworkDashboard.__new__(NetworkDashboard)

        assert dashboard._get_signal_status(-45) == "[green]Excellent[/green]"
        assert dashboard._get_signal_status(-65) == "[yellow]Fair[/yellow]"
        assert dashboard._get_noise_status(-91) == "[green]Very Low[/green]"
        assert dashboard._get_snr_status(10) == "[red]Poor[/red]"
        assert dashboard._get_rate_status(75) == "[green]Good[/green]"

    def test_panel_helpers_render_missing_and_present_data(self):
        dashboard = NetworkDashboard.__new__(NetworkDashboard)
        metrics = WiFiMetrics(
            status=WiFiStatus.CONNECTED,
            signal_strength=-55,
            noise_level=-92,
            snr=37,
            transmit_rate=144,
            connection_uptime=0,
            ssid="labwifi",
            bssid="",
            channel=149,
            band="5GHz",
        )

        assert "unavailable" in str(dashboard._create_wifi_panel(None).renderable)
        assert "labwifi" in str(dashboard._create_wifi_panel(metrics).renderable)
        assert "unavailable" in str(dashboard._create_service_panel([]).renderable)
        assert "Wi-Fi" in str(dashboard._create_service_panel(["Wi-Fi", "USB"]).renderable)
