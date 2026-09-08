"""Thin wrappers around `adb` commands used by Cerebrus."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Default port ADB uses for TCP/IP debugging once enabled on a device.
DEFAULT_WIRELESS_PORT = 5555

# Matches adb's wireless "serial" format, e.g. "192.168.1.42:5555".
_WIRELESS_SERIAL_PATTERN = re.compile(
    r"^\d{1,3}(?:\.\d{1,3}){3}:\d{1,5}$"
)


class AdbError(RuntimeError):
    """Raised when an adb invocation fails."""


@dataclass
class AdbClient:
    """Execute adb commands and parse their output."""

    executable: str = "adb"

    def list_devices(self) -> List[str]:
        """Return a list of connected device serial numbers."""
        # Check if adb is available first? _run handles it.

        try:
            result = self._run(["devices"])
        except AdbError:
            return []

        serials: list[str] = []
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            # Expecting: <serial> <status>
            # e.g. "serial123 device" or "serial123\tdevice"
            if len(parts) >= 2 and parts[1] == "device":
                serials.append(parts[0])
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

    def push(self, serial: str, source: str, destination: str) -> None:
        """Push a file or directory to the device."""
        self._run(["-s", serial, "push", source, destination])

    def remove_file(self, serial: str, path: str) -> None:
        """Remove a file from the device."""
        self._run(["-s", serial, "shell", "rm", "-f", path])

    def list_files(self, serial: str, path: str) -> List[str]:
        """List files in a directory on the device."""
        try:
            result = self._run(["-s", serial, "shell", "ls", "-1", path])
            # Filter out error messages like "ls: /path/to/dir: No such file or directory"
            if result.stderr and (
                "No such file or directory" in result.stderr
                or "Permission denied" in result.stderr
            ):
                return []
            files = [
                f.strip()
                for f in result.stdout.splitlines()
                if f.strip() and "No such file or directory" not in f
            ]
            return files
            return []
        except AdbError:
            return []

    def get_main_activity(self, serial: str, package_name: str) -> str | None:
        """Find the main launcher activity for a package."""
        try:
            result = self._run(
                ["-s", serial, "shell", "dumpsys", "package", package_name]
            )
            # Look for categories containing LAUNCHER
            # Example: 42b667e com.test.app/com.epicgames.ue4.GameActivity filter 5c91f5
            #          Action: "android.intent.action.MAIN"
            #          Category: "android.intent.category.LAUNCHER"

            lines = result.stdout.splitlines()
            for i, line in enumerate(lines):
                if "android.intent.category.LAUNCHER" in line:
                    # Search backwards for the activity name
                    for j in range(i - 1, max(0, i - 10), -1):
                        curr_line = lines[j].strip()
                        if package_name in curr_line and "/" in curr_line:
                            # It's likely formatted like: a1b2c3d <pkg>/<activity>
                            parts = curr_line.split()
                            for p in parts:
                                if "/" in p:
                                    return p
            return None
        except Exception:
            return None

    def launch_package(self, serial: str, package_name: str) -> None:
        """
        Launch the application or bring it to foreground if already running.
        First tries 'am start' with explicit activity, falls back to monkey.
        """
        activity = self.get_main_activity(serial, package_name)
        if activity:
            try:
                self._run(["-s", serial, "shell", "am", "start", "-n", activity])
                return
            except Exception:
                pass

        # Fallback to monkey if activity not found or start fails
        result = self._run(
            [
                "-s",
                serial,
                "shell",
                "monkey",
                "-p",
                package_name,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ]
        )
        if "No activities found" in result.stdout:
            raise AdbError(f"No launchable activity found for {package_name}")

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

    def force_stop_package(self, serial: str, package_name: str) -> None:
        """Force stop the application and all its subprocesses."""
        # Standard force stop
        self._run(["-s", serial, "shell", "am", "force-stop", package_name])

        # Broadcast a kill intent if the app is listening for it (Unreal specific sometimes helps)
        try:
            self._run(
                [
                    "-s",
                    serial,
                    "shell",
                    "am",
                    "broadcast",
                    "-a",
                    "android.intent.action.PACKAGE_REMOVED",
                    "-d",
                    f"package:{package_name}",
                ]
            )
        except:
            pass

        # Optional: ensure it's removed from recents by killing the task
        # This is more intrusive and might not work on all Android versions without rooting,
        # but force-stop usually handles it.
        # For now, let's just stick to the robust force-stop and clear data.

    def minimize_package(self, serial: str) -> None:
        """Send HOME key event to minimize current app."""
        self._run(["-s", serial, "shell", "input", "keyevent", "3"])

    def clear_package_data(self, serial: str, package_name: str) -> None:
        """Clear the application data and cache using pm clear."""
        self._run(["-s", serial, "shell", "pm", "clear", package_name])

    def toggle_auto_rotate(self, serial: str, enabled: bool) -> None:
        """Enable or disable system-wide auto-rotate (accelerometer_rotation)."""
        value = "1" if enabled else "0"
        self._run(
            [
                "-s",
                serial,
                "shell",
                "settings",
                "put",
                "system",
                "accelerometer_rotation",
                value,
            ]
        )

    def remove_task_from_recents(self, serial: str, package_name: str) -> None:
        """Find the TaskId for the given package and remove it from Recents/Overview."""
        if not package_name:
            return

        try:
            # Query the recents stack
            result = self._run(
                ["-s", serial, "shell", "dumpsys", "activity", "recents"]
            )
            lines = result.stdout.splitlines()

            # Tasks in dumpsys are often grouped.
            # We look for lines containing '#' followed by a Task ID or taskId=ID,
            # then check the metadata in that block for the package name.

            current_task_id = None
            found_package_in_block = False

            import re

            # Regex to find task ID like #123 or taskId=123
            task_pattern = re.compile(r"(?:#|taskId=)(\d+)")

            for line in lines:
                task_match = task_pattern.search(line)

                if task_match:
                    # If the previous block belonged to our package, remove it
                    if current_task_id and found_package_in_block:
                        self._run(
                            [
                                "-s",
                                serial,
                                "shell",
                                "am",
                                "task",
                                "remove",
                                current_task_id,
                            ]
                        )

                    # Start tracking a new task block
                    current_task_id = task_match.group(1)
                    found_package_in_block = False

                # If we're inside a task block, check if the package name appears in the metadata
                if package_name in line:
                    found_package_in_block = True

            # Final check for the last task block in the output
            if current_task_id and found_package_in_block:
                self._run(
                    ["-s", serial, "shell", "am", "task", "remove", current_task_id]
                )

        except Exception:
            # Silently fail if parsing or command fails, as it's a non-critical cleanup step
            pass

    def clear_package_cache_only(self, serial: str, package_name: str) -> None:
        """Attempt to clear UE Saved and cache folders on SD card."""
        parts = package_name.split(".")
        if len(parts) >= 3:
            project_name = parts[-1]
            # Try to clear common Unreal cache/saved locations on SD card
            paths_to_clear = [
                f"/sdcard/Android/data/{package_name}/cache/",
                f"/sdcard/Android/data/{package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Logs/",
                f"/sdcard/Android/data/{package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Crashes/",
            ]
            for path in paths_to_clear:
                self._run(["-s", serial, "shell", "rm", "-rf", path])

    # ------------------------------------------------------------------
    # Wireless (TCP/IP) debugging
    # ------------------------------------------------------------------

    @staticmethod
    def is_wireless_serial(serial: str) -> bool:
        """Return True if `serial` looks like an adb wireless target (ip:port)."""
        return bool(_WIRELESS_SERIAL_PATTERN.match(serial))

    def get_device_ip(self, serial: str) -> Optional[str]:
        """Best-effort lookup of the device's Wi-Fi IPv4 address.

        Tries `wlan0` first (the common interface name), then falls back to
        parsing `ip route` for a default-route source address. Returns None
        if no address could be determined (e.g. Wi-Fi is off).
        """
        try:
            result = self._run(
                ["-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"]
            )
            match = re.search(r"inet\s+(\d{1,3}(?:\.\d{1,3}){3})", result.stdout)
            if match:
                return match.group(1)
        except AdbError:
            pass

        # Fallback: ask the routing table which source address would be used
        # to reach the network, which works even if the interface isn't
        # named wlan0 (some OEMs rename it).
        try:
            result = self._run(["-s", serial, "shell", "ip", "route"])
            match = re.search(r"src\s+(\d{1,3}(?:\.\d{1,3}){3})", result.stdout)
            if match:
                return match.group(1)
        except AdbError:
            pass

        return None

    def enable_tcpip(self, serial: str, port: int = DEFAULT_WIRELESS_PORT) -> bool:
        """Switch a USB-connected device into TCP/IP debugging mode.

        The device must currently be reachable (typically over USB) to run
        this command. After this succeeds, the device keeps listening for
        adb connections on `port` until it reboots or is switched back to
        USB mode with `adb usb`.
        """
        try:
            result = self._run(["-s", serial, "tcpip", str(port)])
        except AdbError:
            return False
        return "restarting" in result.stdout.lower() or result.returncode == 0

    def connect_wireless(
        self, ip_address: str, port: int = DEFAULT_WIRELESS_PORT, retries: int = 2
    ) -> Tuple[bool, str]:
        """Connect to a device already in TCP/IP mode.

        Returns (success, message). Does not raise AdbError so callers can
        surface a friendly status without a try/except for the common
        "device not reachable" case (e.g. wrong network, device asleep).
        """
        target = f"{ip_address}:{port}"
        last_output = ""
        for attempt in range(retries + 1):
            try:
                result = self._run(["connect", target])
            except AdbError as exc:
                last_output = str(exc)
                if attempt < retries:
                    time.sleep(1.0)
                    continue
                return False, last_output

            last_output = result.stdout.strip()
            lowered = last_output.lower()
            if "connected to" in lowered or "already connected" in lowered:
                return True, last_output
            if attempt < retries:
                time.sleep(1.0)

        return False, last_output or f"Could not connect to {target}"

    def disconnect_wireless(
        self, ip_address: str, port: int = DEFAULT_WIRELESS_PORT
    ) -> None:
        """Disconnect a previously-connected wireless device."""
        target = f"{ip_address}:{port}"
        try:
            self._run(["disconnect", target])
        except AdbError:
            # Already disconnected / never connected - nothing to clean up.
            pass

    def pair_wireless(self, ip_address: str, port: int, pairing_code: str) -> Tuple[bool, str]:
        """Pair with a device advertising a Wi-Fi debugging pairing code.

        This is the Android 11+ cable-free path (Settings > Developer
        options > Wireless debugging > Pair device with pairing code),
        useful when the device has no USB cable available at all. Pairing
        happens on a separate, short-lived port to the one used for
        `connect_wireless`/`enable_tcpip`; the device UI shows both.
        """
        target = f"{ip_address}:{port}"
        try:
            result = self._run(["pair", target, pairing_code])
        except AdbError as exc:
            return False, str(exc)

        output = result.stdout.strip()
        return "successfully paired" in output.lower(), output

    def enable_wireless_debugging(
        self, serial: str, port: int = DEFAULT_WIRELESS_PORT
    ) -> Tuple[bool, str, Optional[str]]:
        """Convenience flow: switch a USB device to TCP/IP mode, detect its
        IP, and connect to it wirelessly in one call.

        Returns (success, message, ip_address). On success the returned
        serial to use for subsequent AdbClient calls is f"{ip_address}:{port}".
        """
        ip_address = self.get_device_ip(serial)
        if not ip_address:
            return False, "Could not determine device IP. Is Wi-Fi enabled?", None

        if not self.enable_tcpip(serial, port):
            return False, "Failed to switch device into TCP/IP mode.", None

        # Give the device a moment to restart its adbd in TCP/IP mode
        # before we try to connect - immediate connects often fail.
        time.sleep(1.5)

        connected, message = self.connect_wireless(ip_address, port)
        return connected, message, ip_address if connected else None

    def get_battery_temperature(self, serial: str) -> Optional[float]:
        """Return the device's battery temperature in degrees Celsius.

        Parses `adb shell dumpsys battery`, which reports temperature as
        tenths of a degree Celsius (e.g. "temperature: 285" -> 28.5C).
        This works across virtually all Android devices/OEMs without root,
        unlike `dumpsys thermalservice` skin/battery zones which vary by
        vendor and Android version. Returns None if the value couldn't be
        read (e.g. device disconnected mid-poll).
        """
        try:
            result = self._run(["-s", serial, "shell", "dumpsys", "battery"])
        except AdbError:
            return None

        match = re.search(r"temperature:\s*(-?\d+)", result.stdout)
        if not match:
            return None

        return int(match.group(1)) / 10.0

    def capture_screenshot(self, serial: str) -> Optional[bytes]:
        """Capture the device's current screen as raw PNG bytes.

        Uses `adb exec-out screencap -p`, which streams the capture
        directly over the adb connection without ever writing a file to
        the device's storage (no on-device cleanup needed). Returns None
        if the capture failed (e.g. device disconnected mid-poll).

        Unlike other AdbClient methods, this can't go through `_run()`
        since that decodes output as text - a screenshot is binary.
        """
        command = [self.executable, "-s", serial, "exec-out", "screencap", "-p"]
        try:
            completed = subprocess.run(
                command,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            return None

        if completed.returncode != 0 or not completed.stdout:
            return None

        return completed.stdout

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
