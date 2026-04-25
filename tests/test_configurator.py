"""
Tests for main configurator
"""

from unittest.mock import ANY, MagicMock, patch

from darwin_mgmt_nic.configurator import USBNICConfigurator


class TestUSBNICConfigurator:
    """Test main configurator workflow"""

    def test_init_with_config(self, sample_network_config):
        """Test configurator initialization"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=True)
        assert configurator.config == sample_network_config
        assert configurator.dry_run is True
        assert configurator.detector is not None

    def test_init_with_custom_detector(self, sample_network_config):
        """Test configurator with custom detector"""
        mock_detector = MagicMock()
        configurator = USBNICConfigurator(sample_network_config, detector=mock_detector)
        assert configurator.detector == mock_detector

    def test_find_best_usb_interface_active(self, sample_network_config, usb_interface_active, protected_interface):
        """Test finding best USB interface with active USB"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [protected_interface, usb_interface_active]

        configurator = USBNICConfigurator(sample_network_config, detector=mock_detector)

        interface = configurator.find_best_usb_interface()
        assert interface == usb_interface_active

    def test_find_best_usb_interface_inactive_fallback(
        self, sample_network_config, usb_interface_inactive, protected_interface
    ):
        """Test falling back to inactive USB if no active ones"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [protected_interface, usb_interface_inactive]

        configurator = USBNICConfigurator(sample_network_config, detector=mock_detector)

        interface = configurator.find_best_usb_interface()
        assert interface == usb_interface_inactive

    def test_find_best_usb_interface_none_found(self, sample_network_config, protected_interface):
        """Test when no USB interfaces found"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [protected_interface]

        configurator = USBNICConfigurator(sample_network_config, detector=mock_detector)

        interface = configurator.find_best_usb_interface()
        assert interface is None

    def test_confirm_configuration_dry_run(self, sample_network_config, usb_interface_active):
        """Test confirmation in dry-run mode (auto-confirm)"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=True)
        assert configurator.confirm_configuration(usb_interface_active)

    def test_confirm_configuration_protected_interface(self, sample_network_config, protected_interface):
        """Test confirmation rejects protected interface"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert not configurator.confirm_configuration(protected_interface)

    @patch("darwin_mgmt_nic.configurator.Confirm.ask", return_value=True)
    def test_confirm_configuration_user_accepts(self, mock_confirm, sample_network_config, usb_interface_active):
        """Test user accepts configuration"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert configurator.confirm_configuration(usb_interface_active)
        mock_confirm.assert_called_once_with(
            "Proceed with configuration?",
            default=True,
            console=ANY,
        )

    @patch("darwin_mgmt_nic.configurator.Confirm.ask", return_value=False)
    def test_confirm_configuration_user_rejects(self, mock_confirm, sample_network_config, usb_interface_active):
        """Test user rejects configuration"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert not configurator.confirm_configuration(usb_interface_active)
        mock_confirm.assert_called_once()

    @patch("darwin_mgmt_nic.configurator.Confirm.ask", return_value=True)
    def test_confirm_configuration_uses_rich_confirm(self, mock_confirm, sample_network_config, usb_interface_active):
        """Test configurator delegates interactive confirmation to Rich."""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert configurator.confirm_configuration(usb_interface_active)
        mock_confirm.assert_called_once()

    def test_configure_dry_run(self, sample_network_config, usb_interface_active):
        """Test dry-run configuration (no actual changes)"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]

        configurator = USBNICConfigurator(
            sample_network_config,
            dry_run=True,
            detector=mock_detector,
            preserve_wifi=True,
        )
        configurator.service_order_manager = MagicMock()
        configurator.wifi_monitor = MagicMock()
        configurator.route_manager = MagicMock()

        result = configurator.configure()
        assert result is True

        # Verify no actual configuration was called
        mock_detector.configure_interface.assert_not_called()
        mock_detector.add_static_route.assert_not_called()
        configurator.service_order_manager.prevent_usb_priority_takeover.assert_not_called()
        configurator.service_order_manager.backup_service_order.assert_not_called()
        configurator.service_order_manager.set_wifi_priority.assert_not_called()
        configurator.wifi_monitor.get_wifi_status.assert_not_called()
        configurator.route_manager.add_management_route.assert_not_called()

    def test_configure_dry_run_without_usb_does_not_preserve_wifi(self, sample_network_config):
        """Dry-run must not mutate service order even when no USB NIC is present."""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = []

        configurator = USBNICConfigurator(
            sample_network_config,
            dry_run=True,
            detector=mock_detector,
            preserve_wifi=True,
        )
        configurator.service_order_manager = MagicMock()

        assert configurator.configure() is False
        configurator.service_order_manager.prevent_usb_priority_takeover.assert_not_called()
        configurator.service_order_manager.backup_service_order.assert_not_called()
        configurator.service_order_manager.set_wifi_priority.assert_not_called()

    @patch("darwin_mgmt_nic.configurator.Confirm.ask", return_value=True)
    def test_configure_success(self, mock_confirm, sample_network_config, usb_interface_active):
        """Test successful configuration"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]
        mock_detector.configure_interface.return_value = True
        mock_detector.test_connectivity.return_value = True

        configurator = USBNICConfigurator(sample_network_config, dry_run=False, detector=mock_detector)
        configurator.route_manager = MagicMock()

        result = configurator.configure()
        assert result is True

        # Verify methods were called
        mock_detector.configure_interface.assert_called_once()
        configurator.route_manager.add_management_route.assert_called_once_with(
            sample_network_config.mgmt_network,
            usb_interface_active.name,
            sample_network_config.device_ip,
        )
        mock_confirm.assert_called_once()

    @patch("darwin_mgmt_nic.configurator.Confirm.ask", return_value=True)
    def test_configure_failure(self, mock_confirm, sample_network_config, usb_interface_active):
        """Test failed configuration"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]
        mock_detector.configure_interface.return_value = False

        configurator = USBNICConfigurator(sample_network_config, dry_run=False, detector=mock_detector)
        configurator.route_manager = MagicMock()

        result = configurator.configure()
        assert result is False
        configurator.route_manager.add_management_route.assert_not_called()
        mock_confirm.assert_called_once()
