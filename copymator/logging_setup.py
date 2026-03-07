from __future__ import annotations

import logging
from pathlib import Path

from .config import SettingsStorage


def get_log_file_path() -> Path:
    """Return the path to the application's log file."""
    storage = SettingsStorage()
    return storage.base_dir / "copymator.log"


def configure_logging() -> None:
    """Configure global logging for Copymator.

    Logs are written both to a file under the user's config directory and to
    the standard error stream.
    """
    log_path = get_log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

