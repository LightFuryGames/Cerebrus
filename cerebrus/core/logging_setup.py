import logging
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_logging():
    """Configure logging to write errors to DebugInfo/error_log.txt"""

    # Create DebugInfo directory if it doesn't exist
    debug_dir = Path("DebugInfo")
    debug_dir.mkdir(exist_ok=True)

    log_file = debug_dir / "error_log.txt"

    # Configure logging
    logging.basicConfig(
        filename=str(log_file),
        level=logging.ERROR,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Redirect stderr to the log file as well
    class StderrLogger(object):
        def __init__(self):
            self.terminal = sys.stderr
            self.log = open(str(log_file), "a", encoding="utf-8")

        def write(self, message):
            self.terminal.write(message)
            self.log.write(message)
            self.log.flush()

        def flush(self):
            self.terminal.flush()
            self.log.flush()

    sys.stderr = StderrLogger()
