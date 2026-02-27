from __future__ import annotations

from cerebrus.core.devices import DeviceInfo, collect_device_info
from cerebrus.tools.adb import AdbError


class FakeAdbClient:
    def __init__(self, installed_packages: set[str] | None = None) -> None:
        self.installed_packages = installed_packages or set()
        self.properties: dict[tuple[str, str], str] = {}
        self.serials: list[str] = []
        self.running_packages: set[str] = set()  # serial -> set of running pkgs

    def list_devices(self) -> list[str]:
        return list(self.serials)

    def get_property(self, serial: str, prop: str) -> str:
        key = (serial, prop)
        if key not in self.properties:
            raise AdbError(f"missing {prop}")
        return self.properties[key]

    def is_package_installed(self, serial: str, package_name: str) -> bool:
        return package_name in self.installed_packages

    def is_package_running(self, serial: str, package_name: str) -> bool:
        return package_name in self.running_packages


def test_collect_device_info_returns_entries_for_serials() -> None:
    client = FakeAdbClient(installed_packages={"com.test.app"})
    client.serials = ["abc", "def"]
    client.properties = {
        ("abc", "ro.product.manufacturer"): "Google",
        ("abc", "ro.product.model"): "Pixel",
        ("abc", "ro.build.version.release"): "14",
        ("abc", "ro.build.version.sdk"): "34",
        ("def", "ro.product.manufacturer"): "Samsung",
        ("def", "ro.product.model"): "Galaxy",
        ("def", "ro.build.version.release"): "13",
        ("def", "ro.build.version.sdk"): "33",
    }

    devices = collect_device_info("com.test.app", adb_client=client)

    assert devices == [
        DeviceInfo("Google", "Pixel", "abc", "14", "34", True, False),
        DeviceInfo("Samsung", "Galaxy", "def", "13", "33", True, False),
    ]


def test_collect_device_info_handles_missing_properties() -> None:
    client = FakeAdbClient()
    client.serials = ["abc"]
    client.properties = {
        ("abc", "ro.product.model"): "ModelX",
        ("abc", "ro.build.version.release"): "12",
        ("abc", "ro.build.version.sdk"): "31",
    }

    devices = collect_device_info("com.missing.app", adb_client=client)

    assert devices == [DeviceInfo("Unknown", "ModelX", "abc", "12", "31", False, False)]


def test_collect_device_info_returns_empty_when_listing_fails() -> None:
    class FailingClient(FakeAdbClient):
        def list_devices(self) -> list[str]:
            raise AdbError("adb missing")

    devices = collect_device_info("com.app", adb_client=FailingClient())

    assert devices == []
