from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cerebrus.tools.adb import AdbClient, AdbError


def _completed(
    stdout: str, returncode: int = 0, stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["adb"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _assert_adb_invoked(run_mock: MagicMock, expected_cmd: list[str]) -> None:
    """Assert ``subprocess.run`` was called at least once with the exact
    command list, ignoring extra kwargs the AdbClient adds (timeout, the
    Windows window-suppression flags). Tests must not pin those kwargs
    or they break the moment we tighten subprocess hygiene."""
    for call in run_mock.call_args_list:
        args, kwargs = call
        if args and list(args[0]) == expected_cmd:
            assert kwargs.get("check") is False
            assert kwargs.get("stdout") == subprocess.PIPE
            assert kwargs.get("stderr") == subprocess.PIPE
            assert kwargs.get("text") is True
            return
    raise AssertionError(
        f"expected adb call {expected_cmd!r} in {run_mock.call_args_list!r}"
    )


@patch("subprocess.run")
def test_list_devices_parses_device_lines(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed(
        "emulator-5554\tdevice\n012345\tunauthorized\nreal\tdevice"
    )

    client = AdbClient()
    devices = client.list_devices()

    assert devices == ["emulator-5554", "real"]
    _assert_adb_invoked(run_mock, ["adb", "devices"])


@patch("subprocess.run")
def test_get_property_raises_on_failure(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed("", returncode=1, stderr="boom")
    client = AdbClient()

    with pytest.raises(AdbError):
        client.get_property("serial", "ro.product.model")


@patch("subprocess.run")
def test_is_package_installed_short_circuits_for_empty_name(
    run_mock: MagicMock,
) -> None:
    client = AdbClient()

    assert client.is_package_installed("serial", "") is False
    run_mock.assert_not_called()


@patch("subprocess.run")
def test_force_stop_package(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed("")
    client = AdbClient()
    client.force_stop_package("serial", "com.test.app")
    # AdbClient.force_stop_package makes two calls: am force-stop and am broadcast
    assert run_mock.call_count == 2
    _assert_adb_invoked(
        run_mock,
        ["adb", "-s", "serial", "shell", "am", "force-stop", "com.test.app"],
    )


@patch("subprocess.run")
def test_clear_package_data(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed("")
    client = AdbClient()
    client.clear_package_data("serial", "com.test.app")
    _assert_adb_invoked(
        run_mock,
        ["adb", "-s", "serial", "shell", "pm", "clear", "com.test.app"],
    )


@patch("subprocess.run")
def test_launch_package(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed("")
    client = AdbClient()
    client.launch_package("serial", "com.test.app")

    # Now makes 2 calls: get_main_activity (dumpsys) and fallback (monkey)
    assert run_mock.call_count == 2

    # Verify fallback call
    _assert_adb_invoked(
        run_mock,
        [
            "adb",
            "-s",
            "serial",
            "shell",
            "monkey",
            "-p",
            "com.test.app",
            "-c",
            "android.intent.category.LAUNCHER",
            "1",
        ],
    )


@patch("subprocess.run")
def test_send_console_command(run_mock: MagicMock) -> None:
    run_mock.return_value = _completed("")
    client = AdbClient()
    client.send_console_command("serial", "stat unit")
    _assert_adb_invoked(
        run_mock,
        [
            "adb",
            "-s",
            "serial",
            "shell",
            "am",
            "broadcast",
            "-a",
            "android.intent.action.RUN",
            "-e",
            "cmd",
            "'stat unit'",
        ],
    )
