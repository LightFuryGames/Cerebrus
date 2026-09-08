"""Background low-resolution screenshot sampling for a device, over adb.

Runs alongside a normal CsvProfile Start/Stop capture (see
`cerebrus.tools.thermal_capture.BatteryThermalSampler`, which this
mirrors) and periodically grabs a screenshot, downscales it, and
re-encodes it as a low-quality JPEG. The goal is lightweight visual
evidence for spotting anomalies or comparing runs - not a video capture,
so the interval is intentionally coarse and each file is kept small.
"""

from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

from cerebrus.tools.adb import AdbClient

DEFAULT_SCREENSHOT_INTERVAL_SECONDS = 30.0
DEFAULT_MAX_WIDTH_PX = 640
DEFAULT_JPEG_QUALITY = 40


@dataclass
class ScreenshotSampler:
    """Periodically captures a device's screen on a background thread,
    downscaling and re-encoding each capture as a low-quality JPEG.

    Usage:
        sampler = ScreenshotSampler(AdbClient(), serial, output_dir)
        sampler.start()
        ...
        sampler.stop()
    """

    adb_client: AdbClient
    serial: str
    output_dir: Path
    interval_seconds: float = DEFAULT_SCREENSHOT_INTERVAL_SECONDS
    max_width_px: int = DEFAULT_MAX_WIDTH_PX
    jpeg_quality: int = DEFAULT_JPEG_QUALITY

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

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> Path:
        """Signal the sampling loop to stop and wait for the current
        capture (if any) to finish. Returns the output directory
        regardless of whether any screenshots were captured.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._thread = None
        return self.output_dir

    def _run_loop(self) -> None:
        start_time = time.monotonic()

        while not self._stop_event.is_set():
            sample_start = time.monotonic()
            elapsed = sample_start - start_time

            self._capture_one(elapsed)

            remaining = self.interval_seconds - (time.monotonic() - sample_start)
            if remaining > 0:
                self._stop_event.wait(timeout=remaining)

    def _capture_one(self, elapsed_seconds: float) -> None:
        raw_png = self.adb_client.capture_screenshot(self.serial)
        if raw_png is None:
            self._last_error = (
                "Could not capture screenshot (device disconnected or "
                "screencap unavailable)."
            )
            return

        try:
            image = Image.open(io.BytesIO(raw_png))
            image = image.convert("RGB")

            if image.width > self.max_width_px:
                scale = self.max_width_px / image.width
                new_size = (self.max_width_px, max(1, round(image.height * scale)))
                image = image.resize(new_size, Image.LANCZOS)

            filename = f"screenshot_{self._sample_count:04d}_{elapsed_seconds:06.0f}s.jpg"
            image.save(
                self.output_dir / filename, format="JPEG", quality=self.jpeg_quality
            )
            self._sample_count += 1
        except Exception as exc:
            self._last_error = f"Could not process screenshot: {exc}"
