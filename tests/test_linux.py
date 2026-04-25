"""
Tests for the Linux detector placeholder.
"""

import subprocess

from darwin_mgmt_nic.linux import LinuxUSBNICDetector


class FakeCarrierPath:
    """Path-like test double for Linux carrier files."""

    def __init__(self, value="1", *, exists=True, raises=False):
        self.value = value
        self._exists = exists
        self.raises = raises

    def exists(self):
        return self._exists

    def read_text(self):
        if self.raises:
            raise OSError("carrier unavailable")
        return self.value


def test_detect_interfaces_placeholder_returns_empty_list():
    detector = LinuxUSBNICDetector()

    assert detector.detect_interfaces() == []


def test_get_interface_status_reads_carrier(monkeypatch):
    detector = LinuxUSBNICDetector()
    monkeypatch.setattr("darwin_mgmt_nic.linux.Path", lambda path: FakeCarrierPath("1\n"))

    assert detector.get_interface_status("eth0") is True

    monkeypatch.setattr("darwin_mgmt_nic.linux.Path", lambda path: FakeCarrierPath("0\n"))

    assert detector.get_interface_status("eth0") is False


def test_get_interface_status_handles_missing_or_unreadable_carrier(monkeypatch):
    detector = LinuxUSBNICDetector()
    monkeypatch.setattr("darwin_mgmt_nic.linux.Path", lambda path: FakeCarrierPath(exists=False))

    assert detector.get_interface_status("eth0") is False

    monkeypatch.setattr("darwin_mgmt_nic.linux.Path", lambda path: FakeCarrierPath(raises=True))

    assert detector.get_interface_status("eth0") is False


def test_configure_and_route_placeholders_fail_closed():
    detector = LinuxUSBNICDetector()

    assert detector.configure_interface("eth0", "192.0.2.100", "255.255.255.0") is False
    assert detector.add_static_route("198.51.100.0/24", "192.0.2.1") is False


def test_test_connectivity_uses_ping_result(monkeypatch):
    detector = LinuxUSBNICDetector()
    commands = []

    def fake_run(cmd, **kwargs):
        commands.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)

    assert detector.test_connectivity("192.0.2.1", count=2, timeout=4) is True
    assert commands == [
        (
            ["ping", "-c", "2", "-W", "4", "192.0.2.1"],
            {"capture_output": True, "timeout": 13},
        )
    ]


def test_test_connectivity_handles_ping_failure_and_exception(monkeypatch):
    detector = LinuxUSBNICDetector()
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1))

    assert detector.test_connectivity("192.0.2.1") is False

    def raise_os_error(*args, **kwargs):
        raise OSError("ping missing")

    monkeypatch.setattr("subprocess.run", raise_os_error)

    assert detector.test_connectivity("192.0.2.1") is False
