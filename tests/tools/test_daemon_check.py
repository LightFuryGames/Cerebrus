from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

from cerebrus.core.devices import DeviceInfo
from cerebrus.tools.daemon_check import (
    check_daemon_reachable,
    resolve_device_ip_for_daemon,
)


def _device(serial: str) -> DeviceInfo:
    return DeviceInfo(
        make="Test",
        model="Device",
        serial=serial,
        android_version="14",
        sdk_level="34",
        package_found=True,
    )


def test_resolve_device_ip_uses_wireless_serial_address() -> None:
    client = MagicMock()
    client.is_wireless_serial.return_value = True

    assert (
        resolve_device_ip_for_daemon(_device("192.168.1.25:5555"), client)
        == "192.168.1.25"
    )
    client.get_device_ip.assert_not_called()


def test_resolve_device_ip_uses_adb_for_usb_device() -> None:
    client = MagicMock()
    client.is_wireless_serial.return_value = False
    client.get_device_ip.return_value = "192.168.1.26"

    assert resolve_device_ip_for_daemon(_device("USB123"), client) == "192.168.1.26"
    client.get_device_ip.assert_called_once_with("USB123")


@patch("cerebrus.tools.daemon_check.socket.create_connection")
def test_check_daemon_reachable_returns_true_for_open_port(
    create_connection: MagicMock,
) -> None:
    assert check_daemon_reachable("192.168.1.25", 8022) is True
    create_connection.assert_called_once_with(("192.168.1.25", 8022), timeout=2.0)


@patch(
    "cerebrus.tools.daemon_check.socket.create_connection",
    side_effect=socket.timeout,
)
def test_check_daemon_reachable_returns_false_when_connection_fails(
    create_connection: MagicMock,
) -> None:
    assert check_daemon_reachable("192.168.1.25", 8022) is False
    create_connection.assert_called_once_with(("192.168.1.25", 8022), timeout=2.0)


def test_check_daemon_reachable_rejects_invalid_input() -> None:
    assert check_daemon_reachable(None, 8022) is False
    assert check_daemon_reachable("192.168.1.25", 0) is False
    assert check_daemon_reachable("192.168.1.25", 65536) is False
