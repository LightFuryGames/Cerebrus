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
