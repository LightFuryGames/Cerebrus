"""Helpers for checking a device-hosted TCP daemon from the desktop app."""

from __future__ import annotations

import socket

from cerebrus.core.devices import DeviceInfo
from cerebrus.tools.adb import AdbClient


def resolve_device_ip_for_daemon(device: DeviceInfo, client: AdbClient) -> str | None:
    """Return the reachable Wi-Fi address for a device daemon check."""
    if client.is_wireless_serial(device.serial):
        return device.serial.rsplit(":", 1)[0]
    return client.get_device_ip(device.serial)


def check_daemon_reachable(
    ip_address: str | None, port: int, timeout_s: float = 2.0
) -> bool:
    """Return whether a TCP daemon accepts a connection at the given address."""
    if not ip_address or not 1 <= port <= 65535:
        return False

    try:
        with socket.create_connection((ip_address, port), timeout=timeout_s):
            return True
    except (OSError, ValueError):
        return False
