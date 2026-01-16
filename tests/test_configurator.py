"""
Tests for main configurator
"""

import pytest
from unittest.mock import MagicMock, patch
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
        configurator = USBNICConfigurator(
            sample_network_config,
            detector=mock_detector
        )
        assert configurator.detector == mock_detector

    def test_find_best_usb_interface_active(
        self,
        sample_network_config,
        usb_interface_active,
        protected_interface
    ):
        """Test finding best USB interface with active USB"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [
            protected_interface,
            usb_interface_active
        ]

        configurator = USBNICConfigurator(
            sample_network_config,
            detector=mock_detector
        )

        interface = configurator.find_best_usb_interface()
        assert interface == usb_interface_active

    def test_find_best_usb_interface_inactive_fallback(
        self,
        sample_network_config,
        usb_interface_inactive,
        protected_interface
    ):
        """Test falling back to inactive USB if no active ones"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [
            protected_interface,
            usb_interface_inactive
        ]

        configurator = USBNICConfigurator(
            sample_network_config,
            detector=mock_detector
        )

        interface = configurator.find_best_usb_interface()
        assert interface == usb_interface_inactive

    def test_find_best_usb_interface_none_found(
        self,
        sample_network_config,
        protected_interface
    ):
        """Test when no USB interfaces found"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [protected_interface]

        configurator = USBNICConfigurator(
            sample_network_config,
            detector=mock_detector
        )

        interface = configurator.find_best_usb_interface()
        assert interface is None

    def test_confirm_configuration_dry_run(
        self,
        sample_network_config,
        usb_interface_active
    ):
        """Test confirmation in dry-run mode (auto-confirm)"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=True)
        assert configurator.confirm_configuration(usb_interface_active)

    def test_confirm_configuration_protected_interface(
        self,
        sample_network_config,
        protected_interface
    ):
        """Test confirmation rejects protected interface"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert not configurator.confirm_configuration(protected_interface)

    @patch('builtins.input', return_value='yes')
    def test_confirm_configuration_user_accepts(
        self,
        mock_input,
        sample_network_config,
        usb_interface_active
    ):
        """Test user accepts configuration"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert configurator.confirm_configuration(usb_interface_active)

    @patch('builtins.input', return_value='no')
    def test_confirm_configuration_user_rejects(
        self,
        mock_input,
        sample_network_config,
        usb_interface_active
    ):
        """Test user rejects configuration"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert not configurator.confirm_configuration(usb_interface_active)

    @patch('builtins.input', side_effect=['maybe', 'invalid', 'yes'])
    def test_confirm_configuration_invalid_input(
        self,
        mock_input,
        sample_network_config,
        usb_interface_active
    ):
        """Test handling invalid user input"""
        configurator = USBNICConfigurator(sample_network_config, dry_run=False)
        assert configurator.confirm_configuration(usb_interface_active)
        # Should have been called 3 times
        assert mock_input.call_count == 3

    def test_configure_dry_run(self, sample_network_config, usb_interface_active):
        """Test dry-run configuration (no actual changes)"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]

        configurator = USBNICConfigurator(
            sample_network_config,
            dry_run=True,
            detector=mock_detector
        )

        result = configurator.configure()
        assert result is True

        # Verify no actual configuration was called
        mock_detector.configure_interface.assert_not_called()
        mock_detector.add_static_route.assert_not_called()

    @patch('builtins.input', return_value='yes')
    def test_configure_success(
        self,
        mock_input,
        sample_network_config,
        usb_interface_active
    ):
        """Test successful configuration"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]
        mock_detector.configure_interface.return_value = True
        mock_detector.add_static_route.return_value = True
        mock_detector.test_connectivity.return_value = True

        configurator = USBNICConfigurator(
            sample_network_config,
            dry_run=False,
            detector=mock_detector
        )

        result = configurator.configure()
        assert result is True

        # Verify methods were called
        mock_detector.configure_interface.assert_called_once()
        mock_detector.add_static_route.assert_called_once()

    @patch('builtins.input', return_value='yes')
    def test_configure_failure(
        self,
        mock_input,
        sample_network_config,
        usb_interface_active
    ):
        """Test failed configuration"""
        mock_detector = MagicMock()
        mock_detector.detect_interfaces.return_value = [usb_interface_active]
        mock_detector.configure_interface.return_value = False

        configurator = USBNICConfigurator(
            sample_network_config,
            dry_run=False,
            detector=mock_detector
        )

        result = configurator.configure()
        assert result is False
