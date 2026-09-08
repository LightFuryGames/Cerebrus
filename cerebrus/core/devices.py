"""Device collection helpers built on top of the adb tooling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from cerebrus.tools.adb import AdbClient, AdbError


@dataclass
class DeviceInfo:
    make: str
    model: str
    serial: str
    android_version: str
    sdk_level: str
    package_found: bool
    is_running: bool = False
    # "USB" or "Wireless" - derived from the shape of `serial`. Wireless
    # devices are USB-transport-free but noticeably slower for large file
    # pulls (memreports, CSVs), so the UI surfaces this distinction.
    connection_type: str = "USB"


def collect_device_info(
    package_name: str, adb_client: AdbClient | None = None
) -> List[DeviceInfo]:
    """Discover connected devices and fetch key properties.

    Returns an empty list when adb is unavailable or produces errors.
    """

    client = adb_client or AdbClient()
    try:
        serials = client.list_devices()
    except AdbError:
        return []

    devices: list[DeviceInfo] = []
    for serial in serials:
        try:
            devices.append(_read_device(serial, package_name, client))
        except AdbError:
            continue
    return devices


def _read_device(serial: str, package_name: str, client: AdbClient) -> DeviceInfo:
    make = _safe_property(client, serial, "ro.product.manufacturer")
    model = _safe_property(client, serial, "ro.product.model")
    android_version = _safe_property(client, serial, "ro.build.version.release")
    sdk_level = _safe_property(client, serial, "ro.build.version.sdk")
    package_found = client.is_package_installed(serial, package_name)
    is_running = client.is_package_running(serial, package_name)
    connection_type = "Wireless" if AdbClient.is_wireless_serial(serial) else "USB"

    return DeviceInfo(
        make=make,
        model=model,
        serial=serial,
        android_version=android_version,
        sdk_level=sdk_level,
        package_found=package_found,
        is_running=is_running,
        connection_type=connection_type,
    )


def _safe_property(client: AdbClient, serial: str, prop: str) -> str:
    try:
        value = client.get_property(serial, prop)
    except AdbError:
        value = ""
    return value or "Unknown"
