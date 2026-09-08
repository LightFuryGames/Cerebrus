"""Background battery-thermal sampling for a device, over adb.

Unreal's CSV Profiler already reports CPU temperature/throttling on
Android (`AndroidCPU/CPUTemp`, `AndroidCPU/ThermalStatus`,
`AndroidCPU/ThermalStress`), but it does not report *battery*
temperature. This module fills that gap by polling
`dumpsys battery` on a fixed interval, independent of - and running
alongside - a normal `CsvProfile Start/Stop` capture, and writing the
result to its own CSV so it can be lined up against the perf capture
by timestamp afterwards.
"""

from __future__ import annotations

import csv
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cerebrus.tools.adb import AdbClient

DEFAULT_SAMPLE_INTERVAL_SECONDS = 2.0


@dataclass
class BatteryThermalSampler:
    """Polls a device's battery temperature on a background thread and
    writes each sample to a CSV as it's collected.

    Usage:
        sampler = BatteryThermalSampler(AdbClient(), serial, output_path)
        sampler.start()
        ...
        csv_path = sampler.stop()
    """

    adb_client: AdbClient
    serial: str
    output_path: Path
    interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS

    _thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _sample_count: int = field(default=0, init=False)
    _last_error: Optional[str] = field(default=None, init=False)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def start(self) -> None:
        """Begin sampling on a daemon thread. Safe to call once; calling
        again while already running is a no-op.
        """
        if self.is_running:
            return

        self._stop_event.clear()
        self._sample_count = 0
        self._last_error = None

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> Path:
        """Signal the sampling loop to stop and wait for it to finish
        flushing its last row. Returns the path to the written CSV
        regardless of whether any samples were captured.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        return self.output_path

    def _run_loop(self) -> None:
        start_time = time.monotonic()
        try:
            with open(self.output_path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["Timestamp", "ElapsedSeconds", "BatteryTempC"])
                handle.flush()

                while not self._stop_event.is_set():
                    sample_start = time.monotonic()
                    temp_c = self.adb_client.get_battery_temperature(self.serial)
                    elapsed = time.monotonic() - start_time

                    if temp_c is not None:
                        writer.writerow(
                            [
                                time.strftime("%Y-%m-%d %H:%M:%S"),
                                f"{elapsed:.2f}",
                                f"{temp_c:.1f}",
                            ]
                        )
                        handle.flush()
                        self._sample_count += 1
                    else:
                        self._last_error = (
                            "Could not read battery temperature "
                            "(device disconnected or dumpsys unavailable)."
                        )

                    # Sleep the remainder of the interval, accounting for
                    # how long the adb round-trip itself took, so samples
                    # land close to `interval_seconds` apart rather than
                    # drifting under load.
                    remaining = self.interval_seconds - (time.monotonic() - sample_start)
                    if remaining > 0:
                        self._stop_event.wait(timeout=remaining)
        except OSError as exc:
            self._last_error = f"Could not write thermal capture file: {exc}"
