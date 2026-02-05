"""Thin wrappers around `adb` commands used by Cerebrus."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List


class AdbError(RuntimeError):
    """Raised when an adb invocation fails."""


@dataclass
class AdbClient:
    """Execute adb commands and parse their output."""

    executable: str = "adb"

    def list_devices(self) -> List[str]:
        """Return a list of connected device serial numbers."""

        result = self._run(["devices"])
        serials: list[str] = []
        for line in result.stdout.splitlines():
            if "\tdevice" in line:
                serials.append(line.split("\t", maxsplit=1)[0])
        return serials

    def get_property(self, serial: str, prop: str) -> str:
        """Fetch a system property from the device."""

        result = self._run(["-s", serial, "shell", "getprop", prop])
        return result.stdout.strip()

    def is_package_installed(self, serial: str, package_name: str) -> bool:
        """Check whether the provided package is installed on the device."""

        if not package_name:
            return False

        result = self._run(
            ["-s", serial, "shell", "pm", "list", "packages", package_name]
        )
        return package_name in result.stdout

    def pull(self, serial: str, source: str, destination: str) -> None:
        """Pull a file or directory from the device."""
        self._run(["-s", serial, "pull", source, destination])

    def shell(self, serial: str, command: List[str]) -> str:
        """Run a shell command on the device."""
        result = self._run(["-s", serial, "shell", *command])
        return result.stdout

    def send_console_command(self, serial: str, command: str) -> None:
        """Send a console command to the running Unreal Engine application."""
        # Broadcast intent with 'cmd' extra which UE listens for
        # Command: adb shell am broadcast -a android.intent.action.RUN -e cmd 'command'
        self._run(
            [
                "-s",
                serial,
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.RUN",
                "-e",
                "cmd",
                f"'{command}'",
            ]
        )

    def is_package_running(self, serial: str, package_name: str) -> bool:
        """Check if the package is currently running (has a PID)."""
        if not package_name:
            return False
        try:
            # pidof returns the PID if running, or fails if not
            result = self._run(["-s", serial, "shell", "pidof", package_name])
            return bool(result.stdout.strip())
        except AdbError:
            return False

    def _run(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        command = [self.executable, *args]
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if completed.returncode != 0:
            error_message = completed.stderr.strip() or "adb command failed"
            raise AdbError(f"{' '.join(command)}: {error_message}")
        return completed
